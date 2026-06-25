"""
Modelos para CU-09: Administración de Reglas y Parámetros

Este módulo contiene los modelos para gestionar conjuntos de reglas versionados,
parámetros de productos, requisitos documentales y configuración de workflow.
"""

from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from api.core.models import TenantModel


class TenantRuleSet(TenantModel):
    """
    Conjunto versionado de reglas por tenant.
    
    Cada vez que se activa un conjunto, se crea una nueva versión.
    Las solicitudes guardan un snapshot (FK) al conjunto activo al momento de creación.
    """
    
    class Status(models.TextChoices):
        DRAFT = 'DRAFT', 'Borrador'
        ACTIVE = 'ACTIVE', 'Activa'
        ARCHIVED = 'ARCHIVED', 'Archivada'
    
    version = models.CharField(
        max_length=20,
        verbose_name='Versión',
        help_text='Ej: 1.0.0, 1.1.0, 2.0.0'
    )
    
    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.DRAFT,
        verbose_name='Estado',
        db_index=True
    )
    
    name = models.CharField(
        max_length=200,
        verbose_name='Nombre',
        help_text='Nombre descriptivo del conjunto de reglas'
    )
    
    description = models.TextField(
        blank=True,
        verbose_name='Descripción'
    )
    
    activated_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Fecha de Activación'
    )
    
    activated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='activated_rule_sets',
        verbose_name='Activado Por'
    )
    
    archived_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Fecha de Archivo'
    )
    
    notes = models.TextField(
        blank=True,
        verbose_name='Notas',
        help_text='Notas sobre cambios en esta versión'
    )
    
    class Meta:
        db_table = 'tenant_rule_sets'
        verbose_name = 'Conjunto de Reglas'
        verbose_name_plural = 'Conjuntos de Reglas'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['institution', 'status']),
            models.Index(fields=['institution', 'version']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['institution', 'version'],
                name='unique_version_per_tenant'
            ),
            # Solo puede haber un conjunto ACTIVE por tenant
            models.UniqueConstraint(
                fields=['institution'],
                condition=models.Q(status='ACTIVE'),
                name='unique_active_rule_set_per_tenant'
            )
        ]
    
    def __str__(self):
        return f"{self.institution.name} - v{self.version} ({self.status})"
    
    def increment_version(self):
        """Incrementa la versión automáticamente."""
        parts = self.version.split('.')
        if len(parts) == 3:
            major, minor, patch = map(int, parts)
            return f"{major}.{minor}.{patch + 1}"
        return "1.0.1"


class EligibilityRule(TenantModel):
    """
    Reglas de elegibilidad crediticia por conjunto de reglas.
    
    Define los criterios mínimos que debe cumplir un solicitante.
    """
    
    rule_set = models.OneToOneField(
        TenantRuleSet,
        on_delete=models.CASCADE,
        related_name='eligibility_rule',
        verbose_name='Conjunto de Reglas'
    )
    
    # Relación Cuota-Ingreso
    max_debt_to_income_ratio = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=40.00,
        validators=[MinValueValidator(0)],
        verbose_name='RCI Máximo (%)',
        help_text='Relación Cuota-Ingreso máxima permitida (típicamente 40%)'
    )
    
    # Ingreso Mínimo
    min_income_required = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        verbose_name='Ingreso Mínimo Requerido (Bs)',
        help_text='Ingreso líquido mensual mínimo'
    )
    
    # Antigüedad Laboral
    min_employment_months = models.IntegerField(
        default=6,
        validators=[MinValueValidator(0)],
        verbose_name='Antigüedad Laboral Mínima (meses)'
    )
    
    # Mora Permitida
    max_arrears_allowed = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0)],
        verbose_name='Mora Máxima Permitida (Bs)',
        help_text='Monto máximo de mora activa permitido'
    )
    
    # Categorías CIC Permitidas
    allowed_cic_categories = models.JSONField(
        default=list,
        verbose_name='Categorías CIC Permitidas',
        help_text='Lista de categorías CIC aceptadas: ["A", "B", "C"]'
    )
    
    # Cobertura de Garantía
    min_collateral_coverage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=125.00,
        validators=[MinValueValidator(0)],
        verbose_name='Cobertura Mínima de Garantía (%)',
        help_text='Valor garantía / Monto crédito (típicamente 125%)'
    )
    
    # Edad
    min_age = models.IntegerField(
        default=18,
        validators=[MinValueValidator(18)],
        verbose_name='Edad Mínima'
    )
    
    max_age = models.IntegerField(
        default=70,
        validators=[MinValueValidator(18)],
        verbose_name='Edad Máxima'
    )
    
    class Meta:
        db_table = 'eligibility_rules'
        verbose_name = 'Regla de Elegibilidad'
        verbose_name_plural = 'Reglas de Elegibilidad'
    
    def __str__(self):
        return f"Elegibilidad - {self.rule_set.version}"


