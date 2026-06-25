"""
ViewSets para CU-07: Consultar Estado y Seguimiento.

Proporciona endpoints REST para:
- Clientes: consultar el estado de sus solicitudes
- Ver timeline completo con historial de cambios
- Ver acciones pendientes
"""

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from api.loans.models import LoanApplication
from api.loans.serializers.timeline_serializers import (
    LoanApplicationTimelineSerializer,
    TimelineEventSerializer,
    PendingActionSerializer
)
from api.loans.permissions import IsApplicationOwner


class ClientApplicationViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet para que clientes consulten sus solicitudes.
    
    Endpoints:
    - GET /api/loans/my-applications/ - Listar mis solicitudes
    - GET /api/loans/my-applications/{id}/ - Detalle con timeline completo
    - GET /api/loans/my-applications/{id}/timeline/ - Timeline detallado
    - GET /api/loans/my-applications/{id}/pending-actions/ - Acciones pendientes
    """
    
    serializer_class = LoanApplicationTimelineSerializer
    permission_classes = [IsAuthenticated, IsApplicationOwner]
    
    def get_queryset(self):
        # Verificar si el usuario tiene un cliente asociado
        if not hasattr(self.request.user, 'client_profile'):
            return LoanApplication.objects.none()
        
        return LoanApplication.objects.filter(
            institution=self.request.user.institution,
            client=self.request.user.client_profile
        ).select_related(
            'product',
            'rule_set_snapshot'
        ).prefetch_related(
            'status_history',
            'document_checklist',
            'document_checklist__document_requirement',
            'document_checklist__file_resource'
        ).order_by('-created_at')
    
    @action(detail=True, methods=['get'])
    def timeline(self, request, pk=None):
        """
        Retorna el timeline detallado de una solicitud.
        
        GET /api/loans/my-applications/{id}/timeline/
        """
        application = self.get_object()
        
        # Obtener eventos del timeline (solo visibles para el cliente)
        timeline_events = application.status_history.filter(
            is_visible_to_borrower=True
        ).order_by('-created_at')
        
        serializer = TimelineEventSerializer(timeline_events, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def pending_actions(self, request, pk=None):
        """
        Retorna las acciones pendientes del cliente.
        
        GET /api/loans/my-applications/{id}/pending-actions/
        """
        application = self.get_object()
        
        # Obtener acciones pendientes
        pending_actions = application.status_history.filter(
            is_visible_to_borrower=True,
            requires_client_action=True,
            action_completed_at__isnull=True
        ).order_by('-created_at')
        
        serializer = PendingActionSerializer(pending_actions, many=True)
        return Response(serializer.data)
