"""
Serializers para el sistema de aprobaciones y ejecución de workflows.

SPRINT 1 - CU-16: Diseñar Flujos de Aprobación
"""

from rest_framework import serializers
from api.loans.models_approval import (
    WorkflowExecution,
    WorkflowStageExecution,
    ApprovalDecision,
)
from api.loans.models_rules import WorkflowStageDefinition


class UserBasicSerializer(serializers.Serializer):
    """Serializer básico para información de usuario."""
    id = serializers.IntegerField(read_only=True)
    email = serializers.EmailField(read_only=True)
    first_name = serializers.CharField(read_only=True)
    last_name = serializers.CharField(read_only=True)
    
    def to_representation(self, instance):
        if instance is None:
            return None
        return {
            'id': instance.id,
            'email': instance.email,
            'first_name': instance.first_name,
            'last_name': instance.last_name,
            'full_name': instance.get_full_name() if hasattr(instance, 'get_full_name') else f"{instance.first_name} {instance.last_name}"
        }


class WorkflowStageDefinitionBasicSerializer(serializers.ModelSerializer):
    """Serializer básico para WorkflowStageDefinition (para evitar importaciones circulares)."""
    
    class Meta:
        model = WorkflowStageDefinition
        fields = [
            'id',
            'stage_name',
            'stage_code',
            'stage_order',
            'time_limit_hours',
            'is_automated',
            'requires_manual_approval',
        ]
        read_only_fields = fields


class WorkflowExecutionSerializer(serializers.ModelSerializer):
    """
    Serializer para WorkflowExecution.
    
    Incluye información completa de la ejecución del workflow.
    """
    
    current_stage_detail = WorkflowStageDefinitionBasicSerializer(
        source='current_stage',
        read_only=True
    )
    
    status_display = serializers.CharField(
        source='get_status_display',
        read_only=True
    )
    
    # Campos calculados
    is_completed = serializers.SerializerMethodField()
    is_in_progress = serializers.SerializerMethodField()
    duration_hours = serializers.SerializerMethodField()
    progress_percentage = serializers.SerializerMethodField()
    
    class Meta:
        model = WorkflowExecution
        fields = [
            'id',
            'loan_application',
            'rule_set',
            'current_stage',
            'current_stage_detail',
            'started_at',
            'completed_at',
            'status',
            'status_display',
            'total_stages_completed',
            'total_time_seconds',
            'execution_data',
            'is_completed',
            'is_in_progress',
            'duration_hours',
            'progress_percentage',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'id',
            'started_at',
            'completed_at',
            'total_time_seconds',
            'created_at',
            'updated_at',
        ]
    
    def get_is_completed(self, obj):
        """Verifica si el workflow está completado."""
        return obj.status == 'COMPLETED'
    
    def get_is_in_progress(self, obj):
        """Verifica si el workflow está en progreso."""
        return obj.status == 'IN_PROGRESS'
    
    def get_duration_hours(self, obj):
        """Calcula la duración en horas."""
        if obj.total_time_seconds:
            return round(obj.total_time_seconds / 3600, 2)
        return None
    
    def get_progress_percentage(self, obj):
        """Calcula el porcentaje de progreso basado en etapas completadas."""
        if not obj.rule_set:
            return 0
        
        total_stages = obj.rule_set.workflow_stages.count()
        if total_stages == 0:
            return 0
        
        return round((obj.total_stages_completed / total_stages) * 100, 2)


class WorkflowStageExecutionSerializer(serializers.ModelSerializer):
    """
    Serializer para WorkflowStageExecution.
    
    Incluye información detallada de la ejecución de una etapa.
    """
    
    stage_definition_detail = WorkflowStageDefinitionBasicSerializer(
        source='stage_definition',
        read_only=True
    )
    
    assigned_to_detail = UserBasicSerializer(
        source='assigned_to',
        read_only=True
    )
    
    completed_by_detail = UserBasicSerializer(
        source='completed_by',
        read_only=True
    )
    
    escalated_to_detail = UserBasicSerializer(
        source='escalated_to',
        read_only=True
    )
    
    status_display = serializers.CharField(
        source='get_status_display',
        read_only=True
    )
    
    outcome_display = serializers.CharField(
        source='get_outcome_display',
        read_only=True
    )
    
    # Campos calculados
    is_overdue = serializers.SerializerMethodField()
    time_remaining_hours = serializers.SerializerMethodField()
    duration_hours = serializers.SerializerMethodField()
    is_completed = serializers.SerializerMethodField()
    
    class Meta:
        model = WorkflowStageExecution
        fields = [
            'id',
            'workflow_execution',
            'stage_definition',
            'stage_definition_detail',
            'entered_at',
            'completed_at',
            'time_spent_seconds',
            'status',
            'status_display',
            'outcome',
            'outcome_display',
            'assigned_to',
            'assigned_to_detail',
            'completed_by',
            'completed_by_detail',
            'is_escalated',
            'escalated_at',
            'escalated_to',
            'escalated_to_detail',
            'escalation_reason',
            'decision_notes',
            'decision_data',
            'is_overdue',
            'time_remaining_hours',
            'duration_hours',
            'is_completed',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'id',
            'entered_at',
            'completed_at',
            'time_spent_seconds',
            'created_at',
            'updated_at',
        ]
    
    def get_is_overdue(self, obj):
        """Verifica si la etapa está vencida."""
        return obj.is_overdue()
    
    def get_time_remaining_hours(self, obj):
        """Obtiene las horas restantes antes del SLA."""
        return obj.get_time_remaining_hours()
    
    def get_duration_hours(self, obj):
        """Calcula la duración en horas."""
        if obj.time_spent_seconds:
            return round(obj.time_spent_seconds / 3600, 2)
        return None
    
    def get_is_completed(self, obj):
        """Verifica si la etapa está completada."""
        return obj.status == 'COMPLETED'


