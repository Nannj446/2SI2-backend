"""
Vistas para el sistema de auditoría.
Solo accesibles para administradores SaaS.
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Q, Count
from django.utils import timezone
from datetime import timedelta

from api.audit.models import AuditLog, SecurityEvent
from api.audit.serializers import (
    AuditLogSerializer,
    AuditLogListSerializer,
    SecurityEventSerializer,
    SecurityEventListSerializer,
    ResolveSecurityEventSerializer,
)
from api.audit.services import SecurityEventService
from api.core.pagination import StandardResultsSetPagination


class IsSaaSAdmin(IsAuthenticated):
    """Permiso que solo permite acceso a administradores SaaS."""
    
    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        
        # Verificar que el usuario sea SaaS admin
        if not hasattr(request.user, 'profile'):
            return False
        
        return request.user.profile.is_saas_admin()


class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet para consultar logs de auditoría.
    Solo lectura, accesible solo para administradores SaaS.
    """
    
    permission_classes = [IsSaaSAdmin]
    pagination_class = StandardResultsSetPagination
    
    def get_queryset(self):
        """Obtiene todos los logs de auditoría con filtros."""
        queryset = AuditLog.objects.select_related(
            'user',
            'institution'
        ).all()
        
        # Filtros
        user_id = self.request.query_params.get('user_id')
        institution_id = self.request.query_params.get('institution_id')
        action = self.request.query_params.get('action')
        severity = self.request.query_params.get('severity')
        resource_type = self.request.query_params.get('resource_type')
        date_from = self.request.query_params.get('date_from')
        date_to = self.request.query_params.get('date_to')
        search = self.request.query_params.get('search')
        
        if user_id:
            queryset = queryset.filter(user_id=user_id)
        
        if institution_id:
            queryset = queryset.filter(institution_id=institution_id)
        
        if action:
            queryset = queryset.filter(action=action)
        
        if severity:
            queryset = queryset.filter(severity=severity)
        
        if resource_type:
            queryset = queryset.filter(resource_type=resource_type)
        
        if date_from:
            queryset = queryset.filter(timestamp__gte=date_from)
        
        if date_to:
            queryset = queryset.filter(timestamp__lte=date_to)
        
        if search:
            queryset = queryset.filter(
                Q(description__icontains=search) |
                Q(user__email__icontains=search) |
                Q(ip_address__icontains=search)
            )
        
        return queryset.order_by('-timestamp')
    
    def get_serializer_class(self):
        """Usa serializer simplificado para listado."""
        if self.action == 'list':
            return AuditLogListSerializer
        return AuditLogSerializer
    
    @action(detail=False, methods=['get'])
    def stats(self, request):
        """Obtiene estadísticas de auditoría."""
        # Últimos 30 días
        date_from = timezone.now() - timedelta(days=30)
        
        queryset = AuditLog.objects.filter(timestamp__gte=date_from)
        
        # Estadísticas por acción
        actions_stats = queryset.values('action').annotate(
            count=Count('id')
        ).order_by('-count')
        
        # Estadísticas por severidad
        severity_stats = queryset.values('severity').annotate(
            count=Count('id')
        ).order_by('-count')
        
        # Estadísticas por institución
        institution_stats = queryset.filter(
            institution__isnull=False
        ).values(
            'institution__id',
            'institution__name'
        ).annotate(
            count=Count('id')
        ).order_by('-count')[:10]
        
        # Usuarios más activos
        user_stats = queryset.filter(
            user__isnull=False
        ).values(
            'user__id',
            'user__email'
        ).annotate(
            count=Count('id')
        ).order_by('-count')[:10]
        
        # Total de logs
        total_logs = queryset.count()
        
        return Response({
            'total_logs': total_logs,
            'actions': list(actions_stats),
            'severity': list(severity_stats),
            'institutions': list(institution_stats),
            'users': list(user_stats),
        })
    
    @action(detail=False, methods=['get'])
    def recent_critical(self, request):
        """Obtiene los eventos críticos más recientes."""
        queryset = AuditLog.objects.filter(
            severity='critical'
        ).select_related(
            'user',
            'institution'
        ).order_by('-timestamp')[:20]
        
        serializer = AuditLogListSerializer(queryset, many=True)
        return Response(serializer.data)


class SecurityEventViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet para consultar eventos de seguridad.
    Solo lectura, accesible solo para administradores SaaS.
    """
    
    permission_classes = [IsSaaSAdmin]
    pagination_class = StandardResultsSetPagination
    
    def get_queryset(self):
        """Obtiene todos los eventos de seguridad con filtros."""
        queryset = SecurityEvent.objects.select_related(
            'user',
            'resolved_by'
        ).all()
        
        # Filtros
        event_type = self.request.query_params.get('event_type')
        resolved = self.request.query_params.get('resolved')
        user_id = self.request.query_params.get('user_id')
        ip_address = self.request.query_params.get('ip_address')
        date_from = self.request.query_params.get('date_from')
        date_to = self.request.query_params.get('date_to')
        search = self.request.query_params.get('search')
        
        if event_type:
            queryset = queryset.filter(event_type=event_type)
        
        if resolved is not None:
            resolved_bool = resolved.lower() in ['true', '1', 'yes']
            queryset = queryset.filter(resolved=resolved_bool)
        
        if user_id:
            queryset = queryset.filter(user_id=user_id)
        
        if ip_address:
            queryset = queryset.filter(ip_address=ip_address)
        
        if date_from:
            queryset = queryset.filter(timestamp__gte=date_from)
        
        if date_to:
            queryset = queryset.filter(timestamp__lte=date_to)
        
        if search:
            queryset = queryset.filter(
                Q(description__icontains=search) |
                Q(email__icontains=search) |
                Q(ip_address__icontains=search)
            )
        
        return queryset.order_by('-timestamp')
    
    def get_serializer_class(self):
        """Usa serializer simplificado para listado."""
        if self.action == 'list':
            return SecurityEventListSerializer
        return SecurityEventSerializer
    
    @action(detail=True, methods=['post'])
    def resolve(self, request, pk=None):
        """Marca un evento de seguridad como resuelto."""
        event = self.get_object()
        
        if event.resolved:
            return Response(
                {'error': 'Este evento ya fue resuelto'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        serializer = ResolveSecurityEventSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # Resolver el evento
        event = SecurityEventService.resolve_event(
            event_id=event.id,
            resolved_by=request.user
        )
        
        # Agregar notas si se proporcionaron
        notes = serializer.validated_data.get('notes')
        if notes:
            event.metadata['resolution_notes'] = notes
            event.save()
        
        return Response(
            SecurityEventSerializer(event).data,
            status=status.HTTP_200_OK
        )
    
    @action(detail=False, methods=['get'])
    def unresolved(self, request):
        """Obtiene eventos de seguridad no resueltos."""
        queryset = SecurityEventService.get_unresolved_events()
        
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = SecurityEventListSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = SecurityEventListSerializer(queryset, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def stats(self, request):
        """Obtiene estadísticas de eventos de seguridad."""
        # Últimos 30 días
        date_from = timezone.now() - timedelta(days=30)
        
        queryset = SecurityEvent.objects.filter(timestamp__gte=date_from)
        
        # Estadísticas por tipo de evento
        event_type_stats = queryset.values('event_type').annotate(
            count=Count('id')
        ).order_by('-count')
        
        # IPs más frecuentes
        ip_stats = queryset.values('ip_address').annotate(
            count=Count('id')
        ).order_by('-count')[:10]
        
        # Eventos no resueltos
        unresolved_count = queryset.filter(resolved=False).count()
        
        # Total de eventos
        total_events = queryset.count()
        
        return Response({
            'total_events': total_events,
            'unresolved_count': unresolved_count,
            'event_types': list(event_type_stats),
            'top_ips': list(ip_stats),
        })
