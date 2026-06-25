"""
Serializers para el módulo de contratos
"""

from rest_framework import serializers
from django.contrib.auth import get_user_model
from api.contracts.models import (
    Contract,
    ContractTemplate,
    ContractSignature,
    ContractAmortizationSchedule,
    ContractDocument
)
from api.loans.models import LoanApplication
from api.products.models import CreditProduct
from api.storage.models import FileResource

User = get_user_model()


def _get_request_tenant(request):
    if not request:
        return None

    tenant = getattr(request, 'tenant', None)
    if tenant:
        return tenant

    user = getattr(request, 'user', None)
    if user and hasattr(user, 'institution'):
        return user.institution

    if user and hasattr(user, 'institution_memberships'):
        membership = user.institution_memberships.filter(is_active=True).first()
        if membership:
            return membership.institution

    return None


class ContractTemplateSerializer(serializers.ModelSerializer):
    """Serializer para plantillas de contrato"""
    
    product_name = serializers.CharField(source='product.name', read_only=True)
    contracts_count = serializers.SerializerMethodField()
    
    class Meta:
        model = ContractTemplate
        fields = [
            'id',
            'name',
            'code',
            'product',
            'product_name',
            'template_content',
            'available_variables',
            'is_active',
            'is_default',
            'requires_guarantor_signature',
            'terms_and_conditions',
            'legal_clauses',
            'description',
            'version',
            'contracts_count',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_contracts_count(self, obj):
        """Retorna el número de contratos generados con esta plantilla"""
        return obj.contracts.count()
    
    def validate_product(self, value):
        """Valida que se haya especificado un producto"""
        if value is None:
            raise serializers.ValidationError(
                "El producto crediticio es obligatorio. Cada plantilla debe estar asociada a un producto específico."
            )
        return value
    
    def validate_code(self, value):
        """Valida que el código sea único para el tenant"""
        request = self.context.get('request')
        institution = _get_request_tenant(request)
        if institution:
            
            # Si es actualización, excluir el objeto actual
            if self.instance:
                exists = ContractTemplate.objects.filter(
                    institution=institution,
                    code=value
                ).exclude(pk=self.instance.pk).exists()
            else:
                exists = ContractTemplate.objects.filter(
                    institution=institution,
                    code=value
                ).exists()
            
            if exists:
                raise serializers.ValidationError(
                    "Ya existe una plantilla con este código."
                )
        
        return value


class ContractTemplateListSerializer(serializers.ModelSerializer):
    """Serializer simplificado para listado de plantillas"""
    
    product_name = serializers.CharField(source='product.name', read_only=True)
    contracts_count = serializers.IntegerField(read_only=True)
    
    class Meta:
        model = ContractTemplate
        fields = [
            'id',
            'name',
            'code',
            'product',
            'product_name',
            'is_active',
            'is_default',
            'requires_guarantor_signature',
            'version',
            'contracts_count',
            'created_at',
        ]


class ContractSignatureSerializer(serializers.ModelSerializer):
    """Serializer para firmas de contrato"""
    
    signer_name = serializers.SerializerMethodField()
    signer_type_display = serializers.CharField(
        source='get_signer_type_display',
        read_only=True
    )
    signature_method_display = serializers.CharField(
        source='get_signature_method_display',
        read_only=True
    )
    
    class Meta:
        model = ContractSignature
        fields = [
            'id',
            'contract',
            'signer_type',
            'signer_type_display',
            'signer_name',
            'user',
            'guarantor',
            'signed_at',
            'signature_method',
            'signature_method_display',
            'signature_data',
            'ip_address',
            'device_info',
            'geolocation',
            'identity_verified',
            'verification_method',
            'notes',
            'created_at',
        ]
        read_only_fields = ['id', 'created_at']
    
    def get_signer_name(self, obj):
        """Retorna el nombre del firmante"""
        return obj.get_signer_name()


class ContractAmortizationScheduleSerializer(serializers.ModelSerializer):
    """Serializer para tabla de amortización"""

    is_overdue = serializers.BooleanField(read_only=True)
    days_overdue = serializers.IntegerField(read_only=True)

    class Meta:
        model = ContractAmortizationSchedule
        fields = [
            'id',
            'contract',
            'payment_number',
            'due_date',
            'principal_amount',
            'interest_amount',
            'insurance_amount',
            'total_payment',
            'remaining_balance',
            'is_paid',
            'paid_at',
            'paid_amount',
            'payment_reference',
            'is_overdue',
            'days_overdue',
            'notes',
            'created_at',
        ]
        read_only_fields = ['id', 'created_at', 'is_overdue', 'days_overdue']


class ContractDocumentSerializer(serializers.ModelSerializer):
    """Serializer para documentos adicionales del contrato"""
    
    file_url = serializers.SerializerMethodField()
    file_name = serializers.CharField(source='file.file_name', read_only=True)
    file_size = serializers.IntegerField(source='file.file_size', read_only=True)
    uploaded_by_name = serializers.SerializerMethodField()
    document_type_display = serializers.CharField(
        source='get_document_type_display',
        read_only=True
    )
    
    class Meta:
        model = ContractDocument
        fields = [
            'id',
            'contract',
            'document_type',
            'document_type_display',
            'title',
            'description',
            'file',
            'file_url',
            'file_name',
            'file_size',
            'uploaded_by',
            'uploaded_by_name',
            'is_required',
            'created_at',
        ]
        read_only_fields = ['id', 'created_at', 'uploaded_by']
    
    def get_file_url(self, obj):
        """Retorna la URL del archivo"""
        if obj.file:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.file.get_download_url())
        return None
    
    def get_uploaded_by_name(self, obj):
        """Retorna el nombre del usuario que subió el documento"""
        if obj.uploaded_by:
            return obj.uploaded_by.get_full_name() or obj.uploaded_by.email
        return None


