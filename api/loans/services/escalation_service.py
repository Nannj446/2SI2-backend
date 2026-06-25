"""
Servicio de escalamiento automático (EscalationService).

SPRINT 4 - CU-16: Diseñar Flujos de Aprobación

Gestiona escalamientos automáticos por timeout.
Diseñado para ejecutarse como tarea periódica (Celery).
"""

from django.utils import timezone
from typing import List, Dict
import logging

from api.loans.models_approval import WorkflowStageExecution
from api.loans.services.workflow_engine import WorkflowEngine

logger = logging.getLogger(__name__)


class EscalationService:
    """
    Servicio para gestionar escalamientos automáticos.
    
    Detecta etapas que han excedido su SLA y las escala
    automáticamente según las reglas configuradas.
    """
    
    @staticmethod
    def check_and_escalate_all(institution_id: int = None) -> Dict:
        """
        Verifica y escala todas las etapas vencidas.
        
        Este método está diseñado para ejecutarse periódicamente
        (cada hora, por ejemplo) como tarea de Celery.
        
        Args:
            institution_id: ID de institución (opcional, para filtrar)
            
        Returns:
            Dict con estadísticas de escalamiento:
            {
                'total_checked': int,
                'escalated_count': int,
                'failed_count': int,
                'escalated_stages': List[Dict]
            }
        """
        logger.info(
            f"[ESCALATION] Iniciando verificación de escalamientos "
            f"{'para institución ' + str(institution_id) if institution_id else 'globalmente'}"
        )
        
        # Obtener etapas que deben escalarse
        overdue_stages = WorkflowEngine.check_escalations(institution_id)
        
        total_checked = len(overdue_stages)
        escalated_count = 0
        failed_count = 0
        escalated_stages = []
        
        for stage_execution in overdue_stages:
            try:
                # Escalar la etapa
                WorkflowEngine.escalate_stage(
                    stage_execution=stage_execution,
                    escalated_to=None,  # Se determina automáticamente
                    reason=f'Escalamiento automático por timeout (SLA: {stage_execution.stage_definition.time_limit_hours}h)'
                )
                
                escalated_count += 1
                
                escalated_stages.append({
                    'stage_execution_id': stage_execution.id,
                    'loan_application_id': stage_execution.workflow_execution.loan_application_id,
                    'application_number': stage_execution.workflow_execution.loan_application.application_number,
                    'stage_name': stage_execution.stage_definition.stage_name,
                    'time_overdue_hours': round(
                        (timezone.now() - stage_execution.entered_at).total_seconds() / 3600 -
                        stage_execution.stage_definition.time_limit_hours,
                        2
                    )
                })
                
                # Enviar notificación
                EscalationService._send_escalation_notification(stage_execution)
                
            except Exception as e:
                failed_count += 1
                logger.error(
                    f"[ESCALATION] Error escalando etapa {stage_execution.id}: {str(e)}",
                    exc_info=True
                )
        
        result = {
            'total_checked': total_checked,
            'escalated_count': escalated_count,
            'failed_count': failed_count,
            'escalated_stages': escalated_stages,
            'timestamp': timezone.now().isoformat()
        }
        
        logger.info(
            f"[ESCALATION] Verificación completada: "
            f"{escalated_count} escaladas, {failed_count} fallidas de {total_checked} revisadas"
        )
        
        return result
    
    @staticmethod
    def escalate_stage_manually(
        stage_execution_id: int,
        escalated_to_user_id: int = None,
        reason: str = ''
    ) -> WorkflowStageExecution:
        """
        Escala una etapa manualmente.
        
        Args:
            stage_execution_id: ID de la ejecución de etapa
            escalated_to_user_id: ID del usuario al que escalar (opcional)
            reason: Motivo del escalamiento
            
        Returns:
            WorkflowStageExecution escalada
            
        Raises:
            ValueError: Si la etapa no existe o ya está escalada
        """
        logger.info(
            f"[ESCALATION] Escalamiento manual de etapa {stage_execution_id}"
        )
        
        try:
            stage_execution = WorkflowStageExecution.objects.get(id=stage_execution_id)
        except WorkflowStageExecution.DoesNotExist:
            raise ValueError(f"Etapa {stage_execution_id} no encontrada")
        
        if stage_execution.is_escalated:
            raise ValueError(f"Etapa {stage_execution_id} ya está escalada")
        
        # Obtener usuario si se especificó
        escalated_to = None
        if escalated_to_user_id:
            from api.authentication.models import User
            try:
                escalated_to = User.objects.get(id=escalated_to_user_id)
            except User.DoesNotExist:
                raise ValueError(f"Usuario {escalated_to_user_id} no encontrado")
        
        # Escalar
        WorkflowEngine.escalate_stage(
            stage_execution=stage_execution,
            escalated_to=escalated_to,
            reason=reason or 'Escalamiento manual'
        )
        
        # Enviar notificación
        EscalationService._send_escalation_notification(stage_execution)
        
        logger.info(
            f"[ESCALATION] Etapa {stage_execution_id} escalada manualmente"
        )
        
        return stage_execution
    
    @staticmethod
    def get_escalation_report(institution_id: int = None, days: int = 7) -> Dict:
        """
        Genera un reporte de escalamientos.
        
        Args:
            institution_id: ID de institución (opcional)
            days: Número de días hacia atrás
            
        Returns:
            Dict con estadísticas de escalamientos
        """
        from datetime import timedelta
        
        start_date = timezone.now() - timedelta(days=days)
        
        queryset = WorkflowStageExecution.objects.filter(
            is_escalated=True,
            escalated_at__gte=start_date
        ).select_related(
            'stage_definition',
            'workflow_execution__loan_application'
        )
        
        if institution_id:
            queryset = queryset.filter(institution_id=institution_id)
        
        total_escalations = queryset.count()
        
        # Agrupar por etapa
        by_stage = {}
        for stage_execution in queryset:
            stage_name = stage_execution.stage_definition.stage_name
            if stage_name not in by_stage:
                by_stage[stage_name] = 0
            by_stage[stage_name] += 1
        
        # Calcular tiempo promedio de resolución post-escalamiento
        resolved_escalations = queryset.filter(status='COMPLETED')
        avg_resolution_time = None
        
        if resolved_escalations.exists():
            total_time = sum(
                (se.completed_at - se.escalated_at).total_seconds()
                for se in resolved_escalations
                if se.completed_at and se.escalated_at
            )
            avg_resolution_time = round(total_time / resolved_escalations.count() / 3600, 2)
        
        return {
            'period_days': days,
            'total_escalations': total_escalations,
            'by_stage': by_stage,
            'avg_resolution_time_hours': avg_resolution_time,
            'pending_escalations': queryset.filter(status__in=['PENDING', 'IN_PROGRESS']).count(),
            'resolved_escalations': resolved_escalations.count()
        }
    
    @staticmethod
    def get_pending_escalations(institution_id: int = None) -> List[WorkflowStageExecution]:
        """
        Obtiene escalamientos pendientes de atención.
        
        Args:
            institution_id: ID de institución (opcional)
            
        Returns:
            List de WorkflowStageExecution escaladas y pendientes
        """
        queryset = WorkflowStageExecution.objects.filter(
            is_escalated=True,
            status__in=['PENDING', 'IN_PROGRESS']
        ).select_related(
            'stage_definition',
            'workflow_execution__loan_application__client',
            'escalated_to'
        ).order_by('escalated_at')
        
        if institution_id:
            queryset = queryset.filter(institution_id=institution_id)
        
        return list(queryset)
    
    # ==================== MÉTODOS PRIVADOS ====================
    
    @staticmethod
    def _send_escalation_notification(stage_execution: WorkflowStageExecution):
        """
        Envía notificación de escalamiento.
        
        Args:
            stage_execution: Ejecución de etapa escalada
        """
        # TODO: Implementar envío de notificaciones
        # - Email al usuario escalado
        # - Notificación in-app
        # - Webhook si está configurado
        
        logger.info(
            f"[ESCALATION] Notificación de escalamiento enviada para etapa {stage_execution.id}"
        )
        
        # Por ahora solo logging
        loan_application = stage_execution.workflow_execution.loan_application
        
        logger.info(
            f"[ESCALATION] NOTIFICACIÓN: "
            f"Solicitud {loan_application.application_number} "
            f"escalada en etapa {stage_execution.stage_definition.stage_name}. "
            f"Asignado a: {stage_execution.escalated_to.get_full_name() if stage_execution.escalated_to else 'Supervisor'}"
        )
