"""
Servicio de cola de aprobaciones (ApprovalQueueService).

SPRINT 2 - CU-16: Diseñar Flujos de Aprobación

Gestiona la cola de aprobaciones para cada usuario/rol.
"""

from django.db.models import Q, Count, Avg, F, ExpressionWrapper, DurationField
from django.utils import timezone
from typing import Dict, List, Optional
import logging

from api.loans.models import LoanApplication
from api.loans.models_approval import WorkflowStageExecution, ApprovalDecision

logger = logging.getLogger(__name__)


class ApprovalQueueService:
    """
    Servicio para gestionar la cola de aprobaciones.
    
    Proporciona métodos para:
    - Obtener solicitudes pendientes de aprobación
    - Filtrar por rol, prioridad, SLA
    - Asignar solicitudes a usuarios
    - Calcular métricas de la cola
    """
    
    @staticmethod
    def get_pending_approvals(user, role=None, institution_id=None):
        """
        Obtiene solicitudes pendientes de aprobación para un usuario.
        
        Busca WorkflowStageExecution que:
        - Estén en estado PENDING o IN_PROGRESS
        - Estén asignadas al usuario O al rol del usuario
        - No estén completadas
        
        Args:
            user: Usuario
            role: Rol específico (opcional)
            institution_id: ID de institución (opcional)
            
        Returns:
            QuerySet de WorkflowStageExecution
        """
        logger.info(
            f"[APPROVAL_QUEUE] Obteniendo cola de aprobaciones para usuario {user.id}"
        )
        
        # Filtro base: etapas en progreso que requieren aprobación manual
        queryset = WorkflowStageExecution.objects.filter(
            status__in=['PENDING', 'IN_PROGRESS'],
            stage_definition__requires_manual_approval=True
        ).select_related(
            'workflow_execution__loan_application__client',
            'workflow_execution__loan_application__product',
            'stage_definition',
            'assigned_to'
        ).prefetch_related(
            'workflow_execution__loan_application__approval_decisions'
        )
        
        # Filtrar por institución
        if institution_id:
            queryset = queryset.filter(institution_id=institution_id)
        elif hasattr(user, 'institution'):
            queryset = queryset.filter(institution=user.institution)
        
        # Filtrar por asignación
        # Incluir: asignadas directamente al usuario O asignadas al rol del usuario O sin asignar
        role_filter = Q()
        
        if role:
            # Filtrar por rol específico
            role_filter = Q(stage_definition__responsible_role=role)
        else:
            # Obtener roles del usuario
            user_roles = user.user_roles.filter(is_active=True).values_list('role_id', flat=True)
            if user_roles:
                role_filter = Q(stage_definition__responsible_role__in=user_roles)
        
        queryset = queryset.filter(
            Q(assigned_to=user) |  # Asignadas directamente
            (Q(assigned_to__isnull=True) & role_filter)  # Sin asignar pero del rol
        )
        
        # Ordenar por prioridad (SLA próximo a vencer primero)
        queryset = queryset.order_by('entered_at')
        
        logger.info(
            f"[APPROVAL_QUEUE] Encontradas {queryset.count()} solicitudes pendientes"
        )
        
        return queryset
    
    @staticmethod
    def get_my_queue(user, institution_id=None) -> Dict:
        """
        Obtiene la cola personalizada del usuario con prioridades y métricas.
        
        Agrupa las solicitudes por:
        - Urgentes (SLA < 25%)
        - Normales (SLA 25-75%)
        - Sin urgencia (SLA > 75%)
        
        Args:
            user: Usuario
            institution_id: ID de institución (opcional)
            
        Returns:
            Dict con estructura:
            {
                'urgent': QuerySet,
                'normal': QuerySet,
                'low_priority': QuerySet,
                'total_count': int,
                'metrics': Dict
            }
        """
        logger.info(
            f"[APPROVAL_QUEUE] Obteniendo cola personalizada para usuario {user.id}"
        )
        
        # Obtener todas las pendientes
        all_pending = ApprovalQueueService.get_pending_approvals(
            user=user,
            institution_id=institution_id
        )
        
        # Clasificar por urgencia
        now = timezone.now()
        urgent = []
        normal = []
        low_priority = []
        
        for stage_execution in all_pending:
            time_remaining = stage_execution.get_time_remaining_hours()
            
            if time_remaining is None:
                # Sin SLA definido
                low_priority.append(stage_execution)
                continue
            
            # Calcular porcentaje de tiempo restante
            time_limit = stage_execution.stage_definition.time_limit_hours
            time_elapsed = (now - stage_execution.entered_at).total_seconds() / 3600
            time_percentage = (time_remaining / time_limit) * 100 if time_limit > 0 else 100
            
            if time_percentage < 25:
                urgent.append(stage_execution)
            elif time_percentage < 75:
                normal.append(stage_execution)
            else:
                low_priority.append(stage_execution)
        
        # Calcular métricas
        metrics = ApprovalQueueService.get_queue_metrics(user, institution_id)
        
        result = {
            'urgent': urgent,
            'normal': normal,
            'low_priority': low_priority,
            'total_count': len(urgent) + len(normal) + len(low_priority),
            'metrics': metrics
        }
        
        logger.info(
            f"[APPROVAL_QUEUE] Cola personalizada: {len(urgent)} urgentes, "
            f"{len(normal)} normales, {len(low_priority)} baja prioridad"
        )
        
        return result
    
    @staticmethod
    def assign_to_user(stage_execution: WorkflowStageExecution, user):
        """
        Asigna una etapa a un usuario específico.
        
        Args:
            stage_execution: Ejecución de etapa
            user: Usuario al que asignar
        """
        logger.info(
            f"[APPROVAL_QUEUE] Asignando etapa {stage_execution.id} a usuario {user.id}"
        )
        
        stage_execution.assigned_to = user
        stage_execution.save(update_fields=['assigned_to'])
        
        # Crear evento en timeline
        try:
            loan_application = stage_execution.workflow_execution.loan_application
            loan_application.add_timeline_event(
                to_status=loan_application.status,  # Mantener estado
                changed_by=None,  # Sistema
                notes=f'Etapa {stage_execution.stage_definition.stage_name} asignada a {user.get_full_name()}',
                is_visible_to_client=False,
                send_notification=False
            )
        except Exception as e:
            logger.error(
                f"[APPROVAL_QUEUE] Error al crear evento de asignación: {str(e)}"
            )
        
        logger.info(
            f"[APPROVAL_QUEUE] Etapa {stage_execution.id} asignada exitosamente"
        )
    
    @staticmethod
    def get_queue_metrics(user, institution_id=None) -> Dict:
        """
        Obtiene métricas de la cola del usuario.
        
        Calcula:
        - Total de solicitudes pendientes
        - Solicitudes vencidas (SLA excedido)
        - Tiempo promedio de decisión
        - Tasa de aprobación
        
        Args:
            user: Usuario
            institution_id: ID de institución (opcional)
            
        Returns:
            Dict con métricas
        """
        logger.info(
            f"[APPROVAL_QUEUE] Calculando métricas para usuario {user.id}"
        )
        
        # Solicitudes pendientes
        pending = ApprovalQueueService.get_pending_approvals(
            user=user,
            institution_id=institution_id
        )
        
        total_pending = pending.count()
        
        # Solicitudes vencidas
        overdue_count = sum(1 for se in pending if se.is_overdue())
        
        # Decisiones del usuario (últimos 30 días)
        thirty_days_ago = timezone.now() - timezone.timedelta(days=30)
        
        decisions_filter = Q(decided_by=user, decided_at__gte=thirty_days_ago)
        if institution_id:
            decisions_filter &= Q(institution_id=institution_id)
        
        recent_decisions = ApprovalDecision.objects.filter(decisions_filter)
        
        total_decisions = recent_decisions.count()
        approved_count = recent_decisions.filter(decision='APPROVED').count()
        rejected_count = recent_decisions.filter(decision='REJECTED').count()
        
        approval_rate = (approved_count / total_decisions * 100) if total_decisions > 0 else 0
        
        # Tiempo promedio de decisión (etapas completadas por el usuario)
        completed_stages = WorkflowStageExecution.objects.filter(
            completed_by=user,
            completed_at__gte=thirty_days_ago,
            time_spent_seconds__isnull=False
        )
        
        if institution_id:
            completed_stages = completed_stages.filter(institution_id=institution_id)
        
        avg_time_seconds = completed_stages.aggregate(
            avg_time=Avg('time_spent_seconds')
        )['avg_time']
        
        avg_time_hours = round(avg_time_seconds / 3600, 2) if avg_time_seconds else 0
        
        metrics = {
            'total_pending': total_pending,
            'overdue_count': overdue_count,
            'total_decisions_30d': total_decisions,
            'approved_count_30d': approved_count,
            'rejected_count_30d': rejected_count,
            'approval_rate': round(approval_rate, 2),
            'avg_decision_time_hours': avg_time_hours,
        }
        
        logger.info(
            f"[APPROVAL_QUEUE] Métricas calculadas: {total_pending} pendientes, "
            f"{overdue_count} vencidas, {approval_rate:.1f}% aprobación"
        )
        
        return metrics
    
    @staticmethod
    def get_applications_by_status(user, status: str, institution_id=None):
        """
        Obtiene solicitudes en un estado específico asignadas al usuario.
        
        Args:
            user: Usuario
            status: Estado de la solicitud
            institution_id: ID de institución (opcional)
            
        Returns:
            QuerySet de LoanApplication
        """
        # Obtener etapas del usuario en ese estado
        stage_executions = ApprovalQueueService.get_pending_approvals(
            user=user,
            institution_id=institution_id
        ).filter(
            stage_definition__stage_code=status
        )
        
        # Extraer IDs de solicitudes
        application_ids = stage_executions.values_list(
            'workflow_execution__loan_application_id',
            flat=True
        )
        
        # Retornar solicitudes
        return LoanApplication.objects.filter(id__in=application_ids)
    
    @staticmethod
    def get_overdue_applications(user, institution_id=None) -> List[WorkflowStageExecution]:
        """
        Obtiene solicitudes vencidas (SLA excedido) del usuario.
        
        Args:
            user: Usuario
            institution_id: ID de institución (opcional)
            
        Returns:
            List de WorkflowStageExecution vencidas
        """
        pending = ApprovalQueueService.get_pending_approvals(
            user=user,
            institution_id=institution_id
        )
        
        overdue = [se for se in pending if se.is_overdue()]
        
        logger.info(
            f"[APPROVAL_QUEUE] Encontradas {len(overdue)} solicitudes vencidas "
            f"para usuario {user.id}"
        )
        
        return overdue
    
    @staticmethod
    def get_queue_by_role(role, institution_id=None):
        """
        Obtiene la cola de aprobaciones para un rol específico.
        
        Args:
            role: Rol
            institution_id: ID de institución (opcional)
            
        Returns:
            QuerySet de WorkflowStageExecution
        """
        logger.info(
            f"[APPROVAL_QUEUE] Obteniendo cola para rol {role.name}"
        )
        
        queryset = WorkflowStageExecution.objects.filter(
            status__in=['PENDING', 'IN_PROGRESS'],
            stage_definition__requires_manual_approval=True,
            stage_definition__responsible_role=role
        ).select_related(
            'workflow_execution__loan_application__client',
            'workflow_execution__loan_application__product',
            'stage_definition',
            'assigned_to'
        )
        
        if institution_id:
            queryset = queryset.filter(institution_id=institution_id)
        
        return queryset.order_by('entered_at')
