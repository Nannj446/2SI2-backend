"""
Vistas API para gestión de backups de tenants.
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from django.conf import settings
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiParameter
from drf_spectacular.types import OpenApiTypes
import logging

from .models import TenantBackup, BackupAuditLog
from .serializers import (
    TenantBackupSerializer,
    TenantBackupListSerializer,
    CreateBackupSerializer,
    DownloadBackupResponseSerializer,
    BackupAuditLogSerializer,
    RestoreBackupSerializer,
    RestorePreviewSerializer,
    RestoreResultSerializer
)
from .permissions import CanManageBackups
from .services.backup_service import BackupService
from .services.cleanup_service import BackupCleanupService
from .services.restore_service import RestoreService
from api.tenants.models import FinancialInstitution

logger = logging.getLogger(__name__)


@extend_schema_view(
    list=extend_schema(
        summary="Listar backups de un tenant",
        description="Obtiene lista de backups de un tenant específico",
        tags=['Backups']
    ),
    retrieve=extend_schema(
        summary="Obtener detalle de backup",
        description="Obtiene información detallada de un backup específico",
        tags=['Backups']
    ),
    create=extend_schema(
        summary="Crear nuevo backup",
        description="Crea un nuevo backup para el tenant especificado",
        request=CreateBackupSerializer,
        responses={201: TenantBackupSerializer},
        tags=['Backups']
    ),
    destroy=extend_schema(
        summary="Eliminar backup",
        description="Elimina un backup (solo superadmin)",
        tags=['Backups']
    )
)
class TenantBackupViewSet(viewsets.ModelViewSet):
    """
    ViewSet para gestión de backups de tenants.
    
    Endpoints:
    - GET /api/saas/tenants/{tenant_id}/backups/ - Listar backups
    - POST /api/saas/tenants/{tenant_id}/backups/ - Crear backup
    - GET /api/saas/tenants/{tenant_id}/backups/{id}/ - Ver detalle
    - GET /api/saas/tenants/{tenant_id}/backups/{id}/download/ - Descargar
    - DELETE /api/saas/tenants/{tenant_id}/backups/{id}/ - Eliminar
    - GET /api/saas/tenants/{tenant_id}/backups/{id}/audit-logs/ - Ver logs
    """
    
    permission_classes = [IsAuthenticated, CanManageBackups]
    
    def get_serializer_class(self):
        """Retorna el serializer apropiado según la acción."""
        if self.action == 'list':
            return TenantBackupListSerializer
        elif self.action == 'create':
            return CreateBackupSerializer
        elif self.action == 'download':
            return DownloadBackupResponseSerializer
        elif self.action == 'audit_logs':
            return BackupAuditLogSerializer
        return TenantBackupSerializer
    
    def get_queryset(self):
        """
        Retorna queryset filtrado según permisos del usuario.
        
        - Superadmin: ve todos los backups del tenant
        - Admin tenant: solo ve backups de su tenant
        """
        tenant_id = self.kwargs.get('tenant_id')
        
        if not tenant_id:
            return TenantBackup.objects.none()
        
        # Base queryset
        queryset = TenantBackup.objects.filter(
            tenant_id=tenant_id
        ).select_related(
            'tenant',
            'requested_by',
            'manifest'
        ).order_by('-created_at')
        
        # Obtener tipo de usuario
        user_type = None
        if hasattr(self.request.user, 'profile'):
            user_type = self.request.user.profile.user_type
        
        # Superadmin ve todos los backups del tenant
        if user_type == 'saas_admin':
            logger.debug(f"Superadmin {self.request.user.email} accediendo a backups de tenant {tenant_id}")
            return queryset
        
        # Admin tenant solo ve backups de su tenant
        if user_type == 'tenant_user':
            # Obtener la institución del usuario a través de su membresía activa
            membership = self.request.user.institution_memberships.filter(is_active=True).first()
            if membership:
                user_institution_id = membership.institution.id
                logger.debug(
                    f"Usuario {self.request.user.email} accediendo a backups "
                    f"(tenant solicitado: {tenant_id}, tenant usuario: {user_institution_id})"
                )
                
                # Solo puede ver backups de su propio tenant
                if int(tenant_id) == user_institution_id:
                    return queryset
                else:
                    logger.warning(
                        f"Usuario {self.request.user.email} intentó acceder a backups "
                        f"de otro tenant (solicitado: {tenant_id}, propio: {user_institution_id})"
                    )
        
        return TenantBackup.objects.none()
    
    def create(self, request, tenant_id=None):
        """
        Crear nuevo backup para el tenant.
        
        Args:
            request: Request object
            tenant_id: ID del tenant
        
        Returns:
            Response con datos del backup creado
        """
        logger.info(
            f"Usuario {request.user.email} solicitando backup "
            f"para tenant {tenant_id}"
        )
        
        # Validar datos de entrada
        serializer = CreateBackupSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # Obtener IP del cliente
        ip_address = self._get_client_ip(request)
        
        # Crear backup usando el servicio
        backup_service = BackupService()
        
        try:
            backup = backup_service.create_backup(
                tenant_id=int(tenant_id),
                requested_by=request.user,
                backup_type=serializer.validated_data.get(
                    'backup_type',
                    TenantBackup.BackupType.FULL
                ),
                notes=serializer.validated_data.get('notes', ''),
                ip_address=ip_address,
                include_audit_logs=serializer.validated_data.get('include_audit_logs', False),
                include_physical_files=serializer.validated_data.get('include_physical_files', False)
            )
            
            logger.info(
                f"Backup {backup.id} creado exitosamente para tenant {tenant_id} "
                f"por {request.user.email}"
            )
            
            # Serializar respuesta
            response_serializer = TenantBackupSerializer(backup)
            
            return Response(
                response_serializer.data,
                status=status.HTTP_201_CREATED
            )
        
        except Exception as e:
            logger.error(
                f"Error creando backup para tenant {tenant_id}: {str(e)}",
                exc_info=True
            )
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @extend_schema(
        summary="Descargar backup",
        description="Genera URL firmada para descargar el backup",
        responses={200: DownloadBackupResponseSerializer},
        tags=['Backups']
    )
    @action(detail=True, methods=['get'])
    def download(self, request, tenant_id=None, pk=None):
        """
        Generar URL firmada para descargar backup.
        
        Args:
            request: Request object
            tenant_id: ID del tenant
            pk: ID del backup
        
        Returns:
            Response con URL de descarga
        """
        backup = self.get_object()
        
        logger.info(
            f"Usuario {request.user.email} solicitando descarga "
            f"de backup {backup.id}"
        )
        
        # Obtener IP del cliente
        ip_address = self._get_client_ip(request)
        
        backup_service = BackupService()
        
        try:
            signed_url = backup_service.generate_download_url(
                backup=backup,
                user=request.user,
                ip_address=ip_address
            )
            
            response_data = {
                'download_url': signed_url,
                'expires_in': settings.BACKUP_SIGNED_URL_EXPIRATION,
                'backup_id': backup.id,
                'size_mb': backup.total_size_mb
            }
            
            logger.info(
                f"URL de descarga generada para backup {backup.id} "
                f"(expira en {settings.BACKUP_SIGNED_URL_EXPIRATION}s)"
            )
            
            return Response(response_data)
        
        except Exception as e:
            logger.error(
                f"Error generando URL de descarga para backup {backup.id}: {str(e)}",
                exc_info=True
            )
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @extend_schema(
        summary="Ver logs de auditoría del backup",
        description="Obtiene logs de auditoría relacionados con el backup",
        responses={200: BackupAuditLogSerializer(many=True)},
        tags=['Backups']
    )
    @action(detail=True, methods=['get'], url_path='audit-logs')
    def audit_logs(self, request, tenant_id=None, pk=None):
        """
        Obtener logs de auditoría del backup.
        
        Args:
            request: Request object
            tenant_id: ID del tenant
            pk: ID del backup
        
        Returns:
            Response con lista de logs
        """
        backup = self.get_object()
        
        logs = BackupAuditLog.objects.filter(
            backup=backup
        ).select_related('actor').order_by('-created_at')
        
        serializer = BackupAuditLogSerializer(logs, many=True)
        
        return Response(serializer.data)
    
    def destroy(self, request, tenant_id=None, pk=None):
        """
        Eliminar backup (solo superadmin).
        
        Args:
            request: Request object
            tenant_id: ID del tenant
            pk: ID del backup
        
        Returns:
            Response 204 No Content
        """
        # Obtener tipo de usuario
        user_type = None
        if hasattr(request.user, 'profile'):
            user_type = request.user.profile.user_type
        
        # Verificar que es superadmin
        if user_type != 'saas_admin':
            logger.warning(
                f"Usuario {request.user.email} (no superadmin) "
                f"intentó eliminar backup"
            )
            return Response(
                {'error': 'Solo superadmin puede eliminar backups'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        backup = self.get_object()
        
        logger.info(
            f"Superadmin {request.user.email} eliminando backup {backup.id}"
        )
        
        # Obtener IP del cliente
        ip_address = self._get_client_ip(request)
        
        # Eliminar usando el servicio
        backup_service = BackupService()
        
        try:
            backup_service.delete_backup(
                backup=backup,
                user=request.user,
                ip_address=ip_address
            )
            
            logger.info(f"Backup {backup.id} eliminado exitosamente")
            
            return Response(status=status.HTTP_204_NO_CONTENT)
        
        except Exception as e:
            logger.error(
                f"Error eliminando backup {backup.id}: {str(e)}",
                exc_info=True
            )
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @extend_schema(
        summary="Obtener estadísticas de limpieza",
        description="Obtiene estadísticas de backups que requieren limpieza",
        responses={200: dict},
        tags=['Backups']
    )
    @action(detail=False, methods=['get'], url_path='cleanup-stats')
    def cleanup_stats(self, request, tenant_id=None):
        """
        Obtener estadísticas de backups que requieren limpieza.
        
        Args:
            request: Request object
            tenant_id: ID del tenant
        
        Returns:
            Response con estadísticas de limpieza
        """
        logger.info(
            f"Usuario {request.user.email} solicitando estadísticas de limpieza "
            f"para tenant {tenant_id}"
        )
        
        cleanup_service = BackupCleanupService()
        
        try:
            stats = cleanup_service.get_cleanup_stats()
            
            logger.info(
                f"Estadísticas de limpieza obtenidas: "
                f"{stats['expired']['count']} expirados, "
                f"{stats['failed_old']['count']} fallidos antiguos"
            )
            
            return Response(stats)
        
        except Exception as e:
            logger.error(
                f"Error obteniendo estadísticas de limpieza: {str(e)}",
                exc_info=True
            )
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @extend_schema(
        summary="Preview de restauración",
        description="Genera preview de lo que se restauraría sin ejecutar la restauración",
        responses={200: RestorePreviewSerializer},
        tags=['Backups']
    )
    @action(detail=True, methods=['get'], url_path='restore-preview')
    def restore_preview(self, request, tenant_id=None, pk=None):
        """
        Generar preview de restauración sin ejecutarla.
        
        Args:
            request: Request object
            tenant_id: ID del tenant
            pk: ID del backup
        
        Returns:
            Response con preview de restauración
        """
        backup = self.get_object()
        
        logger.info(
            f"Usuario {request.user.email} solicitando preview de restauración "
            f"para backup {backup.id}"
        )
        
        restore_service = RestoreService()
        
        try:
            preview = restore_service.preview_restore(
                backup_id=backup.id,
                requested_by=request.user
            )
            
            logger.info(
                f"Preview generado para backup {backup.id}: "
                f"{preview['total_records']} registros, "
                f"{preview['potential_conflicts']} conflictos"
            )
            
            serializer = RestorePreviewSerializer(preview)
            return Response(serializer.data)
        
        except Exception as e:
            logger.error(
                f"Error generando preview de restauración para backup {backup.id}: {str(e)}",
                exc_info=True
            )
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @extend_schema(
        summary="Restaurar backup",
        description="Restaura un backup completo (datos y archivos)",
        request=RestoreBackupSerializer,
        responses={200: RestoreResultSerializer},
        tags=['Backups']
    )
    @action(detail=True, methods=['post'])
    def restore(self, request, tenant_id=None, pk=None):
        """
        Restaurar backup completo.
        
        Args:
            request: Request object
            tenant_id: ID del tenant
            pk: ID del backup
        
        Returns:
            Response con resultado de restauración
        """
        backup = self.get_object()
        
        logger.info(
            f"Usuario {request.user.email} solicitando restauración "
            f"de backup {backup.id}"
        )
        
        # Validar datos de entrada
        serializer = RestoreBackupSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # Obtener IP del cliente
        ip_address = self._get_client_ip(request)
        
        restore_service = RestoreService()
        
        try:
            result = restore_service.restore_backup(
                backup_id=backup.id,
                requested_by=request.user,
                conflict_strategy=serializer.validated_data.get('conflict_strategy', 'skip'),
                restore_files=serializer.validated_data.get('restore_files', True),
                ip_address=ip_address,
                dry_run=serializer.validated_data.get('dry_run', False)
            )
            
            logger.info(
                f"Restauración de backup {backup.id} completada: "
                f"{result['import_stats']['total_created']} creados, "
                f"{result['import_stats']['total_updated']} actualizados, "
                f"{result['files_restored']} archivos restaurados"
            )
            
            response_serializer = RestoreResultSerializer(result)
            return Response(response_serializer.data)
        
        except Exception as e:
            logger.error(
                f"Error restaurando backup {backup.id}: {str(e)}",
                exc_info=True
            )
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    def _get_client_ip(self, request):
        """
        Obtiene la IP del cliente desde el request.
        
        Args:
            request: Request object
        
        Returns:
            IP address string
        """
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip
