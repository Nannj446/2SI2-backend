"""
ViewSets para motivos de rechazo.

SP3-99: Aprobación o Rechazo de Créditos
"""

from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from api.loans.models_rejection import RejectionReason
from api.loans.serializers.rejection_serializers import RejectionReasonSerializer


class RejectionReasonViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet para motivos de rechazo (solo lectura).
    
    Endpoints:
    - GET /api/loans/rejection-reasons/ - Listar motivos activos
    - GET /api/loans/rejection-reasons/{id}/ - Detalle de motivo
    
    Query params:
    - category: Filtrar por categoría
    """
    
    permission_classes = [IsAuthenticated]
    serializer_class = RejectionReasonSerializer
    
    def get_queryset(self):
        user = self.request.user
        
        queryset = RejectionReason.objects.filter(is_active=True)
        
        # Filtrar por institución
        if hasattr(user, 'institution'):
            queryset = queryset.filter(institution=user.institution)
        
        # Filtrar por categoría si se proporciona
        category = self.request.query_params.get('category')
        if category:
            queryset = queryset.filter(category=category)
        
        return queryset.order_by('display_order', 'name')
