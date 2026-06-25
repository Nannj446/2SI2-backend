"""
Serializers para gestión de suscripciones SaaS.
"""

from rest_framework import serializers
from .models import SubscriptionPlan, Subscription, Invoice, Payment
from api.tenants.models import FinancialInstitution


class SubscriptionPlanSerializer(serializers.ModelSerializer):
    """Serializer completo para planes de suscripción."""
    
    price_per_month = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        read_only=True,
        source='get_price_per_month'
    )
    
    billing_cycle_display = serializers.CharField(
        source='get_billing_cycle_display',
        read_only=True
    )
    
    class Meta:
        model = SubscriptionPlan
        fields = [
            'id',
            'name',
            'slug',
            'description',
            'price',
            'price_per_month',
            'billing_cycle',
            'billing_cycle_display',
            'trial_days',
            'setup_fee',
            'max_users',
            'max_branches',
            'max_products',
            'max_loans_per_month',
            'max_storage_gb',
            'has_ai_scoring',
            'has_workflows',
            'has_reporting',
            'has_mobile_app',
            'has_api_access',
            'has_white_label',
            'has_priority_support',
            'has_custom_integrations',
            'is_active',
            'is_featured',
            'display_order',
            'features_list',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class SubscriptionPlanListSerializer(serializers.ModelSerializer):
    """Serializer simplificado para lista de planes."""
    
    price_per_month = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        read_only=True,
        source='get_price_per_month'
    )
    
    billing_cycle_display = serializers.CharField(
        source='get_billing_cycle_display',
        read_only=True
    )
    
    class Meta:
        model = SubscriptionPlan
        fields = [
            'id',
            'name',
            'slug',
            'description',
            'price',
            'price_per_month',
            'billing_cycle',
            'billing_cycle_display',
            'trial_days',
            'is_active',
            'is_featured',
            'display_order',
        ]


class CreateSubscriptionPlanSerializer(serializers.ModelSerializer):
    """Serializer para crear planes de suscripción."""
    
    class Meta:
        model = SubscriptionPlan
        fields = [
            'name',
            'slug',
            'description',
            'price',
            'billing_cycle',
            'trial_days',
            'setup_fee',
            'max_users',
            'max_branches',
            'max_products',
            'max_loans_per_month',
            'max_storage_gb',
            'has_ai_scoring',
            'has_workflows',
            'has_reporting',
            'has_mobile_app',
            'has_api_access',
            'has_white_label',
            'has_priority_support',
            'has_custom_integrations',
            'is_active',
            'is_featured',
            'display_order',
            'features_list',
        ]
    
    def validate_price(self, value):
        """Valida que el precio sea positivo."""
        if value < 0:
            raise serializers.ValidationError("El precio debe ser mayor o igual a 0")
        return value
    
    def validate_slug(self, value):
        """Valida que el slug sea único."""
        if SubscriptionPlan.objects.filter(slug=value).exists():
            raise serializers.ValidationError("Ya existe un plan con este slug")
        return value


class UpdateSubscriptionPlanSerializer(serializers.ModelSerializer):
    """Serializer para actualizar planes de suscripción."""
    
    class Meta:
        model = SubscriptionPlan
        fields = [
            'name',
            'description',
            'price',
            'billing_cycle',
            'trial_days',
            'setup_fee',
            'max_users',
            'max_branches',
            'max_products',
            'max_loans_per_month',
            'max_storage_gb',
            'has_ai_scoring',
            'has_workflows',
            'has_reporting',
            'has_mobile_app',
            'has_api_access',
            'has_white_label',
            'has_priority_support',
            'has_custom_integrations',
            'is_active',
            'is_featured',
            'display_order',
            'features_list',
        ]
    
    def validate_price(self, value):
        """Valida que el precio sea positivo."""
        if value < 0:
            raise serializers.ValidationError("El precio debe ser mayor o igual a 0")
        return value


class InstitutionBasicSerializer(serializers.ModelSerializer):
    """Serializer básico para institución en suscripciones."""
    
    class Meta:
        model = FinancialInstitution
        fields = ['id', 'name', 'slug']


