"""
Serializers para CU-11: Gestionar Originación de Créditos

Proporciona serializers para:
- Crear solicitudes de crédito
- Actualizar borradores
- Enviar solicitudes
- Cambiar estados
- Listar y ver detalles
- Timeline y comentarios
"""

from rest_framework import serializers
from django.contrib.auth import get_user_model
from decimal import Decimal

from ..models import (
    LoanApplication,
    LoanApplicationStatusHistory,
    LoanApplicationComment,
    LoanApplicationDocument,
)
from api.clients.serializers import ClientListSerializer
from api.products.serializers import CreditProductListSerializer

User = get_user_model()


class LoanApplicationStatusHistorySerializer(serializers.ModelSerializer):
    """Serializer para el historial de estados"""
    actor_name = serializers.CharField(source='actor.get_full_name', read_only=True)
    
    class Meta:
        model = LoanApplicationStatusHistory
        fields = [
            'id', 'previous_status', 'new_status', 'title', 'description',
            'actor', 'actor_name', 'actor_role', 'is_visible_to_borrower',
            'metadata', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']


class LoanApplicationCommentSerializer(serializers.ModelSerializer):
    """Serializer para comentarios"""
    user_name = serializers.CharField(source='user.get_full_name', read_only=True)
    user_email = serializers.EmailField(source='user.email', read_only=True)
    
    class Meta:
        model = LoanApplicationComment
        fields = [
            'id', 'user', 'user_name', 'user_email', 'comment',
            'is_internal', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'user', 'created_at', 'updated_at']


class LoanApplicationDocumentSerializer(serializers.ModelSerializer):
    """Serializer para documentos"""
    uploaded_by_name = serializers.CharField(
        source='uploaded_by.get_full_name', read_only=True
    )
    file_url = serializers.SerializerMethodField()
    
    class Meta:
        model = LoanApplicationDocument
        fields = [
            'id', 'document_type', 'file', 'file_url', 'file_name', 'file_size',
            'description', 'uploaded_by', 'uploaded_by_name', 'is_verified',
            'verified_by', 'verified_at', 'created_at'
        ]
        read_only_fields = ['id', 'file_size', 'created_at']
    
    def get_file_url(self, obj):
        if obj.file:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.file.url)
        return None


class CreditApplicationCreateSerializer(serializers.Serializer):
    """Serializer para crear una solicitud en borrador"""
    product_id = serializers.IntegerField()
    requested_amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    term_months = serializers.IntegerField()
    purpose = serializers.CharField(required=True)
    monthly_income = serializers.DecimalField(max_digits=12, decimal_places=2, required=False, allow_null=True)
    employment_type = serializers.ChoiceField(
        choices=LoanApplication.EmploymentType.choices,
        required=False,
        allow_null=True
    )
    employment_description = serializers.CharField(required=False, allow_blank=True)
    branch_id = serializers.IntegerField(required=False, allow_null=True)
    additional_data = serializers.JSONField(required=False, default=dict)
    
    def validate_requested_amount(self, value):
        """Validar que el monto es positivo"""
        if value <= 0:
            raise serializers.ValidationError("El monto debe ser mayor a cero")
        return value
    
    def validate_term_months(self, value):
        """Validar que el plazo es positivo"""
        if value <= 0:
            raise serializers.ValidationError("El plazo debe ser mayor a cero")
        if value > 360:
            raise serializers.ValidationError("El plazo no puede exceder 360 meses")
        return value
    
    def validate_purpose(self, value):
        """Validar que el propósito no esté vacío"""
        if not value or not value.strip():
            raise serializers.ValidationError("El propósito del crédito es requerido")
        return value


class CreditApplicationUpdateDraftSerializer(serializers.Serializer):
    """Serializer para actualizar un borrador"""
    product_id = serializers.IntegerField(required=False)
    requested_amount = serializers.DecimalField(
        max_digits=12, decimal_places=2, required=False
    )
    term_months = serializers.IntegerField(required=False)
    purpose = serializers.CharField(required=False)
    monthly_income = serializers.DecimalField(
        max_digits=12, decimal_places=2, required=False, allow_null=True
    )
    employment_type = serializers.ChoiceField(
        choices=LoanApplication.EmploymentType.choices,
        required=False,
        allow_null=True
    )
    employment_description = serializers.CharField(required=False, allow_blank=True)
    branch_id = serializers.IntegerField(required=False, allow_null=True)
    additional_data = serializers.JSONField(required=False)
    
    def validate_requested_amount(self, value):
        if value is not None and value <= 0:
            raise serializers.ValidationError("El monto debe ser mayor a cero")
        return value
    
    def validate_term_months(self, value):
        if value is not None:
            if value <= 0:
                raise serializers.ValidationError("El plazo debe ser mayor a cero")
            if value > 360:
                raise serializers.ValidationError("El plazo no puede exceder 360 meses")
        return value


