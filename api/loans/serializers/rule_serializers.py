"""
Serializers para CU-09: Administración de Reglas y Parámetros
"""

from rest_framework import serializers
from django.db import transaction
from api.loans.models_rules import (
    TenantRuleSet,
    EligibilityRule,
    CreditProductParameter,
    # DocumentRequirement,  # DEPRECATED: Eliminado - usar ProductDocumentRequirement
    WorkflowStageDefinition,
    DecisionThreshold,
    RuleSetAudit
)


class EligibilityRuleSerializer(serializers.ModelSerializer):
    """Serializer para EligibilityRule"""
    
    class Meta:
        model = EligibilityRule
        fields = [
            'id',
            'rule_set',
            'max_debt_to_income_ratio',
            'min_income_required',
            'min_employment_months',
            'max_arrears_allowed',
            'allowed_cic_categories',
            'min_collateral_coverage',
            'min_age',
            'max_age',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def validate_allowed_cic_categories(self, value):
        """Valida que las categorías CIC sean válidas"""
        valid_categories = ['A', 'B', 'C', 'D', 'E', 'F']
        
        if not isinstance(value, list):
            raise serializers.ValidationError("Debe ser una lista")
        
        for cat in value:
            if cat not in valid_categories:
                raise serializers.ValidationError(
                    f"Categoría '{cat}' no válida. Válidas: {valid_categories}"
                )
        
        return value
    
    def validate(self, attrs):
        """Validaciones cruzadas"""
        # Validar que edad mínima < edad máxima
        min_age = attrs.get('min_age', 18)
        max_age = attrs.get('max_age', 70)
        
        if min_age >= max_age:
            raise serializers.ValidationError({
                'max_age': 'La edad máxima debe ser mayor que la edad mínima'
            })
        
        return attrs


class CreditProductParameterSerializer(serializers.ModelSerializer):
    """
    Serializer para CreditProductParameter.
    
    EXTENDIDO en Fase 2 con nuevos campos y relaciones M2M.
    """
    
    rule_set_name = serializers.CharField(source='rule_set.name', read_only=True)
    
    # Nested serializers para M2M (solo IDs para escritura, objetos completos para lectura)
    allowed_currencies_detail = serializers.SerializerMethodField(read_only=True)
    allowed_payment_frequencies_detail = serializers.SerializerMethodField(read_only=True)
    allowed_amortization_systems_detail = serializers.SerializerMethodField(read_only=True)
    
    class Meta:
        model = CreditProductParameter
        fields = [
            'id',
            'rule_set',
            'rule_set_name',
            # Montos
            'min_amount',
            'max_amount',
            # Plazos
            'min_term_months',
            'max_term_months',
            # Tasas
            'min_interest_rate',
            'max_interest_rate',
            'interest_type',
            # Comisiones y Seguros (NUEVO)
            'commission_rate_min',
            'commission_rate_max',
            'insurance_rate_min',
            'insurance_rate_max',
            'additional_insurance_rate',
            # Sistema de Pago (NUEVO)
            'grace_period_months_min',
            'grace_period_months_max',
            'allows_early_payment',
            'early_payment_penalty_min',
            'early_payment_penalty_max',
            # Catálogos M2M (NUEVO)
            'allowed_currencies',
            'allowed_currencies_detail',
            'allowed_payment_frequencies',
            'allowed_payment_frequencies_detail',
            'allowed_amortization_systems',
            'allowed_amortization_systems_detail',
            # Financiamiento
            'max_financing_percentage',
            # Elegibilidad (NUEVO)
            'min_income_required',
            'max_debt_to_income_ratio',
            'min_employment_months',
            'min_collateral_coverage',
            # Garantías
            'requires_guarantor',
            'requires_collateral',
            # Scoring (NUEVO)
            'min_credit_score_required',
            'auto_approval_enabled',
            'max_auto_approval_amount',
            # Timestamps
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_allowed_currencies_detail(self, obj):
        """Retorna detalles de las monedas permitidas"""
        from api.loans.serializers.catalog_serializers import CurrencySerializer
        return CurrencySerializer(obj.allowed_currencies.all(), many=True).data
    
    def get_allowed_payment_frequencies_detail(self, obj):
        """Retorna detalles de las frecuencias de pago permitidas"""
        from api.loans.serializers.catalog_serializers import PaymentFrequencySerializer
        return PaymentFrequencySerializer(obj.allowed_payment_frequencies.all(), many=True).data
    
    def get_allowed_amortization_systems_detail(self, obj):
        """Retorna detalles de los sistemas de amortización permitidos"""
        from api.loans.serializers.catalog_serializers import AmortizationSystemSerializer
        return AmortizationSystemSerializer(obj.allowed_amortization_systems.all(), many=True).data
    
    def validate(self, attrs):
        """Validaciones cruzadas"""
        # Validar montos
        min_amount = attrs.get('min_amount')
        max_amount = attrs.get('max_amount')
        
        if min_amount and max_amount and min_amount >= max_amount:
            raise serializers.ValidationError({
                'max_amount': 'El monto máximo debe ser mayor que el monto mínimo'
            })
        
        # Validar plazos
        min_term = attrs.get('min_term_months')
        max_term = attrs.get('max_term_months')
        
        if min_term and max_term and min_term >= max_term:
            raise serializers.ValidationError({
                'max_term_months': 'El plazo máximo debe ser mayor que el plazo mínimo'
            })
        
        # Validar tasas
        min_rate = attrs.get('min_interest_rate')
        max_rate = attrs.get('max_interest_rate')
        
        if min_rate and max_rate and min_rate >= max_rate:
            raise serializers.ValidationError({
                'max_interest_rate': 'La tasa máxima debe ser mayor que la tasa mínima'
            })
        
        # Validar comisiones (NUEVO)
        commission_min = attrs.get('commission_rate_min', 0)
        commission_max = attrs.get('commission_rate_max', 0)
        
        if commission_min > commission_max:
            raise serializers.ValidationError({
                'commission_rate_max': 'La comisión máxima debe ser mayor o igual a la mínima'
            })
        
        # Validar seguros (NUEVO)
        insurance_min = attrs.get('insurance_rate_min', 0)
        insurance_max = attrs.get('insurance_rate_max', 0)
        
        if insurance_min > insurance_max:
            raise serializers.ValidationError({
                'insurance_rate_max': 'El seguro máximo debe ser mayor o igual al mínimo'
            })
        
        # Validar período de gracia (NUEVO)
        grace_min = attrs.get('grace_period_months_min', 0)
        grace_max = attrs.get('grace_period_months_max', 6)
        
        if grace_min > grace_max:
            raise serializers.ValidationError({
                'grace_period_months_max': 'El período de gracia máximo debe ser mayor o igual al mínimo'
            })
        
        # Validar penalidad pago anticipado (NUEVO)
        penalty_min = attrs.get('early_payment_penalty_min', 0)
        penalty_max = attrs.get('early_payment_penalty_max', 5)
        
        if penalty_min > penalty_max:
            raise serializers.ValidationError({
                'early_payment_penalty_max': 'La penalidad máxima debe ser mayor o igual a la mínima'
            })
        
        return attrs


# ============================================================
# DEPRECATED: DocumentRequirementSerializer
# ============================================================
# Este serializer ha sido ELIMINADO.
# Los documentos requeridos ahora se gestionan directamente en cada producto
# a través de ProductDocumentRequirement (relación M2M entre CreditProduct y DocumentType).
#
# Migración: 0012_remove_document_requirement_model.py
# Fecha: 2026-05-10
# ============================================================


class WorkflowStageDefinitionSerializer(serializers.ModelSerializer):
    """Serializer para WorkflowStageDefinition"""
    
    responsible_role_name = serializers.CharField(
        source='responsible_role.name',
        read_only=True
    )
    
    display_order = serializers.IntegerField(
        source='stage_order',
        read_only=True
    )
    
    description = serializers.SerializerMethodField()
    is_required = serializers.BooleanField(default=True, read_only=True)
    icon = serializers.SerializerMethodField()
    color = serializers.SerializerMethodField()
    
    class Meta:
        model = WorkflowStageDefinition
        fields = [
            'id',
            'rule_set',
            'stage_name',
            'stage_code',
            'stage_order',
            'display_order',
            'description',
            'is_required',
            'icon',
            'color',
            'responsible_role',
            'responsible_role_name',
            'time_limit_hours',
            'is_automated',
            'auto_advance_enabled',
            'auto_advance_conditions',
            'next_stage_on_success',
            'next_stage_on_failure',
            'requires_manual_approval',
            'escalation_enabled',
            'escalation_rules',
            'notification_template',
            'client_message_template',
            'requires_client_action',
            'client_action_description',
            'client_action_url',
            'is_final_stage',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_description(self, obj):
        return f"{obj.stage_name} - Paso {obj.stage_order}"
    
    def get_icon(self, obj):
        icons = {
            'DRAFT': 'edit_document',
            'SUBMITTED': 'send',
            'KYC': 'verified_user',
            'DOCUMENTS': 'folder',
            'SCORING': 'analytics',
            'REVIEW': 'rate_review',
            'APPROVED': 'check_circle',
            'REJECTED': 'cancel',
            'DISBURSED': 'payments',
        }
        return icons.get(obj.stage_code, 'circle')
    
    def get_color(self, obj):
        colors = {
            'DRAFT': '#64748B',
            'SUBMITTED': '#3B82F6',
            'KYC': '#8B5CF6',
            'DOCUMENTS': '#F59E0B',
            'SCORING': '#10B981',
            'REVIEW': '#6366F1',
            'APPROVED': '#22C55E',
            'REJECTED': '#EF4444',
            'DISBURSED': '#14B8A6',
        }
        return colors.get(obj.stage_code, '#94A3B8')
    
    def validate_stage_code(self, value):
        """Valida que el código de etapa sea válido"""
        valid_codes = [
            'DRAFT', 'SUBMITTED', 'DOCUMENTS', 'KYC', 'SCORING',
            'REVIEW', 'APPROVED', 'REJECTED', 'DISBURSED'
        ]
        
        if value not in valid_codes:
            raise serializers.ValidationError(
                f"Código '{value}' no válido. Válidos: {valid_codes}"
            )
        
        return value


class DecisionThresholdSerializer(serializers.ModelSerializer):
    """Serializer para DecisionThreshold"""
    
    # Definir explícitamente los campos para evitar el warning de min_value
    min_score_auto_approval = serializers.IntegerField(
        default=70,
        min_value=0,
        help_text='Score >= este valor → aprobación automática'
    )
    min_score_manual_review = serializers.IntegerField(
        default=50,
        min_value=0,
        help_text='Score entre este valor y auto_approval → revisión manual'
    )
    max_score_auto_rejection = serializers.IntegerField(
        default=49,
        min_value=0,
        help_text='Score <= este valor → rechazo automático'
    )
    max_amount_auto_approval = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        required=False,
        allow_null=True,
        min_value=0,
        help_text='Montos superiores requieren revisión manual'
    )
    requires_manager_approval_amount = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        required=False,
        allow_null=True,
        min_value=0,
        help_text='Montos superiores requieren aprobación de gerente/comité'
    )
    
    class Meta:
        model = DecisionThreshold
        fields = [
            'id',
            'rule_set',
            'min_score_auto_approval',
            'min_score_manual_review',
            'max_score_auto_rejection',
            'max_amount_auto_approval',
            'requires_manager_approval_amount',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def validate(self, attrs):
        """Validaciones cruzadas de scores"""
        auto_approval = attrs.get('min_score_auto_approval', 70)
        manual_review = attrs.get('min_score_manual_review', 50)
        auto_rejection = attrs.get('max_score_auto_rejection', 49)
        
        # Validar que auto_approval > manual_review > auto_rejection
        if not (auto_approval > manual_review > auto_rejection):
            raise serializers.ValidationError(
                "Los umbrales deben cumplir: auto_approval > manual_review > auto_rejection"
            )
        
        return attrs


class RuleSetAuditSerializer(serializers.ModelSerializer):
    """Serializer para RuleSetAudit (solo lectura)"""
    
    changed_by_name = serializers.CharField(
        source='changed_by.get_full_name',
        read_only=True
    )
    
    class Meta:
        model = RuleSetAudit
        fields = [
            'id',
            'rule_set',
            'changed_by',
            'changed_by_name',
            'change_type',
            'field_name',
            'old_value',
            'new_value',
            'ip_address',
            'user_agent',
            'notes',
            'created_at',
        ]
        read_only_fields = fields  # Todos son read-only


class TenantRuleSetSerializer(serializers.ModelSerializer):
    """
    Serializer para TenantRuleSet (lectura).
    
    Incluye nested serializers para todos los componentes del conjunto de reglas.
    """
    
    eligibility_rule = serializers.SerializerMethodField()
    product_parameters = serializers.SerializerMethodField()
    document_requirements = serializers.SerializerMethodField()
    workflow_stages = serializers.SerializerMethodField()
    decision_threshold = serializers.SerializerMethodField()
    
    activated_by_name = serializers.CharField(
        source='activated_by.get_full_name',
        read_only=True
    )
    
    class Meta:
        model = TenantRuleSet
        fields = [
            'id',
            'version',
            'status',
            'name',
            'description',
            'activated_at',
            'activated_by',
            'activated_by_name',
            'archived_at',
            'notes',
            'created_at',
            'updated_at',
            # Nested
            'eligibility_rule',
            'product_parameters',
            'document_requirements',
            'workflow_stages',
            'decision_threshold',
        ]
        read_only_fields = ['id', 'activated_at', 'archived_at', 'created_at', 'updated_at']
    
    def get_eligibility_rule(self, obj):
        if hasattr(obj, 'eligibility_rule'):
            return EligibilityRuleSerializer(obj.eligibility_rule).data
        return None
    
    def get_product_parameters(self, obj):
        return CreditProductParameterSerializer(
            obj.product_parameters.all(),
            many=True
        ).data
    
    def get_document_requirements(self, obj):
        # DEPRECATED: DocumentRequirement eliminado
        # Los documentos ahora se gestionan en ProductDocumentRequirement
        return []
    
    def get_workflow_stages(self, obj):
        return WorkflowStageDefinitionSerializer(
            obj.workflow_stages.all(),
            many=True
        ).data
    
    def get_decision_threshold(self, obj):
        if hasattr(obj, 'decision_threshold'):
            return DecisionThresholdSerializer(obj.decision_threshold).data
        return None


class TenantRuleSetWriteSerializer(serializers.ModelSerializer):
    """
    Serializer para crear/actualizar TenantRuleSet.
    
    Solo permite editar conjuntos en estado DRAFT.
    """
    
    class Meta:
        model = TenantRuleSet
        fields = [
            'version',
            'name',
            'description',
            'notes',
        ]
    
    def validate(self, attrs):
        # Si es actualización, verificar que esté en DRAFT
        if self.instance and self.instance.status != TenantRuleSet.Status.DRAFT:
            raise serializers.ValidationError(
                "Solo se pueden editar conjuntos de reglas en estado DRAFT"
            )
        return attrs
    
    def create(self, validated_data):
        # Agregar tenant del request
        validated_data['institution'] = self.context['request'].tenant
        validated_data['status'] = TenantRuleSet.Status.DRAFT
        return super().create(validated_data)


__all__ = [
    'TenantRuleSetSerializer',
    'TenantRuleSetWriteSerializer',
    'EligibilityRuleSerializer',
    'CreditProductParameterSerializer',
    # 'DocumentRequirementSerializer',  # DEPRECATED: Eliminado
    'WorkflowStageDefinitionSerializer',
    'DecisionThresholdSerializer',
    'RuleSetAuditSerializer',
]