class CreditProductParameter(TenantModel):
    """
    Parámetros específicos por producto crediticio dentro de un conjunto de reglas.
    
    Permite configurar límites y condiciones por producto.
    EXTENDIDO en Fase 2 con campos adicionales y relaciones M2M a catálogos.
    """
    
    # ============================================================
    # RELACIONES
    # ============================================================
    rule_set = models.ForeignKey(
        TenantRuleSet,
        on_delete=models.CASCADE,
        related_name='product_parameters',
        verbose_name='Conjunto de Reglas'
    )
    
    # ============================================================
    # MONTOS
    # ============================================================
    min_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        verbose_name='Monto Mínimo (Bs)'
    )
    
    max_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        verbose_name='Monto Máximo (Bs)'
    )
    
    # ============================================================
    # PLAZOS
    # ============================================================
    min_term_months = models.IntegerField(
        validators=[MinValueValidator(1)],
        verbose_name='Plazo Mínimo (meses)'
    )
    
    max_term_months = models.IntegerField(
        validators=[MinValueValidator(1)],
        verbose_name='Plazo Máximo (meses)'
    )
    
    # ============================================================
    # TASAS DE INTERÉS
    # ============================================================
    min_interest_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        verbose_name='Tasa Mínima (%)'
    )
    
    max_interest_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        verbose_name='Tasa Máxima (%)'
    )
    
    interest_type = models.CharField(
        max_length=20,
        choices=[
            ('FIXED', 'Tasa Fija'),
            ('VARIABLE', 'Tasa Variable'),
            ('MIXED', 'Tasa Mixta'),
        ],
        default='FIXED',
        verbose_name='Tipo de Tasa'
    )
    
    # ============================================================
    # COMISIONES Y SEGUROS (NUEVO - Fase 2)
    # ============================================================
    commission_rate_min = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0.00,
        validators=[MinValueValidator(0)],
        verbose_name='Comisión Mínima (%)'
    )
    
    commission_rate_max = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0.00,
        validators=[MinValueValidator(0)],
        verbose_name='Comisión Máxima (%)'
    )
    
    insurance_rate_min = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0.00,
        validators=[MinValueValidator(0)],
        verbose_name='Seguro Mínimo (%)'
    )
    
    insurance_rate_max = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0.00,
        validators=[MinValueValidator(0)],
        verbose_name='Seguro Máximo (%)'
    )
    
    additional_insurance_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0.00,
        validators=[MinValueValidator(0)],
        verbose_name='Seguro Adicional (%)'
    )
    
    # ============================================================
    # SISTEMA DE PAGO (NUEVO - Fase 2)
    # ============================================================
    grace_period_months_min = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0)],
        verbose_name='Período de Gracia Mínimo (meses)'
    )
    
    grace_period_months_max = models.IntegerField(
        default=6,
        validators=[MinValueValidator(0)],
        verbose_name='Período de Gracia Máximo (meses)'
    )
    
    allows_early_payment = models.BooleanField(
        default=True,
        verbose_name='Permite Pago Anticipado'
    )
    
    early_payment_penalty_min = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0.00,
        validators=[MinValueValidator(0)],
        verbose_name='Penalidad Pago Anticipado Mínima (%)'
    )
    
    early_payment_penalty_max = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=5.00,
        validators=[MinValueValidator(0)],
        verbose_name='Penalidad Pago Anticipado Máxima (%)'
    )
    
    # ============================================================
    # CATÁLOGOS (M2M - NUEVO - Fase 2)
    # ============================================================
    allowed_currencies = models.ManyToManyField(
        'Currency',
        related_name='product_parameters',
        verbose_name='Monedas Permitidas',
        blank=True
    )
    
    allowed_payment_frequencies = models.ManyToManyField(
        'PaymentFrequency',
        related_name='product_parameters',
        verbose_name='Frecuencias de Pago Permitidas',
        blank=True
    )
    
    allowed_amortization_systems = models.ManyToManyField(
        'AmortizationSystem',
        related_name='product_parameters',
        verbose_name='Sistemas de Amortización Permitidos',
        blank=True
    )
    
    # ============================================================
    # FINANCIAMIENTO
    # ============================================================
    max_financing_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=100.00,
        validators=[MinValueValidator(0)],
        verbose_name='Porcentaje Máximo de Financiamiento (%)'
    )
    
    # ============================================================
    # REQUISITOS DE ELEGIBILIDAD (NUEVO - Fase 2)
    # ============================================================
    min_income_required = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
        verbose_name='Ingreso Mínimo Requerido (Bs)',
        help_text='Si es NULL, usa el valor de EligibilityRule'
    )
    
    max_debt_to_income_ratio = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
        verbose_name='RCI Máximo (%)',
        help_text='Si es NULL, usa el valor de EligibilityRule'
    )
    
    min_employment_months = models.IntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
        verbose_name='Antigüedad Laboral Mínima (meses)',
        help_text='Si es NULL, usa el valor de EligibilityRule'
    )
    
    min_collateral_coverage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
        verbose_name='Cobertura Mínima de Garantía (%)',
        help_text='Si es NULL, usa el valor de EligibilityRule'
    )
    
    # ============================================================
    # GARANTÍAS
    # ============================================================
    requires_guarantor = models.BooleanField(
        default=False,
        verbose_name='Requiere Garante'
    )
    
    requires_collateral = models.BooleanField(
        default=False,
        verbose_name='Requiere Garantía Real'
    )
    
    # ============================================================
    # SCORING Y APROBACIÓN AUTOMÁTICA (NUEVO - Fase 2)
    # ============================================================
    min_credit_score_required = models.IntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
        verbose_name='Score Mínimo Requerido',
        help_text='Si es NULL, usa el valor de DecisionThreshold'
    )
    
    auto_approval_enabled = models.BooleanField(
        default=False,
        verbose_name='Aprobación Automática Habilitada'
    )
    
    max_auto_approval_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
        verbose_name='Monto Máximo para Aprobación Automática (Bs)',
        help_text='Si es NULL, usa el valor de DecisionThreshold'
    )
    
    class Meta:
        db_table = 'credit_product_parameters'
        verbose_name = 'Parámetro de Producto'
        verbose_name_plural = 'Parámetros de Productos'
        ordering = ['rule_set__version']
        constraints = [
            models.UniqueConstraint(
                fields=['rule_set'],
                name='unique_rule_set_parameter'
            )
        ]
        indexes = [
            models.Index(fields=['rule_set']),
        ]
    
    def __str__(self):
        return f"Parámetros - {self.rule_set.version}"
    
    # ============================================================
    # MÉTODOS DE VALIDACIÓN
    # ============================================================
    def clean(self):
        """Validaciones personalizadas"""
        from django.core.exceptions import ValidationError
        
        errors = {}
        
        # Validar montos
        if self.min_amount and self.max_amount and self.min_amount >= self.max_amount:
            errors['max_amount'] = 'El monto máximo debe ser mayor al mínimo'
        
        # Validar plazos
        if self.min_term_months and self.max_term_months and self.min_term_months >= self.max_term_months:
            errors['max_term_months'] = 'El plazo máximo debe ser mayor al mínimo'
        
        # Validar tasas
        if self.min_interest_rate and self.max_interest_rate and self.min_interest_rate >= self.max_interest_rate:
            errors['max_interest_rate'] = 'La tasa máxima debe ser mayor a la mínima'
        
        # Validar comisiones
        if self.commission_rate_min > self.commission_rate_max:
            errors['commission_rate_max'] = 'La comisión máxima debe ser mayor o igual a la mínima'
        
        # Validar seguros
        if self.insurance_rate_min > self.insurance_rate_max:
            errors['insurance_rate_max'] = 'El seguro máximo debe ser mayor o igual al mínimo'
        
        # Validar período de gracia
        if self.grace_period_months_min > self.grace_period_months_max:
            errors['grace_period_months_max'] = 'El período de gracia máximo debe ser mayor o igual al mínimo'
        
        # Validar penalidad pago anticipado
        if self.early_payment_penalty_min > self.early_payment_penalty_max:
            errors['early_payment_penalty_max'] = 'La penalidad máxima debe ser mayor o igual a la mínima'
        
        if errors:
            raise ValidationError(errors)
    
    # ============================================================
    # MÉTODOS DE ACCESO CON FALLBACK
    # ============================================================
    def get_min_income(self):
        """Obtiene ingreso mínimo con fallback a EligibilityRule"""
        if self.min_income_required is not None:
            return self.min_income_required
        
        try:
            return self.rule_set.eligibility_rule.min_income_required
        except:
            return None
    
    def get_max_dti_ratio(self):
        """Obtiene RCI máximo con fallback a EligibilityRule"""
        if self.max_debt_to_income_ratio is not None:
            return self.max_debt_to_income_ratio
        
        try:
            return self.rule_set.eligibility_rule.max_debt_to_income_ratio
        except:
            return None
    
    def get_min_employment_months(self):
        """Obtiene antigüedad laboral mínima con fallback a EligibilityRule"""
        if self.min_employment_months is not None:
            return self.min_employment_months
        
        try:
            return self.rule_set.eligibility_rule.min_employment_months
        except:
            return None
    
    def get_min_collateral_coverage(self):
        """Obtiene cobertura mínima de garantía con fallback a EligibilityRule"""
        if self.min_collateral_coverage is not None:
            return self.min_collateral_coverage
        
        try:
            return self.rule_set.eligibility_rule.min_collateral_coverage
        except:
            return None
    
    def get_min_credit_score(self):
        """Obtiene score mínimo con fallback a DecisionThreshold"""
        if self.min_credit_score_required is not None:
            return self.min_credit_score_required
        
        try:
            return self.rule_set.decision_threshold.min_score_manual_review
        except:
            return None
    
    def get_max_auto_approval_amount(self):
        """Obtiene monto máximo de aprobación automática con fallback a DecisionThreshold"""
        if self.max_auto_approval_amount is not None:
            return self.max_auto_approval_amount
        
        try:
            return self.rule_set.decision_threshold.max_amount_auto_approval
        except:
            return None


