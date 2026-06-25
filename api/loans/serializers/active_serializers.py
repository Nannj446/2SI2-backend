"""
Serializers para SP3: Créditos Activos y Pagos.

Incluye serializers de lectura (detail/list) y escritura (create/update)
para todos los modelos del dominio de créditos activos.
"""

from rest_framework import serializers
from api.loans.models_active import (
    ActiveCredit,
    CreditInstallment,
    CreditPayment,
    CreditPaymentAllocation,
    CreditGracePeriod,
    CreditRestructuring,
    CreditStatusHistory,
    CreditSupportRequest,
)


# ─── CreditInstallment ───────────────────────────────────────────

class CreditInstallmentSerializer(serializers.ModelSerializer):
    """Serializer de lectura para cuotas."""
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = CreditInstallment
        fields = [
            'id', 'installment_number', 'due_date', 'paid_at',
            'days_overdue', 'opening_balance', 'principal_amount',
            'interest_amount', 'insurance_amount', 'fee_amount',
            'penalty_amount', 'total_amount', 'paid_amount',
            'closing_balance', 'status', 'status_display',
            'original_due_date', 'restructuring', 'metadata',
            'insurance_detail', 'created_at',
        ]
        read_only_fields = fields


class CreditInstallmentListSerializer(serializers.ModelSerializer):
    """Serializer simplificado para listas de cuotas."""
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = CreditInstallment
        fields = [
            'id', 'installment_number', 'due_date', 'total_amount',
            'paid_amount', 'status', 'status_display', 'days_overdue',
        ]


# ─── CreditPaymentAllocation ─────────────────────────────────────

class CreditPaymentAllocationSerializer(serializers.ModelSerializer):
    installment_number = serializers.IntegerField(source='installment.installment_number', read_only=True)

    class Meta:
        model = CreditPaymentAllocation
        fields = [
            'id', 'installment', 'installment_number', 'amount_applied',
            'principal_covered', 'interest_covered', 'insurance_covered',
            'fee_covered', 'penalty_covered',
        ]


# ─── CreditPayment ───────────────────────────────────────────────

# Mapping de método de pago → display
PAYMENT_METHOD_DISPLAY = {
    'CASH': 'Efectivo',
    'TRANSFER': 'Transferencia',
    'QR': 'Código QR',
    'CARD': 'Tarjeta',
    'DEBIT_CARD': 'Tarjeta de Débito',
    'CREDIT_CARD': 'Tarjeta de Crédito',
    'ONLINE': 'En Línea',
    'STRIPE': 'Stripe',
    'BANK_TRANSFER': 'Transferencia Bancaria',
}


class CreditPaymentSerializer(serializers.ModelSerializer):
    """Serializer completo de lectura para pagos."""
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    channel_display = serializers.CharField(source='get_channel_display', read_only=True)
    method_display = serializers.SerializerMethodField()
    currency_code = serializers.CharField(source='currency.code', read_only=True)
    registered_by_name = serializers.SerializerMethodField()
    confirmed_by_name = serializers.SerializerMethodField()
    allocations = CreditPaymentAllocationSerializer(many=True, read_only=True)
    credit_number = serializers.CharField(source='active_credit.credit_number', read_only=True)
    invoice_url = serializers.SerializerMethodField()
    invoice_pdf_url = serializers.SerializerMethodField()
    invoice_number = serializers.SerializerMethodField()

    class Meta:
        model = CreditPayment
        fields = [
            'id', 'active_credit', 'credit_number', 'amount', 'currency',
            'currency_code', 'payment_date', 'confirmed_at',
            'channel', 'channel_display', 'method', 'method_display',
            'reference_number', 'provider', 'provider_payment_id',
            'provider_event_id', 'status', 'status_display',
            'registered_by', 'registered_by_name', 'confirmed_by',
            'confirmed_by_name', 'receipt_file', 'notes', 'metadata',
            'allocations', 'invoice_url', 'invoice_pdf_url',
            'invoice_number', 'created_at',
        ]
        read_only_fields = fields

    def get_method_display(self, obj):
        return PAYMENT_METHOD_DISPLAY.get(obj.method, obj.method)

    def get_invoice_url(self, obj):
        url = obj.metadata.get('stripe_invoice_url') or obj.metadata.get('stripe_receipt_url')
        return url

    def get_invoice_pdf_url(self, obj):
        return obj.metadata.get('stripe_invoice_pdf')

    def get_invoice_number(self, obj):
        return obj.metadata.get('stripe_invoice_number')

    def get_registered_by_name(self, obj):
        if obj.registered_by:
            return obj.registered_by.get_full_name() or obj.registered_by.email
        return None

    def get_confirmed_by_name(self, obj):
        if obj.confirmed_by:
            return obj.confirmed_by.get_full_name() or obj.confirmed_by.email
        return None


