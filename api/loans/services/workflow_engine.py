"""
Motor de ejecución de workflows (WorkflowEngine).

SPRINT 1 - CU-16: Diseñar Flujos de Aprobación

Este servicio es el núcleo del sistema de workflows. Responsable de:
- Iniciar workflows para nuevas solicitudes
- Ejecutar transiciones entre etapas
- Evaluar condiciones de avance automático
- Gestionar escalamientos
- Coordinar con WorkflowService existente
"""

from django.db import transaction
from django.utils import timezone
from django.core.exceptions import ValidationError
from typing import Optional, Dict, List, Tuple
import logging

from api.loans.models import LoanApplication
from api.loans.models_approval import (
    WorkflowExecution,
    WorkflowStageExecution,
    ApprovalDecision,
)
from api.loans.models_rules import WorkflowStageDefinition, TenantRuleSet

logger = logging.getLogger(__name__)


class WorkflowEngine:
    """
    Motor principal de ejecución de workflows.
    
    Coordina la ejecución de workflows para solicitudes de crédito,
    integrándose con el WorkflowService existente para mantener
    compatibilidad con la lógica actual.
    """
    
    @staticmethod
    @transaction.atomic
    def start_workflow(loan_application: LoanApplication, started_by=None) -> WorkflowExecution:
        """
        Inicia un workflow para una solicitud de crédito.
        
        Crea un WorkflowExecution y una WorkflowStageExecution inicial
        basándose en el estado actual de la solicitud.
        
        Args:
            loan_application: Solicitud de crédito
            started_by: Usuario que inicia el workflow (opcional)
            
        Returns:
            WorkflowExecution: Ejecución de workflow creada
            
        Raises:
            ValidationError: Si la solicitud no tiene rule_set o ya tiene workflow
        """
        logger.info(
            f"[WORKFLOW_ENGINE] Iniciando workflow para solicitud {loan_application.id}"
        )
        
        # Validar que tenga rule_set
        if not loan_application.rule_set_snapshot:
            raise ValidationError(
                "La solicitud no tiene un conjunto de reglas asignado. "
                "No se puede iniciar el workflow."
            )
        
        # Verificar si ya tiene workflow
        if hasattr(loan_application, 'workflow_execution'):
            logger.warning(
                f"[WORKFLOW_ENGINE] Solicitud {loan_application.id} ya tiene workflow. "
                f"Retornando existente."
            )
            return loan_application.workflow_execution
        
        # Obtener la etapa inicial basándose en el estado actual
        current_stage = WorkflowEngine._get_stage_for_status(
            loan_application.rule_set_snapshot,
            loan_application.status
        )
        
        # Crear WorkflowExecution
        workflow_execution = WorkflowExecution.objects.create(
            institution=loan_application.institution,
            loan_application=loan_application,
            rule_set=loan_application.rule_set_snapshot,
            current_stage=current_stage,
            status='IN_PROGRESS',
            execution_data={
                'started_by': started_by.id if started_by else None,
                'initial_status': loan_application.status,
            }
        )
        
        # Crear WorkflowStageExecution inicial si hay etapa
        if current_stage:
            WorkflowEngine._create_stage_execution(
                workflow_execution=workflow_execution,
                stage_definition=current_stage,
                assigned_to=loan_application.assigned_to
            )
        
        logger.info(
            f"[WORKFLOW_ENGINE] Workflow {workflow_execution.id} iniciado para "
            f"solicitud {loan_application.id} en etapa {current_stage.stage_name if current_stage else 'N/A'}"
        )
        
        return workflow_execution
    
    @staticmethod
    @transaction.atomic
    def transition_to_stage(
        workflow_execution: WorkflowExecution,
        target_stage_code: str,
        triggered_by=None,
        outcome: str = 'SUCCESS',
        notes: str = ''
    ) -> WorkflowStageExecution:
        """
        Transiciona el workflow a una nueva etapa.
        
        Completa la etapa actual y crea una nueva ejecución de etapa.
        También actualiza el estado de la solicitud usando WorkflowService.
        
        Args:
            workflow_execution: Ejecución de workflow
            target_stage_code: Código de la etapa destino
            triggered_by: Usuario que dispara la transición
            outcome: Resultado de la etapa actual (SUCCESS/FAILURE/TIMEOUT)
            notes: Notas de la transición
            
        Returns:
            WorkflowStageExecution: Nueva ejecución de etapa creada
            
        Raises:
            ValidationError: Si la transición no es válida
        """
        logger.info(
            f"[WORKFLOW_ENGINE] Transicionando workflow {workflow_execution.id} "
            f"a etapa {target_stage_code}"
        )
        
        # Obtener la definición de la etapa destino
        target_stage = workflow_execution.rule_set.workflow_stages.filter(
            stage_code=target_stage_code
        ).first()
        
        if not target_stage:
            raise ValidationError(
                f"Etapa '{target_stage_code}' no encontrada en el workflow configurado."
            )
        
        # Completar la etapa actual si existe
        current_stage_execution = workflow_execution.stage_executions.filter(
            status__in=['PENDING', 'IN_PROGRESS']
        ).first()
        
        if current_stage_execution:
            current_stage_execution.mark_completed(
                outcome=outcome,
                completed_by=triggered_by,
                notes=notes
            )
            
            # Incrementar contador de etapas completadas
            workflow_execution.total_stages_completed += 1
            workflow_execution.save(update_fields=['total_stages_completed'])
        
        # Actualizar el estado de la solicitud usando WorkflowService
        from api.loans.services.workflow_service import WorkflowService
        
        try:
            WorkflowService.transition_state(
                loan_application_id=workflow_execution.loan_application_id,
                to_status=target_stage_code,
                changed_by=triggered_by,
                notes=notes,
                send_notification=True
            )
        except Exception as e:
            logger.error(
                f"[WORKFLOW_ENGINE] Error al transicionar estado de solicitud: {str(e)}"
            )
            # No fallar la transición del workflow por error en WorkflowService
        
        # Crear nueva ejecución de etapa
        new_stage_execution = WorkflowEngine._create_stage_execution(
            workflow_execution=workflow_execution,
            stage_definition=target_stage,
            assigned_to=WorkflowEngine._determine_assignee(target_stage)
        )
        
        # Actualizar etapa actual del workflow
        workflow_execution.current_stage = target_stage
        workflow_execution.save(update_fields=['current_stage'])
        
        # Verificar si es etapa final
        if target_stage.is_final_stage:
            workflow_execution.mark_completed()
            logger.info(
                f"[WORKFLOW_ENGINE] Workflow {workflow_execution.id} completado "
                f"en etapa final {target_stage.stage_name}"
            )
        
        # Evaluar auto-avance si está habilitado
        if target_stage.auto_advance_enabled:
            WorkflowEngine.evaluate_auto_advance(new_stage_execution)
        
        logger.info(
            f"[WORKFLOW_ENGINE] Transición completada. Nueva etapa: {target_stage.stage_name}"
        )
        
        return new_stage_execution
    
    @staticmethod
    def evaluate_auto_advance(stage_execution: WorkflowStageExecution) -> bool:
        """
        Evalúa si se cumplen las condiciones de avance automático.
        
        Si se cumplen, ejecuta la transición automáticamente.
        
        Args:
            stage_execution: Ejecución de etapa a evaluar
            
        Returns:
            bool: True si se avanzó automáticamente
        """
        logger.info(
            f"[WORKFLOW_ENGINE] Evaluando auto-avance para etapa {stage_execution.id}"
        )
        
        stage_def = stage_execution.stage_definition
        
        if not stage_def.auto_advance_enabled:
            logger.debug(
                f"[WORKFLOW_ENGINE] Auto-avance no habilitado para etapa {stage_def.stage_name}"
            )
            return False
        
        # Obtener la solicitud
        loan_application = stage_execution.workflow_execution.loan_application
        
        # Evaluar condiciones usando el método del modelo
        conditions_met = stage_def.check_auto_advance_conditions(loan_application)
        
        if not conditions_met:
            logger.debug(
                f"[WORKFLOW_ENGINE] Condiciones de auto-avance no cumplidas para "
                f"etapa {stage_def.stage_name}"
            )
            return False
        
        # Determinar siguiente etapa
        next_stage_code = stage_def.next_stage_on_success
        
        if not next_stage_code:
            logger.warning(
                f"[WORKFLOW_ENGINE] Auto-avance habilitado pero no hay etapa siguiente "
                f"configurada para {stage_def.stage_name}"
            )
            return False
        
        # Ejecutar transición automática
        try:
            WorkflowEngine.transition_to_stage(
                workflow_execution=stage_execution.workflow_execution,
                target_stage_code=next_stage_code,
                triggered_by=None,  # Sistema
                outcome='SUCCESS',
                notes=f'Avance automático desde {stage_def.stage_name}'
            )
            
            logger.info(
                f"[WORKFLOW_ENGINE] Auto-avance ejecutado: {stage_def.stage_name} → {next_stage_code}"
            )
            
            return True
            
        except Exception as e:
            logger.error(
                f"[WORKFLOW_ENGINE] Error en auto-avance: {str(e)}",
                exc_info=True
            )
            return False
    
    @staticmethod
    def check_escalations(institution_id: int = None) -> List[WorkflowStageExecution]:
        """
        Verifica etapas que deben escalarse por timeout.
        
        Busca ejecuciones de etapas que:
        - Estén en progreso
        - Tengan escalamiento habilitado
        - Hayan excedido el tiempo límite
        
        Args:
            institution_id: ID de institución (opcional, para filtrar)
            
        Returns:
            List[WorkflowStageExecution]: Lista de etapas que deben escalarse
        """
        logger.info(
            f"[WORKFLOW_ENGINE] Verificando escalamientos "
            f"{'para institución ' + str(institution_id) if institution_id else 'globalmente'}"
        )
        
        # Obtener etapas en progreso con escalamiento habilitado
        queryset = WorkflowStageExecution.objects.filter(
            status__in=['PENDING', 'IN_PROGRESS'],
            stage_definition__escalation_enabled=True,
            is_escalated=False
        ).select_related(
            'stage_definition',
            'workflow_execution__loan_application'
        )
        
        if institution_id:
            queryset = queryset.filter(institution_id=institution_id)
        
        # Filtrar las que están vencidas
        overdue_stages = []
        
        for stage_execution in queryset:
            if stage_execution.is_overdue():
                overdue_stages.append(stage_execution)
        
        logger.info(
            f"[WORKFLOW_ENGINE] Encontradas {len(overdue_stages)} etapas para escalar"
        )
        
        return overdue_stages
    
    @staticmethod
    @transaction.atomic
    def escalate_stage(
        stage_execution: WorkflowStageExecution,
        escalated_to=None,
        reason: str = ''
    ):
        """
        Escala una etapa a otro usuario o rol.
        
        Args:
            stage_execution: Ejecución de etapa a escalar
            escalated_to: Usuario al que se escala (opcional)
            reason: Motivo del escalamiento
        """
        logger.info(
            f"[WORKFLOW_ENGINE] Escalando etapa {stage_execution.id}"
        )
        
        # Si no se especifica usuario, buscar según reglas de escalamiento
        if not escalated_to:
            escalated_to = WorkflowEngine._determine_escalation_target(stage_execution)
        
        # Marcar como escalada
        stage_execution.escalate(
            escalated_to=escalated_to,
            reason=reason or f'Escalamiento automático por timeout (SLA: {stage_execution.stage_definition.time_limit_hours}h)'
        )
        
        # Crear evento en timeline
        loan_application = stage_execution.workflow_execution.loan_application
        
        try:
            loan_application.add_timeline_event(
                to_status=loan_application.status,  # Mantener estado
                changed_by=None,  # Sistema
                notes=f'Etapa {stage_execution.stage_definition.stage_name} escalada por timeout',
                is_visible_to_client=False,
                client_message='',
                send_notification=True
            )
        except Exception as e:
            logger.error(
                f"[WORKFLOW_ENGINE] Error al crear evento de escalamiento: {str(e)}"
            )
        
        logger.info(
            f"[WORKFLOW_ENGINE] Etapa {stage_execution.id} escalada a "
            f"{escalated_to.get_full_name() if escalated_to else 'supervisor'}"
        )
    
    @staticmethod
    def get_workflow_for_application(loan_application: LoanApplication) -> Optional[WorkflowExecution]:
        """
        Obtiene el workflow de una solicitud.
        
        Si no existe, lo crea automáticamente.
        
        Args:
            loan_application: Solicitud de crédito
            
        Returns:
            WorkflowExecution o None
        """
        try:
            return loan_application.workflow_execution
        except WorkflowExecution.DoesNotExist:
            # Crear workflow si no existe
            if loan_application.rule_set_snapshot:
                return WorkflowEngine.start_workflow(loan_application)
            return None
    
    # ==================== MÉTODOS PRIVADOS ====================
    
    @staticmethod
    def _get_stage_for_status(rule_set: TenantRuleSet, status: str) -> Optional[WorkflowStageDefinition]:
        """
        Obtiene la definición de etapa correspondiente a un estado.
        
        Args:
            rule_set: Conjunto de reglas
            status: Código de estado
            
        Returns:
            WorkflowStageDefinition o None
        """
        return rule_set.workflow_stages.filter(stage_code=status).first()
    
    @staticmethod
    def _create_stage_execution(
        workflow_execution: WorkflowExecution,
        stage_definition: WorkflowStageDefinition,
        assigned_to=None
    ) -> WorkflowStageExecution:
        """
        Crea una nueva ejecución de etapa.
        
        Args:
            workflow_execution: Ejecución de workflow
            stage_definition: Definición de etapa
            assigned_to: Usuario asignado (opcional)
            
        Returns:
            WorkflowStageExecution creada
        """
        stage_execution = WorkflowStageExecution.objects.create(
            institution=workflow_execution.institution,
            workflow_execution=workflow_execution,
            stage_definition=stage_definition,
            status='IN_PROGRESS' if not stage_definition.is_automated else 'PENDING',
            assigned_to=assigned_to
        )
        
        logger.debug(
            f"[WORKFLOW_ENGINE] Creada ejecución de etapa {stage_execution.id} "
            f"para {stage_definition.stage_name}"
        )
        
        return stage_execution
    
    @staticmethod
    def _determine_assignee(stage_definition: WorkflowStageDefinition):
        """
        Determina a quién asignar una etapa.
        
        Por ahora retorna None (asignación manual).
        En el futuro implementar lógica de asignación automática.
        
        Args:
            stage_definition: Definición de etapa
            
        Returns:
            User o None
        """
        # TODO: Implementar lógica de asignación automática
        # - Round-robin por rol
        # - Por carga de trabajo
        # - Por especialización
        return None
    
    @staticmethod
    def _determine_escalation_target(stage_execution: WorkflowStageExecution):
        """
        Determina a quién escalar una etapa.
        
        Busca en las reglas de escalamiento de la etapa.
        
        Args:
            stage_execution: Ejecución de etapa
            
        Returns:
            User o None
        """
        escalation_rules = stage_execution.stage_definition.escalation_rules
        
        if not escalation_rules:
            return None
        
        # TODO: Implementar lógica de escalamiento
        # - Buscar supervisor del rol
        # - Buscar usuario específico en reglas
        # - Escalar a rol superior
        
        return None
