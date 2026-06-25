"""
Servicio orquestador para generación de backups.
"""
import logging
import json
from typing import Optional
from datetime import timedelta
from django.db import transaction
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.conf import settings
from rest_framework.exceptions import ValidationError

from api.tenants.models import FinancialInstitution
from api.backups.models import TenantBackup, BackupAuditLog
from api.backups.storage_service import BackupStorageService
from api.backups.constants import (
    build_backup_data_path,
    build_backup_manifest_path,
    build_backup_zip_path,
    MAX_BACKUPS_PER_HOUR,
    AUDIT_ACTION_REQUESTED,
    AUDIT_ACTION_STARTED,
    AUDIT_ACTION_COMPLETED,
    AUDIT_ACTION_FAILED,
    AUDIT_ACTION_DOWNLOADED,
    AUDIT_ACTION_DELETED,
    AUDIT_SEVERITY_INFO,
    AUDIT_SEVERITY_WARNING,
    AUDIT_SEVERITY_ERROR,
)
from .export_service import ExportService
from .manifest_service import ManifestService

User = get_user_model()
logger = logging.getLogger(__name__)


class BackupService:
    """
    Servicio orquestador para generación de backups.
    
    Coordina todo el proceso:
    1. Validación de tenant y rate limiting
    2. Exportación de datos
    3. Generación de manifest
    4. Subida a Storage
    5. Actualización de estado
    6. Auditoría
    """
    
    def __init__(self):
        self.storage_service = BackupStorageService()
        logger.debug("BackupService inicializado")
    
    def create_backup(
        self,
        tenant_id: int,
        requested_by: User,
        backup_type: str = 'full',
        notes: str = '',
        ip_address: str = None,
        include_audit_logs: bool = False,
        include_physical_files: bool = False
    ) -> TenantBackup:
        """
        Crea un backup completo de un tenant.
        
        Args:
            tenant_id: ID del tenant
            requested_by: Usuario que solicita el backup
            backup_type: Tipo de backup (full, metadata_only, storage_only)
            notes: Notas adicionales
            ip_address: IP del solicitante (para auditoría)
            include_audit_logs: Si True, incluye logs de auditoría (puede ser grande)
            include_physical_files: Si True, incluye archivos físicos en ZIP (puede ser MUY grande)
        
        Returns:
            Instancia de TenantBackup creada y completada
        
        Raises:
            ValidationError: Si validaciones fallan
            Exception: Si ocurre error durante el proceso
        """
        logger.info(
            f"Iniciando creación de backup para tenant {tenant_id} "
            f"(tipo: {backup_type}, solicitado por: {requested_by.email})"
        )
        
        # 1. Validar tenant
        tenant = self.validate_tenant(tenant_id)
        
        # 2. Validar rate limiting
        self._check_rate_limit(tenant)
        
        # 3. Verificar que no haya backup en progreso
        self._check_backup_in_progress(tenant)
        
        # 4. Crear registro de backup
        backup = TenantBackup.objects.create(
            tenant=tenant,
            requested_by=requested_by,
            backup_type=backup_type,
            status=TenantBackup.Status.PENDING,
            notes=notes
        )
        
        # Log de auditoría: Backup solicitado
        self._create_audit_log(
            tenant=tenant,
            backup=backup,
            actor=requested_by,
            action=AUDIT_ACTION_REQUESTED,
            severity=AUDIT_SEVERITY_INFO,
            description=f"Backup {backup_type} solicitado",
            ip_address=ip_address
        )
        
        try:
            # 5. Actualizar estado a RUNNING
            backup.status = TenantBackup.Status.RUNNING
            backup.started_at = timezone.now()
            backup.save()
            
            self._create_audit_log(
                tenant=tenant,
                backup=backup,
                actor=requested_by,
                action=AUDIT_ACTION_STARTED,
                severity=AUDIT_SEVERITY_INFO,
                description="Backup iniciado",
                ip_address=ip_address
            )
            
            # 6. Exportar datos
            exported_data = self._export_tenant_data(tenant, include_audit_logs)
            
            # 7. Generar manifest
            manifest = self._generate_manifest(backup, exported_data)
            
            # 8. Subir a Storage
            storage_paths = self._upload_to_storage(
                backup, 
                exported_data, 
                manifest, 
                include_physical_files
            )
            
            # 9. Actualizar backup como completado
            backup.status = TenantBackup.Status.COMPLETED
            backup.completed_at = timezone.now()
            backup.backup_path = storage_paths['data_path']
            backup.manifest_path = storage_paths['manifest_path']
            backup.record_count = manifest.record_counts
            backup.file_count = len(manifest.file_list)
            backup.expires_at = self._calculate_expiration_date()
            backup.save()
            
            self._create_audit_log(
                tenant=tenant,
                backup=backup,
                actor=requested_by,
                action=AUDIT_ACTION_COMPLETED,
                severity=AUDIT_SEVERITY_INFO,
                description=f"Backup completado exitosamente ({backup.total_size_mb} MB)",
                ip_address=ip_address,
                metadata={
                    'total_records': manifest.total_records,
                    'total_size_bytes': backup.total_size_bytes,
                    'duration_seconds': backup.duration_seconds
                }
            )
            
            logger.info(
                f"Backup {backup.id} completado exitosamente "
                f"({backup.total_size_mb} MB, {manifest.total_records} registros)"
            )
            
            return backup
        
        except Exception as e:
            # Marcar como fallido
            backup.status = TenantBackup.Status.FAILED
            backup.error_message = str(e)
            backup.completed_at = timezone.now()
            backup.save()
            
            self._create_audit_log(
                tenant=tenant,
                backup=backup,
                actor=requested_by,
                action=AUDIT_ACTION_FAILED,
                severity=AUDIT_SEVERITY_ERROR,
                description=f"Backup falló: {str(e)}",
                ip_address=ip_address,
                metadata={'error': str(e)}
            )
            
            logger.error(f"Error creando backup {backup.id}: {str(e)}")
            raise
    
    def validate_tenant(
        self, 
        tenant_id: int, 
        allow_inactive: bool = False
    ) -> FinancialInstitution:
        """
        Valida que el tenant existe y está activo.
        
        Args:
            tenant_id: ID del tenant
            allow_inactive: Si True, permite tenant inactivo
        
        Returns:
            Instancia de FinancialInstitution
        
        Raises:
            ValidationError: Si tenant no válido
        """
        try:
            tenant = FinancialInstitution.objects.get(id=tenant_id)
        except FinancialInstitution.DoesNotExist:
            raise ValidationError({
                'tenant_id': 'Institución financiera no encontrada'
            })
        
        if not tenant.is_active and not allow_inactive:
            raise ValidationError({
                'tenant_id': 'La institución financiera está inactiva'
            })
        
        return tenant
    
    def _check_rate_limit(self, tenant: FinancialInstitution):
        """
        Verifica límite de backups por hora.
        
        Raises:
            ValidationError: Si se excede el límite
        """
        one_hour_ago = timezone.now() - timedelta(hours=1)
        
        recent_backups = TenantBackup.objects.filter(
            tenant=tenant,
            created_at__gte=one_hour_ago
        ).count()
        
        if recent_backups >= MAX_BACKUPS_PER_HOUR:
            logger.warning(
                f"Rate limit excedido para tenant {tenant.id}: "
                f"{recent_backups} backups en la última hora"
            )
            raise ValidationError({
                'rate_limit': f'Máximo {MAX_BACKUPS_PER_HOUR} backups por hora'
            })
    
    def _check_backup_in_progress(self, tenant: FinancialInstitution):
        """
        Verifica que no haya backup en progreso.
        
        Raises:
            ValidationError: Si hay backup en progreso
        """
        in_progress = TenantBackup.objects.filter(
            tenant=tenant,
            status__in=[
                TenantBackup.Status.PENDING,
                TenantBackup.Status.RUNNING
            ]
        ).exists()
        
        if in_progress:
            logger.warning(f"Backup en progreso para tenant {tenant.id}")
            raise ValidationError({
                'backup_in_progress': 'Ya hay un backup en progreso para este tenant'
            })
    
    def _export_tenant_data(
        self, 
        tenant: FinancialInstitution,
        include_audit_logs: bool = False
    ) -> dict:
        """
        Exporta datos del tenant usando ExportService.
        
        Args:
            tenant: Tenant a exportar
            include_audit_logs: Si True, incluye logs de auditoría
        
        Returns:
            Diccionario con datos exportados
        """
        logger.info(
            f"Exportando datos de tenant {tenant.id} "
            f"(incluir auditoría: {include_audit_logs})"
        )
        
        export_service = ExportService(tenant, include_audit_logs=include_audit_logs)
        exported_data = export_service.export_all_data()
        
        total_records = sum(
            len(records) if isinstance(records, list) else 0
            for records in exported_data.get('data', {}).values()
        )
        
        logger.info(f"Exportación completada: {total_records} registros totales")
        
        return exported_data
    
    def _generate_manifest(
        self, 
        backup: TenantBackup, 
        exported_data: dict,
        file_list: list = None
    ) -> 'BackupManifest':
        """
        Genera manifest del backup usando ManifestService.
        
        Args:
            backup: Instancia de TenantBackup
            exported_data: Datos exportados
            file_list: Lista de archivos físicos incluidos (opcional)
        
        Returns:
            Instancia de BackupManifest creada
        """
        logger.info(f"Generando manifest para backup {backup.id}")
        
        manifest_service = ManifestService(backup)
        manifest = manifest_service.generate_manifest(
            exported_data,
            file_list=file_list or []
        )
        
        logger.info(
            f"Manifest generado: {manifest.total_records} registros, "
            f"{len(manifest.included_tables)} tablas, "
            f"{len(manifest.file_list)} archivos"
        )
        
        return manifest
    
    def _upload_to_storage(
        self, 
        backup: TenantBackup, 
        exported_data: dict,
        manifest: 'BackupManifest',
        include_physical_files: bool = False
    ) -> dict:
        """
        Sube backup a Supabase Storage.
        
        Si include_physical_files=True, crea un ZIP con datos + archivos físicos.
        Si include_physical_files=False, solo sube data.json y manifest.json (actual).
        
        Args:
            backup: Instancia de TenantBackup
            exported_data: Datos exportados
            manifest: Manifest generado
            include_physical_files: Si True, incluye archivos físicos en ZIP
        
        Returns:
            Diccionario con rutas: {'data_path': '...', 'manifest_path': '...'}
        """
        logger.info(
            f"Subiendo backup {backup.id} a Storage "
            f"(archivos físicos: {include_physical_files})"
        )
        
        # Generar rutas usando constantes centralizadas
        now = timezone.now()
        
        if include_physical_files:
            # OPCIÓN A: Backup completo en ZIP con archivos físicos
            logger.info("Creando backup completo con archivos físicos (ZIP)")
            
            # 1. Descargar archivos físicos del tenant
            export_service = ExportService(backup.tenant, include_audit_logs=False)
            files = export_service.download_tenant_files()
            
            logger.info(f"Archivos descargados: {len(files)}")
            
            # 2. Actualizar manifest con file_list
            file_paths = list(files.keys())
            manifest.file_list = file_paths
            manifest.metadata['total_files'] = len(file_paths)
            manifest.save()
            
            logger.info(f"Manifest actualizado con {len(file_paths)} archivos")
            
            # 3. Generar manifest JSON
            manifest_service = ManifestService(backup)
            manifest_json = manifest_service.generate_manifest_json()
            
            # 4. Crear ZIP con datos + manifest + archivos
            zip_content = export_service.create_backup_zip(
                exported_data, 
                manifest_json, 
                files
            )
            
            logger.info(f"ZIP creado: {len(zip_content)} bytes ({len(zip_content) / 1024 / 1024:.2f} MB)")
            
            # 5. Subir ZIP a Storage usando ruta centralizada
            zip_path = build_backup_zip_path(backup.tenant.id, backup.id, now)
            zip_result = self.storage_service.upload_file(
                file_path=zip_path,
                file_content=zip_content,
                content_type='application/zip',
                upsert=True
            )
            
            # 6. Actualizar backup
            backup.checksum = zip_result['checksum']
            backup.total_size_bytes = len(zip_content)
            backup.backup_path = zip_path
            backup.manifest_path = zip_path  # Manifest está dentro del ZIP
            backup.save()
            
            logger.info(
                f"Backup ZIP subido exitosamente: {backup.total_size_mb} MB "
                f"(checksum: {backup.checksum[:16]}...)"
            )
            
            return {
                'data_path': zip_path,
                'manifest_path': zip_path
            }
        
        else:
            # OPCIÓN B: Solo datos JSON (sin archivos físicos)
            logger.info("Creando backup solo con datos JSON (sin archivos físicos)")
            
            # 1. Subir data.json usando ruta centralizada
            data_path = build_backup_data_path(backup.tenant.id, backup.id, now)
            data_content = json.dumps(
                exported_data, 
                indent=2, 
                ensure_ascii=False,
                default=str  # Convertir datetime y otros objetos no serializables a string
            ).encode('utf-8')
            
            data_result = self.storage_service.upload_file(
                file_path=data_path,
                file_content=data_content,
                content_type='application/json',
                upsert=True
            )
            
            logger.info(f"data.json subido: {len(data_content)} bytes")
            
            # 2. Subir manifest.json usando ruta centralizada
            manifest_service = ManifestService(backup)
            manifest_json = manifest_service.generate_manifest_json()
            manifest_path = build_backup_manifest_path(backup.tenant.id, backup.id, now)
            manifest_content = json.dumps(
                manifest_json, 
                indent=2, 
                ensure_ascii=False,
                default=str  # Convertir datetime y otros objetos no serializables a string
            ).encode('utf-8')
            
            manifest_result = self.storage_service.upload_file(
                file_path=manifest_path,
                file_content=manifest_content,
                content_type='application/json',
                upsert=True
            )
            
            logger.info(f"manifest.json subido: {len(manifest_content)} bytes")
            
            # 3. Actualizar checksums y tamaños en el backup
            backup.checksum = data_result['checksum']
            backup.total_size_bytes = len(data_content) + len(manifest_content)
            backup.save()
            
            logger.info(
                f"Backup subido a Storage: {backup.total_size_mb} MB "
                f"(checksum: {backup.checksum[:16]}...)"
            )
            
            return {
                'data_path': data_path,
                'manifest_path': manifest_path
            }
    
    def _calculate_expiration_date(self):
        """
        Calcula fecha de expiración del backup.
        
        Returns:
            Datetime de expiración
        """
        retention_days = getattr(settings, 'BACKUP_RETENTION_DAYS', 30)
        return timezone.now() + timedelta(days=retention_days)
    
    def generate_download_url(
        self, 
        backup: TenantBackup,
        user: User = None,
        ip_address: str = None
    ) -> str:
        """
        Genera URL firmada para descargar backup.
        
        Args:
            backup: Instancia de TenantBackup
            user: Usuario que solicita la descarga (para auditoría)
            ip_address: IP del solicitante
        
        Returns:
            URL firmada con expiración
        
        Raises:
            ValidationError: Si backup no está disponible
        """
        # Validar estado
        if backup.status != TenantBackup.Status.COMPLETED:
            raise ValidationError({
                'status': 'El backup no está completado'
            })
        
        if backup.is_expired:
            raise ValidationError({
                'expired': 'El backup ha expirado'
            })
        
        # Generar signed URL
        signed_url = self.storage_service.generate_signed_url(
            file_path=backup.backup_path,
            expires_in=settings.BACKUP_SIGNED_URL_EXPIRATION
        )
        
        # Auditoría
        if user:
            self._create_audit_log(
                tenant=backup.tenant,
                backup=backup,
                actor=user,
                action=AUDIT_ACTION_DOWNLOADED,
                severity=AUDIT_SEVERITY_INFO,
                description=f"URL de descarga generada",
                ip_address=ip_address
            )
        
        logger.info(f"URL de descarga generada para backup {backup.id}")
        
        return signed_url
    
    def delete_backup(
        self,
        backup: TenantBackup,
        user: User,
        ip_address: str = None
    ):
        """
        Elimina un backup de Storage y marca como eliminado.
        
        Args:
            backup: Instancia de TenantBackup
            user: Usuario que elimina
            ip_address: IP del solicitante
        """
        logger.info(f"Eliminando backup {backup.id}")
        
        try:
            # Eliminar archivos de Storage
            if backup.backup_path:
                self.storage_service.delete_file(backup.backup_path)
            
            if backup.manifest_path:
                self.storage_service.delete_file(backup.manifest_path)
            
            # Marcar como expirado (soft delete)
            backup.status = TenantBackup.Status.EXPIRED
            backup.save()
            
            # Auditoría
            self._create_audit_log(
                tenant=backup.tenant,
                backup=backup,
                actor=user,
                action=AUDIT_ACTION_DELETED,
                severity=AUDIT_SEVERITY_WARNING,
                description=f"Backup eliminado manualmente",
                ip_address=ip_address
            )
            
            logger.info(f"Backup {backup.id} eliminado exitosamente")
        
        except Exception as e:
            logger.error(f"Error eliminando backup {backup.id}: {str(e)}")
            raise
    
    def _create_audit_log(
        self,
        tenant: FinancialInstitution,
        backup: TenantBackup,
        actor: User,
        action: str,
        severity: str,
        description: str,
        ip_address: str = None,
        metadata: dict = None
    ):
        """
        Crea log de auditoría para operación de backup.
        
        Args:
            tenant: Tenant relacionado
            backup: Backup relacionado
            actor: Usuario que realiza la acción
            action: Tipo de acción (BackupAuditLog.Action)
            severity: Severidad (BackupAuditLog.Severity)
            description: Descripción de la acción
            ip_address: IP del actor
            metadata: Datos adicionales
        """
        try:
            BackupAuditLog.objects.create(
                tenant=tenant,
                backup=backup,
                actor=actor,
                action=action,
                severity=severity,
                description=description,
                ip_address=ip_address,
                metadata=metadata or {}
            )
        except Exception as e:
            # No fallar el proceso principal si falla la auditoría
            logger.error(f"Error creando audit log: {str(e)}")