class CreditPaymentListSerializer(serializers.ModelSerializer):
    """Serializer simplificado para listas de pagos."""
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    channel_display = serializers.CharField(source='get_channel_display', read_only=True)
    method_display = serializers.SerializerMethodField()
    currency_code = serializers.CharField(source='currency.code', read_only=True)
    credit_number = serializers.CharField(source='active_credit.credit_number', read_only=True)
    registered_by_name = serializers.SerializerMethodField()

    class Meta:
        model = CreditPayment
        fields = [
            'id', 'active_credit', 'credit_number', 'amount',
            'currency_code', 'payment_date', 'channel', 'channel_display',
            'method', 'method_display', 'reference_number',
            'status', 'status_display', 'registered_by_name',
            'notes', 'created_at',
        ]

    def get_method_display(self, obj):
        return PAYMENT_METHOD_DISPLAY.get(obj.method, obj.method)

    def get_registered_by_name(self, obj):
        if obj.registered_by:
            return obj.registered_by.get_full_name() or obj.registered_by.email
        return None


class CreatePaymentSerializer(serializers.ModelSerializer):
    """Serializer para registrar un pago (presencial u online)."""

    class Meta:
        model = CreditPayment
        fields = [
            'active_credit', 'amount', 'currency', 'payment_date',
            'channel', 'method', 'reference_number', 'provider',
            'provider_payment_id', 'provider_event_id',
            'receipt_file', 'notes', 'metadata',
        ]

    def validate_amount(self, value):
        from decimal import Decimal
        if value <= Decimal('0'):
            raise serializers.ValidationError("El monto debe ser mayor a cero.")
        return value

    def validate(self, data):
        # Presencial requiere reference_number
        if data.get('channel') == CreditPayment.Channel.PRESENTIAL:
            if not data.get('reference_number'):
                data['reference_number'] = f"PRES-{data['active_credit'].credit_number}"
        return data

    def create(self, validated_data):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            validated_data['registered_by'] = request.user
        validated_data['status'] = CreditPayment.Status.PENDING_CONFIRMATION
        validated_data['institution'] = validated_data['active_credit'].institution
        return super().create(validated_data)


class ConfirmPaymentSerializer(serializers.Serializer):
    """Serializer para confirmar un pago."""
    confirmed_by = serializers.IntegerField(required=False)
    notes = serializers.CharField(required=False, allow_blank=True)


class StartOnlinePaymentSerializer(serializers.Serializer):
    """Serializer para iniciar un pago online."""
    installment_id = serializers.IntegerField(required=True)
    amount = serializers.DecimalField(required=False, max_digits=12, decimal_places=2)


# ─── ActiveCredit ────────────────────────────────────────────────

class ActiveCreditSerializer(serializers.ModelSerializer):
    """Serializer completo de lectura para crédito activo."""
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    client_name = serializers.SerializerMethodField()
    product_name = serializers.CharField(source='product.name', read_only=True)
    currency_code = serializers.CharField(source='currency.code', read_only=True)
    payment_frequency_name = serializers.CharField(source='payment_frequency.name', read_only=True)
    amortization_system_name = serializers.CharField(source='amortization_system.name', read_only=True)
    application_number = serializers.CharField(
        source='loan_application.application_number', read_only=True
    )
    contract_number = serializers.SerializerMethodField()
    installments = CreditInstallmentSerializer(many=True, read_only=True)
    recent_payments = serializers.SerializerMethodField()

    class Meta:
        model = ActiveCredit
        fields = [
            'id', 'credit_number', 'loan_application', 'application_number',
            'contract', 'contract_number', 'client', 'client_name',
            'product', 'product_name', 'approved_amount', 'currency',
            'currency_code', 'annual_interest_rate', 'term_periods',
            'payment_frequency', 'payment_frequency_name',
            'amortization_system', 'amortization_system_name',
            'disbursement_date', 'first_payment_date', 'maturity_date',
            'next_due_date', 'current_balance', 'total_paid',
            'principal_paid', 'interest_paid', 'fees_paid', 'penalty_paid',
            'status', 'status_display', 'days_in_arrears',
            'notes', 'metadata', 'installments', 'recent_payments',
            'created_at', 'updated_at',
        ]
        read_only_fields = [f for f in fields if f not in ('notes',)]

    def get_client_name(self, obj):
        if obj.client:
            return str(obj.client)
        return None

    def get_contract_number(self, obj):
        if obj.contract:
            return obj.contract.contract_number
        return None

    def get_recent_payments(self, obj):
        recent = obj.payments.order_by('-payment_date')[:5]
        return CreditPaymentListSerializer(recent, many=True).data


