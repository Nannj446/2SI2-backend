"""
Views para Gestión de Seguros con filtrado explícito por tenant.
"""
from decimal import Decimal

from django.db.models import Count, Sum
from rest_framework import generics, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema, extend_schema_view

from .models import (
    Insurer, Insurance, InsuranceCoverage,
    ProductInsurance, CreditInsurance
)
from .permissions import (
    CanManageInsuranceCatalog, CanViewInsurance,
    CanAssociateInsuranceToCredit, CanManageProductInsurance
)
from .serializers import (
    InsurerSerializer, InsurerListSerializer,
    InsuranceSerializer, InsuranceListSerializer, CreateInsuranceSerializer,
    InsuranceCoverageSerializer,
    ProductInsuranceSerializer, ProductInsuranceListSerializer, CreateProductInsuranceSerializer,
    CreditInsuranceSerializer, CreditInsuranceListSerializer,
    CreateCreditInsuranceSerializer, UpdateCreditInsuranceSerializer,
    PremiumCalculationSerializer, PremiumCalculationResponseSerializer
)
from .services import InsuranceService, InsuranceCalculationService, CreditInsuranceService


def get_tenant_filter(self):
    """
    Obtiene el filtro de tenant según el tipo de usuario.
    Superadmin (saas_admin) ve todos, usuarios de tenant ven solo los suyos.
    """
    if hasattr(self, 'request') and hasattr(self.request, 'tenant'):
        if self.request.tenant is not None:
            return self.request.tenant.id
    return None


@extend_schema_view(
    list=extend_schema(description='Listar todas las aseguradoras del tenant'),
    retrieve=extend_schema(description='Obtener detalle de aseguradora'),
    create=extend_schema(description='Crear nueva aseguradora'),
    update=extend_schema(description='Actualizar aseguradora'),
    partial_update=extend_schema(description='Actualizar parcialmente aseguradora'),
    destroy=extend_schema(description='Desactivar aseguradora')
)
class InsurerViewSet(viewsets.ModelViewSet):
    """
    ViewSet para gestionar aseguradoras.
    """
    permission_classes = [CanManageInsuranceCatalog]

    def get_serializer_class(self):
        if self.action == 'list':
            return InsurerListSerializer
        return InsurerSerializer

    def get_queryset(self):
        tenant_id = get_tenant_filter(self)
        if tenant_id is not None:
            queryset = Insurer.objects.filter(institution_id=tenant_id, is_active=True)
        else:
            queryset = Insurer.objects.filter(is_active=True)

        if self.action == 'list':
            queryset = queryset.annotate(insurance_count=Count('insurances'))
        return queryset

    def perform_create(self, serializer):
        tenant_id = get_tenant_filter(self)
        if tenant_id is not None:
            serializer.save(institution_id=tenant_id)
        else:
            serializer.save()

    def perform_destroy(self, instance):
        instance.is_active = False
        instance.save()


@extend_schema_view(
    list=extend_schema(description='Listar todos los seguros del tenant'),
    retrieve=extend_schema(description='Obtener detalle de seguro'),
    create=extend_schema(description='Crear nuevo seguro'),
    update=extend_schema(description='Actualizar seguro'),
    partial_update=extend_schema(description='Actualizar parcialmente seguro'),
    destroy=extend_schema(description='Desactivar seguro')
)
class InsuranceViewSet(viewsets.ModelViewSet):
    """
    ViewSet para gestionar el catálogo de seguros.
    """
    permission_classes = [CanManageInsuranceCatalog]

    def get_serializer_class(self):
        if self.action == 'list':
            return InsuranceListSerializer
        if self.action in ['create', 'update', 'partial_update']:
            return CreateInsuranceSerializer
        return InsuranceSerializer

    def get_queryset(self):
        tenant_id = get_tenant_filter(self)
        if tenant_id is not None:
            queryset = Insurance.objects.filter(institution_id=tenant_id, is_active=True)
        else:
            queryset = Insurance.objects.filter(is_active=True)

        if self.action == 'list':
            queryset = queryset.select_related('insurer')
        else:
            queryset = queryset.prefetch_related('coverages')
        return queryset

    def perform_create(self, serializer):
        tenant_id = get_tenant_filter(self)
        if tenant_id is not None:
            serializer.save(institution_id=tenant_id)
        else:
            serializer.save()

    def perform_destroy(self, instance):
        instance.is_active = False
        instance.save()

    @extend_schema(
        request=PremiumCalculationSerializer,
        responses={200: PremiumCalculationResponseSerializer},
        description='Calcular prima de seguro'
    )
    @action(detail=False, methods=['post'])
    def calculate_premium(self, request):
        """Calcular prima de seguro."""
        serializer = PremiumCalculationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        insurance_id = serializer.validated_data['insurance_id']
        loan_amount = serializer.validated_data['loan_amount']
        loan_term_months = serializer.validated_data['loan_term_months']
        balance = serializer.validated_data.get('balance')

        tenant_id = get_tenant_filter(self)
        if tenant_id is not None:
            try:
                insurance = Insurance.objects.get(
                    id=insurance_id,
                    institution_id=tenant_id,
                    is_active=True
                )
            except Insurance.DoesNotExist:
                return Response(
                    {'error': 'Seguro no encontrado'},
                    status=status.HTTP_404_NOT_FOUND
                )
        else:
            try:
                insurance = Insurance.objects.get(id=insurance_id, is_active=True)
            except Insurance.DoesNotExist:
                return Response(
                    {'error': 'Seguro no encontrado'},
                    status=status.HTTP_404_NOT_FOUND
                )

        result = InsuranceCalculationService.calculate_premium(
            insurance, loan_amount, loan_term_months, balance
        )

        return Response(result)


