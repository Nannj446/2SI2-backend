"""
Vistas para gestión de integraciones externas
"""

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
import time

from .models import ExternalIntegration, IntegrationLog
from .serializers import (
    ExternalIntegrationSerializer,
    ExternalIntegrationListSerializer,
    IntegrationLogSerializer,
    IntegrationLogListSerializer,
)


class ExternalIntegrationViewSet(viewsets.ModelViewSet):
    """
    ViewSet para gestión de integraciones externas.
    
    Permite CRUD completo y acciones adicionales como
    probar conexión y obtener métricas.
    """
    
    permission_classes = [IsAuthenticated]

    def _get_institution(self):
        """Obtiene la institución activa del usuario autenticado."""
        membership = self.request.user.institution_memberships.filter(
            is_active=True
        ).select_related('institution').first()
        return membership.institution if membership else None
    
    def get_queryset(self):
        """Filtra por institución del usuario autenticado"""
        institution = self._get_institution()
        if institution is None:
            return ExternalIntegration.objects.none()

        queryset = ExternalIntegration.objects.filter(
            institution=institution
        )
        
        # Filtros opcionales
        integration_type = self.request.query_params.get('integration_type')
        if integration_type:
            queryset = queryset.filter(integration_type=integration_type)
        
        status_param = self.request.query_params.get('status')
        if status_param:
            queryset = queryset.filter(status=status_param)
        
        return queryset.select_related('institution')
    
    def get_serializer_class(self):
        """Usa serializer simplificado para listas"""
        if self.action == 'list':
            return ExternalIntegrationListSerializer
        return ExternalIntegrationSerializer
    
    def perform_create(self, serializer):
        """Asigna la institución del usuario al crear"""
        institution = self._get_institution()
        serializer.save(institution=institution)
    
    @action(detail=True, methods=['post'])
    def test_connection(self, request, pk=None):
        """
        Prueba la conexión con el servicio externo.
        
        POST /api/integrations/{id}/test_connection/
        """
        integration = self.get_object()
        
        # Registrar log de prueba
        start_time = time.time()
        
        try:
            # Intentar probar conexión
            success, message = integration.test_connection()
            duration_ms = int((time.time() - start_time) * 1000)
            
            # Crear log
            IntegrationLog.objects.create(
                integration=integration,
                action='TEST_CONNECTION',
                status='SUCCESS' if success else 'FAILED',
                request_data={},
                response_data={'message': message},
                duration_ms=duration_ms,
                user=request.user,
                ip_address=self.get_client_ip(request),
            )
            
            if success:
                integration.increment_success()
                return Response({
                    'success': True,
                    'message': message,
                    'duration_ms': duration_ms
                })
            else:
                integration.increment_error(message)
                return Response({
                    'success': False,
                    'message': message,
                    'duration_ms': duration_ms
                }, status=status.HTTP_400_BAD_REQUEST)
                
        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            error_message = str(e)
            
            # Crear log de error
            IntegrationLog.objects.create(
                integration=integration,
                action='TEST_CONNECTION',
                status='FAILED',
                request_data={},
                response_data={},
                error_message=error_message,
                duration_ms=duration_ms,
                user=request.user,
                ip_address=self.get_client_ip(request),
            )
            
            integration.increment_error(error_message)
            return Response({
                'success': False,
                'message': f'Error al probar conexión: {error_message}',
                'duration_ms': duration_ms
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['post'])
    def sync(self, request, pk=None):
        """
        Sincroniza datos con el servicio externo.
        
        POST /api/integrations/{id}/sync/
        """
        integration = self.get_object()
        
        # Actualizar timestamp de sync
        integration.last_sync_at = timezone.now()
        integration.save(update_fields=['last_sync_at'])
        
        return Response({
            'success': True,
            'message': 'Sincronización iniciada',
            'synced_at': integration.last_sync_at
        })
    
    @action(detail=True, methods=['get'])
    def metrics(self, request, pk=None):
        """
        Obtiene métricas de uso de la integración.
        
        GET /api/integrations/{id}/metrics/
        """
        integration = self.get_object()
        
        # Calcular métricas
        total_calls = integration.success_count + integration.error_count
        success_rate = (
            (integration.success_count / total_calls * 100) 
            if total_calls > 0 else 0
        )
        
        # Logs recientes
        recent_logs = integration.logs.order_by('-created_at')[:10]
        recent_logs_data = IntegrationLogListSerializer(recent_logs, many=True).data
        
        return Response({
            'integration_id': integration.id,
            'integration_name': integration.name,
            'integration_type': integration.integration_type,
            'status': integration.status,
            'metrics': {
                'total_calls': total_calls,
                'success_count': integration.success_count,
                'error_count': integration.error_count,
                'success_rate': round(success_rate, 2),
                'last_sync_at': integration.last_sync_at,
                'last_success_at': integration.last_success_at,
                'last_error_at': integration.last_error_at,
                'last_error_message': integration.last_error_message,
            },
            'recent_logs': recent_logs_data,
        })
    
    @action(detail=True, methods=['get'])
    def logs(self, request, pk=None):
        """
        Obtiene los logs de una integración específica.
        
        GET /api/integrations/{id}/logs/
        """
        integration = self.get_object()
        
        # Filtros
        action_filter = request.query_params.get('action')
        status_filter = request.query_params.get('status')
        limit = int(request.query_params.get('limit', 50))
        
        logs = integration.logs.all()
        
        if action_filter:
            logs = logs.filter(action=action_filter)
        
        if status_filter:
            logs = logs.filter(status=status_filter)
        
        logs = logs.order_by('-created_at')[:limit]
        
        serializer = IntegrationLogListSerializer(logs, many=True)
        return Response(serializer.data)
    
    def get_client_ip(self, request):
        """Obtiene la IP del cliente"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip


class IntegrationLogViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet para visualización de logs de integraciones.
    """
    
    permission_classes = [IsAuthenticated]
    serializer_class = IntegrationLogSerializer
    
    def get_queryset(self):
        """Filtra por institución del usuario autenticado"""
        membership = self.request.user.institution_memberships.filter(
            is_active=True
        ).select_related('institution').first()
        institution = membership.institution if membership else None
        if institution is None:
            return IntegrationLog.objects.none()
        queryset = IntegrationLog.objects.filter(
            integration__institution=institution
        ).select_related('integration', 'user')
        
        # Filtros opcionales
        integration_id = self.request.query_params.get('integration')
        if integration_id:
            queryset = queryset.filter(integration_id=integration_id)
        
        action = self.request.query_params.get('action')
        if action:
            queryset = queryset.filter(action=action)
        
        log_status = self.request.query_params.get('status')
        if log_status:
            queryset = queryset.filter(status=log_status)
        
        return queryset.order_by('-created_at')
    
    def get_serializer_class(self):
        """Usa serializer simplificado para listas"""
        if self.action == 'list':
            return IntegrationLogListSerializer
        return IntegrationLogSerializer