# ============================================================
# DEPRECATED: DocumentRequirement
# ============================================================
# Este modelo ha sido ELIMINADO y reemplazado por ProductDocumentRequirement
# en api/products/models.py
#
# Razón: Los documentos requeridos ahora se configuran directamente en cada
# producto crediticio, no a nivel de conjunto de reglas.
#
# Relación actual:
# DocumentType (Catálogo) ←→ CreditProduct (M2M a través de ProductDocumentRequirement)
#
# class DocumentRequirement(TenantModel):
#     """DEPRECATED - Usar ProductDocumentRequirement en su lugar"""
#     pass
# ============================================================


class WorkflowStageDefinition(TenantModel):
    """
    Definición de etapas del workflow configurable.
    
    Permite configurar las etapas por las que pasa una solicitud.
    Incluye reglas de avance automático y escalamiento.
    """
    
    rule_set = models.ForeignKey(
        TenantRuleSet,
        on_delete=models.CASCADE,
        related_name='workflow_stages',
        verbose_name='Conjunto de Reglas'
    )
    
    stage_name = models.CharField(
        max_length=100,
        verbose_name='Nombre de la Etapa'
    )
    
    stage_code = models.CharField(
        max_length=50,
        verbose_name='Código de la Etapa',
        help_text='DRAFT, SUBMITTED, DOCUMENTS, KYC, SCORING, REVIEW, APPROVED, etc.'
    )
    
    stage_order = models.IntegerField(
        verbose_name='Orden',
        help_text='Orden secuencial de la etapa'
    )
    
    responsible_role = models.ForeignKey(
        'roles.Role',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='workflow_stages',
        verbose_name='Rol Responsable'
    )
    
    time_limit_hours = models.IntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1)],
        verbose_name='Tiempo Límite (horas)',
        help_text='Tiempo máximo para completar la etapa'
    )
    
    is_automated = models.BooleanField(
        default=False,
        verbose_name='Automatizada',
        help_text='Si la etapa se ejecuta automáticamente'
    )
    
    # NUEVOS CAMPOS DINÁMICOS
    
    auto_advance_enabled = models.BooleanField(
        default=False,
        verbose_name='Avance Automático Habilitado',
        help_text='Si la etapa puede avanzar automáticamente al cumplir condiciones'
    )
    
    auto_advance_conditions = models.JSONField(
        default=dict,
        blank=True,
        verbose_name='Condiciones de Avance Automático',
        help_text='Condiciones que deben cumplirse para avanzar automáticamente. Ej: {"documents_complete": true, "kyc_approved": true}'
    )
    
    next_stage_on_success = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        verbose_name='Siguiente Etapa (Éxito)',
        help_text='Código de la etapa siguiente si se completa exitosamente'
    )
    
    next_stage_on_failure = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        verbose_name='Siguiente Etapa (Fallo)',
        help_text='Código de la etapa siguiente si falla (ej: REJECTED)'
    )
    
    requires_manual_approval = models.BooleanField(
        default=True,
        verbose_name='Requiere Aprobación Manual',
        help_text='Si requiere que un usuario apruebe manualmente para avanzar'
    )
    
    escalation_enabled = models.BooleanField(
        default=False,
        verbose_name='Escalamiento Habilitado',
        help_text='Si se debe escalar cuando se excede el tiempo límite'
    )
    
    escalation_rules = models.JSONField(
        default=dict,
        blank=True,
        verbose_name='Reglas de Escalamiento',
        help_text='Configuración de escalamiento por timeout. Ej: {"notify_supervisor": true, "escalate_to_role": "SUPERVISOR", "escalation_message": "..."}'
    )
    
    notification_template = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        verbose_name='Plantilla de Notificación',
        help_text='Nombre de la plantilla de notificación a usar al entrar en esta etapa'
    )
    
    client_message_template = models.TextField(
        null=True,
        blank=True,
        verbose_name='Mensaje para el Cliente',
        help_text='Mensaje que se mostrará al cliente al entrar en esta etapa'
    )
    
    requires_client_action = models.BooleanField(
        default=False,
        verbose_name='Requiere Acción del Cliente',
        help_text='Si el cliente debe realizar alguna acción en esta etapa'
    )
    
    client_action_description = models.TextField(
        null=True,
        blank=True,
        verbose_name='Descripción de Acción del Cliente',
        help_text='Descripción de la acción que debe realizar el cliente'
    )
    
    client_action_url = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        verbose_name='URL de Acción del Cliente',
        help_text='URL relativa donde el cliente puede realizar la acción'
    )
    
    is_final_stage = models.BooleanField(
        default=False,
        verbose_name='Etapa Final',
        help_text='Si esta es una etapa final del workflow (APPROVED, REJECTED, DISBURSED)'
    )
    
    class Meta:
        db_table = 'workflow_stage_definitions'
        verbose_name = 'Definición de Etapa de Workflow'
        verbose_name_plural = 'Definiciones de Etapas de Workflow'
        ordering = ['stage_order']
        constraints = [
            models.UniqueConstraint(
                fields=['rule_set', 'stage_code'],
                name='unique_stage_per_rule_set'
            )
        ]
    
    def __str__(self):
        return f"{self.stage_name} (Orden: {self.stage_order})"
    
    def check_auto_advance_conditions(self, loan_application):
        """
        Verifica si se cumplen las condiciones para avance automático.
        
        Args:
            loan_application: LoanApplication instance
            
        Returns:
            bool: True si se cumplen todas las condiciones
        """
        if not self.auto_advance_enabled or not self.auto_advance_conditions:
            return False
        
        conditions = self.auto_advance_conditions
        
        # Verificar cada condición
        for key, expected_value in conditions.items():
            if key == 'documents_complete':
                if loan_application.documents_status != 'COMPLETE':
                    return False
            elif key == 'kyc_approved':
                if loan_application.identity_verification_status != 'APPROVED':
                    return False
            elif key == 'score_calculated':
                if not hasattr(loan_application, 'credit_score'):
                    return False
            elif key == 'min_score':
                if not hasattr(loan_application, 'credit_score'):
                    return False
                if loan_application.credit_score.score < expected_value:
                    return False
            # Agregar más condiciones según sea necesario
        
        return True
    
    def should_escalate(self, loan_application):
        """
        Verifica si la solicitud debe ser escalada.
        
        Args:
            loan_application: LoanApplication instance
            
        Returns:
            dict: Información de escalamiento o None
        """
        if not self.escalation_enabled or not self.time_limit_hours:
            return None
        
        from django.utils import timezone
        
        # Obtener el último evento de cambio a este estado
        last_event = loan_application.status_history.filter(
            to_status=self.stage_code
        ).order_by('-created_at').first()
        
        if not last_event:
            return None
        
        # Calcular tiempo transcurrido
        time_elapsed = timezone.now() - last_event.created_at
        time_limit = timezone.timedelta(hours=self.time_limit_hours)
        
        if time_elapsed > time_limit:
            return {
                'should_escalate': True,
                'stage': self.stage_name,
                'time_elapsed_hours': time_elapsed.total_seconds() / 3600,
                'time_limit_hours': self.time_limit_hours,
                'escalation_rules': self.escalation_rules
            }
        
        return {
            'should_escalate': False,
            'time_remaining_hours': (time_limit - time_elapsed).total_seconds() / 3600
        }