class ActiveCreditListSerializer(serializers.ModelSerializer):
    """Serializer simplificado para listas de créditos activos."""
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    client_name = serializers.SerializerMethodField()
    product_name = serializers.CharField(source='product.name', read_only=True)
    currency_code = serializers.CharField(source='currency.code', read_only=True)
    payment_frequency_name = serializers.CharField(source='payment_frequency.name', read_only=True)
    amortization_system_name = serializers.CharField(source='amortization_system.name', read_only=True)

    class Meta:
        model = ActiveCredit
        fields = [
            'id', 'credit_number', 'client', 'client_name',
            'product', 'product_name', 'approved_amount',
            'currency_code', 'current_balance', 'annual_interest_rate',
            'term_periods', 'payment_frequency_name',
            'amortization_system_name', 'disbursement_date',
            'next_due_date', 'maturity_date', 'status', 'status_display',
            'days_in_arrears', 'total_paid', 'created_at',
        ]

    def get_client_name(self, obj):
        if obj.client:
            return str(obj.client)
        return None


class ActivateFromContractSerializer(serializers.Serializer):
    """Serializer para activar crédito desde contrato."""
    contract_id = serializers.IntegerField(required=True)
    notes = serializers.CharField(required=False, allow_blank=True)


# ─── CreditGracePeriod ───────────────────────────────────────────

class CreditGracePeriodSerializer(serializers.ModelSerializer):
    """Serializer para período de gracia."""
    grace_type_display = serializers.CharField(source='get_grace_type_display', read_only=True)
    applied_by_name = serializers.SerializerMethodField()

    class Meta:
        model = CreditGracePeriod
        fields = [
            'id', 'active_credit', 'grace_type', 'grace_type_display',
            'start_date', 'end_date', 'reason', 'applied_by',
            'applied_by_name', 'is_active', 'metadata', 'created_at',
        ]
        read_only_fields = ['id', 'applied_by', 'is_active', 'created_at']

    def get_applied_by_name(self, obj):
        if obj.applied_by:
            return obj.applied_by.get_full_name() or obj.applied_by.email
        return None


class ApplyGracePeriodSerializer(serializers.Serializer):
    """Serializer para aplicar período de gracia."""
    grace_type = serializers.ChoiceField(choices=CreditGracePeriod.GraceType.choices)
    start_date = serializers.DateField()
    end_date = serializers.DateField()
    reason = serializers.CharField()

    def validate(self, data):
        if data['start_date'] >= data['end_date']:
            raise serializers.ValidationError({
                'end_date': 'La fecha de fin debe ser posterior a la fecha de inicio.'
            })
        return data


# ─── CreditRestructuring ─────────────────────────────────────────

class CreditRestructuringSerializer(serializers.ModelSerializer):
    """Serializer para reestructuración."""
    applied_by_name = serializers.SerializerMethodField()

    class Meta:
        model = CreditRestructuring
        fields = [
            'id', 'active_credit', 'original_terms', 'new_term_periods',
            'new_interest_rate', 'new_payment_frequency',
            'new_amortization_system', 'new_first_payment_date',
            'reason', 'applied_by', 'applied_by_name', 'applied_at',
            'is_active', 'metadata', 'created_at',
        ]
        read_only_fields = ['id', 'applied_by', 'applied_at', 'is_active', 'created_at']

    def get_applied_by_name(self, obj):
        if obj.applied_by:
            return obj.applied_by.get_full_name() or obj.applied_by.email
        return None


class RestructureSerializer(serializers.Serializer):
    """Serializer para solicitud de reestructuración."""
    new_term_periods = serializers.IntegerField(required=False, min_value=1)
    new_interest_rate = serializers.DecimalField(required=False, max_digits=6, decimal_places=2, min_value=0)
    new_payment_frequency_id = serializers.IntegerField(required=False)
    new_amortization_system_id = serializers.IntegerField(required=False)
    new_first_payment_date = serializers.DateField(required=False)
    reason = serializers.CharField()
    preview = serializers.BooleanField(default=False)


# ─── CreditStatusHistory ─────────────────────────────────────────

class CreditStatusHistorySerializer(serializers.ModelSerializer):
    """Serializer para historial de cambios de estado."""
    changed_by_name = serializers.SerializerMethodField()

    class Meta:
        model = CreditStatusHistory
        fields = [
            'id', 'active_credit', 'previous_status', 'new_status',
            'changed_by', 'changed_by_name', 'reason',
            'metadata', 'created_at',
        ]

    def get_changed_by_name(self, obj):
        if obj.changed_by:
            return obj.changed_by.get_full_name() or obj.changed_by.email
        return None


# ─── Summary Serializer ──────────────────────────────────────────