class CreditApplicationSubmitSerializer(serializers.Serializer):
    """Serializer para enviar una solicitud"""
    # No campos adicionales requeridos, se envía solo con el ID
    pass


class CreditApplicationChangeStatusSerializer(serializers.Serializer):
    """Serializer para cambiar el estado de una solicitud"""
    new_status = serializers.ChoiceField(
        choices=[
            LoanApplication.Status.IN_REVIEW,
            LoanApplication.Status.OBSERVED,
            LoanApplication.Status.APPROVED,
            LoanApplication.Status.REJECTED,
            LoanApplication.Status.CANCELLED,
            LoanApplication.Status.SUBMITTED,
        ]
    )
    reason = serializers.CharField(required=False, allow_blank=True)
    approved_amount = serializers.DecimalField(
        max_digits=12, decimal_places=2, required=False, allow_null=True
    )
    approved_term_months = serializers.IntegerField(required=False, allow_null=True)
    approved_interest_rate = serializers.DecimalField(
        max_digits=5, decimal_places=2, required=False, allow_null=True
    )


class CreditApplicationListSerializer(serializers.ModelSerializer):
    """Serializer optimizado para listar solicitudes"""
    client_name = serializers.CharField(source='client.user.get_full_name', read_only=True)
    product_name = serializers.CharField(source='product.name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    assigned_to_name = serializers.CharField(
        source='assigned_to.get_full_name', read_only=True, allow_null=True
    )
    
    class Meta:
        model = LoanApplication
        fields = [
            'id', 'application_number', 'client_name', 'product_name',
            'requested_amount', 'term_months', 'status', 'status_display',
            'submitted_at', 'identity_verification_status', 'assigned_to',
            'assigned_to_name', 'created_at', 'updated_at'
        ]
        read_only_fields = fields


