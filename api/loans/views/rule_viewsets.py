"""
ViewSets para CU-09: Administración de Reglas.

Proporciona endpoints REST para:
- Gestión de conjuntos de reglas (TenantRuleSet)
- Reglas de elegibilidad
- Parámetros de productos crediticios
- Requisitos documentales
"""

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import ValidationError
from api.loans.models_rules import (
    TenantRuleSet,
    EligibilityRule,
    CreditProductParameter,
    # DocumentRequirement,  # DEPRECATED: Eliminado - usar ProductDocumentRequirement
    WorkflowStageDefinition,
    DecisionThreshold,
    RuleSetAudit
)
from api.loans.serializers.rule_serializers import (
    TenantRuleSetSerializer,
    TenantRuleSetWriteSerializer,
    EligibilityRuleSerializer,
    CreditProductParameterSerializer,
    # DocumentRequirementSerializer,  # DEPRECATED: Eliminado
    WorkflowStageDefinitionSerializer,
    DecisionThresholdSerializer,
    RuleSetAuditSerializer
)
from api.loans.services.rule_set_service import RuleSetService
from api.loans.permissions import CanManageRules


class RuleViewSetMixin:
    """Mixin para ViewSets de reglas que necesitan filtrar por institución."""
    
    def get_user_institution(self):
        """Obtiene la institución del usuario autenticado."""
        # Primero intentar usar request.tenant (establecido por TenantMiddleware)
        if hasattr(self.request, 'tenant') and self.request.tenant:
            return self.request.tenant
        
        # Fallback: obtener desde membresías del usuario
        membership = self.request.user.institution_memberships.filter(is_active=True).first()
        if not membership:
            raise ValidationError('El usuario no tiene una institución activa asignada')
        return membership.institution


