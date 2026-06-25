"""
Serializers para CU-07: Timeline y Seguimiento
"""

from rest_framework import serializers
from api.loans.models import LoanApplicationStatusHistory, LoanApplication


class TimelineEventSerializer(serializers.ModelSerializer):
    """Serializer para eventos del timeline"""
    
    changed_by_name = serializers.CharField(
        source='actor.get_full_name',
        read_only=True
    )
    
    is_pending_action = serializers.BooleanField(read_only=True)
    
    class Meta:
        model = LoanApplicationStatusHistory
        fields = [
            'id',
            'previous_status',
            'new_status',
            'title',
            'client_message',
            'requires_client_action',
            'action_description',
            'action_url',
            'action_completed_at',
            'is_pending_action',
            'changed_by_name',
            'created_at',
        ]
        read_only_fields = fields  # Todos son read-only


class PendingActionSerializer(serializers.ModelSerializer):
    """Serializer para acciones pendientes del cliente"""
    
    class Meta:
        model = LoanApplicationStatusHistory
        fields = [
            'id',
            'new_status',
            'action_description',
            'action_url',
            'created_at',
        ]
        read_only_fields = fields


class LoanApplicationTimelineSerializer(serializers.Serializer):
    """
    Serializer completo para el timeline de una solicitud.
    
    Incluye:
    - Información básica de la solicitud
    - Timeline de eventos
    - Acciones pendientes
    - Resumen de documentos
    """
    
    # Información básica
    application_id = serializers.IntegerField(source='id', read_only=True)
    application_number = serializers.CharField(read_only=True)
    product_name = serializers.CharField(source='product.name', read_only=True)
    requested_amount = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    status = serializers.CharField(read_only=True)
    created_at = serializers.DateTimeField(read_only=True)
    
    # Etapa actual
    current_stage = serializers.SerializerMethodField()
    
    # Timeline
    timeline = serializers.SerializerMethodField()
    
    # Acciones pendientes
    pending_actions = serializers.SerializerMethodField()
    
    # Resumen de documentos
    documents_summary = serializers.SerializerMethodField()
    
    def get_current_stage(self, obj):
        """Retorna la etapa actual"""
        return obj.get_current_stage()
    
    def get_timeline(self, obj):
        """Retorna el timeline visible para el cliente"""
        timeline = obj.get_timeline(for_client=True)
        return TimelineEventSerializer(timeline, many=True).data
    
    def get_pending_actions(self, obj):
        """Retorna las acciones pendientes"""
        pending = obj.get_pending_actions()
        return PendingActionSerializer(pending, many=True).data
    
    def get_documents_summary(self, obj):
        """Retorna el resumen de documentos"""
        checklist = obj.document_checklist.all()
        
        total = checklist.count()
        mandatory = checklist.filter(document_requirement__is_mandatory=True).count()
        uploaded = checklist.exclude(status='PENDING').count()
        approved = checklist.filter(status='APPROVED').count()
        rejected = checklist.filter(status='REJECTED').count()
        pending = checklist.filter(status='PENDING').count()
        
        mandatory_approved = checklist.filter(
            document_requirement__is_mandatory=True,
            status='APPROVED'
        ).count()
        
        is_complete = (mandatory_approved == mandatory) if mandatory > 0 else True
        completion_percentage = (mandatory_approved / mandatory * 100) if mandatory > 0 else 0
        
        return {
            'total_documents': total,
            'mandatory_documents': mandatory,
            'uploaded_documents': uploaded,
            'approved_documents': approved,
            'rejected_documents': rejected,
            'pending_documents': pending,
            'is_complete': is_complete,
            'completion_percentage': round(completion_percentage, 2)
        }


class LoanApplicationListSerializer(serializers.Serializer):
    """
    Serializer para lista de solicitudes del cliente.
    
    Vista resumida para mostrar en lista.
    """
    
    id = serializers.IntegerField(read_only=True)
    application_number = serializers.CharField(read_only=True)
    product_name = serializers.CharField(source='product.name', read_only=True)
    requested_amount = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    status = serializers.CharField(read_only=True)
    created_at = serializers.DateTimeField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)
    
    # Etapa actual
    current_stage = serializers.SerializerMethodField()
    
    # Indicadores
    has_pending_actions = serializers.SerializerMethodField()
    documents_complete = serializers.SerializerMethodField()
    
    def get_current_stage(self, obj):
        """Retorna la etapa actual"""
        stage = obj.get_current_stage()
        return {
            'status': stage['status'],
            'message': stage['message'],
        }
    
    def get_has_pending_actions(self, obj):
        """Indica si hay acciones pendientes"""
        return obj.get_pending_actions().exists()
    
    def get_documents_complete(self, obj):
        """Indica si los documentos están completos"""
        return obj.check_documents_complete()


__all__ = [
    'TimelineEventSerializer',
    'PendingActionSerializer',
    'LoanApplicationTimelineSerializer',
    'LoanApplicationListSerializer',
]
