"""
ViewSets para SP3: Créditos Activos — Cliente (Mobile).

Endpoints:
- GET /api/loans/my-active-credits/ → Mis créditos
- GET /api/loans/my-active-credits/{id}/ → Detalle
- GET /api/loans/my-active-credits/{id}/schedule/ → Cronograma
- GET /api/loans/my-active-credits/{id}/payments/ → Pagos
- POST /api/loans/my-active-credits/{id}/payments/start-online/ → Pagar online
"""

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404

from api.loans.models_active import ActiveCredit, CreditPayment, CreditSupportRequest
from api.core.pagination import StandardResultsSetPagination
from api.loans.services.stripe_service import StripePaymentService
from django.conf import settings
from api.loans.serializers.active_serializers import (
    ActiveCreditSerializer,
    ActiveCreditListSerializer,
    CreditInstallmentSerializer,
    CreditPaymentListSerializer,
    CreditPaymentSerializer,
    StartOnlinePaymentSerializer,
    CreditSupportRequestSerializer,
    CreateSupportRequestSerializer,
)


class MyActiveCreditsViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet para que clientes vean sus créditos activos.

    Filtra automáticamente por el cliente autenticado.
    """
    queryset = ActiveCredit.objects.select_related(
        'client', 'product', 'currency',
        'payment_frequency', 'amortization_system',
    ).prefetch_related('installments', 'payments')

    pagination_class = StandardResultsSetPagination

    def get_permissions(self):
        return [IsAuthenticated()]

    def get_serializer_class(self):
        if self.action == 'list':
            return ActiveCreditListSerializer
        return ActiveCreditSerializer

    def get_queryset(self):
        qs = super().get_queryset()

        # Filtrar por el cliente del usuario autenticado
        client = self._get_client_from_user()
        if client:
            qs = qs.filter(client=client)
        else:
            # Si no hay cliente asociado, no devolver nada
            return qs.none()

        return qs

    def _get_client_from_user(self):
        """Obtiene el cliente asociado al usuario autenticado."""
        user = self.request.user
        if hasattr(user, 'client_profile'):
            return user.client_profile
        elif hasattr(user, 'client'):
            return user.client
        return None

    @action(detail=True, methods=['get'], url_path='schedule')
    def schedule(self, request, pk=None):
        """
        GET /api/loans/my-active-credits/{id}/schedule/
        Cronograma de mi crédito.
        """
        active_credit = self.get_object()
        installments = active_credit.installments.order_by('installment_number')
        serializer = CreditInstallmentSerializer(installments, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['get'], url_path='payments')
    def payments(self, request, pk=None):
        """
        GET /api/loans/my-active-credits/{id}/payments/
        Historial de pagos de mi crédito.
        """
        active_credit = self.get_object()
        payments = active_credit.payments.order_by('-payment_date', '-created_at')
        serializer = CreditPaymentListSerializer(payments, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['get'], url_path=r'payments/(?P<payment_id>\d+)')
    def payment_detail(self, request, pk=None, payment_id=None):
        """
        GET /api/loans/my-active-credits/{id}/payments/{payment_id}/
        Detalle de un pago específico (con asignaciones y URLs de factura).
        """
        active_credit = self.get_object()
        payment = get_object_or_404(
            active_credit.payments.all(),
            pk=payment_id,
        )
        # Intentar obtener URLs de factura de Stripe si aún no existen
        from api.loans.services.stripe_service import StripePaymentService
        StripePaymentService.ensure_invoice_urls(payment)
        serializer = CreditPaymentSerializer(payment, context={'request': request})
        return Response(serializer.data)

    @action(detail=True, methods=['post'], url_path='payments/start-online')
    def start_online_payment(self, request, pk=None):
        """
        POST /api/loans/my-active-credits/{id}/payments/start-online/
        Inicia un pago online.

        Crea un registro de pago con estado PENDING_CONFIRMATION.
        Cuando la pasarela de pago esté integrada, este endpoint
        se conectará con Stripe u otro proveedor.
        """
        active_credit = self.get_object()

        serializer = StartOnlinePaymentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        installment_id = serializer.validated_data['installment_id']
        amount = serializer.validated_data.get('amount')

        # Validar que la cuota exista y pertenezca al crédito
        installment = active_credit.installments.filter(
            pk=installment_id,
            status__in=['PENDING', 'PARTIAL', 'OVERDUE', 'IN_GRACE'],
        ).first()

        if not installment:
            return Response(
                {'error': 'Cuota no encontrada o no está pendiente de pago'},
                status=status.HTTP_400_BAD_REQUEST
            )

        payment_amount = amount or (installment.total_amount - installment.paid_amount)

        # Crear pago online
        payment = CreditPayment.objects.create(
            institution=active_credit.institution,
            active_credit=active_credit,
            amount=payment_amount,
            currency=active_credit.currency,
            payment_date=active_credit.next_due_date or installment.due_date,
            channel=CreditPayment.Channel.ONLINE,
            method='ONLINE',
            reference_number=f"ONLINE-{active_credit.credit_number}",
            status=CreditPayment.Status.PENDING_CONFIRMATION,
            registered_by=request.user,
            metadata={
                'installment_id': installment.id,
                'installment_number': installment.installment_number,
            }
        )

        # Intentar crear sesión de Stripe Checkout
        stripe_session = None
        stripe_error = None
        if StripePaymentService.is_configured():
            try:
                # Usar URLs del backend que auto-cierran para mobile
                # (stripe_return_views.py sirve páginas HTML con window.close())
                base = request.build_absolute_uri('/api/loans')[:-len('/api/loans')]
                success_url = f"{base}/api/loans/stripe/success/?session_id={{CHECKOUT_SESSION_ID}}"
                cancel_url = f"{base}/api/loans/stripe/cancel/"
                stripe_session = StripePaymentService.create_checkout_session(
                    payment=payment,
                    success_url=success_url,
                    cancel_url=cancel_url,
                )
            except ValueError as e:
                stripe_error = str(e)
                payment.metadata['stripe_error'] = stripe_error
                payment.save(update_fields=['metadata'])

        response_data = {
            'payment_id': payment.id,
            'amount': str(payment.amount),
            'installment_number': installment.installment_number,
            'total_due': str(installment.total_amount),
            'status': payment.status,
            'stripe_configured': StripePaymentService.is_configured(),
        }

        if stripe_session:
            response_data['stripe_session_url'] = stripe_session['url']
            response_data['stripe_session_id'] = stripe_session['session_id']
            response_data['message'] = 'Redirigir al cliente a la URL de Stripe Checkout'
        elif stripe_error:
            response_data['stripe_error'] = stripe_error
            response_data['message'] = f'Error con Stripe: {stripe_error}'
        else:
            response_data['message'] = 'Pago iniciado. Configure STRIPE_SECRET_KEY para habilitar pagos online.'

        return Response(response_data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], url_path='payments/verify-online')
    def verify_online_payment(self, request, pk=None):
        """
        POST /api/loans/my-active-credits/{id}/payments/verify-online/
        Verifica el estado de un pago online consultando directamente a Stripe.

        Si Stripe confirma que el pago fue completado, lo aplica al crédito.
        Body: { payment_id: int }
        """
        from api.loans.models_active import CreditPayment

        payment_id = request.data.get('payment_id')
        if not payment_id:
            return Response({'error': 'payment_id requerido'}, status=status.HTTP_400_BAD_REQUEST)

        # Validar que el pago pertenezca al crédito del cliente
        active_credit = self.get_object()
        try:
            payment = CreditPayment.objects.get(
                pk=payment_id,
                active_credit=active_credit,
            )
        except CreditPayment.DoesNotExist:
            return Response({'error': 'Pago no encontrado'}, status=status.HTTP_404_NOT_FOUND)

        if payment.status == 'CONFIRMED':
            return Response({
                'confirmed': True,
                'status': 'CONFIRMED',
                'message': 'Pago ya confirmado',
            })

        try:
            result = StripePaymentService.verify_payment(payment_id)
            return Response(result)
        except ValueError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    # ─── Solicitudes de Apoyo de Pago (Mobile) ──────────────────

    @action(detail=True, methods=['get', 'post'], url_path='support-requests')
    def support_requests(self, request, pk=None):
        """
        GET  /api/loans/my-active-credits/{id}/support-requests/
        POST /api/loans/my-active-credits/{id}/support-requests/

        Lista o crea solicitudes de apoyo de pago para este crédito.
        """
        active_credit = self.get_object()

        if request.method == 'GET':
            requests_qs = active_credit.support_requests.order_by('-created_at')
            serializer = CreditSupportRequestSerializer(requests_qs, many=True)
            return Response(serializer.data)

        elif request.method == 'POST':
            serializer = CreateSupportRequestSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)

            client = self._get_client_from_user()
            if not client:
                return Response(
                    {'error': 'No se encontró perfil de cliente'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            from api.loans.services.support_request_service import SupportRequestService

            try:
                support_request = SupportRequestService.create_request(
                    active_credit=active_credit,
                    client=client,
                    data=serializer.validated_data,
                    user=request.user,
                )
                response_serializer = CreditSupportRequestSerializer(support_request)
                return Response(response_serializer.data, status=status.HTTP_201_CREATED)
            except ValueError as e:
                return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'], url_path='support-requests/(?P<request_id>[^/.]+)/cancel')
    def cancel_support_request(self, request, pk=None, request_id=None):
        """
        POST /api/loans/my-active-credits/{id}/support-requests/{request_id}/cancel/
        El cliente cancela su propia solicitud.
        """
        active_credit = self.get_object()

        try:
            support_request = CreditSupportRequest.objects.get(
                pk=request_id,
                active_credit=active_credit,
            )
        except CreditSupportRequest.DoesNotExist:
            return Response({'error': 'Solicitud no encontrada'}, status=status.HTTP_404_NOT_FOUND)

        from api.loans.services.support_request_service import SupportRequestService

        try:
            SupportRequestService.cancel(support_request, user=request.user)
            serializer = CreditSupportRequestSerializer(support_request)
            return Response(serializer.data)
        except ValueError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
