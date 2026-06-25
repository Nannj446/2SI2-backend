"""
Servicio para limpieza de backups expirados y fallidos.
"""
import logging
from datetime import timedelta
from django.utils import timezone
from django.conf import settings
from api.backups.models import TenantBackup, BackupAuditLog
from api.backups.storage_service import BackupStorageService

logger = logging.getLogger(__name__)


class BackupCleanupService:
    """
    Servicio para limpieza automática de backups.
    
    Funcionalidades:
    - Eliminar backups expirados
    - Eliminar backups fallidos antiguos
    - Limpiar archivos físicos de Storage
    - Mantener logs de auditoría
    """
    
    def __init__(self):
        self.storage_service = BackupStorageService()
        logger.debug("BackupCleanupService inicializado")
    
    def cleanup_expired_backups(self, dry_run: bool = False) -> dict:
        """
        Limpia backups que han expirado.
        
        Args:
            dry_run: Si True, solo simula la limpieza sin eliminar
        
        Returns:
            Diccionario con estadísticas:
            {
                'total_expired': 10,
                'deleted': 8,
                'errors': 2,
                'freed_mb': 150.5,
                'timestamp': '2026-05-06T...'
            }
        """
        logger.info("Iniciando limpieza de backups expirados")
        
        now = timezone.now()
        
        # Obtener backups expirados (completados y con fecha de expiración pasada)
        expired_backups = TenantBackup.objects.filter(
            status=TenantBackup.Status.COMPLETED,
            expires_at__lt=now
        ).select_related('tenant')
        
        total = expired_backups.count()
        deleted = 0
        errors = 0
        freed_bytes = 0
        
        logger.info(f"Encontrados {total} backups expirados")
        
        if dry_run:
            logger.info("Modo DRY RUN - No se eliminarán archivos")
        
        for backup in expired_backups:
            try:
                # Acumular tamaño antes de eliminar
                freed_bytes += backup.total_size_bytes
                
                if not dry_run:
                    # Eliminar archivos físicos
                    self._delete_backup_files(backup)
                    
                    # Actualizar status a EXPIRED
                    backup.status = TenantBackup.Status.EXPIRED
                    backup.save()
                    
                    # Log de auditoría
                    self._create_cleanup_audit_log(
                        backup=backup,
                        action=BackupAuditLog.Action.EXPIRED,
                        description=f"Backup expirado y eliminado automáticamente"
                    )
                
                deleted += 1
                
                logger.info(
                    f"Backup {backup.id} {'simulado' if dry_run else 'eliminado'} "
                    f"(tenant: {backup.tenant.name}, {backup.total_size_mb} MB)"
                )
            
            except Exception as e:
                errors += 1
                logger.error(
                    f"Error eliminando backup {backup.id}: {str(e)}",
                    exc_info=True
                )
        
        freed_mb = round(freed_bytes / (1024 * 1024), 2)
        
        result = {
            'total_expired': total,
            'deleted': deleted,
            'errors': errors,
            'freed_mb': freed_mb,
            'timestamp': now.isoformat(),
            'dry_run': dry_run
        }
        
        logger.info(
            f"Limpieza completada: {deleted}/{total} backups eliminados, "
            f"{freed_mb} MB liberados"
        )
        
        return result
    
    def cleanup_failed_backups(self, days_old: int = 7, dry_run: bool = False) -> dict:
        """
        Limpia backups fallidos antiguos.
        
        Args:
            days_old: Días de antigüedad mínima
            dry_run: Si True, solo simula la limpieza
        
        Returns:
            Diccionario con estadísticas
        """
        logger.info(f"Limpiando backups fallidos de más de {days_old} días")
        
        cutoff_date = timezone.now() - timedelta(days=days_old)
        
        failed_backups = TenantBackup.objects.filter(
            status=TenantBackup.Status.FAILED,
            created_at__lt=cutoff_date
        ).select_related('tenant')
        
        total = failed_backups.count()
        
        logger.info(f"Encontrados {total} backups fallidos antiguos")
        
        if dry_run:
            logger.info("Modo DRY RUN - No se eliminarán registros")
        else:
            # Eliminar archivos físicos si existen
            for backup in failed_backups:
                try:
                    if backup.backup_path or backup.manifest_path:
                        self._delete_backup_files(backup)
                except Exception as e:
                    logger.warning(
                        f"Error eliminando archivos de backup fallido {backup.id}: {str(e)}"
                    )
            
            # Eliminar registros de la base de datos
            failed_backups.delete()
        
        logger.info(f"{'Simulados' if dry_run else 'Eliminados'} {total} backups fallidos")
        
        return {
            'total_deleted': total,
            'cutoff_date': cutoff_date.isoformat(),
            'days_old': days_old,
            'dry_run': dry_run
        }
    
    def cleanup_orphaned_files(self, tenant_id: int = None) -> dict:
        """
        Limpia archivos huérfanos en Storage (archivos sin registro en DB).
        
        NOTA: Esta operación es costosa, usar con precaución.
        
        Args:
            tenant_id: ID del tenant (opcional, si no se especifica limpia todos)
        
        Returns:
            Diccionario con estadísticas
        """
        logger.warning("Limpieza de archivos huérfanos - operación costosa")
        
        # TODO: Implementar cuando sea necesario
        # Requiere listar todos los archivos en Storage y comparar con DB
        
        return {
            'status': 'not_implemented',
            'message': 'Funcionalidad pendiente de implementación'
        }
    
    def _delete_backup_files(self, backup: TenantBackup):
        """
        Elimina archivos físicos de un backup en Storage.
        
        Args:
            backup: Instancia de TenantBackup
        
        Raises:
            Exception: Si falla la eliminación
        """
        deleted_files = []
        
        # Eliminar data.json
        if backup.backup_path:
            try:
                self.storage_service.delete_file(backup.backup_path)
                deleted_files.append(backup.backup_path)
                logger.debug(f"Eliminado: {backup.backup_path}")
            except Exception as e:
                logger.warning(
                    f"No se pudo eliminar {backup.backup_path}: {str(e)}"
                )
                # No lanzar excepción, continuar con manifest
        
        # Eliminar manifest.json
        if backup.manifest_path:
            try:
                self.storage_service.delete_file(backup.manifest_path)
                deleted_files.append(backup.manifest_path)
                logger.debug(f"Eliminado: {backup.manifest_path}")
            except Exception as e:
                logger.warning(
                    f"No se pudo eliminar {backup.manifest_path}: {str(e)}"
                )
        
        if not deleted_files:
            logger.warning(f"No se eliminaron archivos para backup {backup.id}")
    
    def _create_cleanup_audit_log(
        self,
        backup: TenantBackup,
        action: str,
        description: str
    ):
        """
        Crea log de auditoría para operación de limpieza.
        
        Args:
            backup: Backup relacionado
            action: Acción realizada
            description: Descripción de la acción
        """
        try:
            BackupAuditLog.objects.create(
                tenant=backup.tenant,
                backup=backup,
                actor=None,  # Acción automática del sistema
                action=action,
                severity=BackupAuditLog.Severity.INFO,
                description=description,
                metadata={
                    'cleanup_type': 'automatic',
                    'backup_id': backup.id,
                    'size_mb': backup.total_size_mb
                }
            )
        except Exception as e:
            # No fallar la limpieza si falla el log
            logger.error(f"Error creando audit log: {str(e)}")
    
    def get_cleanup_stats(self) -> dict:
        """
        Obtiene estadísticas de backups que requieren limpieza.
        
        Returns:
            Diccionario con estadísticas
        """
        now = timezone.now()
        
        # Backups expirados
        expired_count = TenantBackup.objects.filter(
            status=TenantBackup.Status.COMPLETED,
            expires_at__lt=now
        ).count()
        
        expired_size = TenantBackup.objects.filter(
            status=TenantBackup.Status.COMPLETED,
            expires_at__lt=now
        ).aggregate(
            total=models.Sum('total_size_bytes')
        )['total'] or 0
        
        # Backups fallidos antiguos (>7 días)
        cutoff_date = now - timedelta(days=7)
        failed_count = TenantBackup.objects.filter(
            status=TenantBackup.Status.FAILED,
            created_at__lt=cutoff_date
        ).count()
        
        # Backups próximos a expirar (próximos 7 días)
        expiring_soon = TenantBackup.objects.filter(
            status=TenantBackup.Status.COMPLETED,
            expires_at__gte=now,
            expires_at__lt=now + timedelta(days=7)
        ).count()
        
        return {
            'expired': {
                'count': expired_count,
                'size_mb': round(expired_size / (1024 * 1024), 2)
            },
            'failed_old': {
                'count': failed_count
            },
            'expiring_soon': {
                'count': expiring_soon
            },
            'timestamp': now.isoformat()
        }


# Importar models para aggregate
from django.db import models
