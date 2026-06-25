"""
ViewSets para catálogos centralizados.
"""

from rest_framework import viewsets, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.exceptions import ValidationError

from api.loans.models_catalogs import (
    DocumentType,
    ProductType,
    PaymentFrequency,
    AmortizationSystem,
    Currency
)
from api.loans.serializers.catalog_serializers import (
    DocumentTypeSerializer,
    ProductTypeSerializer,
    PaymentFrequencySerializer,
    AmortizationSystemSerializer,
    CurrencySerializer
)


class CatalogViewSetMixin:
    """Mixin para ViewSets de catálogos que necesitan filtrar por institución."""
    
    def get_user_institution(self):
        """Obtiene la institución del usuario autenticado."""
        membership = self.request.user.institution_memberships.filter(is_active=True).first()
        if not membership:
            raise ValidationError('El usuario no tiene una institución activa asignada')
        return membership.institution


class DocumentTypeViewSet(CatalogViewSetMixin, viewsets.ModelViewSet):
    """
    ViewSet para tipos de documento.
    
    Permite gestionar el catálogo de tipos de documentos que pueden
    ser requeridos en solicitudes de crédito.
    """
    
    serializer_class = DocumentTypeSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['category', 'is_active']
    search_fields = ['code', 'name', 'description']
    ordering_fields = ['display_order', 'name', 'created_at']
    ordering = ['display_order', 'name']
    
    def get_queryset(self):
        return DocumentType.objects.filter(
            institution=self.get_user_institution()
        )
    
    def perform_create(self, serializer):
        serializer.save(institution=self.get_user_institution())
    
    @action(detail=False, methods=['get'])
    def active(self, request):
        """Obtener solo tipos de documento activos."""
        queryset = self.get_queryset().filter(is_active=True)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)


class ProductTypeViewSet(CatalogViewSetMixin, viewsets.ModelViewSet):
    """
    ViewSet para tipos de producto.
    
    Permite gestionar el catálogo de tipos de productos crediticios.
    """
    
    serializer_class = ProductTypeSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['category', 'is_active']
    search_fields = ['code', 'name', 'description']
    ordering_fields = ['display_order', 'name', 'created_at']
    ordering = ['display_order', 'name']
    
    def get_queryset(self):
        return ProductType.objects.filter(
            institution=self.get_user_institution()
        )
    
    def perform_create(self, serializer):
        serializer.save(institution=self.get_user_institution())
    
    @action(detail=False, methods=['get'])
    def active(self, request):
        """Obtener solo tipos de producto activos."""
        queryset = self.get_queryset().filter(is_active=True)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)


class PaymentFrequencyViewSet(CatalogViewSetMixin, viewsets.ModelViewSet):
    """
    ViewSet para frecuencias de pago.
    
    Permite gestionar el catálogo de frecuencias de pago disponibles.
    """
    
    serializer_class = PaymentFrequencySerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['code', 'name']
    ordering_fields = ['display_order', 'name']
    ordering = ['display_order']
    
    def get_queryset(self):
        return PaymentFrequency.objects.filter(
            institution=self.get_user_institution()
        )
    
    def perform_create(self, serializer):
        serializer.save(institution=self.get_user_institution())
    
    @action(detail=False, methods=['get'])
    def active(self, request):
        """Obtener solo frecuencias activas."""
        queryset = self.get_queryset().filter(is_active=True)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)


class AmortizationSystemViewSet(CatalogViewSetMixin, viewsets.ModelViewSet):
    """
    ViewSet para sistemas de amortización.
    
    Permite gestionar el catálogo de sistemas de amortización disponibles.
    """
    
    serializer_class = AmortizationSystemSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['code', 'name', 'description']
    ordering_fields = ['display_order', 'name']
    ordering = ['display_order']
    
    def get_queryset(self):
        return AmortizationSystem.objects.filter(
            institution=self.get_user_institution()
        )
    
    def perform_create(self, serializer):
        serializer.save(institution=self.get_user_institution())
    
    @action(detail=False, methods=['get'])
    def active(self, request):
        """Obtener solo sistemas activos."""
        queryset = self.get_queryset().filter(is_active=True)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)


class CurrencyViewSet(CatalogViewSetMixin, viewsets.ModelViewSet):
    """
    ViewSet para monedas.
    
    Permite gestionar el catálogo de monedas disponibles.
    """
    
    serializer_class = CurrencySerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['code', 'name']
    ordering_fields = ['display_order', 'name']
    ordering = ['display_order']
    
    def get_queryset(self):
        return Currency.objects.filter(
            institution=self.get_user_institution()
        )
    
    def perform_create(self, serializer):
        serializer.save(institution=self.get_user_institution())
    
    @action(detail=False, methods=['get'])
    def active(self, request):
        """Obtener solo monedas activas."""
        queryset = self.get_queryset().filter(is_active=True)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def base(self, request):
        """Obtener la moneda base del tenant."""
        try:
            currency = self.get_queryset().get(is_base_currency=True)
            serializer = self.get_serializer(currency)
            return Response(serializer.data)
        except Currency.DoesNotExist:
            return Response(
                {'detail': 'No se ha configurado una moneda base'},
                status=status.HTTP_404_NOT_FOUND
            )
