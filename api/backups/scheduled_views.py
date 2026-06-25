"""
Views para gestión de backups programados.
"""
import logging
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404

from api.backups.scheduled_models import BackupScheduleConfig, ScheduledBackupLog
from api.backups.scheduled_serializers import (
    BackupScheduleConfigSerializer,
    BackupScheduleConfigCreateSerializer,
    BackupScheduleConfigUpdateSerializer,
    ScheduledBackupLogSerializer,
    BackupScheduleStatusSerializer,
)
from api.backups.services.scheduler_service import BackupSchedulerService
from api.backups.permissions import IsBackupAdmin
from api.backups.scheduler_thread import is_scheduler_running

logger = logging.getLogger(__name__)


class BackupScheduleConfigViewSet(viewsets.ModelViewSet):
    """
    ViewSet para gestionar configuraciones de backups programados.
    
    Endpoints:
    - GET /api/backups/schedules/ - Listar configuraciones
    - POST /api/backups/schedules/ - Crear configuración
    - GET /api/backups/schedules/{id}/ - Detalle de configuración
    - PUT/PATCH /api/backups/schedules/{id}/ - Actualizar configuración
    - DELETE /api/backups/schedules/{id}/ - Eliminar configuración
    - POST /api/backups/schedules/{id}/enable/ - Habilitar schedule
    - POST /api/backups/schedules/{id}/disable/ - Deshabilitar schedule
    - GET /api/backups/schedules/{id}/status/ - Estado del schedule
    - POST /api/backups/schedules/{id}/run-now/ - Ejecutar backup ahora
    - GET /api/backups/schedules/scheduler-status/ - Estado del scheduler automático
    """
    
    queryset = BackupScheduleConfig.objects.all()
    permission_classes = [IsAuthenticated, IsBackupAdmin]
    
    def get_serializer_class(self):
        """Retorna el serializer apropiado según la acción."""
        if self.action == 'create':
            return BackupScheduleConfigCreateSerializer
        elif self.action in ['update', 'partial_update']:
            return BackupScheduleConfigUpdateSerializer
        return BackupScheduleConfigSerializer
    
    def get_queryset(self):
        """Filtra configuraciones por tenant del usuario."""
        user = self.request.user
        
        # Superadmin puede ver todas
        if user.is_superuser:
            return BackupScheduleConfig.objects.all().select_related(
                'tenant', 'last_backup'
            )
        
        # Superadmin SaaS puede ver todas
        if hasattr(user, 'profile') and user.profile.user_type == 'saas_admin':
            return BackupScheduleConfig.objects.all().select_related(
                'tenant', 'last_backup'
            )
        
        # Usuario normal solo ve su tenant
        membership = user.institution_memberships.filter(is_active=True).first()
        if membership:
            return BackupScheduleConfig.objects.filter(
                tenant=membership.institution
            ).select_related('tenant', 'last_backup')
        
        return BackupScheduleConfig.objects.none()
    
    def perform_create(self, serializer):
        """Crea configuración y calcula next_run_at."""
        config = serializer.save()
        
        # Calcular próxima ejecución si está habilitado
        if config.is_enabled:
            scheduler_service = BackupSchedulerService()
            scheduler_service.initialize_schedule(config)
        
        logger.info(
            f"Configuración de backup programado creada para tenant {config.tenant.id} "
            f"por usuario {self.request.user.email}"
        )
    
    @action(detail=False, methods=['get'])
    def scheduler_status(self, request):
        """
        Obtiene el estado del scheduler automático.
        
        GET /api/backups/schedules/scheduler-status/
        
        Returns:
            Estado del scheduler en background
        """
        is_running = is_scheduler_running()
        
        return Response({
            'scheduler_running': is_running,
            'status': 'running' if is_running else 'stopped',
            'message': 'El scheduler de backups automáticos está corriendo en background' if is_running else 'El scheduler no está corriendo',
            'info': 'Los backups programados se ejecutan automáticamente cada minuto sin necesidad de comandos externos'
        })
    
    @action(detail=True, methods=['post'])
    def enable(self, request, pk=None):
        """
        Habilita el schedule de backups.
        
        POST /api/backups/schedules/{id}/enable/
        """
        config = self.get_object()
        
        if config.is_enabled:
            return Response(
                {'detail': 'El schedule ya está habilitado'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        config.is_enabled = True
        config.save()
        
        # Calcular próxima ejecución
        scheduler_service = BackupSchedulerService()
        scheduler_service.initialize_schedule(config)
        
        logger.info(
            f"Schedule habilitado para tenant {config.tenant.id} "
            f"por usuario {request.user.email}"
        )
        
        serializer = self.get_serializer(config)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def disable(self, request, pk=None):
        """
        Deshabilita el schedule de backups.
        
        POST /api/backups/schedules/{id}/disable/
        """
        config = self.get_object()
        
        if not config.is_enabled:
            return Response(
                {'detail': 'El schedule ya está deshabilitado'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        config.is_enabled = False
        config.next_run_at = None
        config.save()
        
        logger.info(
            f"Schedule deshabilitado para tenant {config.tenant.id} "
            f"por usuario {request.user.email}"
        )
        
        serializer = self.get_serializer(config)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def status(self, request, pk=None):
        """
        Obtiene el estado actual del schedule.
        
        GET /api/backups/schedules/{id}/status/
        
        Returns:
            Estado detallado con estadísticas y logs recientes
        """
        config = self.get_object()
        
        scheduler_service = BackupSchedulerService()
        status_data = scheduler_service.get_schedule_status(config)
        
        serializer = BackupScheduleStatusSerializer(status_data)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def run_now(self, request, pk=None):
        """
        Ejecuta un backup inmediatamente (fuera del schedule).
        
        POST /api/backups/schedules/{id}/run-now/
        
        Nota: Esto NO afecta el schedule programado, es una ejecución manual.
        """
        config = self.get_object()
        
        # Verificar que el tenant esté activo
        if not config.tenant.is_active:
            return Response(
                {'detail': 'El tenant está inactivo'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Ejecutar backup usando el scheduler service
        scheduler_service = BackupSchedulerService()
        
        try:
            result = scheduler_service._execute_scheduled_backup(config)
            
            if result['status'] == 'success':
                return Response({
                    'detail': 'Backup ejecutado exitosamente',
                    'backup_id': result['backup_id'],
                    'duration_seconds': result['duration_seconds']
                }, status=status.HTTP_201_CREATED)
            elif result['status'] == 'skipped':
                return Response({
                    'detail': 'Backup omitido',
                    'reason': result['error']
                }, status=status.HTTP_400_BAD_REQUEST)
            else:  # failed
                return Response({
                    'detail': 'Backup falló',
                    'error': result['error']
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        except Exception as e:
            logger.error(f"Error ejecutando backup manual: {str(e)}")
            return Response(
                {'detail': f'Error ejecutando backup: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class ScheduledBackupLogViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet de solo lectura para logs de backups programados.
    
    Endpoints:
    - GET /api/backups/scheduled-logs/ - Listar logs
    - GET /api/backups/scheduled-logs/{id}/ - Detalle de log
    """
    
    queryset = ScheduledBackupLog.objects.all()
    serializer_class = ScheduledBackupLogSerializer
    permission_classes = [IsAuthenticated, IsBackupAdmin]
    
    def get_queryset(self):
        """Filtra logs por tenant del usuario."""
        user = self.request.user
        
        # Superadmin puede ver todos
        if user.is_superuser:
            queryset = ScheduledBackupLog.objects.all()
        # Superadmin SaaS puede ver todos
        elif hasattr(user, 'profile') and user.profile.user_type == 'saas_admin':
            queryset = ScheduledBackupLog.objects.all()
        else:
            # Usuario normal solo ve logs de su tenant
            membership = user.institution_memberships.filter(is_active=True).first()
            if membership:
                queryset = ScheduledBackupLog.objects.filter(
                    schedule_config__tenant=membership.institution
                )
            else:
                queryset = ScheduledBackupLog.objects.none()
        
        # Filtros opcionales
        config_id = self.request.query_params.get('config_id')
        if config_id:
            queryset = queryset.filter(schedule_config_id=config_id)
        
        status_filter = self.request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        return queryset.select_related(
            'schedule_config',
            'schedule_config__tenant',
            'backup'
        ).order_by('-started_at')
