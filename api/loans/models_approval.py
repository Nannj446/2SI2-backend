"""
Modelos para el sistema de aprobaciones y ejecución de workflows.

SPRINT 1 - CU-16: Diseñar Flujos de Aprobación
Implementa los modelos necesarios para rastrear la ejecución de workflows
y las decisiones de aprobación.
"""

from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator
from django.utils import timezone
from api.core.models import TenantModel


class WorkflowExecution(TenantModel):
    """
    Representa una ejecución de workflow para una solicitud específica.
    Rastrea el progreso a través de las etapas configuradas.
    
    Cada LoanApplication tiene una WorkflowExecution que registra:
    - Qué workflow (RuleSet) se está usando
    - En qué etapa está actualmente
    - Cuándo inició y finalizó
    - Métricas de tiempo y progreso
    """
    
    loan_application = models.OneToOneField(
        'loans.LoanApplication',
        on_delete=models.CASCADE,
        related_name='workflow_execution',
        verbose_name='Solicitud de Crédito'
    )
    
    rule_set = models.ForeignKey(
        'loans.TenantRuleSet',
        on_delete=models.PROTECT,
        related_name='workflow_executions',
        verbose_name='Conjunto de Reglas',
        help_text='Snapshot del workflow usado (inmutable durante la ejecución)'
    )
    
    current_stage = models.ForeignKey(
        'loans.WorkflowStageDefinition',
        on_delete=models.PROTECT,
        related_name='current_executions',
        verbose_name='Etapa Actual',
        null=True,
        blank=True
    )
    
    # Tiempos
    started_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Iniciado En'
    )
    
    completed_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Completado En'
    )
    
    # Estado
    STATUS_CHOICES = [
        ('IN_PROGRESS', 'En Progreso'),
        ('COMPLETED', 'Completado'),
        ('FAILED', 'Fallido'),
        ('CANCELLED', 'Cancelado'),
    ]
    
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='IN_PROGRESS',
        verbose_name='Estado'
    )
    
    # Métricas
    total_stages_completed = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0)],
        verbose_name='Etapas Completadas'
    )
    
    total_time_seconds = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0)],
        verbose_name='Tiempo Total (segundos)',
        help_text='Tiempo total desde inicio hasta completado'
    )
    
    # Metadata
    execution_data = models.JSONField(
        default=dict,
        blank=True,
        verbose_name='Datos de Ejecución',
        help_text='Datos adicionales del flujo (variables, contexto, etc.)'
    )
    
    class Meta:
        db_table = 'workflow_executions'
        verbose_name = 'Ejecución de Workflow'
        verbose_name_plural = 'Ejecuciones de Workflow'
        ordering = ['-started_at']
        indexes = [
            models.Index(fields=['loan_application']),
            models.Index(fields=['status', 'started_at']),
            models.Index(fields=['current_stage']),
        ]
    
    def __str__(self):
        return f"Workflow #{self.id} - Solicitud {self.loan_application_id} - {self.status}"
    
    def calculate_total_time(self):
        """Calcula el tiempo total de ejecución."""
        if self.completed_at:
            delta = self.completed_at - self.started_at
            self.total_time_seconds = int(delta.total_seconds())
            self.save(update_fields=['total_time_seconds'])
    
    def mark_completed(self):
        """Marca el workflow como completado."""
        self.status = 'COMPLETED'
        self.completed_at = timezone.now()
        self.calculate_total_time()
        self.save(update_fields=['status', 'completed_at', 'total_time_seconds'])
    
    def mark_failed(self):
        """Marca el workflow como fallido."""
        self.status = 'FAILED'
        self.completed_at = timezone.now()
        self.calculate_total_time()
        self.save(update_fields=['status', 'completed_at', 'total_time_seconds'])
    
    def mark_cancelled(self):
        """Marca el workflow como cancelado."""
        self.status = 'CANCELLED'
        self.completed_at = timezone.now()
        self.calculate_total_time()
        self.save(update_fields=['status', 'completed_at', 'total_time_seconds'])


