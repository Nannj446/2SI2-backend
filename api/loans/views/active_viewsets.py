"""
ViewSets para SP3: Créditos Activos.

Endpoints:
- GET/POST /api/loans/active-credits/ → Listar/Crear
- GET /api/loans/active-credits/{id}/ → Detalle
- POST /api/loans/active-credits/activate-from-contract/ → Activar
- GET /api/loans/active-credits/{id}/summary/ → Resumen
- GET /api/loans/active-credits/{id}/schedule/ → Cronograma
- GET /api/loans/active-credits/{id}/payments/ → Pagos
- POST /api/loans/active-credits/{id}/recalculate/ → Recalcular
- POST /api/loans/active-credits/{id}/refresh-status/ → Refrescar estado
- POST /api/loans/active-credits/{id}/grace-period/ → Gracia
- POST /api/loans/active-credits/{id}/restructure/ → Reestructurar
"""

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from django.db import models as db_models

from api.loans.models_active import ActiveCredit
from api.core.pagination import StandardResultsSetPagination
from api.loans.permissions import (
    CanViewActiveCredits,
    CanManageActiveCredits,
    CanApplyGracePeriod,
    CanRestructure,
)
from api.loans.serializers.active_serializers import (
    ActiveCreditSerializer,
    ActiveCreditListSerializer,
    ActivateFromContractSerializer,
    ActiveCreditSummarySerializer,
    CreditInstallmentSerializer,
    CreditInstallmentListSerializer,
    CreditPaymentListSerializer,
    ApplyGracePeriodSerializer,
    CreditGracePeriodSerializer,
    RestructureSerializer,
    CreditRestructuringSerializer,
    CreditStatusHistorySerializer,
)
from api.loans.services.active_credit_service import ActiveCreditService
from api.loans.services.amortization_calculation_service import AmortizationCalculationService
from api.loans.services.credit_status_service import CreditStatusService
from api.loans.services.grace_period_service import GracePeriodService
from api.loans.services.restructuring_service import RestructuringService