@extend_schema_view(
    list=extend_schema(description='Listar coberturas de un seguro'),
    retrieve=extend_schema(description='Obtener detalle de cobertura'),
    create=extend_schema(description='Crear nueva cobertura'),
    update=extend_schema(description='Actualizar cobertura'),
    partial_update=extend_schema(description='Actualizar parcialmente cobertura'),
    destroy=extend_schema(description='Eliminar cobertura')
)
class InsuranceCoverageViewSet(viewsets.ModelViewSet):
    """
    ViewSet para gestionar coberturas de seguros.
    """
    queryset = InsuranceCoverage.objects.all()
    serializer_class = InsuranceCoverageSerializer
    permission_classes = [CanManageInsuranceCatalog]

    def get_queryset(self):
        insurance_id = self.kwargs.get('insurance_pk')
        tenant_id = get_tenant_filter(self)

        if insurance_id:
            base_qs = InsuranceCoverage.objects.filter(insurance_id=insurance_id)
        else:
            base_qs = InsuranceCoverage.objects.all()

        if tenant_id is not None:
            base_qs = base_qs.filter(institution_id=tenant_id)

        return base_qs

    def perform_create(self, serializer):
        insurance_id = self.kwargs.get('insurance_pk')
        tenant_id = get_tenant_filter(self)

        if insurance_id and tenant_id is not None:
            insurance = Insurance.objects.get(id=insurance_id, institution_id=tenant_id)
            serializer.save(institution=insurance.institution, insurance=insurance)
        elif insurance_id:
            insurance = Insurance.objects.get(id=insurance_id)
            serializer.save(institution=insurance.institution, insurance=insurance)
        else:
            serializer.save()


class ProductInsuranceListView(generics.ListCreateAPIView):
    """
    Listar y asociar seguros a un producto crediticio.
    """
    serializer_class = ProductInsuranceSerializer
    permission_classes = [CanManageProductInsurance]

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return CreateProductInsuranceSerializer
        return ProductInsuranceListSerializer

    def get_queryset(self):
        product_id = self.kwargs.get('product_pk')
        tenant_id = get_tenant_filter(self)

        queryset = ProductInsurance.objects.filter(product_id=product_id)

        if tenant_id is not None:
            queryset = queryset.filter(institution_id=tenant_id)

        return queryset.select_related('insurance', 'insurance__insurer')

    def perform_create(self, serializer):
        from api.products.models import CreditProduct
        product_id = self.kwargs.get('product_pk')
        tenant_id = get_tenant_filter(self)

        product = CreditProduct.objects.get(id=product_id)
        if tenant_id is not None:
            serializer.save(product=product, institution_id=tenant_id)
        else:
            serializer.save(product=product, institution=product.institution)


class ProductInsuranceDetailView(generics.RetrieveDestroyAPIView):
    """
    Obtener o eliminar asociación seguro-producto.
    """
    serializer_class = ProductInsuranceSerializer
    permission_classes = [CanManageProductInsurance]
    lookup_url_kwarg = 'insurance_pk'

    def get_queryset(self):
        product_id = self.kwargs.get('product_pk')
        tenant_id = get_tenant_filter(self)

        queryset = ProductInsurance.objects.filter(product_id=product_id)

        if tenant_id is not None:
            queryset = queryset.filter(institution_id=tenant_id)

        return queryset


