"""
Servicio de métricas y análisis de workflows (WorkflowMetricsService).

SPRINT 5 - CU-16: Diseñar Flujos de Aprobación

Calcula métricas, KPIs y análisis de rendimiento de workflows.
"""

from django.db.models import Avg, Count, Q, F, ExpressionWrapper, DurationField, Sum
from django.utils import timezone
from datetime import timedelta
from typing import Dict, List, Optional, Tuple
import logging

from api.loans.models import LoanApplication
from api.loans.models_approval import (
    WorkflowExecution,
    WorkflowStageExecution,
    ApprovalDecision,
)
from api.loans.models_rules import WorkflowStageDefinition, TenantRuleSet

logger = logging.getLogger(__name__)


class WorkflowMetricsService:
    """
    Servicio para calcular métricas y KPIs de workflows.
    
    Proporciona análisis de:
    - Rendimiento por etapa
    - Cuellos de botella
    - Tasas de aprobación
    - Tiempos promedio
    - Eficiencia de aprobadores
    """
    
    @staticmethod
    def get_overview_metrics(institution_id: int, days: int = 30) -> Dict:
        """
        Obtiene métricas generales del sistema de workflows.
        
        Args:
            institution_id: ID de institución
            days: Número de días hacia atrás
            
        Returns:
            Dict con métricas generales
        """
        logger.info(
            f"[METRICS] Calculando métricas generales para institución {institution_id}, "
            f"últimos {days} días"
        )
        
        start_date = timezone.now() - timedelta(days=days)
        
        # Workflows activos
        active_workflows = WorkflowExecution.objects.filter(
            institution_id=institution_id,
            status='IN_PROGRESS'
        ).count()
        
        # Workflows completados en el período
        completed_workflows = WorkflowExecution.objects.filter(
            institution_id=institution_id,
            status='COMPLETED',
            completed_at__gte=start_date
        )
        
        total_completed = completed_workflows.count()
        
        # Tiempo promedio de completado
        avg_completion_time = None
        if total_completed > 0:
            avg_seconds = completed_workflows.aggregate(
                avg_time=Avg('total_time_seconds')
            )['avg_time']
            avg_completion_time = round(avg_seconds / 3600, 2) if avg_seconds else None
        
        # Solicitudes por estado
        applications_by_status = LoanApplication.objects.filter(
            institution_id=institution_id,
            created_at__gte=start_date
        ).values('status').annotate(count=Count('id'))
        
        status_distribution = {
            item['status']: item['count']
            for item in applications_by_status
        }
        
        # Decisiones en el período
        decisions = ApprovalDecision.objects.filter(
            institution_id=institution_id,
            decided_at__gte=start_date
        )
        
        total_decisions = decisions.count()
        approved_decisions = decisions.filter(decision='APPROVED').count()
        rejected_decisions = decisions.filter(decision='REJECTED').count()
        
        approval_rate = (approved_decisions / total_decisions * 100) if total_decisions > 0 else 0
        
        # Etapas activas
        active_stages = WorkflowStageExecution.objects.filter(
            institution_id=institution_id,
            status__in=['PENDING', 'IN_PROGRESS']
        ).count()
        
        # Etapas vencidas
        overdue_stages = WorkflowStageExecution.objects.filter(
            institution_id=institution_id,
            status__in=['PENDING', 'IN_PROGRESS'],
            stage_definition__time_limit_hours__isnull=False
        )
        
        overdue_count = sum(1 for se in overdue_stages if se.is_overdue())
        
        metrics = {
            'period_days': days,
            'active_workflows': active_workflows,
            'completed_workflows': total_completed,
            'avg_completion_time_hours': avg_completion_time,
            'status_distribution': status_distribution,
            'total_decisions': total_decisions,
            'approved_decisions': approved_decisions,
            'rejected_decisions': rejected_decisions,
            'approval_rate': round(approval_rate, 2),
            'active_stages': active_stages,
            'overdue_stages': overdue_count,
            'sla_compliance_rate': round(
                ((active_stages - overdue_count) / active_stages * 100) if active_stages > 0 else 100,
                2
            )
        }
        
        logger.info(
            f"[METRICS] Métricas generales calculadas: "
            f"{active_workflows} activos, {total_completed} completados, "
            f"{approval_rate:.1f}% aprobación"
        )
        
        return metrics
    
    @staticmethod
    def get_stage_performance(
        stage_definition_id: int,
        institution_id: int,
        days: int = 30
    ) -> Dict:
        """
        Obtiene métricas de rendimiento de una etapa específica.
        
        Args:
            stage_definition_id: ID de definición de etapa
            institution_id: ID de institución
            days: Número de días hacia atrás
            
        Returns:
            Dict con métricas de la etapa
        """
        logger.info(
            f"[METRICS] Calculando rendimiento de etapa {stage_definition_id}"
        )
        
        start_date = timezone.now() - timedelta(days=days)
        
        try:
            stage_definition = WorkflowStageDefinition.objects.get(
                id=stage_definition_id,
                institution_id=institution_id
            )
        except WorkflowStageDefinition.DoesNotExist:
            raise ValueError(f"Etapa {stage_definition_id} no encontrada")
        
        # Ejecuciones de esta etapa
        executions = WorkflowStageExecution.objects.filter(
            stage_definition=stage_definition,
            entered_at__gte=start_date
        )
        
        total_executions = executions.count()
        
        # Ejecuciones completadas
        completed = executions.filter(status='COMPLETED')
        completed_count = completed.count()
        
        # Tiempo promedio
        avg_time_seconds = completed.aggregate(
            avg_time=Avg('time_spent_seconds')
        )['avg_time']
        
        avg_time_hours = round(avg_time_seconds / 3600, 2) if avg_time_seconds else None
        
        # Distribución de outcomes
        outcomes = completed.values('outcome').annotate(count=Count('id'))
        outcome_distribution = {
            item['outcome']: item['count']
            for item in outcomes
        }
        
        # Tasa de éxito
        success_count = outcome_distribution.get('SUCCESS', 0)
        success_rate = (success_count / completed_count * 100) if completed_count > 0 else 0
        
        # Escalamientos
        escalated_count = executions.filter(is_escalated=True).count()
        escalation_rate = (escalated_count / total_executions * 100) if total_executions > 0 else 0
        
        # Etapas activas
        active_count = executions.filter(status__in=['PENDING', 'IN_PROGRESS']).count()
        
        # Etapas vencidas
        overdue_count = sum(
            1 for se in executions.filter(status__in=['PENDING', 'IN_PROGRESS'])
            if se.is_overdue()
        )
        
        # SLA compliance
        sla_compliance = (
            ((active_count - overdue_count) / active_count * 100)
            if active_count > 0 else 100
        )
        
        # Top aprobadores
        top_approvers = completed.values(
            'completed_by__id',
            'completed_by__first_name',
            'completed_by__last_name'
        ).annotate(
            count=Count('id'),
            avg_time=Avg('time_spent_seconds')
        ).order_by('-count')[:5]
        
        metrics = {
            'stage_name': stage_definition.stage_name,
            'stage_code': stage_definition.stage_code,
            'period_days': days,
            'total_executions': total_executions,
            'completed_count': completed_count,
            'active_count': active_count,
            'avg_time_hours': avg_time_hours,
            'sla_hours': stage_definition.time_limit_hours,
            'outcome_distribution': outcome_distribution,
            'success_rate': round(success_rate, 2),
            'escalated_count': escalated_count,
            'escalation_rate': round(escalation_rate, 2),
            'overdue_count': overdue_count,
            'sla_compliance': round(sla_compliance, 2),
            'top_approvers': [
                {
                    'user_id': item['completed_by__id'],
                    'name': f"{item['completed_by__first_name']} {item['completed_by__last_name']}",
                    'count': item['count'],
                    'avg_time_hours': round(item['avg_time'] / 3600, 2) if item['avg_time'] else None
                }
                for item in top_approvers
            ]
        }
        
        logger.info(
            f"[METRICS] Rendimiento de etapa calculado: "
            f"{total_executions} ejecuciones, {avg_time_hours}h promedio"
        )
        
        return metrics
    
    @staticmethod
    def get_bottlenecks(
        rule_set_id: int,
        institution_id: int,
        days: int = 30
    ) -> List[Dict]:
        """
        Identifica cuellos de botella en el workflow.
        
        Un cuello de botella se identifica por:
        - Tiempo promedio > SLA configurado
        - Alta tasa de escalamiento
        - Baja tasa de éxito
        
        Args:
            rule_set_id: ID del conjunto de reglas
            institution_id: ID de institución
            days: Número de días hacia atrás
            
        Returns:
            List de etapas que son cuellos de botella
        """
        logger.info(
            f"[METRICS] Identificando cuellos de botella para rule_set {rule_set_id}"
        )
        
        start_date = timezone.now() - timedelta(days=days)
        
        try:
            rule_set = TenantRuleSet.objects.get(
                id=rule_set_id,
                institution_id=institution_id
            )
        except TenantRuleSet.DoesNotExist:
            raise ValueError(f"RuleSet {rule_set_id} no encontrado")
        
        bottlenecks = []
        
        for stage_definition in rule_set.workflow_stages.all():
            executions = WorkflowStageExecution.objects.filter(
                stage_definition=stage_definition,
                entered_at__gte=start_date
            )
            
            total = executions.count()
            if total == 0:
                continue
            
            completed = executions.filter(status='COMPLETED')
            completed_count = completed.count()
            
            if completed_count == 0:
                continue
            
            # Calcular métricas
            avg_time_seconds = completed.aggregate(
                avg_time=Avg('time_spent_seconds')
            )['avg_time']
            
            avg_time_hours = avg_time_seconds / 3600 if avg_time_seconds else 0
            
            escalation_rate = (
                executions.filter(is_escalated=True).count() / total * 100
            )
            
            success_count = completed.filter(outcome='SUCCESS').count()
            success_rate = (success_count / completed_count * 100)
            
            # Determinar si es cuello de botella
            is_bottleneck = False
            reasons = []
            severity = 0
            
            # Criterio 1: Excede SLA promedio
            if stage_definition.time_limit_hours:
                if avg_time_hours > stage_definition.time_limit_hours:
                    is_bottleneck = True
                    reasons.append(
                        f"Tiempo promedio ({avg_time_hours:.1f}h) excede SLA ({stage_definition.time_limit_hours}h)"
                    )
                    severity += 3
            
            # Criterio 2: Alta tasa de escalamiento (>20%)
            if escalation_rate > 20:
                is_bottleneck = True
                reasons.append(f"Alta tasa de escalamiento ({escalation_rate:.1f}%)")
                severity += 2
            
            # Criterio 3: Baja tasa de éxito (<70%)
            if success_rate < 70:
                is_bottleneck = True
                reasons.append(f"Baja tasa de éxito ({success_rate:.1f}%)")
                severity += 2
            
            # Criterio 4: Muchas etapas activas acumuladas
            active_count = executions.filter(status__in=['PENDING', 'IN_PROGRESS']).count()
            if active_count > total * 0.3:  # Más del 30% activas
                is_bottleneck = True
                reasons.append(f"Acumulación de etapas activas ({active_count})")
                severity += 1
            
            if is_bottleneck:
                bottlenecks.append({
                    'stage_id': stage_definition.id,
                    'stage_name': stage_definition.stage_name,
                    'stage_code': stage_definition.stage_code,
                    'severity': min(severity, 10),  # Máximo 10
                    'reasons': reasons,
                    'metrics': {
                        'avg_time_hours': round(avg_time_hours, 2),
                        'sla_hours': stage_definition.time_limit_hours,
                        'escalation_rate': round(escalation_rate, 2),
                        'success_rate': round(success_rate, 2),
                        'active_count': active_count,
                        'total_executions': total
                    }
                })
        
        # Ordenar por severidad
        bottlenecks.sort(key=lambda x: x['severity'], reverse=True)
        
        logger.info(
            f"[METRICS] Identificados {len(bottlenecks)} cuellos de botella"
        )
        
        return bottlenecks
    
    @staticmethod
    def get_approval_rates(
        institution_id: int,
        user_id: Optional[int] = None,
        days: int = 30
    ) -> Dict:
        """
        Calcula tasas de aprobación/rechazo.
        
        Args:
            institution_id: ID de institución
            user_id: ID de usuario (opcional, para filtrar)
            days: Número de días hacia atrás
            
        Returns:
            Dict con tasas de aprobación
        """
        logger.info(
            f"[METRICS] Calculando tasas de aprobación "
            f"{'para usuario ' + str(user_id) if user_id else 'globalmente'}"
        )
        
        start_date = timezone.now() - timedelta(days=days)
        
        decisions = ApprovalDecision.objects.filter(
            institution_id=institution_id,
            decided_at__gte=start_date
        )
        
        if user_id:
            decisions = decisions.filter(decided_by_id=user_id)
        
        total = decisions.count()
        
        if total == 0:
            return {
                'period_days': days,
                'total_decisions': 0,
                'approval_rate': 0,
                'rejection_rate': 0,
                'return_rate': 0,
                'by_decision': {}
            }
        
        # Distribución por decisión
        by_decision = decisions.values('decision').annotate(count=Count('id'))
        decision_distribution = {
            item['decision']: item['count']
            for item in by_decision
        }
        
        approved = decision_distribution.get('APPROVED', 0)
        rejected = decision_distribution.get('REJECTED', 0)
        returned = decision_distribution.get('RETURNED', 0)
        
        # Tasas por producto
        by_product = decisions.values(
            'loan_application__product__name'
        ).annotate(
            total=Count('id'),
            approved=Count('id', filter=Q(decision='APPROVED')),
            rejected=Count('id', filter=Q(decision='REJECTED'))
        )
        
        product_rates = [
            {
                'product_name': item['loan_application__product__name'],
                'total': item['total'],
                'approved': item['approved'],
                'rejected': item['rejected'],
                'approval_rate': round((item['approved'] / item['total'] * 100), 2)
            }
            for item in by_product
        ]
        
        return {
            'period_days': days,
            'total_decisions': total,
            'approval_rate': round((approved / total * 100), 2),
            'rejection_rate': round((rejected / total * 100), 2),
            'return_rate': round((returned / total * 100), 2),
            'by_decision': decision_distribution,
            'by_product': product_rates
        }
    
    @staticmethod
    def get_average_times(
        rule_set_id: int,
        institution_id: int,
        days: int = 30
    ) -> Dict:
        """
        Calcula tiempos promedio por etapa en un workflow.
        
        Args:
            rule_set_id: ID del conjunto de reglas
            institution_id: ID de institución
            days: Número de días hacia atrás
            
        Returns:
            Dict con tiempos promedio por etapa
        """
        logger.info(
            f"[METRICS] Calculando tiempos promedio para rule_set {rule_set_id}"
        )
        
        start_date = timezone.now() - timedelta(days=days)
        
        try:
            rule_set = TenantRuleSet.objects.get(
                id=rule_set_id,
                institution_id=institution_id
            )
        except TenantRuleSet.DoesNotExist:
            raise ValueError(f"RuleSet {rule_set_id} no encontrado")
        
        stages_times = []
        total_avg_time = 0
        
        for stage_definition in rule_set.workflow_stages.order_by('stage_order'):
            executions = WorkflowStageExecution.objects.filter(
                stage_definition=stage_definition,
                status='COMPLETED',
                entered_at__gte=start_date,
                time_spent_seconds__isnull=False
            )
            
            count = executions.count()
            
            if count == 0:
                stages_times.append({
                    'stage_name': stage_definition.stage_name,
                    'stage_code': stage_definition.stage_code,
                    'stage_order': stage_definition.stage_order,
                    'avg_time_hours': None,
                    'sla_hours': stage_definition.time_limit_hours,
                    'executions_count': 0
                })
                continue
            
            avg_seconds = executions.aggregate(
                avg_time=Avg('time_spent_seconds')
            )['avg_time']
            
            avg_hours = round(avg_seconds / 3600, 2) if avg_seconds else None
            total_avg_time += avg_seconds if avg_seconds else 0
            
            stages_times.append({
                'stage_name': stage_definition.stage_name,
                'stage_code': stage_definition.stage_code,
                'stage_order': stage_definition.stage_order,
                'avg_time_hours': avg_hours,
                'sla_hours': stage_definition.time_limit_hours,
                'executions_count': count,
                'within_sla': (
                    avg_hours <= stage_definition.time_limit_hours
                    if avg_hours and stage_definition.time_limit_hours else None
                )
            })
        
        return {
            'rule_set_name': rule_set.name,
            'period_days': days,
            'total_avg_time_hours': round(total_avg_time / 3600, 2) if total_avg_time > 0 else None,
            'stages': stages_times
        }
    
    @staticmethod
    def get_user_performance(
        user_id: int,
        institution_id: int,
        days: int = 30
    ) -> Dict:
        """
        Obtiene métricas de desempeño de un usuario específico.
        
        Args:
            user_id: ID del usuario
            institution_id: ID de institución
            days: Número de días hacia atrás
            
        Returns:
            Dict con métricas del usuario
        """
        logger.info(
            f"[METRICS] Calculando desempeño de usuario {user_id}"
        )
        
        start_date = timezone.now() - timedelta(days=days)
        
        # Decisiones del usuario
        decisions = ApprovalDecision.objects.filter(
            decided_by_id=user_id,
            institution_id=institution_id,
            decided_at__gte=start_date
        )
        
        total_decisions = decisions.count()
        
        # Etapas completadas
        completed_stages = WorkflowStageExecution.objects.filter(
            completed_by_id=user_id,
            institution_id=institution_id,
            completed_at__gte=start_date,
            time_spent_seconds__isnull=False
        )
        
        total_stages = completed_stages.count()
        
        # Tiempo promedio de decisión
        avg_time_seconds = completed_stages.aggregate(
            avg_time=Avg('time_spent_seconds')
        )['avg_time']
        
        avg_time_hours = round(avg_time_seconds / 3600, 2) if avg_time_seconds else None
        
        # Tasa de aprobación
        approved = decisions.filter(decision='APPROVED').count()
        approval_rate = (approved / total_decisions * 100) if total_decisions > 0 else 0
        
        # Etapas actualmente asignadas
        assigned_stages = WorkflowStageExecution.objects.filter(
            assigned_to_id=user_id,
            institution_id=institution_id,
            status__in=['PENDING', 'IN_PROGRESS']
        ).count()
        
        # Etapas vencidas
        overdue_stages = WorkflowStageExecution.objects.filter(
            assigned_to_id=user_id,
            institution_id=institution_id,
            status__in=['PENDING', 'IN_PROGRESS']
        )
        
        overdue_count = sum(1 for se in overdue_stages if se.is_overdue())
        
        return {
            'period_days': days,
            'total_decisions': total_decisions,
            'total_stages_completed': total_stages,
            'avg_decision_time_hours': avg_time_hours,
            'approval_rate': round(approval_rate, 2),
            'assigned_stages': assigned_stages,
            'overdue_stages': overdue_count,
            'productivity_score': WorkflowMetricsService._calculate_productivity_score(
                total_stages, avg_time_hours, overdue_count, days
            )
        }
    
    @staticmethod
    def _calculate_productivity_score(
        total_stages: int,
        avg_time_hours: Optional[float],
        overdue_count: int,
        days: int
    ) -> float:
        """
        Calcula un score de productividad (0-100).
        
        Factores:
        - Cantidad de etapas completadas
        - Velocidad de decisión
        - Cumplimiento de SLA
        """
        if total_stages == 0:
            return 0.0
        
        # Factor 1: Volumen (40 puntos)
        # Asumiendo 2 etapas por día como promedio
        expected_stages = days * 2
        volume_score = min((total_stages / expected_stages) * 40, 40)
        
        # Factor 2: Velocidad (30 puntos)
        # Asumiendo 4 horas como tiempo ideal
        speed_score = 0
        if avg_time_hours:
            if avg_time_hours <= 4:
                speed_score = 30
            elif avg_time_hours <= 8:
                speed_score = 20
            elif avg_time_hours <= 24:
                speed_score = 10
        
        # Factor 3: SLA Compliance (30 puntos)
        sla_rate = ((total_stages - overdue_count) / total_stages) if total_stages > 0 else 1
        sla_score = sla_rate * 30
        
        total_score = volume_score + speed_score + sla_score
        
        return round(total_score, 2)
