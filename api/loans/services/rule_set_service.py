"""
Servicio para gestión de conjuntos de reglas (CU-09).

Maneja la lógica de negocio para:
- Creación de conjuntos de reglas
- Activación y versionado
- Creación de snapshots
- Validaciones
- Auditoría
"""

from django.db import transaction
from django.utils import timezone
from api.loans.models_rules import (
    TenantRuleSet,
    EligibilityRule,
    CreditProductParameter,
    # DocumentRequirement,  # DEPRECATED: Eliminado - usar ProductDocumentRequirement
    WorkflowStageDefinition,
    DecisionThreshold,
    RuleSetAudit
)


class RuleSetService:
    """
    Servicio para gestión de conjuntos de reglas.
    """
    
    @staticmethod
    @transaction.atomic
    def create_rule_set(tenant, name, description='', notes='', created_by=None):
        """
        Crea un nuevo conjunto de reglas en estado DRAFT.
        
        Args:
            tenant: FinancialInstitution
            name: Nombre del conjunto
            description: Descripción
            notes: Notas
            created_by: Usuario que crea
        
        Returns:
            TenantRuleSet: Conjunto creado
        """
        # Obtener la última versión
        last_rule_set = TenantRuleSet.objects.filter(
            institution=tenant
        ).order_by('-created_at').first()
        
        if last_rule_set:
            version = last_rule_set.increment_version()
        else:
            version = "1.0.0"
        
        # Crear conjunto
        rule_set = TenantRuleSet.objects.create(
            institution=tenant,
            version=version,
            name=name,
            description=description,
            notes=notes,
            status=TenantRuleSet.Status.DRAFT
        )
        
        # Auditar
        RuleSetAudit.objects.create(
            institution=tenant,
            rule_set=rule_set,
            changed_by=created_by,
            change_type='CREATED',
            notes=f"Conjunto de reglas creado: {name}"
        )
        
        return rule_set
    
    @staticmethod
    @transaction.atomic
    def activate_rule_set(rule_set_id, activated_by, ip_address=None, user_agent=None):
        """
        Activa un conjunto de reglas.
        
        - Archiva el conjunto activo anterior
        - Activa el nuevo conjunto
        - Registra auditoría
        
        Args:
            rule_set_id: ID del conjunto a activar
            activated_by: Usuario que activa
            ip_address: IP del usuario
            user_agent: User agent
        
        Returns:
            TenantRuleSet: Conjunto activado
        
        Raises:
            ValueError: Si el conjunto no está en DRAFT o ya está activo
        """
        rule_set = TenantRuleSet.objects.select_for_update().get(id=rule_set_id)
        
        # Validar estado
        if rule_set.status != TenantRuleSet.Status.DRAFT:
            raise ValueError(f"Solo se pueden activar conjuntos en estado DRAFT. Estado actual: {rule_set.status}")
        
        # Validar que tenga todos los componentes necesarios
        RuleSetService.validate_rule_set_completeness(rule_set)
        
        # Archivar conjunto activo anterior
        previous_active = TenantRuleSet.objects.filter(
            institution=rule_set.institution,
            status=TenantRuleSet.Status.ACTIVE
        ).first()
        
        if previous_active:
            previous_active.status = TenantRuleSet.Status.ARCHIVED
            previous_active.archived_at = timezone.now()
            previous_active.save(update_fields=['status', 'archived_at'])
            
            # Auditar archivo
            RuleSetAudit.objects.create(
                institution=rule_set.institution,
                rule_set=previous_active,
                changed_by=activated_by,
                change_type='ARCHIVED',
                ip_address=ip_address,
                user_agent=user_agent,
                notes=f"Archivado al activar versión {rule_set.version}"
            )
        
        # Activar nuevo conjunto
        rule_set.status = TenantRuleSet.Status.ACTIVE
        rule_set.activated_at = timezone.now()
        rule_set.activated_by = activated_by
        rule_set.save(update_fields=['status', 'activated_at', 'activated_by'])
        
        # Auditar activación
        RuleSetAudit.objects.create(
            institution=rule_set.institution,
            rule_set=rule_set,
            changed_by=activated_by,
            change_type='ACTIVATED',
            ip_address=ip_address,
            user_agent=user_agent,
            notes=f"Conjunto de reglas activado: {rule_set.name}"
        )
        
        return rule_set
    
    @staticmethod
    def get_active_rule_set(tenant):
        """
        Obtiene el conjunto de reglas activo del tenant.
        
        Args:
            tenant: FinancialInstitution
        
        Returns:
            TenantRuleSet or None: Conjunto activo
        """
        return TenantRuleSet.objects.filter(
            institution=tenant,
            status=TenantRuleSet.Status.ACTIVE
        ).first()
    
    @staticmethod
    def create_snapshot(tenant):
        """
        Crea un snapshot del conjunto de reglas activo.
        
        Usado al crear una solicitud de crédito.
        
        Args:
            tenant: FinancialInstitution
        
        Returns:
            TenantRuleSet: Conjunto activo (snapshot)
        
        Raises:
            ValueError: Si no hay conjunto activo
        """
        active_rule_set = RuleSetService.get_active_rule_set(tenant)
        
        if not active_rule_set:
            raise ValueError("No hay conjunto de reglas activo para este tenant")
        
        return active_rule_set
    
    @staticmethod
    def validate_rule_set_completeness(rule_set):
        """
        Valida que el conjunto de reglas tenga todos los componentes necesarios.
        
        Args:
            rule_set: TenantRuleSet
        
        Raises:
            ValueError: Si falta algún componente
        """
        errors = []
        
        # Validar que tenga regla de elegibilidad
        if not hasattr(rule_set, 'eligibility_rule'):
            errors.append("Falta configurar la regla de elegibilidad")
        
        # Validar que tenga umbrales de decisión
        if not hasattr(rule_set, 'decision_threshold'):
            errors.append("Falta configurar los umbrales de decisión")
        
        # Validar que tenga al menos un parámetro de producto
        if not rule_set.product_parameters.exists():
            errors.append("Debe configurar al menos un producto crediticio")
        
        # Validar que tenga al menos una etapa de workflow
        if not rule_set.workflow_stages.exists():
            errors.append("Debe configurar al menos una etapa de workflow")
        
        if errors:
            raise ValueError("; ".join(errors))
    
    @staticmethod
    def validate_rules_consistency(rule_set):
        """
        Valida la consistencia de las reglas.
        
        Args:
            rule_set: TenantRuleSet
        
        Raises:
            ValueError: Si hay inconsistencias
        """
        errors = []
        
        # Validar que los umbrales de decisión sean consistentes
        if hasattr(rule_set, 'decision_threshold'):
            threshold = rule_set.decision_threshold
            
            if not (threshold.min_score_auto_approval > threshold.min_score_manual_review > threshold.max_score_auto_rejection):
                errors.append(
                    "Los umbrales de score deben cumplir: "
                    "auto_approval > manual_review > auto_rejection"
                )
        
        # Validar que los parámetros de productos sean consistentes
        for param in rule_set.product_parameters.all():
            if param.min_amount >= param.max_amount:
                errors.append(
                    f"Producto {param.product.name}: "
                    f"El monto máximo debe ser mayor que el monto mínimo"
                )
            
            if param.min_term_months >= param.max_term_months:
                errors.append(
                    f"Producto {param.product.name}: "
                    f"El plazo máximo debe ser mayor que el plazo mínimo"
                )
            
            if param.min_interest_rate >= param.max_interest_rate:
                errors.append(
                    f"Producto {param.product.name}: "
                    f"La tasa máxima debe ser mayor que la tasa mínima"
                )
        
        if errors:
            raise ValueError("; ".join(errors))
    
    @staticmethod
    @transaction.atomic
    def clone_rule_set(rule_set_id, new_name, cloned_by):
        """
        Clona un conjunto de reglas existente.
        
        Útil para crear una nueva versión basada en una anterior.
        
        Args:
            rule_set_id: ID del conjunto a clonar
            new_name: Nombre del nuevo conjunto
            cloned_by: Usuario que clona
        
        Returns:
            TenantRuleSet: Conjunto clonado
        """
        original = TenantRuleSet.objects.get(id=rule_set_id)
        
        # Crear nuevo conjunto
        new_rule_set = RuleSetService.create_rule_set(
            tenant=original.institution,
            name=new_name,
            description=f"Clonado de {original.name} (v{original.version})",
            notes=f"Clonado de versión {original.version}",
            created_by=cloned_by
        )
        
        # Clonar regla de elegibilidad
        if hasattr(original, 'eligibility_rule'):
            orig_eligibility = original.eligibility_rule
            EligibilityRule.objects.create(
                institution=original.institution,
                rule_set=new_rule_set,
                max_debt_to_income_ratio=orig_eligibility.max_debt_to_income_ratio,
                min_income_required=orig_eligibility.min_income_required,
                min_employment_months=orig_eligibility.min_employment_months,
                max_arrears_allowed=orig_eligibility.max_arrears_allowed,
                allowed_cic_categories=orig_eligibility.allowed_cic_categories,
                min_collateral_coverage=orig_eligibility.min_collateral_coverage,
                min_age=orig_eligibility.min_age,
                max_age=orig_eligibility.max_age
            )
        
        # Clonar parámetros de productos
        for param in original.product_parameters.all():
            CreditProductParameter.objects.create(
                institution=original.institution,
                rule_set=new_rule_set,
                product=param.product,
                min_amount=param.min_amount,
                max_amount=param.max_amount,
                min_term_months=param.min_term_months,
                max_term_months=param.max_term_months,
                min_interest_rate=param.min_interest_rate,
                max_interest_rate=param.max_interest_rate,
                allowed_currencies=param.allowed_currencies,
                payment_frequencies=param.payment_frequencies,
                max_financing_percentage=param.max_financing_percentage,
                requires_guarantor=param.requires_guarantor,
                requires_collateral=param.requires_collateral
            )
        
        # DEPRECATED: Clonar requisitos documentales
        # Los documentos ahora se gestionan directamente en cada producto
        # a través de ProductDocumentRequirement (relación M2M entre CreditProduct y DocumentType)
        # for doc_req in original.document_requirements.all():
        #     DocumentRequirement.objects.create(...)
        
        # Clonar etapas de workflow
        for stage in original.workflow_stages.all():
            WorkflowStageDefinition.objects.create(
                institution=original.institution,
                rule_set=new_rule_set,
                stage_name=stage.stage_name,
                stage_code=stage.stage_code,
                stage_order=stage.stage_order,
                responsible_role=stage.responsible_role,
                time_limit_hours=stage.time_limit_hours,
                is_automated=stage.is_automated,
                escalation_rules=stage.escalation_rules
            )
        
        # Clonar umbrales de decisión
        if hasattr(original, 'decision_threshold'):
            orig_threshold = original.decision_threshold
            DecisionThreshold.objects.create(
                institution=original.institution,
                rule_set=new_rule_set,
                min_score_auto_approval=orig_threshold.min_score_auto_approval,
                min_score_manual_review=orig_threshold.min_score_manual_review,
                max_score_auto_rejection=orig_threshold.max_score_auto_rejection,
                max_amount_auto_approval=orig_threshold.max_amount_auto_approval,
                requires_manager_approval_amount=orig_threshold.requires_manager_approval_amount
            )
        
        return new_rule_set