class WorkflowStageExecution(TenantModel):
    """
    Representa la ejecución de una etapa específica dentro de un workflow.
    
    Cada vez que una solicitud entra en una etapa, se crea un registro
    que rastrea:
    - Cuándo entró y salió de la etapa
    - Quién fue asignado y quién completó
    - Si fue escalada
    - El resultado (éxito/fallo)
    - Notas y decisiones
    """
    
    workflow_execution = models.ForeignKey(
        WorkflowExecution,
        on_delete=models.CASCADE,
        related_name='stage_executions',
        verbose_name='Ejecución de Workflow'
    )
    
    stage_definition = models.ForeignKey(
        'loans.WorkflowStageDefinition',
        on_delete=models.PROTECT,
        related_name='stage_executions',
        verbose_name='Definición de Etapa'
    )
    
    # Tiempos
    entered_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Entrada En'
    )
    
    completed_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Completado En'
    )
    
    time_spent_seconds = models.IntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
        verbose_name='Tiempo Gastado (segundos)'
    )
    
    # Estado
    STATUS_CHOICES = [
        ('PENDING', 'Pendiente'),
        ('IN_PROGRESS', 'En Progreso'),
        ('COMPLETED', 'Completado'),
        ('SKIPPED', 'Omitido'),
        ('FAILED', 'Fallido'),
    ]
    
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='PENDING',
        verbose_name='Estado'
    )
    
    OUTCOME_CHOICES = [
        ('SUCCESS', 'Éxito'),
        ('FAILURE', 'Fallo'),
        ('TIMEOUT', 'Timeout'),
        ('CANCELLED', 'Cancelado'),
    ]
    
    outcome = models.CharField(
        max_length=20,
        choices=OUTCOME_CHOICES,
        null=True,
        blank=True,
        verbose_name='Resultado'
    )
    
    # Responsables
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_stage_executions',
        verbose_name='Asignado A'
    )
    
    completed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='completed_stage_executions',
        verbose_name='Completado Por'
    )
    
    # Escalamiento
    is_escalated = models.BooleanField(
        default=False,
        verbose_name='Escalado'
    )
    
    escalated_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Escalado En'
    )
    
    escalated_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='escalated_stage_executions',
        verbose_name='Escalado A'
    )
    
    escalation_reason = models.TextField(
        blank=True,
        verbose_name='Motivo de Escalamiento'
    )
    
    # Decisión
    decision_notes = models.TextField(
        blank=True,
        verbose_name='Notas de Decisión'
    )
    
    decision_data = models.JSONField(
        default=dict,
        blank=True,
        verbose_name='Datos de Decisión',
        help_text='Datos adicionales de la decisión (condiciones, observaciones, etc.)'
    )
    
    class Meta:
        db_table = 'workflow_stage_executions'
        verbose_name = 'Ejecución de Etapa'
        verbose_name_plural = 'Ejecuciones de Etapas'
        ordering = ['entered_at']
        indexes = [
            models.Index(fields=['workflow_execution', 'entered_at']),
            models.Index(fields=['status', 'entered_at']),
            models.Index(fields=['assigned_to', 'status']),
            models.Index(fields=['is_escalated', 'escalated_at']),
        ]
    
    def __str__(self):
        return f"Etapa {self.stage_definition.stage_name} - {self.status}"
    
    def calculate_time_spent(self):
        """Calcula el tiempo gastado en la etapa."""
        if self.completed_at:
            delta = self.completed_at - self.entered_at
            self.time_spent_seconds = int(delta.total_seconds())
            self.save(update_fields=['time_spent_seconds'])
    
    def mark_completed(self, outcome='SUCCESS', completed_by=None, notes=''):
        """Marca la etapa como completada."""
        self.status = 'COMPLETED'
        self.outcome = outcome
        self.completed_at = timezone.now()
        self.completed_by = completed_by
        if notes:
            self.decision_notes = notes
        self.calculate_time_spent()
        self.save(update_fields=[
            'status', 'outcome', 'completed_at', 'completed_by',
            'decision_notes', 'time_spent_seconds'
        ])
    
    def escalate(self, escalated_to=None, reason=''):
        """Escala la etapa a otro usuario."""
        self.is_escalated = True
        self.escalated_at = timezone.now()
        self.escalated_to = escalated_to
        self.escalation_reason = reason
        self.save(update_fields=[
            'is_escalated', 'escalated_at', 'escalated_to', 'escalation_reason'
        ])
    
    def is_overdue(self):
        """Verifica si la etapa está vencida según el SLA."""
        if not self.stage_definition.time_limit_hours:
            return False
        
        if self.completed_at:
            return False
        
        time_limit = timezone.timedelta(hours=self.stage_definition.time_limit_hours)
        time_elapsed = timezone.now() - self.entered_at
        
        return time_elapsed > time_limit
    
    def get_time_remaining_hours(self):
        """Obtiene las horas restantes antes del SLA."""
        if not self.stage_definition.time_limit_hours or self.completed_at:
            return None
        
        time_limit = timezone.timedelta(hours=self.stage_definition.time_limit_hours)
        time_elapsed = timezone.now() - self.entered_at
        time_remaining = time_limit - time_elapsed
        
        return max(0, time_remaining.total_seconds() / 3600)


