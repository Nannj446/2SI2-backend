"""
Serializers para CU-12: Gestión Documental
"""

from rest_framework import serializers
from api.loans.models_documents import (
    LoanApplicationDocumentRequirement,
    DocumentReviewHistory
)
from api.storage.serializers import FileResourceSerializer


class DocumentReviewHistorySerializer(serializers.ModelSerializer):
    """Serializer para DocumentReviewHistory (solo lectura)"""
    
    reviewed_by_name = serializers.CharField(
        source='reviewed_by.get_full_name',
        read_only=True
    )
    
    file_name = serializers.CharField(
        source='file_resource_at_review.original_filename',
        read_only=True
    )
    
    class Meta:
        model = DocumentReviewHistory
        fields = [
            'id',
            'document_requirement',
            'action',
            'reviewed_by',
            'reviewed_by_name',
            'comments',
            'file_resource_at_review',
            'file_name',
            'created_at',
        ]
        read_only_fields = fields  # Todos son read-only


class LoanApplicationDocumentRequirementSerializer(serializers.ModelSerializer):
    """Serializer para LoanApplicationDocumentRequirement"""
    
    # Información del requisito
    document_name = serializers.CharField(
        source='product_document_requirement.document_type.name',
        read_only=True
    )
    document_type = serializers.CharField(
        source='product_document_requirement.document_type.code',
        read_only=True
    )
    description = serializers.CharField(
        source='product_document_requirement.description',
        read_only=True
    )
    is_mandatory = serializers.BooleanField(
        source='product_document_requirement.is_mandatory',
        read_only=True
    )
    allowed_formats = serializers.SerializerMethodField()
    max_file_size_mb = serializers.SerializerMethodField()
    
    # Información del archivo
    file_resource_detail = FileResourceSerializer(
        source='file_resource',
        read_only=True
    )
    
    signed_url = serializers.SerializerMethodField()
    
    # Información de revisión
    uploaded_by_name = serializers.CharField(
        source='uploaded_by.get_full_name',
        read_only=True
    )
    reviewed_by_name = serializers.CharField(
        source='reviewed_by.get_full_name',
        read_only=True
    )
    
    # Información de la solicitud (para staff)
    loan_application_client_name = serializers.CharField(
        source='loan_application.client_name',
        read_only=True
    )
    loan_application_product_name = serializers.CharField(
        source='loan_application.product_name',
        read_only=True
    )
    loan_application_number = serializers.CharField(
        source='loan_application.application_number',
        read_only=True
    )
    loan_application_status = serializers.CharField(
        source='loan_application.status',
        read_only=True
    )
    
    # Historial de revisiones
    review_history = serializers.SerializerMethodField()
    
    class Meta:
        model = LoanApplicationDocumentRequirement
        fields = [
            'id',
            'loan_application',
            'product_document_requirement',
            # Info del requisito

            'document_name',
            'document_type',
            'description',
            'is_mandatory',
            'allowed_formats',
            'max_file_size_mb',
            # Estado
            'status',
            # Archivo
            'file_resource',
            'file_resource_detail',
            'signed_url',
            # Fechas y usuarios
            'uploaded_at',
            'uploaded_by',
            'uploaded_by_name',
            'reviewed_at',
            'reviewed_by',
            'reviewed_by_name',
            'rejection_reason',
            'notes',
            # Info de la solicitud (para staff)
            'loan_application_client_name',
            'loan_application_product_name', 
            'loan_application_number',
            'loan_application_status',
            # Historial
            'review_history',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'id', 'uploaded_at', 'uploaded_by', 'reviewed_at', 'reviewed_by',
            'created_at', 'updated_at'
        ]
    
    def get_signed_url(self, obj):
        """Genera URL firmada para descargar el documento"""
        return obj.get_signed_url(expires_in=3600)
    
    def get_allowed_formats(self, obj):
        """Obtiene formatos permitidos con fallback"""
        return obj.product_document_requirement.get_allowed_formats()
    
    def get_max_file_size_mb(self, obj):
        """Obtiene tamaño máximo con fallback"""
        return float(obj.product_document_requirement.get_max_file_size_mb())
    
    def get_review_history(self, obj):
        """Retorna el historial de revisiones"""
        return DocumentReviewHistorySerializer(
            obj.review_history.all()[:5],  # Últimas 5 revisiones
            many=True
        ).data


class DocumentUploadSerializer(serializers.Serializer):
    """Serializer para carga de documentos"""
    
    document_requirement_id = serializers.IntegerField(
        help_text='ID del LoanApplicationDocumentRequirement'
    )
    
    file = serializers.FileField(
        help_text='Archivo a cargar'
    )
    
    def validate(self, attrs):
        """Validaciones adicionales"""
        doc_req_id = attrs.get('document_requirement_id')
        
        try:
            doc_req = LoanApplicationDocumentRequirement.objects.get(id=doc_req_id)
        except LoanApplicationDocumentRequirement.DoesNotExist:
            raise serializers.ValidationError({
                'document_requirement_id': 'Requisito de documento no encontrado'
            })
        
        # Verificar que la solicitud esté en un estado que permita carga de documentos
        # Permitir carga en todos los estados excepto DISBURSED, CANCELLED y REJECTED
        invalid_statuses = ['DISBURSED', 'CANCELLED', 'REJECTED']
        if doc_req.loan_application.status in invalid_statuses:
            raise serializers.ValidationError(
                f"No se pueden cargar documentos en el estado actual: "
                f"{doc_req.loan_application.get_status_display()}"
            )
        
        attrs['document_requirement'] = doc_req
        
        return attrs


class DocumentReviewSerializer(serializers.Serializer):
    """Serializer para revisión de documentos por analista"""
    
    action = serializers.ChoiceField(
        choices=DocumentReviewHistory.Action.choices,
        help_text='Acción a realizar: APPROVED, REJECTED, REQUESTED_REUPLOAD'
    )
    
    comments = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text='Comentarios de la revisión'
    )
    
    def validate(self, attrs):
        """Validaciones"""
        action = attrs.get('action')
        comments = attrs.get('comments', '')
        
        # Si es rechazo o solicitud de re-carga, los comentarios son obligatorios
        if action in ['REJECTED', 'REQUESTED_REUPLOAD'] and not comments:
            raise serializers.ValidationError({
                'comments': 'Los comentarios son obligatorios para rechazos o solicitudes de re-carga'
            })
        
        return attrs


__all__ = [
    'LoanApplicationDocumentRequirementSerializer',
    'DocumentUploadSerializer',
    'DocumentReviewSerializer',
    'DocumentReviewHistorySerializer',
]