class ActiveCreditViewSet(viewsets.ModelViewSet):
    """
    ViewSet para gestión de créditos activos (staff).

    Permisos requeridos:
    - GET: active_credits.view
    - POST: active_credits.manage
    - PATCH: active_credits.manage
    """
    queryset = ActiveCredit.objects.select_related(
        'client', 'product', 'currency',
        'payment_frequency', 'amortization_system',
        'loan_application', 'contract',
    ).prefetch_related('installments', 'payments')

    pagination_class = StandardResultsSetPagination

    def get_permissions(self):
        from rest_framework.permissions import IsAuthenticated
        base = [IsAuthenticated()]
        if self.action in ['list', 'retrieve', 'summary', 'schedule', 'payments', 'status_history']:
            base.append(CanViewActiveCredits())
        else:
            base.append(CanManageActiveCredits())
        if self.action == 'grace_period':
            base.append(CanApplyGracePeriod())
        if self.action == 'restructure':
            base.append(CanRestructure())
        return base

    def get_serializer_class(self):
        if self.action == 'list':
            return ActiveCreditListSerializer
        return ActiveCreditSerializer

    def get_queryset(self):
        qs = super().get_queryset()

        # Filtrar por tenant (institución) del usuario staff
        tenant = getattr(self.request, 'tenant', None)
        if tenant:
            qs = qs.filter(institution=tenant)

        # Filtros
        status_filter = self.request.query_params.get('status')
        client_id = self.request.query_params.get('client_id')
        product_id = self.request.query_params.get('product_id')
        search = self.request.query_params.get('search')

        if status_filter:
            qs = qs.filter(status=status_filter.upper())
        if client_id:
            qs = qs.filter(client_id=client_id)
        if product_id:
            qs = qs.filter(product_id=product_id)
        if search:
            qs = qs.filter(
                db_models.Q(credit_number__icontains=search) |
                db_models.Q(client__first_name__icontains=search) |
                db_models.Q(client__last_name__icontains=search) |
                db_models.Q(client__document_number__icontains=search)
            )

        return qs

    @action(detail=False, methods=['post'], url_path='activate-from-contract')
    def activate_from_contract(self, request):
        """
        POST /api/loans/active-credits/activate-from-contract/
        Activa un crédito desde un contrato desembolsado.
        """
        serializer = ActivateFromContractSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        from api.contracts.models import Contract
        contract = get_object_or_404(Contract, pk=serializer.validated_data['contract_id'])

        try:
            active_credit = ActiveCreditService.activate_from_contract(
                contract=contract,
                user=request.user,
            )

            output = ActiveCreditSerializer(active_credit, context={'request': request})
            return Response(output.data, status=status.HTTP_201_CREATED)

        except ValueError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['get'], url_path='summary')
    def summary(self, request, pk=None):
        """
        GET /api/loans/active-credits/{id}/summary/
        Resumen financiero del crédito activo.
        """
        active_credit = self.get_object()
        data = ActiveCreditService.get_summary(active_credit)
        return Response(data)

    @action(detail=True, methods=['get'], url_path='schedule')
    def schedule(self, request, pk=None):
        """
        GET /api/loans/active-credits/{id}/schedule/
        Cronograma de cuotas.
        """
        active_credit = self.get_object()
        installments = active_credit.installments.order_by('installment_number')
        serializer = CreditInstallmentSerializer(installments, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['get'], url_path='payments')
    def payments(self, request, pk=None):
        """
        GET /api/loans/active-credits/{id}/payments/
        Historial de pagos del crédito.
        """
        active_credit = self.get_object()
        payments = active_credit.payments.order_by('-payment_date', '-created_at')
        serializer = CreditPaymentListSerializer(payments, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'], url_path='recalculate')
    def recalculate(self, request, pk=None):
        """
        POST /api/loans/active-credits/{id}/recalculate/
        Recalcular cronograma desde cuota actual (solo cuotas no pagadas).
        """
        active_credit = self.get_object()

        from_installment = request.data.get('from_installment_number', 1)

        AmortizationCalculationService.recalculate_schedule(
            active_credit,
            from_installment_number=from_installment,
        )

        installments = active_credit.installments.order_by('installment_number')
        serializer = CreditInstallmentSerializer(installments, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'], url_path='refresh-status')
    def refresh_status(self, request, pk=None):
        """
        POST /api/loans/active-credits/{id}/refresh-status/
        Refrescar el estado del crédito activo.
        """
        active_credit = self.get_object()
        old_status = active_credit.status
        new_status = CreditStatusService.refresh_status(active_credit)

        return Response({
            'credit_number': active_credit.credit_number,
            'previous_status': old_status,
            'new_status': new_status,
        })

    @action(detail=True, methods=['post'], url_path='grace-period')
    def grace_period(self, request, pk=None):
        """
        POST /api/loans/active-credits/{id}/grace-period/
        Aplicar período de gracia.
        """
        active_credit = self.get_object()

        serializer = ApplyGracePeriodSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            grace = GracePeriodService.apply_grace_period(
                active_credit=active_credit,
                grace_type=serializer.validated_data['grace_type'],
                start_date=serializer.validated_data['start_date'],
                end_date=serializer.validated_data['end_date'],
                reason=serializer.validated_data['reason'],
                user=request.user,
            )

            output = CreditGracePeriodSerializer(grace, context={'request': request})
            return Response(output.data, status=status.HTTP_201_CREATED)

        except ValueError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'], url_path='restructure')
    def restructure(self, request, pk=None):
        """
        POST /api/loans/active-credits/{id}/restructure/
        Reestructurar crédito. Si preview=true, solo simula.
        """
        active_credit = self.get_object()

        serializer = RestructureSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        is_preview = serializer.validated_data.pop('preview', False)

        if is_preview:
            preview = RestructuringService.preview_restructuring(
                active_credit,
                serializer.validated_data,
            )
            return Response(preview)

        try:
            restructuring = RestructuringService.apply_restructuring(
                active_credit=active_credit,
                new_terms=serializer.validated_data,
                reason=serializer.validated_data['reason'],
                user=request.user,
            )

            output = CreditRestructuringSerializer(restructuring, context={'request': request})
            return Response(output.data, status=status.HTTP_201_CREATED)

        except ValueError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['get'], url_path='status-history')
    def status_history(self, request, pk=None):
        """
        GET /api/loans/active-credits/{id}/status-history/
        Historial de cambios de estado.
        """
        active_credit = self.get_object()
        history = active_credit.status_history.order_by('-created_at')
        serializer = CreditStatusHistorySerializer(history, many=True)
        return Response(serializer.data)
