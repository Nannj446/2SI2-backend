"""
URLs para API de backups.
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import TenantBackupViewSet
from .scheduled_views import BackupScheduleConfigViewSet, ScheduledBackupLogViewSet

app_name = 'backups'

# Router para backups programados
router = DefaultRouter()
router.register(r'schedules', BackupScheduleConfigViewSet, basename='backup-schedule')
router.register(r'scheduled-logs', ScheduledBackupLogViewSet, basename='scheduled-backup-log')

# Rutas anidadas bajo tenant
urlpatterns = [
    # Listar y crear backups
    path(
        'tenants/<int:tenant_id>/backups/',
        TenantBackupViewSet.as_view({
            'get': 'list',
            'post': 'create'
        }),
        name='tenant-backup-list'
    ),
    
    # Detalle, actualizar y eliminar backup
    path(
        'tenants/<int:tenant_id>/backups/<int:pk>/',
        TenantBackupViewSet.as_view({
            'get': 'retrieve',
            'delete': 'destroy'
        }),
        name='tenant-backup-detail'
    ),
    
    # Descargar backup
    path(
        'tenants/<int:tenant_id>/backups/<int:pk>/download/',
        TenantBackupViewSet.as_view({
            'get': 'download'
        }),
        name='tenant-backup-download'
    ),
    
    # Logs de auditoría del backup
    path(
        'tenants/<int:tenant_id>/backups/<int:pk>/audit-logs/',
        TenantBackupViewSet.as_view({
            'get': 'audit_logs'
        }),
        name='tenant-backup-audit-logs'
    ),
    
    # Preview de restauración
    path(
        'tenants/<int:tenant_id>/backups/<int:pk>/restore-preview/',
        TenantBackupViewSet.as_view({
            'get': 'restore_preview'
        }),
        name='tenant-backup-restore-preview'
    ),
    
    # Restaurar backup
    path(
        'tenants/<int:tenant_id>/backups/<int:pk>/restore/',
        TenantBackupViewSet.as_view({
            'post': 'restore'
        }),
        name='tenant-backup-restore'
    ),
    
    # Estadísticas de limpieza
    path(
        'tenants/<int:tenant_id>/backups/cleanup-stats/',
        TenantBackupViewSet.as_view({
            'get': 'cleanup_stats'
        }),
        name='tenant-backup-cleanup-stats'
    ),
    
    # Incluir rutas del router (backups programados)
    path('', include(router.urls)),
]