class SubscriptionSerializer(serializers.ModelSerializer):
    """Serializer completo para suscripciones."""
    
    # Objetos completos para compatibilidad con frontend
    institution = InstitutionBasicSerializer(read_only=True)
    plan = SubscriptionPlanSerializer(read_only=True)
    pending_plan = SubscriptionPlanSerializer(read_only=True)
    
    status_display = serializers.CharField(
        source='get_status_display',
        read_only=True
    )
    
    payment_status_display = serializers.CharField(
        source='get_payment_status_display',
        read_only=True
    )
    
    usage_percentage = serializers.SerializerMethodField()
    is_within_limits = serializers.BooleanField(read_only=True)
    is_trial = serializers.SerializerMethodField()
    days_until_renewal = serializers.IntegerField(read_only=True, allow_null=True)
    
    # Campos adicionales para compatibilidad
    current_loans_this_month = serializers.IntegerField(
        source='current_month_loans',
        read_only=True
    )
    
    class Meta:
        model = Subscription
        fields = [
            'id',
            'institution',
            'plan',
            'pending_plan',
            'status',
            'status_display',
            'start_date',
            'end_date',
            'trial_end_date',
            'next_billing_date',
            'last_billing_date',
            'payment_status',
            'payment_status_display',
            'amount_due',
            'total_paid',
            'current_users',
            'current_branches',
            'current_products',
            'current_month_loans',
            'current_loans_this_month',
            'current_storage_gb',
            'usage_percentage',
            'is_within_limits',
            'is_trial',
            'days_until_renewal',
            'cancellation_reason',
            'cancel_at_period_end',
            'notes',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'id',
            'created_at',
            'updated_at',
            'total_paid',
        ]
    
    def get_usage_percentage(self, obj):
        """Obtiene el porcentaje de uso de los límites."""
        return obj.get_usage_percentage()
    
    def get_is_trial(self, obj):
        """Verifica si está en período de prueba."""
        return obj.is_trial()


class SubscriptionListSerializer(serializers.ModelSerializer):
    """Serializer simplificado para lista de suscripciones."""
    
    institution_name = serializers.CharField(
        source='institution.name',
        read_only=True
    )
    
    plan_name = serializers.CharField(
        source='plan.name',
        read_only=True
    )
    
    status_display = serializers.CharField(
        source='get_status_display',
        read_only=True
    )
    
    payment_status_display = serializers.CharField(
        source='get_payment_status_display',
        read_only=True
    )
    
    class Meta:
        model = Subscription
        fields = [
            'id',
            'institution',
            'institution_name',
            'plan',
            'plan_name',
            'status',
            'status_display',
            'payment_status',
            'payment_status_display',
            'start_date',
            'next_billing_date',
            'amount_due',
            'created_at',
        ]


class CreateSubscriptionSerializer(serializers.ModelSerializer):
    """Serializer para crear suscripciones."""
    
    class Meta:
        model = Subscription
        fields = [
            'institution',
            'plan',
            'start_date',
        ]
    
    def validate_institution(self, value):
        """Valida que la institución no tenga ya una suscripción activa."""
        if Subscription.objects.filter(
            institution=value,
            status__in=['TRIAL', 'ACTIVE']
        ).exists():
            raise serializers.ValidationError(
                "Esta institución ya tiene una suscripción activa"
            )
        return value
    
    def create(self, validated_data):
        """Crea la suscripción y activa el período de prueba."""
        subscription = Subscription.objects.create(**validated_data)
        subscription.activate_trial()
        return subscription


class UpdateSubscriptionSerializer(serializers.ModelSerializer):
    """Serializer para actualizar suscripciones."""
    
    class Meta:
        model = Subscription
        fields = [
            'plan',
            'status',
            'payment_status',
            'amount_due',
            'current_users',
            'current_branches',
            'current_products',
            'current_month_loans',
            'current_storage_gb',
            'notes',
        ]


class ActivateSubscriptionSerializer(serializers.Serializer):
    """Serializer para activar una suscripción después del trial."""
    
    payment_method = serializers.CharField(
        max_length=50,
        required=False,
        help_text='Método de pago utilizado'
    )
    
    transaction_id = serializers.CharField(
        max_length=100,
        required=False,
        help_text='ID de transacción del pago'
    )


class SuspendSubscriptionSerializer(serializers.Serializer):
    """Serializer para suspender una suscripción."""
    
    reason = serializers.CharField(
        required=True,
        help_text='Motivo de la suspensión'
    )


class CancelSubscriptionSerializer(serializers.Serializer):
    """Serializer para cancelar una suscripción."""

    reason = serializers.CharField(
        required=True,
        help_text='Motivo de la cancelación'
    )

    immediate = serializers.BooleanField(
        default=False,
        help_text='Cancelar inmediatamente o al final del período'
    )


class InvoiceSerializer(serializers.ModelSerializer):
    """Serializer para facturas."""

    status_display = serializers.CharField(
        source='get_status_display',
        read_only=True
    )

    class Meta:
        model = Invoice
        fields = [
            'id',
            'subscription',
            'stripe_invoice_id',
            'invoice_number',
            'amount',
            'currency',
            'status',
            'status_display',
            'invoice_pdf',
            'hosted_invoice_url',
            'due_date',
            'paid_at',
            'created_at',
        ]
        read_only_fields = ['id', 'created_at']


class PaymentSerializer(serializers.ModelSerializer):
    """Serializer para pagos."""

    status_display = serializers.CharField(
        source='get_status_display',
        read_only=True
    )

    class Meta:
        model = Payment
        fields = [
            'id',
            'subscription',
            'invoice',
            'stripe_payment_intent_id',
            'amount',
            'currency',
            'status',
            'status_display',
            'payment_method_type',
            'failure_reason',
            'created_at',
        ]
        read_only_fields = ['id', 'created_at']
