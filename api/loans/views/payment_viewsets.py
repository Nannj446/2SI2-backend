"""
ViewSets para SP3: Pagos.

Endpoints:
- GET /api/loans/payments/ → Listar pagos
- POST /api/loans/payments/ → Registrar pago
- GET /api/loans/payments/{id}/ → Detalle
- POST /api/loans/payments/{id}/confirm/ → Confirmar
- POST /api/loans/payments/{id}/cancel/ → Cancelar
- POST /api/loans/payments/{id}/reverse/ → Reversar
"""

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404

from api.loans.models_active import CreditPayment
from api.core.pagination import StandardResultsSetPagination
from api.loans.permissions import CanManagePayments
from api.loans.serializers.active_serializers import (
    CreditPaymentSerializer,
    CreditPaymentListSerializer,
    CreatePaymentSerializer,
    ConfirmPaymentSerializer,
)
from api.loans.services.payment_application_service import PaymentApplicationService


class CreditPaymentViewSet(viewsets.ModelViewSet):
    """
    ViewSet para gestión de pagos (staff).

    Permisos requeridos:
    - GET: payments.view
    - POST: payments.create
    """
    queryset = CreditPayment.objects.select_related(
        'active_credit', 'currency', 'registered_by', 'confirmed_by',
    ).prefetch_related('allocations')

    pagination_class = StandardResultsSetPagination

    def get_permissions(self):
        from rest_framework.permissions import IsAuthenticated
        return [IsAuthenticated(), CanManagePayments()]

    def get_serializer_class(self):
        if self.action == 'list':
            return CreditPaymentListSerializer
        elif self.action == 'create':
            return CreatePaymentSerializer
        return CreditPaymentSerializer

    def get_queryset(self):
        qs = super().get_queryset()

        # Filtrar por tenant (institución) del usuario staff
        tenant = getattr(self.request, 'tenant', None)
        if tenant:
            qs = qs.filter(institution=tenant)

        # Filtros
        credit_id = self.request.query_params.get('active_credit_id')
        status_filter = self.request.query_params.get('status')
        channel = self.request.query_params.get('channel')

        if credit_id:
            qs = qs.filter(active_credit_id=credit_id)
        if status_filter:
            qs = qs.filter(status=status_filter.upper())
        if channel:
            qs = qs.filter(channel=channel.upper())

        return qs

    def perform_create(self, serializer):
        payment = serializer.save()
        payment.institution = payment.active_credit.institution
        payment.save(update_fields=['institution'])

    def retrieve(self, request, *args, **kwargs):
        """GET /api/loans/payments/{id}/ — incluye URLs de factura de Stripe."""
        instance = self.get_object()
        from api.loans.services.stripe_service import StripePaymentService
        StripePaymentService.ensure_invoice_urls(instance)
        serializer = self.get_serializer(instance)
        return Response(serializer.data)

    @action(detail=True, methods=['post'], url_path='confirm')
    def confirm(self, request, pk=None):
        """
        POST /api/loans/payments/{id}/confirm/
        Confirmar un pago y aplicarlo al crédito.
        """
        payment = self.get_object()

        try:
            payment.confirmed_by = request.user
            payment.save(update_fields=['confirmed_by'])

            PaymentApplicationService.apply_payment(payment)

            serializer = CreditPaymentSerializer(payment, context={'request': request})
            return Response(serializer.data)

        except ValueError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'], url_path='cancel')
    def cancel(self, request, pk=None):
        """
        POST /api/loans/payments/{id}/cancel/
        Cancelar un pago pendiente (no aplicado).
        """
        payment = self.get_object()

        if payment.status != CreditPayment.Status.PENDING_CONFIRMATION:
            return Response(
                {'error': 'Solo pagos PENDING_CONFIRMATION pueden cancelarse'},
                status=status.HTTP_400_BAD_REQUEST
            )

        payment.status = CreditPayment.Status.CANCELLED
        payment.save()

        return Response({'status': 'cancelled'})

    @action(detail=True, methods=['post'], url_path='reverse')
    def reverse(self, request, pk=None):
        """
        POST /api/loans/payments/{id}/reverse/
        Reversar un pago confirmado.
        """
        payment = self.get_object()
        reason = request.data.get('reason', '')

        try:
            PaymentApplicationService.reverse_payment(
                payment=payment,
                user=request.user,
                reason=reason,
            )

            serializer = CreditPaymentSerializer(payment, context={'request': request})
            return Response(serializer.data)

        except ValueError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
