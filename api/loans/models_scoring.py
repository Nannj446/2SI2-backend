"""
Modelos para CU-15: Evaluación Crediticia con IA.
"""

from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from decimal import Decimal
from api.core.models import TenantModel


class CreditBureauQuery(TenantModel):
    """
    Consulta a buró de crédito (SP3-93).
    """

    class BureauProvider(models.TextChoices):
        INFOCORP = 'INFOCORP', 'Infocorp'
        SENTINEL = 'SENTINEL', 'Sentinel'
        EQUIFAX = 'EQUIFAX', 'Equifax'
        CIC = 'CIC', 'CIC (Central de Información Crediticia)'
        SIMULATED = 'SIMULATED', 'Simulado'

    class QueryStatus(models.TextChoices):
        PENDING = 'PENDING', 'Pendiente'
        SUCCESS = 'SUCCESS', 'Exitosa'
        FAILED = 'FAILED', 'Fallida'
        TIMEOUT = 'TIMEOUT', 'Time Out'

    application = models.ForeignKey(
        'loans.LoanApplication',
        on_delete=models.CASCADE,
        related_name='bureau_queries',
        verbose_name='Solicitud'
    )
    provider = models.CharField(
        max_length=20,
        choices=BureauProvider.choices,
        verbose_name='Proveedor'
    )
    status = models.CharField(
        max_length=20,
        choices=QueryStatus.choices,
        default=QueryStatus.PENDING,
        verbose_name='Estado'
    )
    query_data = models.JSONField(
        default=dict,
        verbose_name='Datos de la consulta',
        help_text='Parámetros enviados al buró'
    )
    response_data = models.JSONField(
        default=dict,
        verbose_name='Respuesta del buró',
        help_text='Respuesta completa del proveedor'
    )
    score_external = models.IntegerField(
        null=True, blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(999)],
        verbose_name='Score Externo',
        help_text='Score reportado por el buró'
    )
    debt_total = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True,
        verbose_name='Deuda Total Reportada'
    )
    has_defaults = models.BooleanField(
        null=True, blank=True,
        verbose_name='Tiene Moras/Defaults'
    )
    default_details = models.JSONField(
        default=dict, blank=True,
        verbose_name='Detalles de Mora'
    )
    cic_category = models.CharField(
        max_length=5, null=True, blank=True,
        verbose_name='Categoría CIC'
    )
    error_message = models.TextField(
        blank=True, verbose_name='Mensaje de Error'
    )
    queried_at = models.DateTimeField(
        null=True, blank=True, verbose_name='Fecha de Consulta'
    )
    response_time_ms = models.IntegerField(
        null=True, blank=True,
        verbose_name='Tiempo de Respuesta (ms)'
    )

    class Meta:
        verbose_name = 'Consulta a Buró de Crédito'
        verbose_name_plural = 'Consultas a Buró de Crédito'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['application', 'provider']),
            models.Index(fields=['status']),
        ]

    def __str__(self):
        return f"{self.provider} - {self.application.application_number} - {self.status}"