class DecisionThreshold(TenantModel):
    """
    Umbrales de decisión automática por conjunto de reglas.
    
    Define los scores y montos para aprobación/rechazo automático.
    """
    
    rule_set = models.OneToOneField(
        TenantRuleSet,
        on_delete=models.CASCADE,
        related_name='decision_threshold',
        verbose_name='Conjunto de Reglas'
    )
    
    # Umbrales de Score
    min_score_auto_approval = models.IntegerField(
        default=70,
        validators=[MinValueValidator(0)],
        verbose_name='Score Mínimo para Aprobación Automática',
        help_text='Score >= este valor → aprobación automática'
    )
    
    min_score_manual_review = models.IntegerField(
        default=50,
        validators=[MinValueValidator(0)],
        verbose_name='Score Mínimo para Revisión Manual',
        help_text='Score entre este valor y auto_approval → revisión manual'
    )
    
    max_score_auto_rejection = models.IntegerField(
        default=49,
        validators=[MinValueValidator(0)],
        verbose_name='Score Máximo para Rechazo Automático',
        help_text='Score <= este valor → rechazo automático'
    )
    
    # Umbrales de Monto
    max_amount_auto_approval = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
        verbose_name='Monto Máximo para Aprobación Automática (Bs)',
        help_text='Montos superiores requieren revisión manual'
    )
    
    requires_manager_approval_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
        verbose_name='Monto que Requiere Aprobación de Gerente (Bs)',
        help_text='Montos superiores requieren aprobación de gerente/comité'
    )
    
    class Meta:
        db_table = 'decision_thresholds'
        verbose_name = 'Umbral de Decisión'
        verbose_name_plural = 'Umbrales de Decisión'
    
    def __str__(self):
        return f"Umbrales - {self.rule_set.version}"


