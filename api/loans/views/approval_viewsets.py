"""
ViewSets para el sistema de aprobaciones.

SPRINT 1-2 - CU-16: Diseñar Flujos de Aprobación
"""

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Q

from api.loans.models_approval import (
    WorkflowExecution,
    WorkflowStageExecution,
    ApprovalDecision,
)
from api.loans.serializers.approval_serializers import (
    WorkflowExecutionSerializer,
    WorkflowExecutionDetailSerializer,
    WorkflowStageExecutionSerializer,
    WorkflowStageExecutionListSerializer,
    ApprovalDecisionSerializer,
    ApprovalDecisionCreateSerializer,
    ApprovalDecisionListSerializer,
)
from api.loans.services.workflow_engine import WorkflowEngine
from api.loans.services.approval_queue_service import ApprovalQueueService
from api.core.permissions import IsStaffUser


class WorkflowExecutionViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet para WorkflowExecution.
    
    Endpoints:
    - GET /api/loans/workflow-executions/ - Listar ejecuciones
    - GET /api/loans/workflow-executions/{id}/ - Detalle de ejecución
    - GET /api/loans/workflow-executions/{id}/stage-history/ - Historial de etapas
    """
    
    permission_classes = [IsAuthenticated, IsStaffUser]
    
    def get_queryset(self):
        user = self.request.user
        
        queryset = WorkflowExecution.objects.select_related(
            'loan_application',
            'rule_set',
            'current_stage'
        ).prefetch_related(
            'stage_executions__stage_definition'
        )
        
        # Filtrar por institución del usuario
        if hasattr(user, 'institution'):
            queryset = queryset.filter(institution=user.institution)
        
        # Filtrar por solicitud si se proporciona
        application_id = self.request.query_params.get('loan_application')
        if application_id:
            queryset = queryset.filter(loan_application_id=application_id)
        
        # Filtrar por estado
        workflow_status = self.request.query_params.get('status')
        if workflow_status:
            queryset = queryset.filter(status=workflow_status)
        
        return queryset.order_by('-started_at')
    
    def get_serializer_class(self):
        if self.action == 'retrieve':
            return WorkflowExecutionDetailSerializer
        return WorkflowExecutionSerializer
    
    @action(detail=True, methods=['get'])
    def stage_history(self, request, pk=None):
        """
        Obtiene el historial de etapas de un workflow.
        
        GET /api/loans/workflow-executions/{id}/stage-history/
        """
        workflow_execution = self.get_object()
        
        stage_executions = workflow_execution.stage_executions.all().order_by('entered_at')
        
        serializer = WorkflowStageExecutionListSerializer(
            stage_executions,
            many=True,
            context={'request': request}
        )
        
        return Response(serializer.data)


class ApprovalQueueViewSet(viewsets.ViewSet):
    """
    ViewSet para la cola de aprobaciones.
    
    Endpoints:
    - GET /api/approvals/queue/ - Mi cola de aprobaciones
    - GET /api/approvals/queue/by-role/{role_id}/ - Cola por rol
    - POST /api/approvals/queue/assign/ - Asignar solicitud
    - GET /api/approvals/queue/metrics/ - Mis métricas
    - GET /api/approvals/queue/overdue/ - Solicitudes vencidas
    """
    
    permission_classes = [IsAuthenticated, IsStaffUser]
    
    def list(self, request):
        """
        Obtiene mi cola de aprobaciones personalizada.
        
        GET /api/approvals/queue/
        
        Query params:
        - priority: urgent|normal|low (filtrar por prioridad)
        """
        user = request.user
        institution_id = user.institution.id if hasattr(user, 'institution') else None
        
        # Obtener cola personalizada
        queue_data = ApprovalQueueService.get_my_queue(
            user=user,
            institution_id=institution_id
        )
        
        # Filtrar por prioridad si se especifica
        priority = request.query_params.get('priority')
        
        if priority == 'urgent':
            stage_executions = queue_data['urgent']
        elif priority == 'normal':
            stage_executions = queue_data['normal']
        elif priority == 'low':
            stage_executions = queue_data['low_priority']
        else:
            # Todas las prioridades
            stage_executions = (
                queue_data['urgent'] +
                queue_data['normal'] +
                queue_data['low_priority']
            )
        
        serializer = WorkflowStageExecutionListSerializer(
            stage_executions,
            many=True,
            context={'request': request}
        )
        
        return Response({
            'results': serializer.data,
            'total_count': queue_data['total_count'],
            'urgent_count': len(queue_data['urgent']),
            'normal_count': len(queue_data['normal']),
            'low_priority_count': len(queue_data['low_priority']),
            'metrics': queue_data['metrics']
        })
    
    @action(detail=False, methods=['get'])
    def by_role(self, request):
        """
        Obtiene la cola de aprobaciones para un rol específico.
        
        GET /api/approvals/queue/by-role/?role_id={role_id}
        """
        role_id = request.query_params.get('role_id')
        
        if not role_id:
            return Response(
                {'error': 'role_id es requerido'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        from api.roles.models import Role
        
        try:
            role = Role.objects.get(id=role_id)
        except Role.DoesNotExist:
            return Response(
                {'error': 'Rol no encontrado'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        user = request.user
        institution_id = user.institution.id if hasattr(user, 'institution') else None
        
        stage_executions = ApprovalQueueService.get_queue_by_role(
            role=role,
            institution_id=institution_id
        )
        
        serializer = WorkflowStageExecutionListSerializer(
            stage_executions,
            many=True,
            context={'request': request}
        )
        
        return Response({
            'role': {
                'id': role.id,
                'name': role.name
            },
            'results': serializer.data,
            'total_count': stage_executions.count()
        })
    
    @action(detail=False, methods=['post'])
    def assign(self, request):
        """
        Asigna una etapa a un usuario.
        
        POST /api/approvals/queue/assign/
        Body: {
            "stage_execution_id": 123,
            "user_id": 456
        }
        """
        stage_execution_id = request.data.get('stage_execution_id')
        user_id = request.data.get('user_id')
        
        if not stage_execution_id or not user_id:
            return Response(
                {'error': 'stage_execution_id y user_id son requeridos'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            stage_execution = WorkflowStageExecution.objects.get(id=stage_execution_id)
        except WorkflowStageExecution.DoesNotExist:
            return Response(
                {'error': 'Ejecución de etapa no encontrada'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        from api.authentication.models import User
        
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response(
                {'error': 'Usuario no encontrado'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Asignar
        ApprovalQueueService.assign_to_user(stage_execution, user)
        
        serializer = WorkflowStageExecutionSerializer(
            stage_execution,
            context={'request': request}
        )
        
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def metrics(self, request):
        """
        Obtiene métricas de mi cola de aprobaciones.
        
        GET /api/approvals/queue/metrics/
        """
        user = request.user
        institution_id = user.institution.id if hasattr(user, 'institution') else None
        
        metrics = ApprovalQueueService.get_queue_metrics(
            user=user,
            institution_id=institution_id
        )
        
        return Response(metrics)
    
    @action(detail=False, methods=['get'])
    def overdue(self, request):
        """
        Obtiene solicitudes vencidas (SLA excedido).
        
        GET /api/approvals/queue/overdue/
        """
        user = request.user
        institution_id = user.institution.id if hasattr(user, 'institution') else None
        
        overdue_stages = ApprovalQueueService.get_overdue_applications(
            user=user,
            institution_id=institution_id
        )
        
        serializer = WorkflowStageExecutionListSerializer(
            overdue_stages,
            many=True,
            context={'request': request}
        )
        
        return Response({
            'results': serializer.data,
            'total_count': len(overdue_stages)
        })


class ApprovalDecisionViewSet(viewsets.ModelViewSet):
    """
    ViewSet para ApprovalDecision.
    
    Endpoints:
    - GET /api/approvals/decisions/ - Listar decisiones
    - POST /api/approvals/decisions/ - Crear decisión
    - GET /api/approvals/decisions/{id}/ - Detalle de decisión
    - GET /api/approvals/decisions/my-history/ - Mi historial de decisiones
    """
    
    permission_classes = [IsAuthenticated, IsStaffUser]
    
    def get_queryset(self):
        user = self.request.user
        
        queryset = ApprovalDecision.objects.select_related(
            'loan_application__client',
            'stage_execution__stage_definition',
            'decided_by'
        )
        
        # Filtrar por institución del usuario
        if hasattr(user, 'institution'):
            queryset = queryset.filter(institution=user.institution)
        
        # Filtrar por solicitud si se proporciona
        application_id = self.request.query_params.get('loan_application')
        if application_id:
            queryset = queryset.filter(loan_application_id=application_id)
        
        # Filtrar por decisión
        decision = self.request.query_params.get('decision')
        if decision:
            queryset = queryset.filter(decision=decision)
        
        # Filtrar por usuario que decidió
        decided_by = self.request.query_params.get('decided_by')
        if decided_by:
            queryset = queryset.filter(decided_by_id=decided_by)
        
        return queryset.order_by('-decided_at')
    
    def get_serializer_class(self):
        if self.action == 'create':
            return ApprovalDecisionCreateSerializer
        elif self.action == 'list':
            return ApprovalDecisionListSerializer
        return ApprovalDecisionSerializer
    
    def perform_create(self, serializer):
        """Crea una decisión de aprobación."""
        user = self.request.user
        institution = user.institution if hasattr(user, 'institution') else None
        
        serializer.save(
            institution=institution,
            decided_by=user
        )
    
    @action(detail=False, methods=['get'])
    def my_history(self, request):
        """
        Obtiene mi historial de decisiones.
        
        GET /api/approvals/decisions/my-history/
        
        Query params:
        - days: Número de días hacia atrás (default: 30)
        """
        user = request.user
        days = int(request.query_params.get('days', 30))
        
        from django.utils import timezone
        from datetime import timedelta
        
        start_date = timezone.now() - timedelta(days=days)
        
        decisions = ApprovalDecision.objects.filter(
            decided_by=user,
            decided_at__gte=start_date
        ).select_related(
            'loan_application__client',
            'stage_execution__stage_definition'
        ).order_by('-decided_at')
        
        if hasattr(user, 'institution'):
            decisions = decisions.filter(institution=user.institution)
        
        serializer = ApprovalDecisionListSerializer(
            decisions,
            many=True,
            context={'request': request}
        )
        
        # Calcular estadísticas
        total = decisions.count()
        approved = decisions.filter(decision='APPROVED').count()
        rejected = decisions.filter(decision='REJECTED').count()
        returned = decisions.filter(decision='RETURNED').count()
        
        return Response({
            'results': serializer.data,
            'total_count': total,
            'statistics': {
                'approved': approved,
                'rejected': rejected,
                'returned': returned,
                'approval_rate': round((approved / total * 100), 2) if total > 0 else 0
            },
            'period_days': days
        })



class EscalationViewSet(viewsets.ViewSet):
    """
    ViewSet para gestión de escalamientos.
    
    Endpoints:
    - GET /api/approvals/escalations/ - Listar escalamientos pendientes
    - POST /api/approvals/escalations/check/ - Verificar y escalar automáticamente
    - POST /api/approvals/escalations/manual/ - Escalar manualmente
    - GET /api/approvals/escalations/report/ - Reporte de escalamientos
    """
    
    permission_classes = [IsAuthenticated, IsStaffUser]
    
    def list(self, request):
        """
        Lista escalamientos pendientes de atención.
        
        GET /api/approvals/escalations/
        """
        user = request.user
        institution_id = user.institution.id if hasattr(user, 'institution') else None
        
        from api.loans.services.escalation_service import EscalationService
        
        pending_escalations = EscalationService.get_pending_escalations(
            institution_id=institution_id
        )
        
        serializer = WorkflowStageExecutionListSerializer(
            pending_escalations,
            many=True,
            context={'request': request}
        )
        
        return Response({
            'results': serializer.data,
            'total_count': len(pending_escalations)
        })
    
    @action(detail=False, methods=['post'])
    def check(self, request):
        """
        Verifica y escala automáticamente etapas vencidas.
        
        POST /api/approvals/escalations/check/
        
        Este endpoint ejecuta la lógica de escalamiento automático.
        Normalmente se ejecuta como tarea periódica, pero puede
        invocarse manualmente.
        """
        user = request.user
        institution_id = user.institution.id if hasattr(user, 'institution') else None
        
        from api.loans.services.escalation_service import EscalationService
        
        result = EscalationService.check_and_escalate_all(
            institution_id=institution_id
        )
        
        return Response(result)
    
    @action(detail=False, methods=['post'])
    def manual(self, request):
        """
        Escala una etapa manualmente.
        
        POST /api/approvals/escalations/manual/
        Body: {
            "stage_execution_id": 123,
            "escalated_to_user_id": 456,  // opcional
            "reason": "Motivo del escalamiento"
        }
        """
        stage_execution_id = request.data.get('stage_execution_id')
        escalated_to_user_id = request.data.get('escalated_to_user_id')
        reason = request.data.get('reason', '')
        
        if not stage_execution_id:
            return Response(
                {'error': 'stage_execution_id es requerido'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        from api.loans.services.escalation_service import EscalationService
        
        try:
            stage_execution = EscalationService.escalate_stage_manually(
                stage_execution_id=stage_execution_id,
                escalated_to_user_id=escalated_to_user_id,
                reason=reason
            )
            
            serializer = WorkflowStageExecutionSerializer(
                stage_execution,
                context={'request': request}
            )
            
            return Response(serializer.data)
        
        except ValueError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'])
    def report(self, request):
        """
        Genera reporte de escalamientos.
        
        GET /api/approvals/escalations/report/?days=7
        """
        user = request.user
        institution_id = user.institution.id if hasattr(user, 'institution') else None
        days = int(request.query_params.get('days', 7))
        
        from api.loans.services.escalation_service import EscalationService
        
        report = EscalationService.get_escalation_report(
            institution_id=institution_id,
            days=days
        )
        
        return Response(report)



class WorkflowMetricsViewSet(viewsets.ViewSet):
    """
    ViewSet para métricas y análisis de workflows.
    
    Endpoints:
    - GET /api/workflow/metrics/overview/ - Métricas generales
    - GET /api/workflow/metrics/stage/{id}/ - Rendimiento de etapa
    - GET /api/workflow/metrics/bottlenecks/ - Cuellos de botella
    - GET /api/workflow/metrics/approval-rates/ - Tasas de aprobación
    - GET /api/workflow/metrics/average-times/ - Tiempos promedio
    - GET /api/workflow/metrics/user-performance/ - Desempeño de usuario
    """
    
    permission_classes = [IsAuthenticated, IsStaffUser]
    
    @action(detail=False, methods=['get'])
    def overview(self, request):
        """
        Obtiene métricas generales del sistema.
        
        GET /api/workflow/metrics/overview/?days=30
        """
        user = request.user
        institution_id = user.institution.id if hasattr(user, 'institution') else None
        
        if not institution_id:
            return Response(
                {'error': 'Usuario no tiene institución asociada'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        days = int(request.query_params.get('days', 30))
        
        from api.loans.services.workflow_metrics_service import WorkflowMetricsService
        
        metrics = WorkflowMetricsService.get_overview_metrics(
            institution_id=institution_id,
            days=days
        )
        
        return Response(metrics)
    
    @action(detail=True, methods=['get'])
    def stage(self, request, pk=None):
        """
        Obtiene métricas de rendimiento de una etapa.
        
        GET /api/workflow/metrics/stage/{stage_id}/?days=30
        """
        user = request.user
        institution_id = user.institution.id if hasattr(user, 'institution') else None
        
        if not institution_id:
            return Response(
                {'error': 'Usuario no tiene institución asociada'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        days = int(request.query_params.get('days', 30))
        
        from api.loans.services.workflow_metrics_service import WorkflowMetricsService
        
        try:
            metrics = WorkflowMetricsService.get_stage_performance(
                stage_definition_id=pk,
                institution_id=institution_id,
                days=days
            )
            return Response(metrics)
        except ValueError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_404_NOT_FOUND
            )
    
    @action(detail=False, methods=['get'])
    def bottlenecks(self, request):
        """
        Identifica cuellos de botella en el workflow.
        
        GET /api/workflow/metrics/bottlenecks/?rule_set_id=1&days=30
        """
        user = request.user
        institution_id = user.institution.id if hasattr(user, 'institution') else None
        
        if not institution_id:
            return Response(
                {'error': 'Usuario no tiene institución asociada'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        rule_set_id = request.query_params.get('rule_set_id')
        if not rule_set_id:
            return Response(
                {'error': 'rule_set_id es requerido'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        days = int(request.query_params.get('days', 30))
        
        from api.loans.services.workflow_metrics_service import WorkflowMetricsService
        
        try:
            bottlenecks = WorkflowMetricsService.get_bottlenecks(
                rule_set_id=int(rule_set_id),
                institution_id=institution_id,
                days=days
            )
            return Response({
                'bottlenecks': bottlenecks,
                'total_count': len(bottlenecks)
            })
        except ValueError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_404_NOT_FOUND
            )
    
    @action(detail=False, methods=['get'], url_path='approval-rates')
    def approval_rates(self, request):
        """
        Calcula tasas de aprobación/rechazo.
        
        GET /api/workflow/metrics/approval-rates/?user_id=1&days=30
        """
        user = request.user
        institution_id = user.institution.id if hasattr(user, 'institution') else None
        
        if not institution_id:
            return Response(
                {'error': 'Usuario no tiene institución asociada'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        user_id = request.query_params.get('user_id')
        days = int(request.query_params.get('days', 30))
        
        from api.loans.services.workflow_metrics_service import WorkflowMetricsService
        
        rates = WorkflowMetricsService.get_approval_rates(
            institution_id=institution_id,
            user_id=int(user_id) if user_id else None,
            days=days
        )
        
        return Response(rates)
    
    @action(detail=False, methods=['get'], url_path='average-times')
    def average_times(self, request):
        """
        Calcula tiempos promedio por etapa.
        
        GET /api/workflow/metrics/average-times/?rule_set_id=1&days=30
        """
        user = request.user
        institution_id = user.institution.id if hasattr(user, 'institution') else None
        
        if not institution_id:
            return Response(
                {'error': 'Usuario no tiene institución asociada'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        rule_set_id = request.query_params.get('rule_set_id')
        if not rule_set_id:
            return Response(
                {'error': 'rule_set_id es requerido'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        days = int(request.query_params.get('days', 30))
        
        from api.loans.services.workflow_metrics_service import WorkflowMetricsService
        
        try:
            times = WorkflowMetricsService.get_average_times(
                rule_set_id=int(rule_set_id),
                institution_id=institution_id,
                days=days
            )
            return Response(times)
        except ValueError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_404_NOT_FOUND
            )
    
    @action(detail=False, methods=['get'], url_path='user-performance')
    def user_performance(self, request):
        """
        Obtiene métricas de desempeño de un usuario.
        
        GET /api/workflow/metrics/user-performance/?user_id=1&days=30
        """
        user = request.user
        institution_id = user.institution.id if hasattr(user, 'institution') else None
        
        if not institution_id:
            return Response(
                {'error': 'Usuario no tiene institución asociada'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        user_id = request.query_params.get('user_id', user.id)
        days = int(request.query_params.get('days', 30))
        
        from api.loans.services.workflow_metrics_service import WorkflowMetricsService
        
        performance = WorkflowMetricsService.get_user_performance(
            user_id=int(user_id),
            institution_id=institution_id,
            days=days
        )
        
        return Response(performance)
