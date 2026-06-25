"""
Servicio para ejecutar backups programados automáticamente.
"""
import logging
import traceback
from typing import List, Optional
from datetime import timedelta
from django.utils import timezone
from django.db import transaction
from django.core.mail import send_mail
from django.conf import settings

from api.backups.scheduled_models import BackupScheduleConfig, ScheduledBackupLog
from api.backups.models import TenantBackup
from api.backups.services.backup_service import BackupService

logger = logging.getLogger(__name__)


class BackupSchedulerService:
    """
    Servicio para ejecutar backups programados.
    
    Este servicio debe ser llamado periódicamente (ej: cada minuto)
    por un cron job o Celery task para verificar y ejecutar backups pendientes.
    """
    
    def __init__(self):
        self.backup_service = BackupService()
        logger.debug("BackupSchedulerService inicializado")
    
    def run_pending_backups(self) -> dict:
        """
        Ejecuta todos los backups programados que están pendientes.
        
        Returns:
            dict: Resumen de ejecuciones {
                'total_checked': int,
                'executed': int,
                'successful': int,
                'failed': int,
                'skipped': int,
                'results': List[dict]
            }
        """
        logger.info("Iniciando verificación de backups programados pendientes")
        
        # Obtener configuraciones habilitadas que deben ejecutarse
        pending_configs = self._get_pending_configs()
        
        results = {
            'total_checked': len(pending_configs),
            'executed': 0,
            'successful': 0,
            'failed': 0,
            'skipped': 0,
            'results': []
        }
        
        for config in pending_configs:
            result = self._execute_scheduled_backup(config)
            results['results'].append(result)
            
            if result['status'] == 'success':
                results['successful'] += 1
                results['executed'] += 1
            elif result['status'] == 'failed':
                results['failed'] += 1
                results['executed'] += 1
            elif result['status'] == 'skipped':
                results['skipped'] += 1
        
        logger.info(
            f"Verificación completada: {results['executed']} ejecutados, "
            f"{results['successful']} exitosos, {results['failed']} fallidos, "
            f"{results['skipped']} omitidos"
        )
        
        return results
    
    def _get_pending_configs(self) -> List[BackupScheduleConfig]:
        """
        Obtiene configuraciones que deben ejecutarse ahora.
        
        Returns:
            QuerySet de BackupScheduleConfig
        """
        now = timezone.now()
        
        # Configuraciones habilitadas con next_run_at <= now
        configs = BackupScheduleConfig.objects.filter(
            is_enabled=True,
            next_run_at__lte=now
        ).select_related('tenant', 'last_backup')
        
        logger.info(f"Encontradas {configs.count()} configuraciones pendientes")
        
        return list(configs)
    
    def _execute_scheduled_backup(self, config: BackupScheduleConfig) -> dict:
        """
        Ejecuta un backup programado para una configuración.
        
        Args:
            config: Configuración de backup programado
        
        Returns:
            dict: Resultado de la ejecución {
                'config_id': int,
                'tenant_id': int,
                'tenant_name': str,
                'status': str,
                'backup_id': int or None,
                'error': str or None,
                'duration_seconds': float or None
            }
        """
        logger.info(
            f"Ejecutando backup programado para tenant {config.tenant.id} "
            f"({config.tenant.name})"
        )
        
        started_at = timezone.now()
        log = None
        backup = None
        error_message = None
        error_traceback = None
        
        try:
            # Verificar que el tenant esté activo
            if not config.tenant.is_active:
                logger.warning(
                    f"Tenant {config.tenant.id} está inactivo, omitiendo backup"
                )
                
                log = ScheduledBackupLog.objects.create(
                    schedule_config=config,
                    status=ScheduledBackupLog.Status.SKIPPED,
                    error_message="Tenant inactivo",
                    metadata={'reason': 'tenant_inactive'}
                )
                
                return {
                    'config_id': config.id,
                    'tenant_id': config.tenant.id,
                    'tenant_name': config.tenant.name,
                    'status': 'skipped',
                    'backup_id': None,
                    'error': 'Tenant inactivo',
                    'duration_seconds': None
                }
            
            # Verificar que no haya backup en progreso
            in_progress = TenantBackup.objects.filter(
                tenant=config.tenant,
                status__in=[
                    TenantBackup.Status.PENDING,
                    TenantBackup.Status.RUNNING
                ]
            ).exists()
            
            if in_progress:
                logger.warning(
                    f"Ya hay un backup en progreso para tenant {config.tenant.id}, "
                    f"omitiendo ejecución programada"
                )
                
                log = ScheduledBackupLog.objects.create(
                    schedule_config=config,
                    status=ScheduledBackupLog.Status.SKIPPED,
                    error_message="Backup en progreso",
                    metadata={'reason': 'backup_in_progress'}
                )
                
                # Actualizar next_run para evitar reintentos inmediatos
                config.update_next_run()
                
                return {
                    'config_id': config.id,
                    'tenant_id': config.tenant.id,
                    'tenant_name': config.tenant.name,
                    'status': 'skipped',
                    'backup_id': None,
                    'error': 'Backup en progreso',
                    'duration_seconds': None
                }
            
            # Crear backup usando BackupService
            # Usar un usuario del sistema para backups automáticos
            system_user = self._get_system_user(config.tenant)
            
            backup = self.backup_service.create_backup(
                tenant_id=config.tenant.id,
                requested_by=system_user,
                backup_type=config.backup_type,
                notes=f"Backup automático programado ({config.schedule_description})",
                ip_address='127.0.0.1',  # Sistema interno
                include_audit_logs=config.include_audit_logs,
                include_physical_files=config.include_physical_files
            )
            
            completed_at = timezone.now()
            duration = (completed_at - started_at).total_seconds()
            
            # Crear log exitoso
            log = ScheduledBackupLog.objects.create(
                schedule_config=config,
                backup=backup,
                status=ScheduledBackupLog.Status.SUCCESS,
                completed_at=completed_at,
                duration_seconds=duration,
                metadata={
                    'backup_size_mb': backup.total_size_mb,
                    'record_count': backup.record_count,
                    'file_count': backup.file_count
                }
            )
            
            # Actualizar configuración
            config.mark_run_success(backup)
            
            # Enviar notificación de éxito si está configurado
            if config.notify_on_success:
                self._send_success_notification(config, backup)
            
            # Limpiar backups antiguos
            self._cleanup_old_backups(config)
            
            logger.info(
                f"Backup programado completado exitosamente para tenant {config.tenant.id} "
                f"(backup_id: {backup.id}, duración: {duration:.2f}s)"
            )
            
            return {
                'config_id': config.id,
                'tenant_id': config.tenant.id,
                'tenant_name': config.tenant.name,
                'status': 'success',
                'backup_id': backup.id,
                'error': None,
                'duration_seconds': duration
            }
        
        except Exception as e:
            error_message = str(e)
            error_traceback = traceback.format_exc()
            
            logger.error(
                f"Error ejecutando backup programado para tenant {config.tenant.id}: "
                f"{error_message}\n{error_traceback}"
            )
            
            completed_at = timezone.now()
            duration = (completed_at - started_at).total_seconds()
            
            # Crear log de fallo
            log = ScheduledBackupLog.objects.create(
                schedule_config=config,
                backup=backup,  # Puede ser None si falló antes de crear
                status=ScheduledBackupLog.Status.FAILED,
                completed_at=completed_at,
                duration_seconds=duration,
                error_message=error_message,
                error_traceback=error_traceback,
                metadata={'error_type': type(e).__name__}
            )
            
            # Actualizar configuración
            config.mark_run_failure()
            
            # Enviar notificación de fallo si está configurado
            if config.notify_on_failure:
                self._send_failure_notification(config, error_message)
            
            return {
                'config_id': config.id,
                'tenant_id': config.tenant.id,
                'tenant_name': config.tenant.name,
                'status': 'failed',
                'backup_id': backup.id if backup else None,
                'error': error_message,
                'duration_seconds': duration
            }
    
    def _get_system_user(self, tenant):
        """
        Obtiene o crea un usuario del sistema para backups automáticos.
        
        Args:
            tenant: Tenant para el cual obtener el usuario
        
        Returns:
            User: Usuario del sistema
        """
        from django.contrib.auth import get_user_model
        
        User = get_user_model()
        
        # Buscar usuario del sistema para este tenant
        system_email = f"system-backup@{tenant.id}.internal"
        system_username = f"system-backup-{tenant.id}"
        
        user, created = User.objects.get_or_create(
            username=system_username,
            defaults={
                'email': system_email,
                'first_name': 'Sistema',
                'last_name': 'Backup Automático',
                'is_active': True,
                'is_staff': False,
                'is_superuser': False
            }
        )
        
        if created:
            # Asegurar que el usuario tenga una contraseña inusable
            if not user.has_usable_password():
                user.set_unusable_password()
                user.save(update_fields=['password'])
            logger.info(f"Usuario del sistema creado: {system_username} ({system_email})")
        
        return user
    
    def _cleanup_old_backups(self, config: BackupScheduleConfig):
        """
        Elimina backups automáticos antiguos según la configuración.
        
        Args:
            config: Configuración con max_backups_to_keep
        """
        logger.info(
            f"Limpiando backups antiguos para tenant {config.tenant.id} "
            f"(mantener: {config.max_backups_to_keep})"
        )
        
        # Obtener backups automáticos completados, ordenados por fecha
        automatic_backups = TenantBackup.objects.filter(
            tenant=config.tenant,
            status=TenantBackup.Status.COMPLETED,
            notes__icontains='Backup automático programado'
        ).order_by('-created_at')
        
        # Mantener solo los N más recientes
        backups_to_delete = list(automatic_backups[config.max_backups_to_keep:])
        
        if backups_to_delete:
            logger.info(f"Eliminando {len(backups_to_delete)} backups antiguos")
            
            for backup in backups_to_delete:
                try:
                    # Usar el servicio para eliminar correctamente
                    system_user = self._get_system_user(config.tenant)
                    self.backup_service.delete_backup(
                        backup=backup,
                        user=system_user,
                        ip_address='127.0.0.1'
                    )
                    logger.debug(f"Backup {backup.id} eliminado")
                except Exception as e:
                    logger.error(f"Error eliminando backup {backup.id}: {str(e)}")
        else:
            logger.info("No hay backups antiguos para eliminar")
    
    def _send_success_notification(self, config: BackupScheduleConfig, backup: TenantBackup):
        """
        Envía notificación de éxito por email.
        
        Args:
            config: Configuración del backup
            backup: Backup completado
        """
        if not config.notification_emails:
            return
        
        subject = f"✅ Backup Automático Completado - {config.tenant.name}"
        
        message = f"""
Backup automático completado exitosamente.

Tenant: {config.tenant.name}
Backup ID: {backup.id}
Tipo: {backup.get_backup_type_display()}
Tamaño: {backup.total_size_mb} MB
Registros: {sum(backup.record_count.values()) if backup.record_count else 0}
Archivos: {backup.file_count}
Duración: {backup.duration_seconds:.2f} segundos

Fecha: {backup.completed_at.strftime('%Y-%m-%d %H:%M:%S')}
Próximo backup: {config.next_run_at.strftime('%Y-%m-%d %H:%M:%S') if config.next_run_at else 'No programado'}

---
Este es un mensaje automático del sistema de backups.
        """.strip()
        
        try:
            send_mail(
                subject=subject,
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=config.notification_emails,
                fail_silently=False
            )
            logger.info(f"Notificación de éxito enviada a {config.notification_emails}")
        except Exception as e:
            logger.error(f"Error enviando notificación de éxito: {str(e)}")
    
    def _send_failure_notification(self, config: BackupScheduleConfig, error_message: str):
        """
        Envía notificación de fallo por email.
        
        Args:
            config: Configuración del backup
            error_message: Mensaje de error
        """
        if not config.notification_emails:
            return
        
        subject = f"❌ Backup Automático Fallido - {config.tenant.name}"
        
        message = f"""
El backup automático ha fallado.

Tenant: {config.tenant.name}
Configuración: {config.schedule_description}
Error: {error_message}

Fecha: {timezone.now().strftime('%Y-%m-%d %H:%M:%S')}
Próximo intento: {config.next_run_at.strftime('%Y-%m-%d %H:%M:%S') if config.next_run_at else 'No programado'}

Por favor, revise la configuración y los logs del sistema.

---
Este es un mensaje automático del sistema de backups.
        """.strip()
        
        try:
            send_mail(
                subject=subject,
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=config.notification_emails,
                fail_silently=False
            )
            logger.info(f"Notificación de fallo enviada a {config.notification_emails}")
        except Exception as e:
            logger.error(f"Error enviando notificación de fallo: {str(e)}")
    
    def initialize_schedule(self, config: BackupScheduleConfig):
        """
        Inicializa el schedule calculando next_run_at.
        
        Args:
            config: Configuración a inicializar
        """
        logger.info(f"Inicializando schedule para tenant {config.tenant.id}")
        
        config.update_next_run()
        
        logger.info(
            f"Schedule inicializado: próxima ejecución en "
            f"{config.next_run_at.strftime('%Y-%m-%d %H:%M:%S') if config.next_run_at else 'No calculado'}"
        )
    
    def get_schedule_status(self, config: BackupScheduleConfig) -> dict:
        """
        Obtiene el estado actual de un schedule.
        
        Args:
            config: Configuración a consultar
        
        Returns:
            dict: Estado del schedule
        """
        recent_logs = config.execution_logs.all()[:10]
        
        return {
            'config_id': config.id,
            'tenant_id': config.tenant.id,
            'tenant_name': config.tenant.name,
            'is_enabled': config.is_enabled,
            'frequency': config.frequency,
            'schedule_description': config.schedule_description,
            'last_run_at': config.last_run_at,
            'next_run_at': config.next_run_at,
            'total_runs': config.total_runs,
            'successful_runs': config.successful_runs,
            'failed_runs': config.failed_runs,
            'success_rate': config.success_rate,
            'last_backup_id': config.last_backup.id if config.last_backup else None,
            'recent_logs': [
                {
                    'id': log.id,
                    'status': log.status,
                    'started_at': log.started_at,
                    'duration_seconds': log.duration_seconds,
                    'error_message': log.error_message
                }
                for log in recent_logs
            ]
        }