class CreditApplicationDetailSerializer(serializers.ModelSerializer):
    """Serializer completo para ver detalles de una solicitud"""
    client = ClientListSerializer(read_only=True)
    product = CreditProductListSerializer(read_only=True)
    product_name = serializers.CharField(source='product.name', read_only=True)
    client_name = serializers.CharField(source='client.user.get_full_name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    identity_verification_display = serializers.CharField(
        source='get_identity_verification_status_display', read_only=True
    )
    documents_status_display = serializers.CharField(
        source='get_documents_status_display', read_only=True
    )
    employment_type_display = serializers.CharField(
        source='get_employment_type_display', read_only=True, allow_null=True
    )
    assigned_to_name = serializers.CharField(
        source='assigned_to.get_full_name', read_only=True, allow_null=True
    )
    reviewed_by_name = serializers.CharField(
        source='reviewed_by.get_full_name', read_only=True, allow_null=True
    )
    approved_by_name = serializers.CharField(
        source='approved_by.get_full_name', read_only=True, allow_null=True
    )
    created_by_name = serializers.CharField(
        source='created_by.get_full_name', read_only=True, allow_null=True
    )
    updated_by_name = serializers.CharField(
        source='updated_by.get_full_name', read_only=True, allow_null=True
    )
    timeline = serializers.SerializerMethodField()
    comments = serializers.SerializerMethodField()
    documents = serializers.SerializerMethodField()
    identity_verification_id = serializers.SerializerMethodField()
    identity_verification_details = serializers.SerializerMethodField()
    product_workflow_stages = serializers.SerializerMethodField()
    current_workflow_stage = serializers.SerializerMethodField()
    risk_level_display = serializers.CharField(source='get_risk_level_display', read_only=True, allow_null=True)
    
    class Meta:
        model = LoanApplication
        fields = [
            'id', 'application_number', 'client', 'client_name', 'product', 'product_name', 'branch',
            'requested_amount', 'term_months', 'purpose', 'monthly_income',
            'employment_type', 'employment_type_display', 'employment_description',
            'additional_data', 'status', 'status_display',
            'identity_verification_status', 'identity_verification_display',
            'documents_status', 'documents_status_display',
            'credit_score', 'risk_level', 'risk_level_display', 'debt_to_income_ratio',
            'approved_amount', 'approved_term_months', 'approved_interest_rate',
            'monthly_payment', 'assigned_to', 'assigned_to_name',
            'reviewed_by', 'reviewed_by_name', 'approved_by', 'approved_by_name',
            'created_by', 'created_by_name', 'updated_by', 'updated_by_name',
            'notes', 'internal_notes', 'observation_reason', 'rejection_reason',
            'submitted_at', 'reviewed_at', 'approved_at', 'rejected_at',
            'disbursed_at', 'created_at', 'updated_at',
            'identity_verification_id', 'identity_verification_details',
            'product_workflow_stages', 'current_workflow_stage',
            'timeline', 'comments', 'documents'
        ]
        read_only_fields = fields
    
    def get_timeline(self, obj):
        """Obtener timeline de la solicitud"""
        request = self.context.get('request')
        is_borrower = False
        if request and request.user:
            is_borrower = (obj.client.user_id == request.user.id)
        
        events = obj.status_history.all()
        if is_borrower:
            events = events.filter(is_visible_to_borrower=True)
        
        return LoanApplicationStatusHistorySerializer(
            events, many=True, context=self.context
        ).data
    
    def get_comments(self, obj):
        """Obtener comentarios visibles para el usuario"""
        request = self.context.get('request')
        comments = obj.comments.all()
        
        if request and request.user:
            is_borrower = (obj.client.user_id == request.user.id)
            if is_borrower:
                # El prestatario solo ve comentarios no internos
                comments = comments.filter(is_internal=False)
        
        return LoanApplicationCommentSerializer(
            comments, many=True, context=self.context
        ).data
    
    def get_documents(self, obj):
        """Obtener documentos"""
        return LoanApplicationDocumentSerializer(
            obj.documents.all(), many=True, context=self.context
        ).data

    def get_identity_verification_id(self, obj):
        """Obtener ID de la última verificación de identidad"""
        latest = obj.identity_verifications.order_by('-created_at').first()
        return latest.id if latest else None
    
    def get_identity_verification_details(self, obj):
        """Obtener detalles de la última verificación de identidad"""
        latest = obj.identity_verifications.order_by('-created_at').first()
        if not latest:
            return None
        
        return {
            'id': latest.id,
            'status': latest.status,
            'decision': latest.decision,
            'document_type': latest.document_type,
            'document_number': latest.document_number,
            'full_name': latest.full_name,
            'date_of_birth': latest.date_of_birth.isoformat() if latest.date_of_birth else None,
            'country': latest.country,
            'provider': latest.provider,
            'completed_at': latest.completed_at.isoformat() if latest.completed_at else None,
            'created_at': latest.created_at.isoformat(),
        }
    
    def get_product_workflow_stages(self, obj):
        """Obtener las etapas de workflow del producto asociado"""
        if obj.product and obj.product.rule_set:
            stages = obj.product.get_workflow_stages()
            if stages.exists():
                from api.loans.serializers.rule_serializers import WorkflowStageDefinitionSerializer
                return WorkflowStageDefinitionSerializer(stages, many=True).data
        return []
    
    def get_current_workflow_stage(self, obj):
        """
        Determinar la etapa actual del workflow basada en el estado de la solicitud.
        
        Busca directamente en el workflow del producto una etapa cuyo stage_code
        coincida con el estado actual de la solicitud. Esto permite workflows
        personalizados por producto sin necesidad de mapeos estáticos.
        """
        if not obj.product or not obj.product.rule_set:
            return None
        
        # Obtener el estado actual de la solicitud
        current_status = obj.status
        
        # Buscar la etapa en el workflow del producto que coincida con el estado actual
        stages = obj.product.get_workflow_stages()
        stage = stages.filter(stage_code=current_status).first()
        
        if stage:
            from api.loans.serializers.rule_serializers import WorkflowStageDefinitionSerializer
            return WorkflowStageDefinitionSerializer(stage).data
        
        return None


class CreditApplicationBorrowerListSerializer(serializers.ModelSerializer):
    """Serializer para listar solicitudes del prestatario"""
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    product_name = serializers.CharField(source='product.name', read_only=True)
    client_name = serializers.CharField(source='client.user.get_full_name', read_only=True)
    identity_verification_display = serializers.CharField(
        source='get_identity_verification_status_display', read_only=True
    )
    
    class Meta:
        model = LoanApplication
        fields = [
            'id', 'application_number', 'client_name', 'product_name', 'requested_amount',
            'term_months', 'purpose', 'status', 'status_display',
            'identity_verification_status', 'identity_verification_display',
            'submitted_at', 'approved_at', 'rejected_at', 'created_at', 'updated_at'
        ]
        read_only_fields = fields
