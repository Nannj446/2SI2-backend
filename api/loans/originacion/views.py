"""
Vistas para CU-11: Gestionar Originación de Créditos

Proporciona endpoints REST para:
- Crear y gestionar solicitudes de crédito
- Cambiar estados
- Ver timeline y comentarios
- Filtrar y listar solicitudes
"""

from rest_framework import generics, status, viewsets, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Q

from ..models import LoanApplication, LoanApplicationStatusHistory, LoanApplicationComment
from .serializers import (
    CreditApplicationCreateSerializer,
    CreditApplicationUpdateDraftSerializer,
    CreditApplicationSubmitSerializer,
    CreditApplicationChangeStatusSerializer,
    CreditApplicationListSerializer,
    CreditApplicationDetailSerializer,
    CreditApplicationBorrowerListSerializer,
    LoanApplicationStatusHistorySerializer,
    LoanApplicationCommentSerializer,
)
from .services import (
    CreditApplicationService,
    CreditApplicationValidationError,
    InvalidStatusTransitionError,
)
from api.core.permissions import HasPermission
from api.core.pagination import StandardResultsSetPagination


class CreditApplicationViewSet(viewsets.ModelViewSet):
    """
    ViewSet para gestionar solicitudes de crédito (CU-11)
    
    GET /credit-applications/ - Listar solicitudes (según rol)
    POST /credit-applications/ - Crear solicitud en borrador
    GET /credit-applications/{id}/ - Ver detalle
    PATCH /credit-applications/{id}/ - Actualizar borrador
    POST /credit-applications/{id}/submit/ - Enviar solicitud
    POST /credit-applications/{id}/change-status/ - Cambiar estado
    GET /credit-applications/{id}/timeline/ - Ver timeline
    POST /credit-applications/{id}/comments/ - Agregar comentario
    GET /credit-applications/{id}/comments/ - Listar comentarios
    """
    
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsSetPagination
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter, filters.SearchFilter]
    filterset_fields = ['status', 'branch_id', 'product_id', 'identity_verification_status']
    search_fields = ['application_number', 'client__user__email', 'client__user__first_name']
    ordering_fields = ['created_at', 'submitted_at', 'approved_at', 'requested_amount']
    ordering = ['-created_at']
    
    def get_queryset(self):
        """Retornar solicitudes según el rol del usuario"""
        user = self.request.user
        queryset = LoanApplication.objects.select_related(
            'client', 'product', 'branch', 'assigned_to', 'reviewed_by', 'approved_by'
        )
        
        # Verificar si es prestatario (cliente)
        if hasattr(user, 'client_profile'):
            # Solo mostrar sus propias solicitudes
            return queryset.filter(
                client=user.client_profile,
                institution=user.client_profile.institution
            )
        
        # Es personal interno - mostrar solicitudes del tenant
        try:
            # Obtener institución del usuario
            membership = user.institution_memberships.filter(
                is_active=True
            ).first()
            
            if membership:
                queryset = queryset.filter(institution=membership.institution)
                
                # Verificar si está asignado a una sucursal
                branches = user.assigned_branches.filter(
                    institution=membership.institution
                )
                branches_count = branches.count()
                
                if branches_count > 0:
                    queryset = queryset.filter(
                        Q(branch__in=branches) | Q(assigned_to=user)
                    )
                
                return queryset
        except Exception:
            pass
        
        return queryset.none()
    
    def get_serializer_class(self):
        """Retornar serializer según la acción"""
        if self.action == 'create':
            return CreditApplicationCreateSerializer
        elif self.action == 'partial_update':
            return CreditApplicationUpdateDraftSerializer
        elif self.action == 'submit':
            return CreditApplicationSubmitSerializer
        elif self.action == 'change_status':
            return CreditApplicationChangeStatusSerializer
        elif self.action == 'list':
            # Mostrar vista simplificada en listas
            user = self.request.user
            if hasattr(user, 'client_profile'):
                return CreditApplicationBorrowerListSerializer
            return CreditApplicationListSerializer
        elif self.action == 'retrieve':
            return CreditApplicationDetailSerializer
        return CreditApplicationDetailSerializer
    
    def create(self, request, *args, **kwargs):
        """Crear una nueva solicitud de crédito"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        try:
            # Obtener la institución del usuario
            if hasattr(request.user, 'client_profile'):
                institution = request.user.client_profile.institution
            else:
                membership = request.user.institution_memberships.filter(
                    is_active=True
                ).first()
                if not membership:
                    return Response(
                        {'error': 'No tiene institución asociada'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                institution = membership.institution
            
            # Crear solicitud usando el servicio
            application = CreditApplicationService.create_draft(
                user=request.user,
                institution=institution,
                data=serializer.validated_data
            )
            
            response_serializer = CreditApplicationDetailSerializer(
                application, context={'request': request}
            )
            return Response(response_serializer.data, status=status.HTTP_201_CREATED)
        
        except CreditApplicationValidationError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    def partial_update(self, request, pk=None):
        """Actualizar un borrador"""
        application = self.get_object()
        
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        try:
            application = CreditApplicationService.update_draft(
                user=request.user,
                application=application,
                data=serializer.validated_data
            )
            
            response_serializer = CreditApplicationDetailSerializer(
                application, context={'request': request}
            )
            return Response(response_serializer.data)
        
        except CreditApplicationValidationError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['post'])
    def submit(self, request, pk=None):
        """Enviar solicitud para evaluación"""
        application = self.get_object()
        
        try:
            application = CreditApplicationService.submit_application(
                user=request.user,
                application=application,
                check_identity=True
            )
            
            response_serializer = CreditApplicationDetailSerializer(
                application, context={'request': request}
            )
            return Response(response_serializer.data)
        
        except CreditApplicationValidationError as e:
            return Response(
                {'error': str(e), 'requires_identity_verification': True},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['post'])
    def change_status(self, request, pk=None):
        """Cambiar el estado de la solicitud"""
        application = self.get_object()

        if not request.user.is_staff and not request.user.is_superuser:
            try:
                has_role = request.user.user_roles.filter(
                    institution=application.institution,
                    is_active=True,
                ).exists()
            except Exception:
                has_role = False

            if not has_role:
                return Response(
                    {'error': 'No tiene permisos para cambiar el estado de esta solicitud'},
                    status=status.HTTP_403_FORBIDDEN,
                )
        
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        try:
            application = CreditApplicationService.change_status(
                user=request.user,
                application=application,
                new_status=serializer.validated_data['new_status'],
                reason=serializer.validated_data.get('reason', ''),
                metadata={
                    'approved_amount': serializer.validated_data.get('approved_amount'),
                    'approved_term_months': serializer.validated_data.get('approved_term_months'),
                    'approved_interest_rate': serializer.validated_data.get('approved_interest_rate'),
                }
            )
            
            response_serializer = CreditApplicationDetailSerializer(
                application, context={'request': request}
            )
            return Response(response_serializer.data)
        
        except InvalidStatusTransitionError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except CreditApplicationValidationError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['get'])
    def timeline(self, request, pk=None):
        """Obtener timeline de la solicitud"""
        application = self.get_object()
        
        # Verificar si es prestatario
        is_borrower = False
        if hasattr(request.user, 'client_profile'):
            is_borrower = (application.client.user_id == request.user.id)
        
        timeline = CreditApplicationService.get_application_timeline(
            application=application,
            borrower_view=is_borrower
        )
        
        serializer = LoanApplicationStatusHistorySerializer(
            timeline, many=True, context={'request': request}
        )
        return Response(serializer.data)
    
    @action(detail=True, methods=['get', 'post'])
    def comments(self, request, pk=None):
        """Obtener o crear comentarios"""
        application = self.get_object()
    
    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """
        Aprobar solicitud con integración de workflow.
        
        POST /api/loans/credit-applications/{id}/approve/
        Body: {
            "approved_amount": 5000.00,
            "approved_term_months": 12,
            "approved_interest_rate": 15.5,
            "reason": "Cliente cumple requisitos",
            "notes": "Notas adicionales",
            "conditions": ["Condición 1", "Condición 2"]
        }
        """
        application = self.get_object()
        user = request.user
        
        # Validar permisos
        if not user.is_staff and not user.is_superuser:
            try:
                has_role = user.user_roles.filter(
                    institution=application.institution,
                    is_active=True,
                ).exists()
            except Exception:
                has_role = False
            
            if not has_role:
                return Response(
                    {'error': 'No tiene permisos para aprobar solicitudes'},
                    status=status.HTTP_403_FORBIDDEN
                )
        
        # Validar datos
        approved_amount = request.data.get('approved_amount')
        approved_term_months = request.data.get('approved_term_months')
        approved_interest_rate = request.data.get('approved_interest_rate')
        reason = request.data.get('reason', 'Solicitud aprobada')
        notes = request.data.get('notes', '')
        conditions = request.data.get('conditions', [])
        
        if not approved_amount:
            return Response(
                {'error': 'approved_amount es requerido'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            # Obtener workflow execution
            from api.loans.services.workflow_engine import WorkflowEngine
            from api.loans.models_approval import ApprovalDecision, WorkflowStageExecution
            
            workflow_execution = WorkflowEngine.get_workflow_for_application(application)
            
            # Obtener etapa actual
            current_stage_execution = None
            if workflow_execution:
                current_stage_execution = workflow_execution.stage_executions.filter(
                    status__in=['PENDING', 'IN_PROGRESS']
                ).first()
            
            # Cambiar estado usando el servicio existente
            application = CreditApplicationService.change_status(
                user=user,
                application=application,
                new_status='APPROVED',
                reason=reason,
                metadata={
                    'approved_amount': approved_amount,
                    'approved_term_months': approved_term_months,
                    'approved_interest_rate': approved_interest_rate,
                }
            )
            
            # Registrar decisión de aprobación si hay workflow
            if current_stage_execution:
                decision = ApprovalDecision.objects.create(
                    institution=application.institution,
                    loan_application=application,
                    stage_execution=current_stage_execution,
                    decision='APPROVED',
                    decided_by=user,
                    reason=reason,
                    notes=notes,
                    approved_amount=approved_amount,
                    approved_term_months=approved_term_months,
                    approved_interest_rate=approved_interest_rate,
                    conditions=conditions,
                    decision_metadata={
                        'approved_via': 'approve_endpoint',
                        'user_role': user.user_roles.filter(
                            institution=application.institution
                        ).first().role.name if user.user_roles.filter(
                            institution=application.institution
                        ).exists() else 'staff'
                    }
                )
                
                # Completar etapa actual
                current_stage_execution.mark_completed(
                    outcome='SUCCESS',
                    completed_by=user,
                    notes=f'Aprobado: {reason}'
                )
                
                # Transicionar workflow si hay siguiente etapa
                if workflow_execution and current_stage_execution.stage_definition.next_stage_on_success:
                    try:
                        WorkflowEngine.transition_to_stage(
                            workflow_execution=workflow_execution,
                            target_stage_code=current_stage_execution.stage_definition.next_stage_on_success,
                            triggered_by=user,
                            outcome='SUCCESS',
                            notes=f'Aprobado por {user.get_full_name()}'
                        )
                    except Exception as e:
                        # No fallar si hay error en transición
                        import logging
                        logger = logging.getLogger(__name__)
                        logger.error(f"Error en transición de workflow: {str(e)}")
            
            response_serializer = CreditApplicationDetailSerializer(
                application, context={'request': request}
            )
            return Response(response_serializer.data)
        
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        """
        Rechazar solicitud con integración de workflow.
        
        POST /api/loans/credit-applications/{id}/reject/
        Body: {
            "reason": "Motivo del rechazo",
            "notes": "Notas adicionales"
        }
        """
        application = self.get_object()
        user = request.user
        
        # Validar permisos
        if not user.is_staff and not user.is_superuser:
            try:
                has_role = user.user_roles.filter(
                    institution=application.institution,
                    is_active=True,
                ).exists()
            except Exception:
                has_role = False
            
            if not has_role:
                return Response(
                    {'error': 'No tiene permisos para rechazar solicitudes'},
                    status=status.HTTP_403_FORBIDDEN
                )
        
        # Validar datos
        reason = request.data.get('reason')
        notes = request.data.get('notes', '')
        
        if not reason:
            return Response(
                {'error': 'reason es requerido'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            # Obtener workflow execution
            from api.loans.services.workflow_engine import WorkflowEngine
            from api.loans.models_approval import ApprovalDecision
            
            workflow_execution = WorkflowEngine.get_workflow_for_application(application)
            
            # Obtener etapa actual
            current_stage_execution = None
            if workflow_execution:
                current_stage_execution = workflow_execution.stage_executions.filter(
                    status__in=['PENDING', 'IN_PROGRESS']
                ).first()
            
            # Cambiar estado usando el servicio existente
            application = CreditApplicationService.change_status(
                user=user,
                application=application,
                new_status='REJECTED',
                reason=reason,
                metadata={}
            )
            
            # Registrar decisión de rechazo si hay workflow
            if current_stage_execution:
                decision = ApprovalDecision.objects.create(
                    institution=application.institution,
                    loan_application=application,
                    stage_execution=current_stage_execution,
                    decision='REJECTED',
                    decided_by=user,
                    reason=reason,
                    notes=notes,
                    decision_metadata={
                        'rejected_via': 'reject_endpoint',
                        'user_role': user.user_roles.filter(
                            institution=application.institution
                        ).first().role.name if user.user_roles.filter(
                            institution=application.institution
                        ).exists() else 'staff'
                    }
                )
                
                # Completar etapa actual
                current_stage_execution.mark_completed(
                    outcome='FAILURE',
                    completed_by=user,
                    notes=f'Rechazado: {reason}'
                )
                
                # Marcar workflow como completado (estado final)
                if workflow_execution:
                    workflow_execution.mark_completed()
            
            response_serializer = CreditApplicationDetailSerializer(
                application, context={'request': request}
            )
            return Response(response_serializer.data)
        
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['post'])
    def return_to_stage(self, request, pk=None):
        """
        Devolver solicitud a una etapa anterior.
        
        POST /api/loans/credit-applications/{id}/return_to_stage/
        Body: {
            "target_stage_code": "DOCUMENTS",
            "reason": "Faltan documentos",
            "notes": "Notas adicionales"
        }
        """
        application = self.get_object()
        user = request.user
        
        # Validar permisos
        if not user.is_staff and not user.is_superuser:
            try:
                has_role = user.user_roles.filter(
                    institution=application.institution,
                    is_active=True,
                ).exists()
            except Exception:
                has_role = False
            
            if not has_role:
                return Response(
                    {'error': 'No tiene permisos para devolver solicitudes'},
                    status=status.HTTP_403_FORBIDDEN
                )
        
        # Validar datos
        target_stage_code = request.data.get('target_stage_code')
        reason = request.data.get('reason')
        notes = request.data.get('notes', '')
        
        if not target_stage_code or not reason:
            return Response(
                {'error': 'target_stage_code y reason son requeridos'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            # Obtener workflow execution
            from api.loans.services.workflow_engine import WorkflowEngine
            from api.loans.models_approval import ApprovalDecision
            
            workflow_execution = WorkflowEngine.get_workflow_for_application(application)
            
            if not workflow_execution:
                return Response(
                    {'error': 'La solicitud no tiene workflow activo'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Obtener etapa actual
            current_stage_execution = workflow_execution.stage_executions.filter(
                status__in=['PENDING', 'IN_PROGRESS']
            ).first()
            
            if not current_stage_execution:
                return Response(
                    {'error': 'No hay etapa activa para devolver'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Registrar decisión de devolución
            decision = ApprovalDecision.objects.create(
                institution=application.institution,
                loan_application=application,
                stage_execution=current_stage_execution,
                decision='RETURNED',
                decided_by=user,
                reason=reason,
                notes=notes,
                decision_metadata={
                    'returned_to_stage': target_stage_code,
                    'returned_via': 'return_to_stage_endpoint'
                }
            )
            
            # Completar etapa actual
            current_stage_execution.mark_completed(
                outcome='FAILURE',
                completed_by=user,
                notes=f'Devuelto a {target_stage_code}: {reason}'
            )
            
            # Transicionar a etapa anterior
            WorkflowEngine.transition_to_stage(
                workflow_execution=workflow_execution,
                target_stage_code=target_stage_code,
                triggered_by=user,
                outcome='FAILURE',
                notes=f'Devuelto por {user.get_full_name()}: {reason}'
            )
            
            response_serializer = CreditApplicationDetailSerializer(
                application, context={'request': request}
            )
            return Response(response_serializer.data)
        
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['get'])
    def workflow_status(self, request, pk=None):
        """
        Obtener estado del workflow de la solicitud.
        
        GET /api/loans/credit-applications/{id}/workflow_status/
        """
        application = self.get_object()
        
        try:
            from api.loans.services.workflow_engine import WorkflowEngine
            from api.loans.serializers.approval_serializers import (
                WorkflowExecutionDetailSerializer
            )
            
            workflow_execution = WorkflowEngine.get_workflow_for_application(application)
            
            if not workflow_execution:
                return Response({
                    'has_workflow': False,
                    'message': 'La solicitud no tiene workflow activo'
                })
            
            serializer = WorkflowExecutionDetailSerializer(
                workflow_execution,
                context={'request': request}
            )
            
            return Response({
                'has_workflow': True,
                'workflow': serializer.data
            })
        
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if request.method == 'POST':
            # Crear comentario
            try:
                comment_text = request.data.get('comment')
                is_internal = request.data.get('is_internal', True)
                
                if not comment_text:
                    return Response(
                        {'error': 'El comentario no puede estar vacío'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                
                # Verificar permisos
                if hasattr(request.user, 'client_profile'):
                    # Prestatario solo puede crear comentarios públicos
                    is_internal = False
                
                comment = CreditApplicationService.add_comment(
                    user=request.user,
                    application=application,
                    comment_text=comment_text,
                    is_internal=is_internal
                )
                
                serializer = LoanApplicationCommentSerializer(
                    comment, context={'request': request}
                )
                return Response(serializer.data, status=status.HTTP_201_CREATED)
            
            except Exception as e:
                return Response(
                    {'error': str(e)},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        else:
            # Listar comentarios
            comments = application.comments.all()
            
            # Filtrar según permisos
            if hasattr(request.user, 'client_profile'):
                is_borrower = (application.client.user_id == request.user.id)
                if is_borrower:
                    comments = comments.filter(is_internal=False)
            
            serializer = LoanApplicationCommentSerializer(
                comments, many=True, context={'request': request}
            )
            return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def sync_workflow(self, request, pk=None):
        """
        Sincroniza el estado del workflow de una solicitud.
        
        FASE 3 - Endpoint de Sincronización:
        Recalcula el estado correcto basándose en:
        - identity_verification_status
        - documents_status
        - Workflow configurado
        
        Útil para corregir solicitudes "atascadas" donde el estado principal
        no refleja el progreso real.
        
        POST /credit-applications/{id}/sync-workflow/
        
        Returns:
            {
                'success': bool,
                'changed': bool,
                'previous_status': str,
                'new_status': str,
                'reason': str,
                'application': {...}
            }
        """
        application = self.get_object()
        
        try:
            from api.loans.services.workflow_sync_service import WorkflowSyncService
            
            result = WorkflowSyncService.sync_application_workflow(application)
            
            serializer = CreditApplicationDetailSerializer(
                result['application'],
                context={'request': request}
            )
            
            return Response({
                'success': True,
                'changed': result['changed'],
                'previous_status': result['previous_status'],
                'new_status': result['new_status'],
                'reason': result['reason'],
                'application': serializer.data
            })
            
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error sincronizando workflow: {str(e)}", exc_info=True)
            return Response(
                {
                    'success': False,
                    'error': str(e)
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    # ============================================================
    # CU-15: Evaluación Crediticia con IA
    # ============================================================

    @action(detail=True, methods=['post'], url_path='calculate-score')
    def calculate_score(self, request, pk=None):
        """
        Calcula el score crediticio con IA para la solicitud.

        POST /credit-applications/{id}/calculate-score/

        Verifica el feature flag has_ai_scoring del plan.
        Retorna la evaluación completa.
        """
        application = self.get_object()

        # Verificar feature flag has_ai_scoring
        try:
            subscription = getattr(application.institution, 'subscription', None)
            if not subscription:
                return Response(
                    {'error': 'Institución sin suscripción activa.'},
                    status=status.HTTP_403_FORBIDDEN
                )
            plan = getattr(subscription, 'plan', None)
            if not plan or not getattr(plan, 'has_ai_scoring', False):
                return Response(
                    {'error': 'El scoring con IA no está habilitado para su plan.'},
                    status=status.HTTP_403_FORBIDDEN
                )
        except Exception:
            pass

        from api.loans.services.scoring_service import ScoringService

        try:
            evaluation = ScoringService.calculate_score(application)
            application.refresh_from_db()

            # CU-15: Si la decisión automática requiere revisión manual,
            # transicionar la solicitud a IN_REVIEW para que el analista
            # pueda aprobar/rechazar desde la cola de revisión.
            if evaluation.auto_decision in ('MANUAL_REVIEW', 'ESCALATE'):
                try:
                    if application.status not in (
                        'APPROVED', 'REJECTED', 'DISBURSED', 'CANCELLED'
                    ):
                        CreditApplicationService.change_status(
                            user=request.user,
                            application=application,
                            new_status='IN_REVIEW',
                            reason=(
                                f'Evaluación IA: {evaluation.get_auto_decision_display()}'
                                f' (score: {evaluation.score_weighted})'
                            ),
                            metadata={}
                        )
                        application.refresh_from_db()
                except Exception as transition_error:
                    import logging
                    _log = logging.getLogger(__name__)
                    _log.warning(
                        f"No se pudo transicionar a IN_REVIEW: {transition_error}"
                    )

            response_serializer = CreditApplicationDetailSerializer(
                application, context={'request': request}
            )

            bureau_query = application.bureau_queries.order_by(
                '-created_at'
            ).first()

            return Response({
                'evaluation_id': evaluation.id,
                'score_ia': evaluation.score_ia,
                'score_bureau': evaluation.score_bureau,
                'score_weighted': evaluation.score_weighted,
                'risk_level': application.risk_level,
                'risk_level_display': application.get_risk_level_display(),
                'debt_to_income_ratio': (
                    str(application.debt_to_income_ratio)
                    if application.debt_to_income_ratio else None
                ),
                'auto_decision': evaluation.auto_decision,
                'auto_decision_reason': evaluation.auto_decision_reason,
                'evaluated_at': (
                    evaluation.evaluated_at.isoformat()
                    if evaluation.evaluated_at else None
                ),
                'application': response_serializer.data,
                'sub_scores': {
                    'payment_capacity': evaluation.payment_capacity_score,
                    'employment_stability': evaluation.employment_stability_score,
                    'credit_history': evaluation.credit_history_score,
                    'debt_burden': evaluation.debt_burden_score,
                    'demographic': evaluation.demographic_score,
                } if evaluation.status == 'COMPLETED' else None,
                'bureau_query': {
                    'provider': bureau_query.provider if bureau_query else None,
                    'status': bureau_query.status if bureau_query else None,
                    'score_external': bureau_query.score_external if bureau_query else None,
                    'debt_total': (
                        str(bureau_query.debt_total)
                        if bureau_query and bureau_query.debt_total else None
                    ),
                    'has_defaults': bureau_query.has_defaults if bureau_query else None,
                    'cic_category': bureau_query.cic_category if bureau_query else None,
                },
            })

        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error calculando score: {str(e)}", exc_info=True)
            return Response(
                {'error': f'Error calculando score: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['get'])
    def evaluation(self, request, pk=None):
        """
        Retorna la evaluación crediticia más reciente.

        GET /credit-applications/{id}/evaluation/

        Retorna 404 si no hay evaluación.
        """
        application = self.get_object()

        from api.loans.models_scoring import CreditEvaluation

        try:
            evaluation = CreditEvaluation.objects.filter(
                application=application
            ).order_by('-created_at').first()

            if not evaluation:
                return Response(
                    {'error': 'No hay evaluación crediticia para esta solicitud.'},
                    status=status.HTTP_404_NOT_FOUND
                )

            bureau_query = application.bureau_queries.order_by(
                '-created_at'
            ).first()

            return Response({
                'id': evaluation.id,
                'status': evaluation.status,
                'score_ia': evaluation.score_ia,
                'score_bureau': evaluation.score_bureau,
                'score_weighted': evaluation.score_weighted,
                'risk_level': application.risk_level,
                'risk_level_display': application.get_risk_level_display(),
                'debt_to_income_ratio': (
                    str(evaluation.dti_calculated)
                    if evaluation.dti_calculated else None
                ),
                'auto_decision': evaluation.auto_decision,
                'auto_decision_reason': evaluation.auto_decision_reason,
                'eligibility_check_passed': evaluation.eligibility_check_passed,
                'bureau_check_passed': evaluation.bureau_check_passed,
                'dti_calculated': (
                    str(evaluation.dti_calculated)
                    if evaluation.dti_calculated else None
                ),
                'recommended_amount': (
                    str(evaluation.recommended_amount)
                    if evaluation.recommended_amount else None
                ),
                'max_affordable_payment': (
                    str(evaluation.max_affordable_payment)
                    if evaluation.max_affordable_payment else None
                ),
                'sub_scores': {
                    'payment_capacity': evaluation.payment_capacity_score,
                    'employment_stability': evaluation.employment_stability_score,
                    'credit_history': evaluation.credit_history_score,
                    'debt_burden': evaluation.debt_burden_score,
                    'demographic': evaluation.demographic_score,
                },
                'model_version': evaluation.model_version,
                'features_used': evaluation.features_used,
                'evaluated_at': (
                    evaluation.evaluated_at.isoformat()
                    if evaluation.evaluated_at else None
                ),
                'evaluation_time_ms': evaluation.evaluation_time_ms,
                'error_message': evaluation.error_message,
                'bureau_query': {
                    'id': bureau_query.id,
                    'provider': bureau_query.provider,
                    'status': bureau_query.status,
                    'score_external': bureau_query.score_external,
                    'debt_total': (
                        str(bureau_query.debt_total)
                        if bureau_query and bureau_query.debt_total else None
                    ),
                    'has_defaults': bureau_query.has_defaults if bureau_query else None,
                    'cic_category': bureau_query.cic_category if bureau_query else None,
                    'queried_at': (
                        bureau_query.queried_at.isoformat()
                        if bureau_query and bureau_query.queried_at else None
                    ),
                    'response_time_ms': (
                        bureau_query.response_time_ms if bureau_query else None
                    ),
                } if bureau_query else None,
            })

        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error obteniendo evaluación: {str(e)}", exc_info=True)
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
