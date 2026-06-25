"""
Servicio orquestador para restauración de backups.
"""
import logging
import json
import zipfile
import io
from typing import Optional, Dict, Any
from datetime import timedelta
from django.db import transaction
from django.utils import timezone
from django.contrib.auth import get_user_model
from rest_framework.exceptions import ValidationError

from api.tenants.models import FinancialInstitution
from api.backups.models import TenantBackup, BackupAuditLog
from api.backups.storage_service import BackupStorageService
from .import_service import ImportService

User = get_user_model()
logger = logging.getLogger(__name__)


class RestoreService:
    """
    Servicio orquestador para restauración de backups.
    
    Coordina todo el proceso:
    1. Validación de backup y permisos
    2. Descarga desde Storage
    3. Extracción de datos (JSON o ZIP)
    4. Importación de datos
    5. Restauración de archivos físicos (si aplica)
    6. Auditoría
    """
    
    def __init__(self):
        self.storage_service = BackupStorageService()
        logger.debug("RestoreService inicializado")
    
    def restore_backup(
        self,
        backup_id: int,
        requested_by: User,
        conflict_strategy: str = 'skip',
        restore_files: bool = True,
        ip_address: str = None,
        dry_run: bool = False
    ) -> Dict[str, Any]:
        """
        Restaura un backup completo.
        
        Args:
            backup_id: ID del backup a restaurar
            requested_by: Usuario que solicita la restauración
            conflict_strategy: Estrategia para conflictos ('skip', 'overwrite', 'fail')
            restore_files: Si True, restaura archivos físicos (solo para backups ZIP)
            ip_address: IP del solicitante (para auditoría)
            dry_run: Si True, simula la restauración sin escribir en BD
        
        Returns:
            Diccionario con resultados de la restauración
        
        Raises:
            ValidationError: Si validaciones fallan
            Exception: Si ocurre error durante el proceso
        """
        logger.info(
            f"Iniciando restauración de backup {backup_id} "
            f"(solicitado por: {requested_by.email}, dry_run: {dry_run})"
        )
        
        # 1. Validar backup
        backup = self._validate_backup(backup_id)
        
        # 2. Validar que no haya restore en progreso
        self._check_restore_in_progress(backup.tenant)
        
        # 3. Crear log de auditoría: Restore solicitado
        self._create_audit_log(
            tenant=backup.tenant,
            backup=backup,
            actor=requested_by,
            action=BackupAuditLog.Action.RESTORE_STARTED,
            severity=BackupAuditLog.Severity.WARNING,
            description=f"Restauración solicitada (estrategia: {conflict_strategy}, dry_run: {dry_run})",
            ip_address=ip_address
        )
        
        start_time = timezone.now()
        
        try:
            # 4. Descargar backup desde Storage
            backup_content = self._download_backup(backup)
            
            # 5. Extraer datos según formato (JSON o ZIP)
            is_zip = backup.backup_path.endswith('.zip')
            
            if is_zip:
                logger.info("Backup es ZIP, extrayendo datos y archivos")
                extracted_data = self._extract_zip_backup(backup_content)
                backup_data = extracted_data['data']
                files = extracted_data['files']
            else:
                logger.info("Backup es JSON, extrayendo datos")
                backup_data = json.loads(backup_content.decode('utf-8'))
                files = {}
            
            # 6. Importar datos
            import_service = ImportService(
                tenant_id=backup.tenant.id,
                conflict_strategy=conflict_strategy,
                dry_run=dry_run
            )
            
            import_stats = import_service.import_data(backup_data)
            
            # 7. Restaurar archivos físicos (si aplica)
            files_restored = 0
            if restore_files and files and not dry_run:
                logger.info(f"Restaurando {len(files)} archivos físicos")
                files_restored = self._restore_physical_files(files, backup.tenant)
            elif not restore_files and files:
                logger.info(f"Omitiendo restauración de {len(files)} archivos físicos")
            
            # 8. Calcular duración
            duration = (timezone.now() - start_time).total_seconds()
            
            # 9. Crear log de auditoría: Restore completado
            self._create_audit_log(
                tenant=backup.tenant,
                backup=backup,
                actor=requested_by,
                action=BackupAuditLog.Action.RESTORE_COMPLETED,
                severity=BackupAuditLog.Severity.WARNING,
                description=f"Restauración completada exitosamente ({duration:.2f}s)",
                ip_address=ip_address,
                metadata={
                    'import_stats': import_stats,
                    'files_restored': files_restored,
                    'duration_seconds': duration,
                    'dry_run': dry_run
                }
            )
            
            logger.info(
                f"Restauración de backup {backup_id} completada exitosamente "
                f"({import_stats['total_created']} creados, "
                f"{import_stats['total_updated']} actualizados, "
                f"{files_restored} archivos restaurados)"
            )
            
            return {
                'success': True,
                'backup_id': backup_id,
                'tenant_id': backup.tenant.id,
                'tenant_name': backup.tenant.name,
                'import_stats': import_stats,
                'files_restored': files_restored,
                'duration_seconds': duration,
                'dry_run': dry_run
            }
        
        except Exception as e:
            # Crear log de auditoría: Restore fallido
            self._create_audit_log(
                tenant=backup.tenant,
                backup=backup,
                actor=requested_by,
                action=BackupAuditLog.Action.RESTORE_FAILED,
                severity=BackupAuditLog.Severity.ERROR,
                description=f"Restauración falló: {str(e)}",
                ip_address=ip_address,
                metadata={'error': str(e)}
            )
            
            logger.error(f"Error restaurando backup {backup_id}: {str(e)}")
            raise
    
    def preview_restore(
        self,
        backup_id: int,
        requested_by: User
    ) -> Dict[str, Any]:
        """
        Genera preview de lo que se restauraría sin ejecutar la restauración.
        
        Args:
            backup_id: ID del backup
            requested_by: Usuario que solicita el preview
        
        Returns:
            Preview con conteos y conflictos potenciales
        """
        logger.info(f"Generando preview de restauración para backup {backup_id}")
        
        # 1. Validar backup
        backup = self._validate_backup(backup_id)
        
        # 2. Descargar backup
        backup_content = self._download_backup(backup)
        
        # 3. Extraer datos
        is_zip = backup.backup_path.endswith('.zip')
        
        if is_zip:
            extracted_data = self._extract_zip_backup(backup_content)
            backup_data = extracted_data['data']
            file_count = len(extracted_data['files'])
        else:
            backup_data = json.loads(backup_content.decode('utf-8'))
            file_count = 0
        
        # 4. Generar preview
        import_service = ImportService(
            tenant_id=backup.tenant.id,
            conflict_strategy='skip',
            dry_run=True
        )
        
        preview = import_service.get_import_preview(backup_data)
        preview['file_count'] = file_count
        preview['backup_id'] = backup_id
        preview['tenant_id'] = backup.tenant.id
        preview['tenant_name'] = backup.tenant.name
        preview['backup_date'] = backup.created_at.isoformat()
        
        logger.info(
            f"Preview generado: {preview['total_records']} registros, "
            f"{preview['potential_conflicts']} conflictos, {file_count} archivos"
        )
        
        return preview
    
    def _validate_backup(self, backup_id: int) -> TenantBackup:
        """
        Valida que el backup existe y está disponible para restauración.
        
        Args:
            backup_id: ID del backup
        
        Returns:
            Instancia de TenantBackup
        
        Raises:
            ValidationError: Si backup no válido
        """
        try:
            backup = TenantBackup.objects.get(id=backup_id)
        except TenantBackup.DoesNotExist:
            raise ValidationError({
                'backup_id': 'Backup no encontrado'
            })
        
        # Validar estado
        if backup.status != TenantBackup.Status.COMPLETED:
            raise ValidationError({
                'status': f'El backup no está completado (estado: {backup.status})'
            })
        
        # Validar expiración
        if backup.is_expired:
            raise ValidationError({
                'expired': 'El backup ha expirado'
            })
        
        # Validar que tenga ruta de backup
        if not backup.backup_path:
            raise ValidationError({
                'backup_path': 'El backup no tiene ruta de archivo'
            })
        
        logger.debug(f"Backup {backup_id} validado correctamente")
        return backup
    
    def _check_restore_in_progress(self, tenant: FinancialInstitution):
        """
        Verifica que no haya restore en progreso.
        
        Raises:
            ValidationError: Si hay restore en progreso
        """
        # Buscar logs de restore iniciado en los últimos 30 minutos
        thirty_minutes_ago = timezone.now() - timedelta(minutes=30)
        
        restore_in_progress = BackupAuditLog.objects.filter(
            tenant=tenant,
            action=BackupAuditLog.Action.RESTORE_STARTED,
            created_at__gte=thirty_minutes_ago
        ).exclude(
            # Excluir si ya hay un log de completado o fallido posterior
            backup__in=BackupAuditLog.objects.filter(
                tenant=tenant,
                action__in=[
                    BackupAuditLog.Action.RESTORE_COMPLETED,
                    BackupAuditLog.Action.RESTORE_FAILED
                ],
                created_at__gte=thirty_minutes_ago
            ).values_list('backup_id', flat=True)
        ).exists()
        
        if restore_in_progress:
            logger.warning(f"Restore en progreso para tenant {tenant.id}")
            raise ValidationError({
                'restore_in_progress': 'Ya hay una restauración en progreso para este tenant'
            })
    
    def _download_backup(self, backup: TenantBackup) -> bytes:
        """
        Descarga backup desde Storage.
        
        Args:
            backup: Instancia de TenantBackup
        
        Returns:
            Contenido del backup en bytes
        """
        logger.info(f"Descargando backup desde {backup.backup_path}")
        
        try:
            content = self.storage_service.download_file(backup.backup_path)
            logger.info(f"Backup descargado: {len(content)} bytes")
            return content
        except Exception as e:
            logger.error(f"Error descargando backup: {str(e)}")
            raise ValidationError({
                'download': f'Error descargando backup: {str(e)}'
            })
    
    def _extract_zip_backup(self, zip_content: bytes) -> Dict[str, Any]:
        """
        Extrae datos y archivos de un backup ZIP.
        
        Args:
            zip_content: Contenido del ZIP en bytes
        
        Returns:
            Diccionario con 'data' (dict) y 'files' (dict)
        """
        logger.info("Extrayendo contenido del ZIP")
        
        zip_buffer = io.BytesIO(zip_content)
        extracted = {
            'data': {},
            'files': {}
        }
        
        with zipfile.ZipFile(zip_buffer, 'r') as zip_file:
            # Extraer data.json
            if 'data.json' in zip_file.namelist():
                data_content = zip_file.read('data.json')
                extracted['data'] = json.loads(data_content.decode('utf-8'))
                logger.debug("✓ data.json extraído")
            else:
                raise ValueError("ZIP no contiene data.json")
            
            # Extraer archivos físicos (carpeta files/)
            for file_info in zip_file.filelist:
                if file_info.filename.startswith('files/') and not file_info.is_dir():
                    # Remover prefijo 'files/'
                    file_path = file_info.filename[6:]
                    file_content = zip_file.read(file_info.filename)
                    extracted['files'][file_path] = file_content
                    logger.debug(f"✓ Extraído {file_path} ({len(file_content)} bytes)")
        
        logger.info(
            f"ZIP extraído: {len(extracted['files'])} archivos físicos"
        )
        
        return extracted
    
    def _restore_physical_files(
        self, 
        files: Dict[str, bytes],
        tenant: FinancialInstitution
    ) -> int:
        """
        Restaura archivos físicos a Supabase Storage.
        
        Args:
            files: Diccionario con {file_path: file_content}
            tenant: Tenant al que pertenecen los archivos
        
        Returns:
            Número de archivos restaurados exitosamente
        """
        from api.storage.services import StorageService
        from api.storage.exceptions import StorageException
        
        storage_service = StorageService()
        restored_count = 0
        
        logger.info(f"Restaurando {len(files)} archivos físicos")
        
        for file_path, file_content in files.items():
            try:
                # Determinar content type por extensión
                content_type = self._get_content_type(file_path)
                
                # Intentar eliminar archivo existente primero (para evitar error 409 Duplicate)
                try:
                    storage_service.delete_from_storage(file_path)
                    logger.debug(f"✓ Archivo existente eliminado: {file_path}")
                except StorageException as e:
                    # Si no existe, está bien - continuar con la subida
                    logger.debug(f"Archivo no existe, se creará: {file_path}")
                
                # Subir archivo a Storage
                storage_service.upload_to_storage(
                    file_path=file_path,
                    file_content=file_content,
                    content_type=content_type
                )
                
                restored_count += 1
                logger.debug(f"✓ Restaurado {file_path}")
            
            except Exception as e:
                logger.error(f"✗ Error restaurando {file_path}: {str(e)}")
                # Continuar con otros archivos
        
        logger.info(f"Archivos restaurados: {restored_count}/{len(files)}")
        
        return restored_count
    
    def _get_content_type(self, file_path: str) -> str:
        """
        Determina content type por extensión de archivo.
        
        Args:
            file_path: Ruta del archivo
        
        Returns:
            Content type MIME
        """
        extension = file_path.split('.')[-1].lower()
        
        content_types = {
            'png': 'image/png',
            'jpg': 'image/jpeg',
            'jpeg': 'image/jpeg',
            'gif': 'image/gif',
            'pdf': 'application/pdf',
            'doc': 'application/msword',
            'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            'xls': 'application/vnd.ms-excel',
            'xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            'txt': 'text/plain',
            'json': 'application/json',
            'zip': 'application/zip',
        }
        
        return content_types.get(extension, 'application/octet-stream')
    
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
        Crea log de auditoría para operación de restore.
        
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