class ProductInsuranceCalculateView(APIView):
    """
    Calcular total de primas para un producto crediticio.
    """
    permission_classes = [CanViewInsurance]

    @extend_schema(
        parameters=[{
            'name': 'loan_amount',
            'in': 'query',
            'schema': {'type': 'number'}
        }, {
            'name': 'loan_term_months',
            'in': 'query',
            'schema': {'type': 'integer'}
        }, {
            'name': 'balance',
            'in': 'query',
            'schema': {'type': 'number', 'required': False}
        }],
        responses={200: PremiumCalculationResponseSerializer},
        description='Calcular primas de todos los seguros del producto'
    )
    def get(self, request, product_pk):
        from api.products.models import CreditProduct

        tenant_id = get_tenant_filter(self)

        try:
            if tenant_id is not None:
                product = CreditProduct.objects.get(id=product_pk, institution_id=tenant_id)
            else:
                product = CreditProduct.objects.get(id=product_pk)
        except CreditProduct.DoesNotExist:
            return Response(
                {'error': 'Producto no encontrado'},
                status=status.HTTP_404_NOT_FOUND
            )

        loan_amount = request.query_params.get('loan_amount')
        loan_term_months = request.query_params.get('loan_term_months')
        balance = request.query_params.get('balance')

        if not loan_amount or not loan_term_months:
            return Response(
                {'error': 'loan_amount y loan_term_months son requeridos'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            loan_amount = Decimal(loan_amount)
            loan_term_months = int(loan_term_months)
            balance = Decimal(balance) if balance else None
        except (ValueError, TypeError):
            return Response(
                {'error': 'Parámetros inválidos'},
                status=status.HTTP_400_BAD_REQUEST
            )

        result = InsuranceCalculationService.calculate_total_premiums(
            product, loan_amount, loan_term_months, balance
        )

        return Response(result)


@extend_schema_view(
    list=extend_schema(description='Listar seguros de un crédito'),
    retrieve=extend_schema(description='Obtener detalle de seguro del crédito'),
    create=extend_schema(description='Registrar seguro para crédito'),
    update=extend_schema(description='Actualizar seguro del crédito'),
    partial_update=extend_schema(description='Actualizar parcialmente seguro del crédito'),
    destroy=extend_schema(description='Eliminar seguro del crédito')
)
class CreditInsuranceViewSet(viewsets.ModelViewSet):
    """
    ViewSet para gestionar seguros asociados a créditos activos.
    """
    permission_classes = [CanAssociateInsuranceToCredit]

    def get_serializer_class(self):
        if self.action == 'list':
            return CreditInsuranceListSerializer
        if self.action == 'create':
            return CreateCreditInsuranceSerializer
        if self.action in ['update', 'partial_update']:
            return UpdateCreditInsuranceSerializer
        return CreditInsuranceSerializer

    def get_queryset(self):
        credit_id = self.kwargs.get('credit_pk')
        tenant_id = get_tenant_filter(self)

        queryset = CreditInsurance.objects.filter(active_credit_id=credit_id)

        if tenant_id is not None:
            queryset = queryset.filter(institution_id=tenant_id)

        return queryset.select_related('insurance', 'insurance__insurer', 'active_credit')

    def perform_create(self, serializer):
        from api.loans.models import ActiveCredit
        credit_id = self.kwargs.get('credit_pk')
        tenant_id = get_tenant_filter(self)

        credit = ActiveCredit.objects.get(id=credit_id)
        if tenant_id is not None:
            serializer.save(active_credit=credit, institution_id=tenant_id)
        else:
            serializer.save(active_credit=credit, institution=credit.institution)

    @extend_schema(
        request=None,
        responses={200: CreditInsuranceSerializer},
        description='Marcar seguro como próximo a vencer'
    )
    @action(detail=True, methods=['post'])
    def mark_expiring(self, request, credit_pk=None, pk=None):
        """Marcar seguro como por vencer."""
        credit_insurance = self.get_object()
        CreditInsuranceService.update_insurance_status(
            credit_insurance,
            'EXPIRING_SOON'
        )
        serializer = CreditInsuranceSerializer(credit_insurance)
        return Response(serializer.data)

    @extend_schema(
        request=None,
        responses={200: CreditInsuranceSerializer},
        description='Suspender seguro'
    )
    @action(detail=True, methods=['post'])
    def suspend(self, request, credit_pk=None, pk=None):
        """Suspender seguro."""
        credit_insurance = self.get_object()
        CreditInsuranceService.update_insurance_status(
            credit_insurance,
            'SUSPENDED'
        )
        serializer = CreditInsuranceSerializer(credit_insurance)
        return Response(serializer.data)

    @extend_schema(
        request=None,
        responses={200: CreditInsuranceSerializer},
        description='Cancelar seguro'
    )
    @action(detail=True, methods=['post'])
    def cancel(self, request, credit_pk=None, pk=None):
        """Cancelar seguro."""
        credit_insurance = self.get_object()
        CreditInsuranceService.update_insurance_status(
            credit_insurance,
            'CANCELLED'
        )
        serializer = CreditInsuranceSerializer(credit_insurance)
        return Response(serializer.data)


class CreditInsuranceSummaryView(APIView):
    """
    Resumen de seguros de un crédito.
    """
    permission_classes = [CanViewInsurance]

    @extend_schema(
        responses={200: {
            'type': 'object',
            'properties': {
                'total_insurances': {'type': 'integer'},
                'active_insurances': {'type': 'integer'},
                'expiring_soon': {'type': 'integer'},
                'expired': {'type': 'integer'},
                'total_premium': {'type': 'number'},
                'total_paid': {'type': 'number'}
            }
        }},
        description='Obtener resumen de seguros del crédito'
    )
    def get(self, request, credit_pk):
        from api.loans.models import ActiveCredit

        tenant_id = get_tenant_filter(self)

        try:
            if tenant_id is not None:
                credit = ActiveCredit.objects.get(id=credit_pk, institution_id=tenant_id)
            else:
                credit = ActiveCredit.objects.get(id=credit_pk)
        except ActiveCredit.DoesNotExist:
            return Response(
                {'error': 'Crédito no encontrado'},
                status=status.HTTP_404_NOT_FOUND
            )

        insurances = CreditInsurance.objects.filter(active_credit=credit)

        if tenant_id is not None:
            insurances = insurances.filter(institution_id=tenant_id)

        active = insurances.filter(
            status__in=['ACTIVE', 'EXPIRING_SOON']
        ).count()
        expiring = insurances.filter(status='EXPIRING_SOON').count()
        expired = insurances.filter(status='EXPIRED').count()

        return Response({
            'total_insurances': insurances.count(),
            'active_insurances': active,
            'expiring_soon': expiring,
            'expired': expired,
            'total_premium': insurances.aggregate(total=Sum('total_premium'))['total'] or 0,
            'total_paid': insurances.aggregate(total=Sum('premium_paid'))['total'] or 0
        })


class CreditInsuranceMarkExpiringView(APIView):
    """Marcar seguro como por vencer."""
    permission_classes = [CanAssociateInsuranceToCredit]

    @extend_schema(
        responses={200: CreditInsuranceSerializer},
        description='Marcar seguro como próximo a vencer'
    )
    def post(self, request, credit_pk, pk):
        tenant_id = get_tenant_filter(self)

        try:
            if tenant_id is not None:
                credit_insurance = CreditInsurance.objects.get(
                    pk=pk,
                    active_credit_id=credit_pk,
                    institution_id=tenant_id
                )
            else:
                credit_insurance = CreditInsurance.objects.get(
                    pk=pk,
                    active_credit_id=credit_pk
                )
        except CreditInsurance.DoesNotExist:
            return Response(
                {'error': 'Seguro no encontrado'},
                status=status.HTTP_404_NOT_FOUND
            )

        CreditInsuranceService.update_insurance_status(
            credit_insurance,
            'EXPIRING_SOON'
        )
        serializer = CreditInsuranceSerializer(credit_insurance)
        return Response(serializer.data)


class CreditInsuranceSuspendView(APIView):
    """Suspender seguro."""
    permission_classes = [CanAssociateInsuranceToCredit]

    @extend_schema(
        responses={200: CreditInsuranceSerializer},
        description='Suspender seguro'
    )
    def post(self, request, credit_pk, pk):
        tenant_id = get_tenant_filter(self)

        try:
            if tenant_id is not None:
                credit_insurance = CreditInsurance.objects.get(
                    pk=pk,
                    active_credit_id=credit_pk,
                    institution_id=tenant_id
                )
            else:
                credit_insurance = CreditInsurance.objects.get(
                    pk=pk,
                    active_credit_id=credit_pk
                )
        except CreditInsurance.DoesNotExist:
            return Response(
                {'error': 'Seguro no encontrado'},
                status=status.HTTP_404_NOT_FOUND
            )

        CreditInsuranceService.update_insurance_status(
            credit_insurance,
            'SUSPENDED'
        )
        serializer = CreditInsuranceSerializer(credit_insurance)
        return Response(serializer.data)


class CreditInsuranceCancelView(APIView):
    """Cancelar seguro."""
    permission_classes = [CanAssociateInsuranceToCredit]

    @extend_schema(
        responses={200: CreditInsuranceSerializer},
        description='Cancelar seguro'
    )
    def post(self, request, credit_pk, pk):
        tenant_id = get_tenant_filter(self)

        try:
            if tenant_id is not None:
                credit_insurance = CreditInsurance.objects.get(
                    pk=pk,
                    active_credit_id=credit_pk,
                    institution_id=tenant_id
                )
            else:
                credit_insurance = CreditInsurance.objects.get(
                    pk=pk,
                    active_credit_id=credit_pk
                )
        except CreditInsurance.DoesNotExist:
            return Response(
                {'error': 'Seguro no encontrado'},
                status=status.HTTP_404_NOT_FOUND
            )

        CreditInsuranceService.update_insurance_status(
            credit_insurance,
            'CANCELLED'
        )
        serializer = CreditInsuranceSerializer(credit_insurance)
        return Response(serializer.data)