class ApprovalDecision(TenantModel):
    """
    Registra cada decisión de aprobación/rechazo tomada en el workflow.
    
    Cada vez que un aprobador toma una decisión (aprobar, rechazar, devolver),
    se crea un registro que documenta:
    - Qué decisión se tomó
    - Quién la tomó y cuándo
    - Los motivos y condiciones
    - Los términos aprobados (si aplica)
    """
    
    loan_application = models.ForeignKey(
        'loans.LoanApplication',
        on_delete=models.CASCADE,
        related_name='approval_decisions',
        verbose_name='Solicitud de Crédito'
    )
    
    stage_execution = models.ForeignKey(
        WorkflowStageExecution,
        on_delete=models.CASCADE,
        related_name='decisions',
        verbose_name='Ejecución de Etapa'
    )
    
    # Decisión
    DECISION_CHOICES = [
        ('APPROVED', 'Aprobado'),
        ('REJECTED', 'Rechazado'),
        ('RETURNED', 'Devuelto'),
        ('ESCALATED', 'Escalado'),
        ('OBSERVED', 'Observado'),
    ]
    
    decision = models.CharField(
        max_length=20,
        choices=DECISION_CHOICES,
        verbose_name='Decisión'
    )
    
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='approval_decisions_made',
        verbose_name='Decidido Por'
    )
    
    decided_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Decidido En'
    )
    
    # Detalles
    reason = models.TextField(
        verbose_name='Motivo',
        help_text='Motivo de la decisión'
    )
    
    notes = models.TextField(
        blank=True,
        verbose_name='Notas',
        help_text='Notas adicionales'
    )
    
    # Condiciones aprobadas (si aplica)
    approved_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
        verbose_name='Monto Aprobado'
    )
    
    approved_term_months = models.IntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1)],
        verbose_name='Plazo Aprobado (meses)'
    )
    
    approved_interest_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
        verbose_name='Tasa de Interés Aprobada (%)'
    )
    
    conditions = models.JSONField(
        default=list,
        blank=True,
        verbose_name='Condiciones Especiales',
        help_text='Lista de condiciones especiales de la aprobación'
    )
    
    # Metadata
    decision_metadata = models.JSONField(
        default=dict,
        blank=True,
        verbose_name='Metadata de Decisión',
        help_text='Datos adicionales de la decisión (score, análisis, etc.)'
    )
    
    class Meta:
        db_table = 'approval_decisions'
        verbose_name = 'Decisión de Aprobación'
        verbose_name_plural = 'Decisiones de Aprobación'
        ordering = ['-decided_at']
        indexes = [
            models.Index(fields=['loan_application', 'decided_at']),
            models.Index(fields=['decided_by', 'decided_at']),
            models.Index(fields=['decision', 'decided_at']),
            models.Index(fields=['stage_execution']),
        ]
    
    def __str__(self):
        return f"{self.decision} - Solicitud {self.loan_application_id} por {self.decided_by}"
    
    def has_approved_terms(self):
        """Verifica si la decisión incluye términos aprobados."""
        return bool(
            self.approved_amount or
            self.approved_term_months or
            self.approved_interest_rate
        )