class ContractSerializer(serializers.ModelSerializer):
    """Serializer completo para contratos"""
    
    # Relaciones
    loan_application_number = serializers.CharField(
        source='loan_application.application_number',
        read_only=True
    )
    client_name = serializers.SerializerMethodField()
    client_document = serializers.CharField(
        source='loan_application.client.document_number',
        read_only=True
    )
    product_name = serializers.CharField(
        source='loan_application.product.name',
        read_only=True
    )
    template_name = serializers.CharField(
        source='template.name',
        read_only=True
    )
    
    # Fechas - permitir null para evitar errores de serialización
    contract_date = serializers.DateField(allow_null=True, required=False)
    start_date = serializers.DateField(allow_null=True, required=False)
    end_date = serializers.DateField(allow_null=True, required=False)
    first_payment_date = serializers.DateField(allow_null=True, required=False)
    
    # Estado
    status_display = serializers.CharField(
        source='get_status_display',
        read_only=True
    )
    
    # Firmas
    signatures = ContractSignatureSerializer(many=True, read_only=True)
    is_signed_by_borrower = serializers.BooleanField(read_only=True)
    requires_guarantor_signatures = serializers.BooleanField(read_only=True)
    all_signatures_complete = serializers.BooleanField(read_only=True)
    pending_signatures = serializers.SerializerMethodField()
    
    # Documentos
    pdf_url = serializers.SerializerMethodField()
    additional_documents = ContractDocumentSerializer(many=True, read_only=True)
    
    # Tabla de amortización
    amortization_schedule = ContractAmortizationScheduleSerializer(
        many=True,
        read_only=True
    )
    
    # Usuarios
    generated_by_name = serializers.SerializerMethodField()
    published_by_name = serializers.SerializerMethodField()
    cancelled_by_name = serializers.SerializerMethodField()
    
    class Meta:
        model = Contract
        fields = [
            'id',
            'contract_number',
            'status',
            'status_display',
            'loan_application',
            'loan_application_number',
            'client_name',
            'client_document',
            'product_name',
            'template',
            'template_name',
            'principal_amount',
            'interest_rate',
            'term_months',
            'monthly_payment',
            'total_amount',
            'contract_date',
            'start_date',
            'end_date',
            'first_payment_date',
            'pdf_file',
            'pdf_url',
            'borrower_signed_at',
            'borrower_signature_ip',
            'borrower_signature_data',
            'is_signed_by_borrower',
            'requires_guarantor_signatures',
            'all_signatures_complete',
            'pending_signatures',
            'signatures',
            'terms_and_conditions',
            'special_clauses',
            'version',
            'generated_by',
            'generated_by_name',
            'published_by',
            'published_by_name',
            'published_at',
            'cancelled_by',
            'cancelled_by_name',
            'cancelled_at',
            'cancellation_reason',
            'notes',
            'amortization_schedule',
            'additional_documents',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'id',
            'contract_number',
            'created_at',
            'updated_at',
            'version',
        ]
    
    def get_client_name(self, obj):
        """Retorna el nombre completo del cliente"""
        return obj.loan_application.client.get_full_name()
    
    def get_pending_signatures(self, obj):
        """Retorna información sobre firmas pendientes"""
        return obj.pending_signatures
    
    def get_pdf_url(self, obj):
        """Retorna la URL del PDF del contrato"""
        if obj.pdf_file:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.pdf_file.get_download_url())
        return None
    
    def get_generated_by_name(self, obj):
        """Retorna el nombre del usuario que generó el contrato"""
        if obj.generated_by:
            return obj.generated_by.get_full_name() or obj.generated_by.email
        return None
    
    def get_published_by_name(self, obj):
        """Retorna el nombre del usuario que publicó el contrato"""
        if obj.published_by:
            return obj.published_by.get_full_name() or obj.published_by.email
        return None
    
    def get_cancelled_by_name(self, obj):
        """Retorna el nombre del usuario que canceló el contrato"""
        if obj.cancelled_by:
            return obj.cancelled_by.get_full_name() or obj.cancelled_by.email
        return None


