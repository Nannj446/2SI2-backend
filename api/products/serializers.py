"""
Serializers para gestión de productos crediticios (REFACTORIZADO).
"""

from rest_framework import serializers
from decimal import Decimal
from api.products.models import CreditProduct, ProductRequirement, ProductDocumentRequirement
from api.loans.models_rules import CreditProductParameter, TenantRuleSet
# from api.loans.models_rules import DocumentRequirement  # DEPRECATED: Eliminado

# Importar serializers de catálogos desde su ubicación centralizada
from api.loans.serializers.catalog_serializers import (
    ProductTypeSerializer,
    CurrencySerializer,
    PaymentFrequencySerializer,
    AmortizationSystemSerializer,
    DocumentTypeSerializer,
)


class ProductDocumentRequirementSerializer(serializers.ModelSerializer):
    """Serializer para documentos requeridos del producto."""
    
    document_type_detail = DocumentTypeSerializer(source='document_type', read_only=True)
    
    class Meta:
        model = ProductDocumentRequirement
        fields = [
            'id',
            'document_type',
            'document_type_detail',
            'is_mandatory',
            'display_order',
            'max_validity_days',
            'allowed_formats',
            'max_file_size_mb',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class TenantRuleSetSimpleSerializer(serializers.ModelSerializer):
    """Serializer simple para TenantRuleSet."""
    
    class Meta:
        model = TenantRuleSet
        fields = ['id', 'version', 'name', 'status', 'description']
        read_only_fields = ['id']


class CreditProductParameterSerializer(serializers.ModelSerializer):
    """Serializer para CreditProductParameter."""
    
    allowed_currencies_detail = CurrencySerializer(source='allowed_currencies', many=True, read_only=True)
    allowed_payment_frequencies_detail = PaymentFrequencySerializer(source='allowed_payment_frequencies', many=True, read_only=True)
    allowed_amortization_systems_detail = AmortizationSystemSerializer(source='allowed_amortization_systems', many=True, read_only=True)
    
    class Meta:
        model = CreditProductParameter
        fields = [
            'id',
            'min_amount',
            'max_amount',
            'min_term_months',
            'max_term_months',
            'min_interest_rate',
            'max_interest_rate',
            'interest_type',
            'commission_rate_min',
            'commission_rate_max',
            'insurance_rate_min',
            'insurance_rate_max',
            'additional_insurance_rate',
            'grace_period_months_min',
            'grace_period_months_max',
            'allows_early_payment',
            'early_payment_penalty_min',
            'early_payment_penalty_max',
            'max_financing_percentage',
            'min_income_required',
            'max_debt_to_income_ratio',
            'min_employment_months',
            'min_collateral_coverage',
            'requires_guarantor',
            'requires_collateral',
            'min_credit_score_required',
            'auto_approval_enabled',
            'max_auto_approval_amount',
            'allowed_currencies',
            'allowed_currencies_detail',
            'allowed_payment_frequencies',
            'allowed_payment_frequencies_detail',
            'allowed_amortization_systems',
            'allowed_amortization_systems_detail',
        ]
        read_only_fields = ['id']


class CreditProductSerializer(serializers.ModelSerializer):
    """Serializer completo para lectura de productos."""
    
    product_type_detail = ProductTypeSerializer(source='product_type', read_only=True)
    rule_set_detail = TenantRuleSetSimpleSerializer(source='rule_set', read_only=True)
    document_requirements = ProductDocumentRequirementSerializer(
        source='document_requirements_config',
        many=True,
        read_only=True
    )
    
    # Nuevos campos de selección
    selected_parameter_detail = CreditProductParameterSerializer(source='selected_parameter', read_only=True)
    selected_threshold_detail = serializers.SerializerMethodField()
    selected_eligibility_rules_detail = serializers.SerializerMethodField()
    
    class Meta:
        model = CreditProduct
        fields = [
            'id',
            'name',
            'code',
            'product_type',
            'product_type_detail',
            'rule_set',
            'rule_set_detail',
            'description',
            'is_active',
            'display_order',
            'target_audience',
            'benefits',
            'terms_and_conditions',
            'icon',
            'color',
            'document_requirements',
            # Nuevos campos
            'selected_parameter',
            'selected_parameter_detail',
            'selected_eligibility_rules',
            'selected_eligibility_rules_detail',
            'selected_threshold',
            'selected_threshold_detail',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_selected_threshold_detail(self, obj):
        """Obtiene detalle del umbral seleccionado."""
        if obj.selected_threshold:
            from api.loans.serializers.rule_serializers import DecisionThresholdSerializer
            return DecisionThresholdSerializer(obj.selected_threshold).data
        return None
    
    def get_selected_eligibility_rules_detail(self, obj):
        """Obtiene detalle de las reglas de elegibilidad seleccionadas."""
        rules = obj.selected_eligibility_rules.all()
        if rules.exists():
            from api.loans.serializers.rule_serializers import EligibilityRuleSerializer
            return EligibilityRuleSerializer(rules, many=True).data
        return []


class CreditProductWithParametersSerializer(serializers.ModelSerializer):
    """Serializer de producto con sus parámetros y configuración completa."""
    
    product_type_detail = ProductTypeSerializer(source='product_type', read_only=True)
    rule_set_detail = TenantRuleSetSimpleSerializer(source='rule_set', read_only=True)
    parameters = serializers.SerializerMethodField()
    document_requirements = ProductDocumentRequirementSerializer(
        source='document_requirements_config',
        many=True,
        read_only=True
    )
    workflow_stages = serializers.SerializerMethodField()
    
    # Nuevos campos de selección
    selected_parameter_detail = CreditProductParameterSerializer(source='selected_parameter', read_only=True)
    selected_threshold_detail = serializers.SerializerMethodField()
    selected_eligibility_rules_detail = serializers.SerializerMethodField()
    
    class Meta:
        model = CreditProduct
        fields = [
            'id',
            'name',
            'code',
            'product_type',
            'product_type_detail',
            'rule_set',
            'rule_set_detail',
            'description',
            'is_active',
            'display_order',
            'target_audience',
            'benefits',
            'terms_and_conditions',
            'icon',
            'color',
            'parameters',
            'document_requirements',
            'workflow_stages',
            # Nuevos campos
            'selected_parameter',
            'selected_parameter_detail',
            'selected_eligibility_rules',
            'selected_eligibility_rules_detail',
            'selected_threshold',
            'selected_threshold_detail',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_parameters(self, obj):
        """Obtiene los parámetros del producto."""
        params = obj.get_parameters()
        if params:
            return CreditProductParameterSerializer(params).data
        return None
    
    def get_workflow_stages(self, obj):
        """Obtiene las etapas de workflow del producto."""
        stages = obj.get_workflow_stages()
        if stages.exists():
            from api.loans.serializers.rule_serializers import WorkflowStageDefinitionSerializer
            return WorkflowStageDefinitionSerializer(stages, many=True).data
        return []
    
    def get_selected_threshold_detail(self, obj):
        """Obtiene detalle del umbral seleccionado."""
        if obj.selected_threshold:
            from api.loans.serializers.rule_serializers import DecisionThresholdSerializer
            return DecisionThresholdSerializer(obj.selected_threshold).data
        return None
    
    def get_selected_eligibility_rules_detail(self, obj):
        """Obtiene detalle de las reglas de elegibilidad seleccionadas."""
        rules = obj.selected_eligibility_rules.all()
        if rules.exists():
            from api.loans.serializers.rule_serializers import EligibilityRuleSerializer
            return EligibilityRuleSerializer(rules, many=True).data
        return []


class CreateCreditProductSerializer(serializers.ModelSerializer):
    """Serializer para crear productos con documentos requeridos."""
    
    document_requirements = serializers.ListField(
        child=serializers.DictField(),
        required=False,
        write_only=True,
        help_text='Lista de documentos requeridos con configuración'
    )
    
    selected_eligibility_rules = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        write_only=True,
        help_text='IDs de reglas de elegibilidad a aplicar'
    )
    
    class Meta:
        model = CreditProduct
        fields = [
            'name',
            'code',
            'product_type',
            'rule_set',
            'description',
            'is_active',
            'display_order',
            'target_audience',
            'benefits',
            'terms_and_conditions',
            'icon',
            'color',
            'document_requirements',
            # Nuevos campos
            'selected_parameter',
            'selected_eligibility_rules',
            'selected_threshold',
        ]
    
    def validate_code(self, value):
        """Valida que el código sea único."""
        if CreditProduct.objects.filter(code=value).exists():
            raise serializers.ValidationError('Ya existe un producto con este código')
        return value
    
    def validate_rule_set(self, value):
        """Valida que el conjunto de reglas pertenezca al tenant."""
        request = self.context.get('request')
        if request and hasattr(request, 'tenant'):
            if value and value.institution != request.tenant:
                raise serializers.ValidationError('El conjunto de reglas no pertenece a su institución')
        return value
    
    def validate_selected_parameter(self, value):
        """Valida que el parámetro pertenezca al rule_set del producto."""
        # Temporalmente deshabilitado para debugging
        return value
    
    def validate_selected_threshold(self, value):
        """Valida que el umbral pertenezca al rule_set del producto."""
        # Temporalmente deshabilitado para debugging
        return value
    
    def validate(self, attrs):
        """Validaciones cruzadas."""
        # Temporalmente deshabilitado para debugging
        return attrs
    
    def create(self, validated_data):
        """Crea el producto y sus documentos requeridos."""
        document_requirements_data = validated_data.pop('document_requirements', [])
        eligibility_rules_ids = validated_data.pop('selected_eligibility_rules', [])
        
        # Crear el producto
        product = CreditProduct.objects.create(**validated_data)
        
        # Asignar reglas de elegibilidad
        if eligibility_rules_ids:
            product.selected_eligibility_rules.set(eligibility_rules_ids)
        
        # Crear los documentos requeridos
        for doc_req_data in document_requirements_data:
            ProductDocumentRequirement.objects.create(
                product=product,
                institution=product.institution,
                document_type_id=doc_req_data.get('document_type'),
                is_mandatory=doc_req_data.get('is_mandatory', True),
                display_order=doc_req_data.get('display_order', 0),
                max_validity_days=doc_req_data.get('max_validity_days'),
                allowed_formats=doc_req_data.get('allowed_formats', []),
                max_file_size_mb=doc_req_data.get('max_file_size_mb'),
            )
        
        return product


class UpdateCreditProductSerializer(serializers.ModelSerializer):
    """Serializer para actualización de productos con documentos requeridos."""
    
    document_requirements = serializers.ListField(
        child=serializers.DictField(),
        required=False,
        write_only=True,
        help_text='Lista de documentos requeridos con configuración'
    )
    
    selected_eligibility_rules = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        write_only=True,
        help_text='IDs de reglas de elegibilidad a aplicar'
    )
    
    # Permitir null y convertir a cadena vacía
    target_audience = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    terms_and_conditions = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    
    class Meta:
        model = CreditProduct
        fields = [
            'name',
            'rule_set',
            'description',
            'is_active',
            'display_order',
            'target_audience',
            'benefits',
            'terms_and_conditions',
            'icon',
            'color',
            'document_requirements',
            # Nuevos campos
            'selected_parameter',
            'selected_eligibility_rules',
            'selected_threshold',
        ]
    
    def validate_rule_set(self, value):
        """Valida que el conjunto de reglas pertenezca al tenant."""
        request = self.context.get('request')
        if request and hasattr(request, 'tenant'):
            if value and value.institution != request.tenant:
                raise serializers.ValidationError('El conjunto de reglas no pertenece a su institución')
        return value
    
    def validate_selected_parameter(self, value):
        """Valida que el parámetro pertenezca al rule_set del producto."""
        import logging
        logger = logging.getLogger(__name__)
        
        if not value:
            return value
        
        # En actualización, obtener rule_set de initial_data o de la instancia
        rule_set_id = self.initial_data.get('rule_set')
        if not rule_set_id and self.instance:
            rule_set_id = self.instance.rule_set_id
        
        logger.error(f"UPDATE validate_selected_parameter - value: {value}, rule_set_id: {rule_set_id}")
        
        if not rule_set_id:
            return value
        
        # Validar que el parámetro pertenezca al rule_set
        param_rule_set_id = getattr(value, 'rule_set_id', None)
        logger.error(f"UPDATE param_rule_set_id: {param_rule_set_id}, comparing with: {rule_set_id}")
        
        if param_rule_set_id and param_rule_set_id != int(rule_set_id):
            raise serializers.ValidationError(
                'El parámetro seleccionado no pertenece al conjunto de reglas del producto'
            )
        
        return value
    
    def validate_selected_threshold(self, value):
        """Valida que el umbral pertenezca al rule_set del producto."""
        import logging
        logger = logging.getLogger(__name__)
        
        if not value:
            return value
        
        # En actualización, obtener rule_set de initial_data o de la instancia
        rule_set_id = self.initial_data.get('rule_set')
        if not rule_set_id and self.instance:
            rule_set_id = self.instance.rule_set_id
        
        logger.error(f"UPDATE validate_selected_threshold - value: {value}, rule_set_id: {rule_set_id}")
        
        if not rule_set_id:
            return value
        
        # Validar que el umbral pertenezca al rule_set
        threshold_rule_set_id = getattr(value, 'rule_set_id', None)
        logger.error(f"UPDATE threshold_rule_set_id: {threshold_rule_set_id}, comparing with: {rule_set_id}")
        
        if threshold_rule_set_id and threshold_rule_set_id != int(rule_set_id):
            raise serializers.ValidationError(
                'El umbral seleccionado no pertenece al conjunto de reglas del producto'
            )
        
        return value
    
    def validate(self, attrs):
        """Validaciones cruzadas."""
        import logging
        logger = logging.getLogger(__name__)
        
        logger.error(f"UPDATE validate() CALLED - attrs keys: {list(attrs.keys())}")
        logger.error(f"UPDATE validate() - full attrs: {attrs}")
        
        # Obtener rule_set (puede venir de attrs o de la instancia)
        rule_set_id = attrs.get('rule_set')
        if not rule_set_id and self.instance:
            rule_set_id = self.instance.rule_set_id
        
        # Normalizar rule_set_id
        if isinstance(rule_set_id, int):
            rule_set_id = rule_set_id
        elif hasattr(rule_set_id, 'id'):
            rule_set_id = rule_set_id.id
        else:
            logger.error(f"UPDATE validate() - No rule_set_id found, attrs: {attrs.keys()}, instance: {self.instance}")
            return attrs
        
        logger.error(f"UPDATE validate() - rule_set_id: {rule_set_id}")
        
        selected_eligibility_rules = attrs.get('selected_eligibility_rules', [])
        logger.error(f"UPDATE validate() - selected_eligibility_rules: {selected_eligibility_rules}")
        
        # Validar que las reglas de elegibilidad pertenezcan al rule_set
        if rule_set_id and selected_eligibility_rules:
            from api.loans.models_rules import EligibilityRule
            for rule_id in selected_eligibility_rules:
                try:
                    rule = EligibilityRule.objects.get(id=rule_id)
                    logger.error(f"UPDATE validate() - checking rule {rule_id}, rule.rule_set_id: {rule.rule_set_id}")
                    if rule.rule_set_id != rule_set_id:
                        logger.error(f"UPDATE validate() - VALIDATION ERROR: rule {rule_id} does not belong to rule_set {rule_set_id}")
                        raise serializers.ValidationError({
                            'selected_eligibility_rules': f'La regla de elegibilidad {rule_id} no pertenece al conjunto de reglas seleccionado'
                        })
                except EligibilityRule.DoesNotExist:
                    logger.error(f"UPDATE validate() - VALIDATION ERROR: rule {rule_id} does not exist")
                    raise serializers.ValidationError({
                        'selected_eligibility_rules': f'La regla de elegibilidad {rule_id} no existe'
                    })
        
        logger.error(f"UPDATE validate() - VALIDATION PASSED, returning attrs")
        return attrs
    
    def update(self, instance, validated_data):
        """Actualiza el producto y sus documentos requeridos."""
        from django.db.models import ProtectedError
        
        document_requirements_data = validated_data.pop('document_requirements', None)
        eligibility_rules_ids = validated_data.pop('selected_eligibility_rules', None)
        
        # Convertir None a cadena vacía para campos de texto
        if validated_data.get('target_audience') is None:
            validated_data['target_audience'] = ''
        if validated_data.get('terms_and_conditions') is None:
            validated_data['terms_and_conditions'] = ''
        
        # Actualizar campos del producto
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        
        # Actualizar reglas de elegibilidad si se proporcionaron
        if eligibility_rules_ids is not None:
            instance.selected_eligibility_rules.set(eligibility_rules_ids)
        
        # Actualizar documentos requeridos si se proporcionaron
        if document_requirements_data is not None:
            # Obtener los existentes indexados por document_type_id
            existing_requirements = {
                req.document_type_id: req
                for req in instance.document_requirements_config.all()
            }
            
            incoming_doc_types = set()
            for doc_req_data in document_requirements_data:
                doc_type_id = doc_req_data.get('document_type')
                if doc_type_id:
                    incoming_doc_types.add(doc_type_id)
                    
                    # Si ya existe, actualizamos sus campos en vez de recrearlo
                    if doc_type_id in existing_requirements:
                        req = existing_requirements[doc_type_id]
                        req.is_mandatory = doc_req_data.get('is_mandatory', True)
                        req.display_order = doc_req_data.get('display_order', 0)
                        req.max_validity_days = doc_req_data.get('max_validity_days')
                        req.allowed_formats = doc_req_data.get('allowed_formats', [])
                        req.max_file_size_mb = doc_req_data.get('max_file_size_mb')
                        req.save()
                    else:
                        # Si no existe, lo creamos
                        ProductDocumentRequirement.objects.create(
                            product=instance,
                            institution=instance.institution,
                            document_type_id=doc_type_id,
                            is_mandatory=doc_req_data.get('is_mandatory', True),
                            display_order=doc_req_data.get('display_order', 0),
                            max_validity_days=doc_req_data.get('max_validity_days'),
                            allowed_formats=doc_req_data.get('allowed_formats', []),
                            max_file_size_mb=doc_req_data.get('max_file_size_mb'),
                        )
            
            # Eliminar los que ya no vienen en la lista
            for doc_type_id, req in existing_requirements.items():
                if doc_type_id not in incoming_doc_types:
                    try:
                        req.delete()
                    except ProtectedError:
                        raise serializers.ValidationError({
                            'document_requirements': (
                                f"No se puede eliminar el requisito de documento '{req.document_type.name}' "
                                "porque está asociado a solicitudes de crédito activas."
                            )
                        })
            # Eliminar documentos existentes
            instance.document_requirements_config.all().delete()
            
            # Crear nuevos documentos requeridos
            for doc_req_data in document_requirements_data:
                ProductDocumentRequirement.objects.create(
                    product=instance,
                    institution=instance.institution,
                    document_type_id=doc_req_data.get('document_type'),
                    is_mandatory=doc_req_data.get('is_mandatory', True),
                    display_order=doc_req_data.get('display_order', 0),
                    max_validity_days=doc_req_data.get('max_validity_days'),
                    allowed_formats=doc_req_data.get('allowed_formats', []),
                    max_file_size_mb=doc_req_data.get('max_file_size_mb'),
                )
        
        return instance


class CreditProductListSerializer(serializers.ModelSerializer):
    """Serializer simplificado para listado de productos."""
    
    product_type_detail = ProductTypeSerializer(source='product_type', read_only=True)
    rule_set_detail = TenantRuleSetSimpleSerializer(source='rule_set', read_only=True)
    has_parameters = serializers.SerializerMethodField()
    documents_count = serializers.SerializerMethodField()
    
    # Campos para compatibilidad con mobile (extraídos de selected_parameter)
    min_amount = serializers.SerializerMethodField()
    max_amount = serializers.SerializerMethodField()
    interest_rate = serializers.SerializerMethodField()
    interest_type = serializers.SerializerMethodField()
    min_term_months = serializers.SerializerMethodField()
    max_term_months = serializers.SerializerMethodField()
    commission_rate = serializers.SerializerMethodField()
    insurance_rate = serializers.SerializerMethodField()
    amortization_system = serializers.SerializerMethodField()
    requires_guarantor = serializers.SerializerMethodField()
    auto_approval_enabled = serializers.SerializerMethodField()
    min_credit_score = serializers.SerializerMethodField()
    
    # Incluir detalles completos para mobile
    selected_parameter_detail = CreditProductParameterSerializer(source='selected_parameter', read_only=True)
    
    class Meta:
        model = CreditProduct
        fields = [
            'id',
            'name',
            'code',
            'product_type',
            'product_type_detail',
            'rule_set',
            'rule_set_detail',
            'description',
            'is_active',
            'display_order',
            'icon',
            'color',
            'has_parameters',
            'documents_count',
            # Campos de compatibilidad mobile
            'min_amount',
            'max_amount',
            'interest_rate',
            'interest_type',
            'min_term_months',
            'max_term_months',
            'commission_rate',
            'insurance_rate',
            'amortization_system',
            'requires_guarantor',
            'auto_approval_enabled',
            'min_credit_score',
            'selected_parameter_detail',
            'created_at',
        ]
    
    def get_has_parameters(self, obj):
        """Indica si el producto tiene parámetros configurados."""
        return obj.selected_parameter is not None
    
    def get_documents_count(self, obj):
        """Cuenta los documentos requeridos del producto."""
        return obj.document_requirements_config.count()
    
    def get_min_amount(self, obj):
        """Obtiene el monto mínimo del parámetro seleccionado."""
        if obj.selected_parameter:
            return str(obj.selected_parameter.min_amount)
        return "0"
    
    def get_max_amount(self, obj):
        """Obtiene el monto máximo del parámetro seleccionado."""
        if obj.selected_parameter:
            return str(obj.selected_parameter.max_amount)
        return "0"
    
    def get_interest_rate(self, obj):
        """Obtiene la tasa de interés (puede ser rango)."""
        if obj.selected_parameter:
            min_rate = obj.selected_parameter.min_interest_rate
            max_rate = obj.selected_parameter.max_interest_rate
            if min_rate == max_rate:
                return str(min_rate)
            return f"{min_rate} - {max_rate}"
        return "0"
    
    def get_interest_type(self, obj):
        """Obtiene el tipo de interés."""
        if obj.selected_parameter:
            return obj.selected_parameter.interest_type
        return "FIXED"
    
    def get_min_term_months(self, obj):
        """Obtiene el plazo mínimo en meses."""
        if obj.selected_parameter:
            return obj.selected_parameter.min_term_months
        return 0
    
    def get_max_term_months(self, obj):
        """Obtiene el plazo máximo en meses."""
        if obj.selected_parameter:
            return obj.selected_parameter.max_term_months
        return 0
    
    def get_commission_rate(self, obj):
        """Obtiene la tasa de comisión (puede ser rango)."""
        if obj.selected_parameter:
            min_rate = obj.selected_parameter.commission_rate_min or 0
            max_rate = obj.selected_parameter.commission_rate_max or 0
            if min_rate == max_rate:
                return str(min_rate)
            return f"{min_rate} - {max_rate}"
        return "0"
    
    def get_insurance_rate(self, obj):
        """Obtiene la tasa de seguro (puede ser rango)."""
        if obj.selected_parameter:
            min_rate = obj.selected_parameter.insurance_rate_min or 0
            max_rate = obj.selected_parameter.insurance_rate_max or 0
            if min_rate == max_rate:
                return str(min_rate)
            return f"{min_rate} - {max_rate}"
        return "0"
    
    def get_amortization_system(self, obj):
        """Obtiene el sistema de amortización por defecto."""
        if obj.selected_parameter and obj.selected_parameter.allowed_amortization_systems.exists():
            # Retornar el primer sistema permitido
            first_system = obj.selected_parameter.allowed_amortization_systems.first()
            return first_system.code if first_system else "FRENCH"
        return "FRENCH"
    
    def get_requires_guarantor(self, obj):
        """Indica si requiere garante."""
        if obj.selected_parameter:
            return obj.selected_parameter.requires_guarantor
        return False
    
    def get_auto_approval_enabled(self, obj):
        """Indica si tiene aprobación automática habilitada."""
        if obj.selected_parameter:
            return obj.selected_parameter.auto_approval_enabled
        return False
    
    def get_min_credit_score(self, obj):
        """Obtiene el score mínimo requerido."""
        if obj.selected_parameter:
            return obj.selected_parameter.min_credit_score_required
        return None


class ProductCalculationRequestSerializer(serializers.Serializer):
    """Serializer para solicitud de cálculo de producto."""
    
    amount = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal('0.01'))
    term_months = serializers.IntegerField(min_value=1)
    interest_rate = serializers.DecimalField(max_digits=5, decimal_places=2, required=False, allow_null=True)
    commission_rate = serializers.DecimalField(max_digits=5, decimal_places=2, required=False, allow_null=True)
    insurance_rate = serializers.DecimalField(max_digits=5, decimal_places=2, required=False, allow_null=True)
    amortization_system = serializers.CharField(max_length=20, required=False, allow_null=True)


class ProductCalculationResponseSerializer(serializers.Serializer):
    """Serializer para respuesta de cálculo de producto."""
    
    monthly_payment = serializers.DecimalField(max_digits=12, decimal_places=2)
    total_payments = serializers.DecimalField(max_digits=12, decimal_places=2)
    total_interest = serializers.DecimalField(max_digits=12, decimal_places=2)
    commission = serializers.DecimalField(max_digits=12, decimal_places=2)
    insurance_cost = serializers.DecimalField(max_digits=12, decimal_places=2)
    total_cost = serializers.DecimalField(max_digits=12, decimal_places=2)


class ProductRequirementSerializer(serializers.ModelSerializer):
    """Serializer para requisitos de productos."""
    
    class Meta:
        model = ProductRequirement
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at']
