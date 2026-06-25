"""
Serializers para catálogos centralizados.
"""

from rest_framework import serializers
from api.loans.models_catalogs import (
    DocumentType,
    ProductType,
    PaymentFrequency,
    AmortizationSystem,
    Currency
)


class DocumentTypeSerializer(serializers.ModelSerializer):
    """Serializer para tipos de documento."""
    
    class Meta:
        model = DocumentType
        fields = [
            'id', 'code', 'name', 'description', 'category',
            'default_formats', 'default_max_size_mb', 'default_validity_days',
            'is_active', 'display_order', 'icon',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def validate_code(self, value):
        """Validar que el código sea único por tenant."""
        request = self.context.get('request')
        if request and hasattr(request, 'user'):
            institution = request.user.institution
            queryset = DocumentType.objects.filter(
                institution=institution,
                code=value
            )
            if self.instance:
                queryset = queryset.exclude(pk=self.instance.pk)
            if queryset.exists():
                raise serializers.ValidationError(
                    f"Ya existe un tipo de documento con el código '{value}'"
                )
        return value.upper()


class ProductTypeSerializer(serializers.ModelSerializer):
    """Serializer para tipos de producto."""
    
    class Meta:
        model = ProductType
        fields = [
            'id', 'code', 'name', 'description', 'category',
            'icon', 'color', 'is_active', 'display_order',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def validate_code(self, value):
        """Validar que el código sea único por tenant."""
        request = self.context.get('request')
        if request and hasattr(request, 'user'):
            institution = request.user.institution
            queryset = ProductType.objects.filter(
                institution=institution,
                code=value
            )
            if self.instance:
                queryset = queryset.exclude(pk=self.instance.pk)
            if queryset.exists():
                raise serializers.ValidationError(
                    f"Ya existe un tipo de producto con el código '{value}'"
                )
        return value.upper()


class PaymentFrequencySerializer(serializers.ModelSerializer):
    """Serializer para frecuencias de pago."""
    
    class Meta:
        model = PaymentFrequency
        fields = [
            'id', 'code', 'name', 'days_between_payments',
            'payments_per_year', 'is_active', 'display_order',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def validate(self, data):
        """Validar consistencia entre días y pagos por año."""
        days = data.get('days_between_payments')
        payments = data.get('payments_per_year')
        
        if days and payments:
            # Validar que la relación sea aproximadamente correcta
            expected_payments = 365 / days
            if abs(expected_payments - payments) > 2:
                raise serializers.ValidationError({
                    'payments_per_year': f'Con {days} días entre pagos, se esperan aproximadamente {int(expected_payments)} pagos por año'
                })
        
        return data


class AmortizationSystemSerializer(serializers.ModelSerializer):
    """Serializer para sistemas de amortización."""
    
    class Meta:
        model = AmortizationSystem
        fields = [
            'id', 'code', 'name', 'description', 'formula_type',
            'is_active', 'display_order',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class CurrencySerializer(serializers.ModelSerializer):
    """Serializer para monedas."""
    
    class Meta:
        model = Currency
        fields = [
            'id', 'code', 'name', 'symbol', 'exchange_rate_to_base',
            'is_base_currency', 'is_active', 'display_order',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def validate(self, data):
        """Validar que solo haya una moneda base por tenant."""
        if data.get('is_base_currency'):
            request = self.context.get('request')
            if request and hasattr(request, 'user'):
                institution = request.user.institution
                queryset = Currency.objects.filter(
                    institution=institution,
                    is_base_currency=True
                )
                if self.instance:
                    queryset = queryset.exclude(pk=self.instance.pk)
                if queryset.exists():
                    raise serializers.ValidationError({
                        'is_base_currency': 'Ya existe una moneda base. Desactiva la actual primero.'
                    })
        
        return data
