"""
ViewSet para SP4: Gestión de Solicitudes de Apoyo de Pago (Staff Web).

Endpoints:
- GET  /api/loans/support-requests/ → Listar todas las solicitudes
- GET  /api/loans/support-requests/{id}/ → Detalle
- POST /api/loans/support-requests/{id}/start-review/ → Iniciar revisión
- POST /api/loans/support-requests/{id}/approve/ → Aprobar
- POST /api/loans/support-requests/{id}/reject/ → Rechazar
- POST /api/loans/support-requests/{id}/request-more-info/ → Pedir más info
- GET  /api/loans/active-credits/{id}/support-requests/ → Solicitudes de un crédito
"""

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from api.loans.models_active import CreditSupportRequest
from api.core.pagination import StandardResultsSetPagination
from api.loans.permissions import CanManageSupportRequests
from api.loans.serializers.active_serializers import (
    CreditSupportRequestSerializer,
    CreditSupportRequestListSerializer,
    ReviewSupportRequestSerializer,
)


class SupportRequestViewSet(viewsets.ModelViewSet):
    """
    ViewSet para que el staff gestione solicitudes de apoyo de pago.
    """
    queryset = CreditSupportRequest.objects.select_related(
        'active_credit', 'client', 'reviewed_by',
    ).all()

    pagination_class = StandardResultsSetPagination

    def get_permissions(self):
        if self.action in ['list', 'retrieve', 'by_credit']:
            return [IsAuthenticated(), CanManageSupportRequests()]
        return [IsAuthenticated(), CanManageSupportRequests()]

    def get_serializer_class(self):
        if self.action == 'list':
            return CreditSupportRequestListSerializer
        return CreditSupportRequestSerializer

    def get_queryset(self):
        qs = super().get_queryset()

        if hasattr(self.request, 'tenant') and self.request.tenant:
            qs = qs.filter(institution=self.request.tenant)

        # Filtros
        status_filter = self.request.query_params.get('status')
        if status_filter:
            qs = qs.filter(status=status_filter)

        credit_id = self.request.query_params.get('active_credit_id')
        if credit_id:
            qs = qs.filter(active_credit_id=credit_id)

        client_id = self.request.query_params.get('client_id')
        if client_id:
            qs = qs.filter(client_id=client_id)

        return qs.order_by('-created_at')

    @action(detail=True, methods=['post'], url_path='start-review')
    def start_review(self, request, pk=None):
        """
        POST /api/loans/support-requests/{id}/start-review/
        Marca la solicitud como "en revisión".
        """
        support_request = self.get_object()

        from api.loans.services.support_request_service import SupportRequestService

        try:
            SupportRequestService.start_review(support_request, user=request.user)
            serializer = self.get_serializer(support_request)
            return Response(serializer.data)
        except ValueError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'], url_path='approve')
    def approve(self, request, pk=None):
        """
        POST /api/loans/support-requests/{id}/approve/
        Aprueba la solicitud y aplica la gracia/reestructuración.
        """
        support_request = self.get_object()

        serializer = ReviewSupportRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        bank_response = serializer.validated_data.get('bank_response', '')

        from api.loans.services.support_request_service import SupportRequestService

        try:
            result = SupportRequestService.approve(
                support_request,
                bank_response=bank_response,
                user=request.user,
            )
            response_serializer = self.get_serializer(support_request)
            return Response({
                **response_serializer.data,
                'applied_result': result,
            })
        except ValueError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'], url_path='reject')
    def reject(self, request, pk=None):
        """
        POST /api/loans/support-requests/{id}/reject/
        Rechaza la solicitud con un motivo.
        """
        support_request = self.get_object()

        serializer = ReviewSupportRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        reason = serializer.validated_data.get('bank_response', '')

        if not reason:
            return Response(
                {'error': 'Debe indicar el motivo de rechazo'},
                status=status.HTTP_400_BAD_REQUEST
            )

        from api.loans.services.support_request_service import SupportRequestService

        try:
            SupportRequestService.reject(support_request, reason=reason, user=request.user)
            response_serializer = self.get_serializer(support_request)
            return Response(response_serializer.data)
        except ValueError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'], url_path='request-more-info')
    def request_more_info(self, request, pk=None):
        """
        POST /api/loans/support-requests/{id}/request-more-info/
        Solicita más información al cliente.
        """
        support_request = self.get_object()

        serializer = ReviewSupportRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        requested_info = serializer.validated_data.get('requested_info', '')

        if not requested_info:
            return Response(
                {'error': 'Debe especificar qué información adicional necesita'},
                status=status.HTTP_400_BAD_REQUEST
            )

        from api.loans.services.support_request_service import SupportRequestService

        try:
            SupportRequestService.request_more_info(
                support_request,
                requested_info=requested_info,
                user=request.user,
            )
            response_serializer = self.get_serializer(support_request)
            return Response(response_serializer.data)
        except ValueError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