class RuleSetAudit(TenantModel):
    """
    Auditoría de cambios en conjuntos de reglas.
    
    Registra todos los cambios realizados a las reglas.
    """
    
    rule_set = models.ForeignKey(
        TenantRuleSet,
        on_delete=models.CASCADE,
        related_name='audit_logs',
        verbose_name='Conjunto de Reglas'
    )
    
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='rule_changes',
        verbose_name='Modificado Por'
    )
    
    change_type = models.CharField(
        max_length=20,
        choices=[
            ('CREATED', 'Creado'),
            ('UPDATED', 'Actualizado'),
            ('ACTIVATED', 'Activado'),
            ('ARCHIVED', 'Archivado'),
        ],
        verbose_name='Tipo de Cambio'
    )
    
    field_name = models.CharField(
        max_length=100,
        blank=True,
        verbose_name='Campo Modificado'
    )
    
    old_value = models.JSONField(
        null=True,
        blank=True,
        verbose_name='Valor Anterior'
    )
    
    new_value = models.JSONField(
        null=True,
        blank=True,
        verbose_name='Valor Nuevo'
    )
    
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        verbose_name='Dirección IP'
    )
    
    user_agent = models.TextField(
        blank=True,
        verbose_name='User Agent'
    )
    
    notes = models.TextField(
        blank=True,
        verbose_name='Notas'
    )
    
    class Meta:
        db_table = 'rule_set_audits'
        verbose_name = 'Auditoría de Reglas'
        verbose_name_plural = 'Auditorías de Reglas'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['rule_set', 'created_at']),
            models.Index(fields=['changed_by', 'created_at']),
        ]
    
    def __str__(self):
        return f"{self.change_type} - {self.rule_set.version} - {self.created_at}"