class ContractListSerializer(serializers.ModelSerializer):
    """Serializer simplificado para listado de contratos"""
    
    loan_application_number = serializers.CharField(
        source='loan_application.application_number',
        read_only=True
    )
    client_name = serializers.SerializerMethodField()
    product_name = serializers.CharField(
        source='loan_application.product.name',
        read_only=True
    )
    status_display = serializers.CharField(
        source='get_status_display',
        read_only=True
    )
    is_signed_by_borrower = serializers.BooleanField(read_only=True)
    all_signatures_complete = serializers.BooleanField(read_only=True)
    
    # Fechas - permitir null para evitar errores de serialización
    contract_date = serializers.DateField(allow_null=True, required=False)
    
    class Meta:
        model = Contract
        fields = [
            'id',
            'contract_number',
            'status',
            'status_display',
            'loan_application',
            'loan_application_number',
            'client_name',
            'product_name',
            'principal_amount',
            'interest_rate',
            'term_months',
            'monthly_payment',
            'contract_date',
            'is_signed_by_borrower',
            'all_signatures_complete',
            'created_at',
        ]
    
    def get_client_name(self, obj):
        """Retorna el nombre completo del cliente"""
        return obj.loan_application.client.get_full_name()


class ContractCreateSerializer(serializers.Serializer):
    """Serializer para crear un contrato desde una solicitud aprobada"""
    
    loan_application_id = serializers.IntegerField(required=True)
    template_id = serializers.IntegerField(required=False, allow_null=True)
    contract_date = serializers.DateField(required=False, allow_null=True)
    start_date = serializers.DateField(required=False, allow_null=True)
    special_clauses = serializers.JSONField(required=False, allow_null=True)
    notes = serializers.CharField(required=False, allow_blank=True)
    
    def validate_loan_application_id(self, value):
        """Valida que la solicitud exista y esté aprobada"""
        request = self.context.get('request')
        institution = _get_request_tenant(request)
        if not institution:
            raise serializers.ValidationError("Usuario sin institución asignada.")
        
        try:
            application = LoanApplication.objects.get(
                id=value,
                institution=institution
            )
        except LoanApplication.DoesNotExist:
            raise serializers.ValidationError("Solicitud no encontrada.")
        
        # Verificar que esté aprobada
        if application.status != LoanApplication.Status.APPROVED:
            raise serializers.ValidationError(
                "La solicitud debe estar en estado APPROVED para generar un contrato."
            )
        
        # Verificar que no tenga ya un contrato
        if hasattr(application, 'contract'):
            raise serializers.ValidationError(
                "Esta solicitud ya tiene un contrato generado."
            )
        
        return value
    
    def validate_template_id(self, value):
        """Valida que la plantilla exista y esté activa"""
        if value is None:
            return value
        
        request = self.context.get('request')
        institution = _get_request_tenant(request)
        if not institution:
            raise serializers.ValidationError("Usuario sin institución asignada.")
        
        try:
            template = ContractTemplate.objects.get(
                id=value,
                institution=institution
            )
        except ContractTemplate.DoesNotExist:
            raise serializers.ValidationError("Plantilla no encontrada.")
        
        if not template.is_active:
            raise serializers.ValidationError("La plantilla no está activa.")
        
        return value


class ContractSignSerializer(serializers.Serializer):
    """Serializer para firmar un contrato"""
    
    signature_method = serializers.ChoiceField(
        choices=ContractSignature.SignatureMethod.choices,
        default=ContractSignature.SignatureMethod.DIGITAL,
        required=False
    )
    signature_data = serializers.CharField(required=True, allow_blank=False)
    device_info = serializers.JSONField(required=False, allow_null=True, default=dict)
    geolocation = serializers.JSONField(required=False, allow_null=True, default=dict)
    verification_method = serializers.CharField(required=False, allow_blank=True, default='')
    
    def validate_signature_data(self, value):
        """Valida que los datos de firma no estén vacíos"""
        if not value or not value.strip():
            raise serializers.ValidationError(
                "Los datos de firma son requeridos."
            )
        return value.strip()
    
    def validate_device_info(self, value):
        """Valida y normaliza device_info"""
        if value is None:
            return {}
        if not isinstance(value, dict):
            raise serializers.ValidationError("device_info debe ser un objeto JSON")
        return value
    
    def validate_geolocation(self, value):
        """Valida y normaliza geolocation"""
        if value is None:
            return {}
        if not isinstance(value, dict):
            raise serializers.ValidationError("geolocation debe ser un objeto JSON")
        return value