class WorkflowStageExecutionListSerializer(serializers.ModelSerializer):
    """
    Serializer simplificado para listar ejecuciones de etapas.
    """
    
    stage_name = serializers.CharField(
        source='stage_definition.stage_name',
        read_only=True
    )
    
    stage_code = serializers.CharField(
        source='stage_definition.stage_code',
        read_only=True
    )
    
    assigned_to_name = serializers.CharField(
        source='assigned_to.get_full_name',
        read_only=True
    )
    
    status_display = serializers.CharField(
        source='get_status_display',
        read_only=True
    )
    
    is_overdue = serializers.SerializerMethodField()
    
    class Meta:
        model = WorkflowStageExecution
        fields = [
            'id',
            'stage_name',
            'stage_code',
            'entered_at',
            'completed_at',
            'status',
            'status_display',
            'assigned_to',
            'assigned_to_name',
            'is_escalated',
            'is_overdue',
        ]
        read_only_fields = fields
    
    def get_is_overdue(self, obj):
        """Verifica si la etapa está vencida."""
        return obj.is_overdue()


class ApprovalDecisionSerializer(serializers.ModelSerializer):
    """
    Serializer para ApprovalDecision.
    
    Incluye información completa de la decisión de aprobación.
    """
    
    decided_by_detail = UserBasicSerializer(
        source='decided_by',
        read_only=True
    )
    
    decision_display = serializers.CharField(
        source='get_decision_display',
        read_only=True
    )
    
    stage_name = serializers.CharField(
        source='stage_execution.stage_definition.stage_name',
        read_only=True
    )
    
    has_approved_terms = serializers.SerializerMethodField()
    
    class Meta:
        model = ApprovalDecision
        fields = [
            'id',
            'loan_application',
            'stage_execution',
            'stage_name',
            'decision',
            'decision_display',
            'decided_by',
            'decided_by_detail',
            'decided_at',
            'reason',
            'notes',
            'approved_amount',
            'approved_term_months',
            'approved_interest_rate',
            'conditions',
            'decision_metadata',
            'has_approved_terms',
            'created_at',
        ]
        read_only_fields = [
            'id',
            'decided_at',
            'created_at',
        ]
    
    def get_has_approved_terms(self, obj):
        """Verifica si la decisión incluye términos aprobados."""
        return obj.has_approved_terms()
    
    def validate(self, data):
        """Validaciones personalizadas."""
        decision = data.get('decision')
        
        # Si es aprobación, validar que tenga términos aprobados
        if decision == 'APPROVED':
            if not any([
                data.get('approved_amount'),
                data.get('approved_term_months'),
                data.get('approved_interest_rate')
            ]):
                raise serializers.ValidationError(
                    "Una decisión de aprobación debe incluir al menos un término aprobado "
                    "(monto, plazo o tasa de interés)."
                )
        
        # Si es rechazo, validar que tenga motivo
        if decision == 'REJECTED' and not data.get('reason'):
            raise serializers.ValidationError(
                "Una decisión de rechazo debe incluir un motivo."
            )
        
        return data


class ApprovalDecisionCreateSerializer(serializers.ModelSerializer):
    """
    Serializer para crear decisiones de aprobación.
    
    Simplificado para el proceso de creación.
    """
    
    class Meta:
        model = ApprovalDecision
        fields = [
            'loan_application',
            'stage_execution',
            'decision',
            'reason',
            'notes',
            'approved_amount',
            'approved_term_months',
            'approved_interest_rate',
            'conditions',
            'decision_metadata',
        ]
    
    def validate(self, data):
        """Validaciones personalizadas."""
        decision = data.get('decision')
        
        # Si es aprobación, validar que tenga términos aprobados
        if decision == 'APPROVED':
            if not any([
                data.get('approved_amount'),
                data.get('approved_term_months'),
                data.get('approved_interest_rate')
            ]):
                raise serializers.ValidationError(
                    "Una decisión de aprobación debe incluir al menos un término aprobado."
                )
        
        # Si es rechazo, validar que tenga motivo
        if decision == 'REJECTED' and not data.get('reason'):
            raise serializers.ValidationError(
                "Una decisión de rechazo debe incluir un motivo."
            )
        
        return data


class ApprovalDecisionListSerializer(serializers.ModelSerializer):
    """
    Serializer simplificado para listar decisiones de aprobación.
    """
    
    decided_by_name = serializers.CharField(
        source='decided_by.get_full_name',
        read_only=True
    )
    
    decision_display = serializers.CharField(
        source='get_decision_display',
        read_only=True
    )
    
    application_number = serializers.CharField(
        source='loan_application.application_number',
        read_only=True
    )
    
    client_name = serializers.CharField(
        source='loan_application.client.full_name',
        read_only=True
    )
    
    class Meta:
        model = ApprovalDecision
        fields = [
            'id',
            'loan_application',
            'application_number',
            'client_name',
            'decision',
            'decision_display',
            'decided_by',
            'decided_by_name',
            'decided_at',
            'approved_amount',
            'reason',
        ]
        read_only_fields = fields


class WorkflowExecutionDetailSerializer(WorkflowExecutionSerializer):
    """
    Serializer detallado para WorkflowExecution.
    
    Incluye las ejecuciones de etapas relacionadas.
    """
    
    stage_executions = WorkflowStageExecutionListSerializer(
        many=True,
        read_only=True
    )
    
    class Meta(WorkflowExecutionSerializer.Meta):
        fields = WorkflowExecutionSerializer.Meta.fields + ['stage_executions']