class CreditEvaluation(TenantModel):
    """
    Evaluación crediticia completa de una solicitud (CU-15).
    Almacena el resultado de la evaluación automática con IA.
    """

    class EvaluationStatus(models.TextChoices):
        PENDING = 'PENDING', 'Pendiente'
        IN_PROGRESS = 'IN_PROGRESS', 'En Progreso'
        COMPLETED = 'COMPLETED', 'Completada'
        FAILED = 'FAILED', 'Fallida'

    class AutoDecision(models.TextChoices):
        APPROVE = 'APPROVE', 'Aprobar'
        REJECT = 'REJECT', 'Rechazar'
        MANUAL_REVIEW = 'MANUAL_REVIEW', 'Revisión Manual'
        ESCALATE = 'ESCALATE', 'Escalar a Gerente'

    application = models.OneToOneField(
        'loans.LoanApplication',
        on_delete=models.CASCADE,
        related_name='ai_evaluation',
        verbose_name='Solicitud'
    )
    status = models.CharField(
        max_length=20,
        choices=EvaluationStatus.choices,
        default=EvaluationStatus.PENDING,
        verbose_name='Estado'
    )

    # Scores
    score_ia = models.IntegerField(
        null=True, blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(1000)],
        verbose_name='Score IA (0-1000)'
    )
    score_bureau = models.IntegerField(
        null=True, blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(999)],
        verbose_name='Score Buró'
    )
    score_weighted = models.IntegerField(
        null=True, blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(1000)],
        verbose_name='Score Ponderado Final'
    )

    # Factores de scoring (0-100)
    payment_capacity_score = models.IntegerField(
        null=True, blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        verbose_name='Capacidad de Pago (0-100)'
    )
    employment_stability_score = models.IntegerField(
        null=True, blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        verbose_name='Estabilidad Laboral (0-100)'
    )
    credit_history_score = models.IntegerField(
        null=True, blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        verbose_name='Historial Crediticio (0-100)'
    )
    debt_burden_score = models.IntegerField(
        null=True, blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        verbose_name='Carga Deuda (0-100)'
    )
    demographic_score = models.IntegerField(
        null=True, blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        verbose_name='Perfil Demográfico (0-100)'
    )

    # Detalles del análisis
    dti_calculated = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True,
        verbose_name='DTI Calculado (%)'
    )
    recommended_amount = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True,
        verbose_name='Monto Recomendado'
    )
    max_affordable_payment = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True,
        verbose_name='Cuota Máxima Asequible'
    )

    # Features utilizadas por el modelo (trazabilidad)
    features_used = models.JSONField(
        default=dict, blank=True,
        verbose_name='Features del Modelo',
        help_text='Variables de entrada utilizadas para la predicción'
    )
    model_version = models.CharField(
        max_length=50, blank=True,
        verbose_name='Versión del Modelo',
        help_text='Versión del modelo ML utilizado'
    )
    model_metadata = models.JSONField(
        default=dict, blank=True,
        verbose_name='Metadata del Modelo',
        help_text='Información adicional del modelo (features importances, thresholds, etc.)'
    )

    # Flags de decisión
    eligibility_check_passed = models.BooleanField(
        null=True, blank=True,
        verbose_name='Reglas de Elegibilidad OK'
    )
    bureau_check_passed = models.BooleanField(
        null=True, blank=True,
        verbose_name='Buró OK'
    )
    auto_decision = models.CharField(
        max_length=20, null=True, blank=True,
        choices=AutoDecision.choices,
        verbose_name='Decisión Automática'
    )
    auto_decision_reason = models.TextField(
        blank=True,
        verbose_name='Razón de Decisión Automática'
    )

    # Control
    evaluated_at = models.DateTimeField(
        null=True, blank=True,
        verbose_name='Fecha de Evaluación'
    )
    evaluation_time_ms = models.IntegerField(
        null=True, blank=True,
        verbose_name='Tiempo de Evaluación (ms)'
    )
    error_message = models.TextField(
        blank=True, verbose_name='Mensaje de Error'
    )

    class Meta:
        verbose_name = 'Evaluación Crediticia'
        verbose_name_plural = 'Evaluaciones Crediticias'
        indexes = [
            models.Index(fields=['application']),
            models.Index(fields=['status']),
            models.Index(fields=['score_weighted']),
        ]

    def __str__(self):
        return f"Evaluación {self.application.application_number} - Score IA: {self.score_ia}"


class ModelRegistry(TenantModel):
    """
    Registro de versiones del modelo ML.
    """

    class ModelStatus(models.TextChoices):
        DRAFT = 'DRAFT', 'Borrador'
        TRAINING = 'TRAINING', 'Entrenando'
        ACTIVE = 'ACTIVE', 'Activo'
        DEPRECATED = 'DEPRECATED', 'Deprecado'
        FAILED = 'FAILED', 'Fallido'

    version = models.CharField(
        max_length=50, unique=True, verbose_name='Versión'
    )
    status = models.CharField(
        max_length=20,
        choices=ModelStatus.choices,
        default=ModelStatus.DRAFT,
        verbose_name='Estado'
    )
    description = models.TextField(
        blank=True, verbose_name='Descripción'
    )
    algorithm = models.CharField(
        max_length=100, default='GradientBoosting', verbose_name='Algoritmo'
    )
    metrics = models.JSONField(
        default=dict, verbose_name='Métricas (precision, recall, f1)'
    )
    feature_names = models.JSONField(
        default=list, verbose_name='Nombres de Features'
    )
    feature_importances = models.JSONField(
        default=dict, verbose_name='Importancia de Features'
    )
    training_date = models.DateTimeField(
        null=True, blank=True, verbose_name='Fecha de Entrenamiento'
    )
    training_samples = models.IntegerField(
        null=True, blank=True, verbose_name='Muestras de Entrenamiento'
    )
    model_path = models.CharField(
        max_length=500, blank=True, verbose_name='Ruta del Modelo'
    )
    is_active = models.BooleanField(
        default=True, verbose_name='Activo'
    )

    class Meta:
        verbose_name = 'Registro de Modelo'
        verbose_name_plural = 'Registros de Modelos'
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['is_active'],
                condition=models.Q(is_active=True),
                name='unique_active_model'
            )
        ]

    def __str__(self):
        return f"Modelo v{self.version} - {self.algorithm} ({self.status})"