class ActiveCreditSummarySerializer(serializers.Serializer):
    """Serializer para resumen financiero de crédito activo."""
    credit_number = serializers.CharField()
    status = serializers.CharField()
    status_display = serializers.CharField()
    approved_amount = serializers.CharField()
    current_balance = serializers.CharField()
    total_paid = serializers.CharField()
    principal_paid = serializers.CharField()
    interest_paid = serializers.CharField()
    fees_paid = serializers.CharField()
    penalty_paid = serializers.CharField()
    annual_interest_rate = serializers.CharField()
    term_periods = serializers.IntegerField()
    payment_frequency = serializers.CharField()
    amortization_system = serializers.CharField()
    currency = serializers.CharField()
    disbursement_date = serializers.CharField()
    first_payment_date = serializers.CharField()
    maturity_date = serializers.CharField()
    next_due_date = serializers.CharField()
    days_in_arrears = serializers.IntegerField()
    total_installments = serializers.IntegerField()
    paid_installments = serializers.IntegerField()
    pending_installments = serializers.IntegerField()
    overdue_installments = serializers.IntegerField()
    progress_percentage = serializers.FloatField()
    next_installment = serializers.DictField()
    total_pending_amount = serializers.CharField()
    client_name = serializers.CharField()
    product_name = serializers.CharField()


# ─── CreditSupportRequest ──────────────────────────────────────────

class CreditSupportRequestSerializer(serializers.ModelSerializer):
    """Serializer de lectura para solicitudes de apoyo (staff y cliente)."""
    request_type_display = serializers.CharField(source='get_request_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    reason_category_display = serializers.CharField(source='get_reason_category_display', read_only=True)
    credit_number = serializers.CharField(source='active_credit.credit_number', read_only=True)
    client_name = serializers.SerializerMethodField()
    reviewed_by_name = serializers.SerializerMethodField()

    class Meta:
        model = CreditSupportRequest
        fields = [
            'id', 'active_credit', 'credit_number', 'client', 'client_name',
            'request_type', 'request_type_display',
            'reason_category', 'reason_category_display',
            'description', 'requested_months', 'contact_phone',
            'status', 'status_display',
            'reviewed_by', 'reviewed_by_name', 'reviewed_at',
            'bank_response', 'approved_terms_snapshot',
            'requires_more_info', 'requested_info',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_client_name(self, obj):
        if obj.client:
            return obj.client.full_name if hasattr(obj.client, 'full_name') else str(obj.client)
        return None

    def get_reviewed_by_name(self, obj):
        if obj.reviewed_by:
            return obj.reviewed_by.get_full_name() or obj.reviewed_by.email
        return None


class CreditSupportRequestListSerializer(serializers.ModelSerializer):
    """Serializer simplificado para listados."""
    request_type_display = serializers.CharField(source='get_request_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    credit_number = serializers.CharField(source='active_credit.credit_number', read_only=True)
    client_name = serializers.SerializerMethodField()

    class Meta:
        model = CreditSupportRequest
        fields = [
            'id', 'active_credit', 'credit_number', 'client', 'client_name',
            'request_type', 'request_type_display',
            'status', 'status_display',
            'reason_category', 'description', 'requested_months',
            'created_at',
        ]
        read_only_fields = fields

    def get_client_name(self, obj):
        if obj.client:
            return obj.client.full_name if hasattr(obj.client, 'full_name') else str(obj.client)
        return None


class CreateSupportRequestSerializer(serializers.Serializer):
    """Serializer para crear una solicitud de apoyo desde mobile."""
    request_type = serializers.ChoiceField(choices=CreditSupportRequest.RequestType.choices)
    reason_category = serializers.ChoiceField(
        choices=CreditSupportRequest.ReasonCategory.choices,
        default='other'
    )
    description = serializers.CharField(min_length=10)
    requested_months = serializers.IntegerField(required=False, min_value=1)
    contact_phone = serializers.CharField(required=False, allow_blank=True, default='')


class ReviewSupportRequestSerializer(serializers.Serializer):
    """Serializer para acciones del staff sobre solicitudes."""
    bank_response = serializers.CharField(required=False, allow_blank=True, default='')
    requested_info = serializers.CharField(required=False, allow_blank=True, default='')
    # Campos opcionales para aprobación con condiciones específicas
    grace_type = serializers.ChoiceField(
        choices=[('FULL_GRACE', 'Gracia Total'), ('INTEREST_ONLY', 'Solo Intereses'), ('PARTIAL_PAYMENT', 'Pago Parcial')],
        required=False
    )
    grace_start_date = serializers.DateField(required=False)
    grace_end_date = serializers.DateField(required=False)
    new_term_periods = serializers.IntegerField(required=False, min_value=1)
    new_interest_rate = serializers.DecimalField(required=False, max_digits=6, decimal_places=2)
    new_payment_frequency_id = serializers.IntegerField(required=False)
    new_amortization_system_id = serializers.IntegerField(required=False)