class TenantRuleSetViewSet(RuleViewSetMixin, viewsets.ModelViewSet):
    """
    ViewSet para gestión de conjuntos de reglas.
    
    Endpoints:
    - GET /api/loans/rule-sets/ - Listar conjuntos
    - POST /api/loans/rule-sets/ - Crear conjunto
    - GET /api/loans/rule-sets/{id}/ - Detalle de conjunto
    - PUT/PATCH /api/loans/rule-sets/{id}/ - Actualizar conjunto (solo DRAFT)
    - DELETE /api/loans/rule-sets/{id}/ - Eliminar conjunto (solo DRAFT)
    - POST /api/loans/rule-sets/{id}/activate/ - Activar conjunto
    - POST /api/loans/rule-sets/{id}/clone/ - Clonar conjunto
    - GET /api/loans/rule-sets/{id}/audit/ - Historial de auditoría
    - GET /api/loans/rule-sets/active/ - Obtener conjunto activo
    """
    
    permission_classes = [IsAuthenticated, CanManageRules]
    
    def get_permissions(self):
        """
        Permite lectura (list, retrieve) a usuarios autenticados.
        Requiere CanManageRules para escritura.
        """
        if self.action in ['list', 'retrieve']:
            return [IsAuthenticated()]
        return [IsAuthenticated(), CanManageRules()]
    
    def get_queryset(self):
        return TenantRuleSet.objects.filter(
            institution=self.get_user_institution()
        ).order_by('-created_at')
    
    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return TenantRuleSetWriteSerializer
        return TenantRuleSetSerializer
    
    def perform_create(self, serializer):
        serializer.save(institution=self.get_user_institution())
    
    @action(detail=True, methods=['post'])
    def activate(self, request, pk=None):
        """
        Activa un conjunto de reglas.
        
        POST /api/loans/rule-sets/{id}/activate/
        """
        rule_set = self.get_object()
        
        try:
            activated = RuleSetService.activate_rule_set(
                rule_set_id=rule_set.id,
                activated_by=request.user,
                ip_address=request.META.get('REMOTE_ADDR'),
                user_agent=request.META.get('HTTP_USER_AGENT')
            )
            
            serializer = self.get_serializer(activated)
            return Response(serializer.data)
        
        except ValueError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['post'])
    def clone(self, request, pk=None):
        """
        Clona un conjunto de reglas.
        
        POST /api/loans/rule-sets/{id}/clone/
        Body: {"name": "Nuevo nombre"}
        """
        rule_set = self.get_object()
        new_name = request.data.get('name')
        
        if not new_name:
            return Response(
                {'error': 'El campo "name" es requerido'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            cloned = RuleSetService.clone_rule_set(
                rule_set_id=rule_set.id,
                new_name=new_name,
                cloned_by=request.user
            )
            
            serializer = self.get_serializer(cloned)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['get'])
    def audit(self, request, pk=None):
        """
        Retorna el historial de auditoría de un conjunto.
        
        GET /api/loans/rule-sets/{id}/audit/
        """
        rule_set = self.get_object()
        audits = rule_set.audit_logs.all()[:50]  # Últimos 50
        
        serializer = RuleSetAuditSerializer(audits, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def active(self, request):
        """
        Retorna el conjunto de reglas activo.
        
        GET /api/loans/rule-sets/active/
        """
        active_rule_set = RuleSetService.get_active_rule_set(request.user.institution)
        
        if not active_rule_set:
            return Response(
                {'error': 'No hay conjunto de reglas activo'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        serializer = self.get_serializer(active_rule_set)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def parameters(self, request, pk=None):
        """
        Retorna los parámetros de productos asociados a este conjunto de reglas.
        
        GET /api/loans/rule-sets/{id}/parameters/
        """
        rule_set = self.get_object()
        parameters = CreditProductParameter.objects.filter(
            rule_set=rule_set
        ).select_related(
            'rule_set',
            'institution'
        ).prefetch_related(
            'allowed_currencies',
            'allowed_payment_frequencies',
            'allowed_amortization_systems'
        )
        
        serializer = CreditProductParameterSerializer(parameters, many=True)
        return Response({'results': serializer.data})
    
    @action(detail=True, methods=['get'], url_path='workflow-stages')
    def workflow_stages(self, request, pk=None):
        """
        Retorna las etapas del workflow asociadas a este conjunto de reglas.
        
        GET /api/loans/rule-sets/{id}/workflow-stages/
        """
        rule_set = self.get_object()
        stages = WorkflowStageDefinition.objects.filter(
            rule_set=rule_set
        ).order_by('stage_order')
        
        serializer = WorkflowStageDefinitionSerializer(stages, many=True)
        return Response({'results': serializer.data})
    
    @action(detail=True, methods=['get'])
    def thresholds(self, request, pk=None):
        """
        Retorna los umbrales de decisión asociados a este conjunto de reglas.
        
        GET /api/loans/rule-sets/{id}/thresholds/
        """
        rule_set = self.get_object()
        thresholds = DecisionThreshold.objects.filter(
            rule_set=rule_set
        )
        
        serializer = DecisionThresholdSerializer(thresholds, many=True)
        return Response({'results': serializer.data})
    
    @action(detail=True, methods=['get'], url_path='eligibility-rules')
    def eligibility_rules(self, request, pk=None):
        """
        Retorna las reglas de elegibilidad asociadas a este conjunto de reglas.
        
        GET /api/loans/rule-sets/{id}/eligibility-rules/
        """
        rule_set = self.get_object()
        rules = EligibilityRule.objects.filter(
            rule_set=rule_set
        )
        
        serializer = EligibilityRuleSerializer(rules, many=True)
        return Response({'results': serializer.data})


class EligibilityRuleViewSet(RuleViewSetMixin, viewsets.ModelViewSet):
    """
    ViewSet para reglas de elegibilidad.
    
    Endpoints:
    - GET /api/loans/eligibility-rules/ - Listar reglas
    - POST /api/loans/eligibility-rules/ - Crear regla
    - GET /api/loans/eligibility-rules/{id}/ - Detalle
    - PUT/PATCH /api/loans/eligibility-rules/{id}/ - Actualizar
    - DELETE /api/loans/eligibility-rules/{id}/ - Eliminar
    """
    
    serializer_class = EligibilityRuleSerializer
    permission_classes = [IsAuthenticated, CanManageRules]
    
    def get_queryset(self):
        return EligibilityRule.objects.filter(
            institution=self.get_user_institution()
        )
    
    def perform_create(self, serializer):
        serializer.save(institution=self.get_user_institution())


class CreditProductParameterViewSet(RuleViewSetMixin, viewsets.ModelViewSet):
    """
    ViewSet para parámetros de productos crediticios.
    
    Endpoints:
    - GET /api/loans/product-parameters/ - Listar parámetros
    - POST /api/loans/product-parameters/ - Crear parámetro
    - GET /api/loans/product-parameters/{id}/ - Detalle
    - PUT/PATCH /api/loans/product-parameters/{id}/ - Actualizar
    - DELETE /api/loans/product-parameters/{id}/ - Eliminar
    - GET /api/loans/product-parameters/{id}/summary/ - Resumen con fallbacks
    - POST /api/loans/product-parameters/{id}/validate/ - Validar configuración
    
    Query params:
    - rule_set: Filtrar por conjunto de reglas
    - has_auto_approval: Filtrar por aprobación automática habilitada
    - min_amount_gte: Monto mínimo mayor o igual a
    - max_amount_lte: Monto máximo menor o igual a
    """
    
    serializer_class = CreditProductParameterSerializer
    permission_classes = [IsAuthenticated, CanManageRules]
    
    def get_queryset(self):
        queryset = CreditProductParameter.objects.filter(
            institution=self.get_user_institution()
        ).select_related(
            'rule_set'
        ).prefetch_related(
            'allowed_currencies',
            'allowed_payment_frequencies',
            'allowed_amortization_systems'
        )
        
        # Filtrar por rule_set
        rule_set_id = self.request.query_params.get('rule_set')
        if rule_set_id:
            queryset = queryset.filter(rule_set_id=rule_set_id)
        
        # Filtrar por aprobación automática
        has_auto_approval = self.request.query_params.get('has_auto_approval')
        if has_auto_approval is not None:
            queryset = queryset.filter(auto_approval_enabled=has_auto_approval.lower() == 'true')
        
        # Filtrar por rango de montos
        min_amount_gte = self.request.query_params.get('min_amount_gte')
        if min_amount_gte:
            queryset = queryset.filter(min_amount__gte=min_amount_gte)
        
        max_amount_lte = self.request.query_params.get('max_amount_lte')
        if max_amount_lte:
            queryset = queryset.filter(max_amount__lte=max_amount_lte)
        
        return queryset
    
    def perform_create(self, serializer):
        serializer.save(institution=self.get_user_institution())
    
    @action(detail=True, methods=['get'])
    def summary(self, request, pk=None):
        """
        Retorna un resumen del parámetro con valores efectivos (incluyendo fallbacks).
        
        GET /api/loans/product-parameters/{id}/summary/
        
        Incluye:
        - Valores configurados directamente
        - Valores con fallback a EligibilityRule
        - Valores con fallback a DecisionThreshold
        """
        param = self.get_object()
        
        summary = {
            'id': param.id,
            'product': {
                'id': param.product.id if param.product else None,
                'name': param.product.name if param.product else None,
            },
            'rule_set': {
                'id': param.rule_set.id,
                'version': param.rule_set.version,
                'status': param.rule_set.status,
            },
            'amounts': {
                'min': float(param.min_amount),
                'max': float(param.max_amount),
            },
            'terms': {
                'min_months': param.min_term_months,
                'max_months': param.max_term_months,
            },
            'interest_rates': {
                'min': float(param.min_interest_rate),
                'max': float(param.max_interest_rate),
                'type': param.interest_type,
            },
            'commissions': {
                'min': float(param.commission_rate_min),
                'max': float(param.commission_rate_max),
            },
            'insurance': {
                'min': float(param.insurance_rate_min),
                'max': float(param.insurance_rate_max),
                'additional': float(param.additional_insurance_rate),
            },
            'grace_period': {
                'min_months': param.grace_period_months_min,
                'max_months': param.grace_period_months_max,
            },
            'early_payment': {
                'allowed': param.allows_early_payment,
                'penalty_min': float(param.early_payment_penalty_min),
                'penalty_max': float(param.early_payment_penalty_max),
            },
            'eligibility': {
                'min_income': float(param.get_min_income()) if param.get_min_income() else None,
                'max_dti_ratio': float(param.get_max_dti_ratio()) if param.get_max_dti_ratio() else None,
                'min_employment_months': param.get_min_employment_months(),
                'min_collateral_coverage': float(param.get_min_collateral_coverage()) if param.get_min_collateral_coverage() else None,
            },
            'scoring': {
                'min_credit_score': param.get_min_credit_score(),
                'auto_approval_enabled': param.auto_approval_enabled,
                'max_auto_approval_amount': float(param.get_max_auto_approval_amount()) if param.get_max_auto_approval_amount() else None,
            },
            'catalogs': {
                'currencies': [
                    {'id': c.id, 'code': c.code, 'name': c.name}
                    for c in param.allowed_currencies.all()
                ],
                'payment_frequencies': [
                    {'id': f.id, 'code': f.code, 'name': f.name}
                    for f in param.allowed_payment_frequencies.all()
                ],
                'amortization_systems': [
                    {'id': s.id, 'code': s.code, 'name': s.name}
                    for s in param.allowed_amortization_systems.all()
                ],
            },
            'requirements': {
                'guarantor': param.requires_guarantor,
                'collateral': param.requires_collateral,
            },
        }
        
        return Response(summary)
    
    @action(detail=True, methods=['post'])
    def validate(self, request, pk=None):
        """
        Valida la configuración del parámetro.
        
        POST /api/loans/product-parameters/{id}/validate/
        
        Verifica:
        - Rangos de montos, plazos, tasas
        - Configuración de catálogos (al menos uno de cada)
        - Consistencia de valores con fallbacks
        """
        param = self.get_object()
        errors = []
        warnings = []
        
        # Validar rangos
        if param.min_amount >= param.max_amount:
            errors.append('El monto máximo debe ser mayor al mínimo')
        
        if param.min_term_months >= param.max_term_months:
            errors.append('El plazo máximo debe ser mayor al mínimo')
        
        if param.min_interest_rate >= param.max_interest_rate:
            errors.append('La tasa máxima debe ser mayor a la mínima')
        
        # Validar catálogos
        if not param.allowed_currencies.exists():
            errors.append('Debe configurar al menos una moneda permitida')
        
        if not param.allowed_payment_frequencies.exists():
            errors.append('Debe configurar al menos una frecuencia de pago')
        
        if not param.allowed_amortization_systems.exists():
            warnings.append('No hay sistemas de amortización configurados')
        
        # Validar elegibilidad
        if not param.get_min_income():
            warnings.append('No hay ingreso mínimo configurado (ni en parámetro ni en regla de elegibilidad)')
        
        # Validar scoring
        if param.auto_approval_enabled and not param.get_max_auto_approval_amount():
            warnings.append('Aprobación automática habilitada pero sin monto máximo configurado')
        
        return Response({
            'valid': len(errors) == 0,
            'errors': errors,
            'warnings': warnings,
        })



# ============================================================
# DEPRECATED: DocumentRequirementViewSet
# ============================================================
# Este ViewSet ha sido ELIMINADO.
# Los documentos requeridos ahora se gestionan directamente en cada producto
# a través de ProductDocumentRequirement (relación M2M entre CreditProduct y DocumentType).
#
# Usar en su lugar:
# - GET /api/products/credit-products/{id}/ - incluye document_requirements
# - POST/PUT /api/products/credit-products/ - con campo document_requirements
#
# Migración: 0012_remove_document_requirement_model.py
# Fecha: 2026-05-10
# ============================================================


class WorkflowStageDefinitionViewSet(RuleViewSetMixin, viewsets.ModelViewSet):
    """
    ViewSet para definición de etapas del workflow.
    
    Endpoints:
    - GET /api/loans/workflow-stages/ - Listar etapas
    - POST /api/loans/workflow-stages/ - Crear etapa
    - GET /api/loans/workflow-stages/{id}/ - Detalle
    - PUT/PATCH /api/loans/workflow-stages/{id}/ - Actualizar
    - DELETE /api/loans/workflow-stages/{id}/ - Eliminar
    
    Query params:
    - rule_set: Filtrar por conjunto de reglas
    """
    
    serializer_class = WorkflowStageDefinitionSerializer
    permission_classes = [IsAuthenticated, CanManageRules]
    
    def get_queryset(self):
        queryset = WorkflowStageDefinition.objects.filter(
            institution=self.get_user_institution()
        )
        
        # Filtrar por rule_set si se proporciona
        rule_set_id = self.request.query_params.get('rule_set')
        if rule_set_id:
            queryset = queryset.filter(rule_set_id=rule_set_id)
        
        return queryset.order_by('stage_order')
    
    def perform_create(self, serializer):
        serializer.save(institution=self.get_user_institution())


class DecisionThresholdViewSet(RuleViewSetMixin, viewsets.ModelViewSet):
    """
    ViewSet para umbrales de decisión.
    
    Endpoints:
    - GET /api/loans/decision-thresholds/ - Listar umbrales
    - POST /api/loans/decision-thresholds/ - Crear umbral
    - GET /api/loans/decision-thresholds/{id}/ - Detalle
    - PUT/PATCH /api/loans/decision-thresholds/{id}/ - Actualizar
    - DELETE /api/loans/decision-thresholds/{id}/ - Eliminar
    
    Query params:
    - rule_set: Filtrar por conjunto de reglas
    """
    
    serializer_class = DecisionThresholdSerializer
    permission_classes = [IsAuthenticated, CanManageRules]
    
    def get_queryset(self):
        queryset = DecisionThreshold.objects.filter(
            institution=self.get_user_institution()
        )
        
        # Filtrar por rule_set si se proporciona
        rule_set_id = self.request.query_params.get('rule_set')
        if rule_set_id:
            queryset = queryset.filter(rule_set_id=rule_set_id)
        
        return queryset
    
    def perform_create(self, serializer):
        serializer.save(institution=self.get_user_institution())