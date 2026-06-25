"""
Signals para recalcular automáticamente el orden de las etapas del workflow.

Este módulo implementa un sistema inteligente de numeración que:
1. Sigue el flujo de éxito para el orden principal
2. Detecta bifurcaciones y asigna subnúmeros (2.1, 2.2)
3. Recalcula automáticamente cuando se crea/actualiza una etapa
"""

from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from api.loans.models_rules import WorkflowStageDefinition
import logging

logger = logging.getLogger(__name__)


def recalculate_workflow_order(rule_set_id):
    """
    Recalcula el orden de todas las etapas de un Rule Set siguiendo el flujo de éxito.
    
    Algoritmo:
    1. Encuentra la etapa inicial (sin etapas anteriores)
    2. Recorre el flujo de éxito asignando números secuenciales
    3. Detecta bifurcaciones (éxito vs fallo al mismo nivel)
    4. Etapas terminales reciben el siguiente número en secuencia
    
    Args:
        rule_set_id: ID del Rule Set a recalcular
    """
    try:
        # Obtener todas las etapas del Rule Set
        stages = WorkflowStageDefinition.objects.filter(
            rule_set_id=rule_set_id
        ).select_related('rule_set')
        
        if not stages.exists():
            return
        
        logger.info(f"[WORKFLOW ORDER] Recalculando orden para Rule Set {rule_set_id}")
        
        # Crear un mapa de etapas por código
        stage_map = {stage.stage_code: stage for stage in stages}
        
        # Encontrar la etapa inicial (sin etapas anteriores que apunten a ella)
        initial_stage = None
        for stage in stages:
            has_incoming = any(
                s.next_stage_on_success == stage.stage_code or 
                s.next_stage_on_failure == stage.stage_code
                for s in stages if s.id != stage.id
            )
            if not has_incoming:
                initial_stage = stage
                break
        
        if not initial_stage:
            logger.warning(f"[WORKFLOW ORDER] No se encontró etapa inicial para Rule Set {rule_set_id}")
            return
        
        # Recorrer el flujo y asignar órdenes
        visited = set()
        order_counter = [1]  # Usar lista para poder modificar en función anidada
        
        def assign_order(stage, current_order, is_failure_branch=False):
            """Asigna orden recursivamente siguiendo el flujo"""
            
            if not stage or stage.stage_code in visited:
                return
            
            visited.add(stage.stage_code)
            
            # Asignar orden actual (incluso si es terminal)
            stage.stage_order = current_order
            stage.save(update_fields=['stage_order'])
            logger.debug(
                f"[WORKFLOW ORDER] {stage.stage_code}: {current_order}"
                f"{' (terminal)' if stage.is_final_stage else ''}"
            )
            
            # Si es terminal, no procesar siguientes etapas
            if stage.is_final_stage:
                # Actualizar el contador para la siguiente etapa terminal
                order_counter[0] = max(order_counter[0], current_order + 1)
                return
            
            # Procesar siguiente etapa de éxito (flujo principal)
            if stage.next_stage_on_success and stage.next_stage_on_success in stage_map:
                next_stage = stage_map[stage.next_stage_on_success]
                if next_stage.stage_code not in visited:
                    assign_order(next_stage, current_order + 1, False)
            
            # Procesar siguiente etapa de fallo (rama alternativa)
            # Solo si es diferente a la de éxito
            if (stage.next_stage_on_failure and 
                stage.next_stage_on_failure in stage_map and
                stage.next_stage_on_failure != stage.next_stage_on_success):
                
                failure_stage = stage_map[stage.next_stage_on_failure]
                if failure_stage.stage_code not in visited:
                    # Usar el contador actual para etapas terminales de fallo
                    if failure_stage.is_final_stage:
                        assign_order(failure_stage, order_counter[0], True)
                    else:
                        assign_order(failure_stage, current_order + 1, True)
        
        # Iniciar desde la etapa inicial
        assign_order(initial_stage, 1, False)
        
        # Procesar etapas no visitadas (huérfanas o desconectadas)
        unvisited = [s for s in stages if s.stage_code not in visited]
        if unvisited:
            logger.warning(
                f"[WORKFLOW ORDER] {len(unvisited)} etapas desconectadas en Rule Set {rule_set_id}: "
                f"{[s.stage_code for s in unvisited]}"
            )
            # Asignar orden alto a etapas desconectadas
            disconnected_order = order_counter[0]
            for stage in unvisited:
                stage.stage_order = disconnected_order
                stage.save(update_fields=['stage_order'])
                disconnected_order += 1
        
        logger.info(
            f"[WORKFLOW ORDER] Recálculo completado para Rule Set {rule_set_id}. "
            f"Etapas procesadas: {len(visited)}, Desconectadas: {len(unvisited)}"
        )
        
    except Exception as e:
        logger.error(f"[WORKFLOW ORDER] Error recalculando orden: {str(e)}", exc_info=True)


@receiver(post_save, sender=WorkflowStageDefinition)
def workflow_stage_saved(sender, instance, created, **kwargs):
    """
    Signal que se ejecuta después de guardar una etapa.
    Recalcula el orden de todas las etapas del Rule Set.
    """
    # Evitar recursión infinita
    if kwargs.get('update_fields') and 'stage_order' in kwargs['update_fields']:
        return
    
    logger.info(
        f"[WORKFLOW SIGNAL] Etapa {'creada' if created else 'actualizada'}: "
        f"{instance.stage_code} (Rule Set {instance.rule_set_id})"
    )
    
    # Recalcular orden de todas las etapas del Rule Set
    recalculate_workflow_order(instance.rule_set_id)


@receiver(post_delete, sender=WorkflowStageDefinition)
def workflow_stage_deleted(sender, instance, **kwargs):
    """
    Signal que se ejecuta después de eliminar una etapa.
    Recalcula el orden de las etapas restantes del Rule Set.
    """
    logger.info(
        f"[WORKFLOW SIGNAL] Etapa eliminada: {instance.stage_code} "
        f"(Rule Set {instance.rule_set_id})"
    )
    
    # Recalcular orden de las etapas restantes
    recalculate_workflow_order(instance.rule_set_id)
