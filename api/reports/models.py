"""
Modelos para el módulo de reportes personalizables.

Este módulo define los modelos para:
- Plantillas de reportes reutilizables
- Reportes generados
- Solicitudes de reportes por voz
"""
from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from api.core.models import TimeStampedModel


class ReportTemplate(TimeStampedModel):
    """
    Plantilla de reporte reutilizable.
    
    Permite a los usuarios guardar configuraciones de reportes
    para reutilizarlas posteriormente.
    """
    
    class ScopeChoices(models.TextChoices):
        TENANT = 'TENANT', _('Tenant')
        SAAS = 'SAAS', _('SaaS')
    
    # Relación con tenant (nullable para reportes SAAS)
    institution = models.ForeignKey(
        'tenants.FinancialInstitution',
        on_delete=models.CASCADE,
        related_name='report_templates',
        null=True,
        blank=True,
        verbose_name=_('Institución'),
        help_text=_('Institución financiera. Null para reportes SAAS.')
    )
    
    # Scope del reporte
    scope = models.CharField(
        max_length=10,
        choices=ScopeChoices.choices,
        verbose_name=_('Scope'),
        help_text=_('Alcance del reporte: TENANT o SAAS')
    )
    
    # Categoría y tipo de reporte
    category = models.CharField(
        max_length=50,
        verbose_name=_('Categoría'),
        help_text=_('Categoría del reporte (CREDITS, CUSTOMERS, etc.)')
    )
    
    report_type = models.CharField(
        max_length=100,
        verbose_name=_('Tipo de Reporte'),
        help_text=_('Tipo específico de reporte según catálogo')
    )
    
    # Información de la plantilla
    name = models.CharField(
        max_length=200,
        verbose_name=_('Nombre'),
        help_text=_('Nombre descriptivo de la plantilla')
    )
    
    description = models.TextField(
        blank=True,
        null=True,
        verbose_name=_('Descripción'),
        help_text=_('Descripción opcional de la plantilla')
    )
    
    # Configuración JSON del reporte
    config_json = models.JSONField(
        verbose_name=_('Configuración JSON'),
        help_text=_('Configuración completa del reporte en formato JSON')
    )
    
    # Usuario que creó la plantilla
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='created_report_templates',
        verbose_name=_('Creado por')
    )
    
    # Estado
    is_active = models.BooleanField(
        default=True,
        verbose_name=_('Activo'),
        help_text=_('Indica si la plantilla está activa')
    )
    
    class Meta:
        db_table = 'reports_template'
        ordering = ['-created_at']
        verbose_name = _('Plantilla de Reporte')
        verbose_name_plural = _('Plantillas de Reportes')
        indexes = [
            models.Index(fields=['institution', 'scope', 'category']),
            models.Index(fields=['created_by', 'is_active']),
            models.Index(fields=['scope', 'category', 'report_type']),
        ]
    
    def __str__(self):
        return f'{self.name} ({self.scope}/{self.category})'
    
    def clean(self):
        """Validaciones personalizadas."""
        from django.core.exceptions import ValidationError
        
        # Validar que reportes TENANT tengan institution
        if self.scope == self.ScopeChoices.TENANT and not self.institution:
            raise ValidationError({
                'institution': _('Los reportes TENANT deben tener una institución asociada.')
            })
        
        # Validar que reportes SAAS no tengan institution
        if self.scope == self.ScopeChoices.SAAS and self.institution:
            raise ValidationError({
                'institution': _('Los reportes SAAS no deben tener una institución asociada.')
            })


class GeneratedReport(TimeStampedModel):
    """
    Reporte generado.
    
    Representa un reporte que ha sido generado y almacenado.
    """
    
    class ScopeChoices(models.TextChoices):
        TENANT = 'TENANT', _('Tenant')
        SAAS = 'SAAS', _('SaaS')
    
    class StatusChoices(models.TextChoices):
        PENDING = 'PENDING', _('Pendiente')
        PROCESSING = 'PROCESSING', _('Procesando')
        COMPLETED = 'COMPLETED', _('Completado')
        FAILED = 'FAILED', _('Fallido')
    
    class GenerationSourceChoices(models.TextChoices):
        MANUAL = 'MANUAL', _('Manual')
        AUDIO = 'AUDIO', _('Audio')
    
    class FormatChoices(models.TextChoices):
        CSV = 'csv', _('CSV')
        XLSX = 'xlsx', _('XLSX')
    
    # Relación con tenant (nullable para reportes SAAS)
    institution = models.ForeignKey(
        'tenants.FinancialInstitution',
        on_delete=models.CASCADE,
        related_name='generated_reports',
        null=True,
        blank=True,
        verbose_name=_('Institución'),
        help_text=_('Institución financiera. Null para reportes SAAS.')
    )
    
    # Scope del reporte
    scope = models.CharField(
        max_length=10,
        choices=ScopeChoices.choices,
        verbose_name=_('Scope')
    )
    
    # Categoría y tipo de reporte
    category = models.CharField(
        max_length=50,
        verbose_name=_('Categoría')
    )
    
    report_type = models.CharField(
        max_length=100,
        verbose_name=_('Tipo de Reporte')
    )
    
    # Usuario que solicitó el reporte
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='requested_reports',
        verbose_name=_('Solicitado por')
    )
    
    # Configuración JSON del reporte
    config_json = models.JSONField(
        verbose_name=_('Configuración JSON'),
        help_text=_('Configuración completa del reporte')
    )
    
    # Fuente de generación
    generation_source = models.CharField(
        max_length=10,
        choices=GenerationSourceChoices.choices,
        default=GenerationSourceChoices.MANUAL,
        verbose_name=_('Fuente de Generación')
    )
    
    # Relación con solicitud de voz (si aplica)
    voice_request = models.ForeignKey(
        'VoiceReportRequest',
        on_delete=models.SET_NULL,
        related_name='generated_reports',
        null=True,
        blank=True,
        verbose_name=_('Solicitud de Voz')
    )
    
    # Estado del reporte
    status = models.CharField(
        max_length=20,
        choices=StatusChoices.choices,
        default=StatusChoices.PENDING,
        verbose_name=_('Estado')
    )
    
    # Formato de archivo
    file_format = models.CharField(
        max_length=10,
        choices=FormatChoices.choices,
        verbose_name=_('Formato de Archivo')
    )
    
    # Archivo generado
    file_resource = models.ForeignKey(
        'storage.FileResource',
        on_delete=models.SET_NULL,
        related_name='generated_reports',
        null=True,
        blank=True,
        verbose_name=_('Archivo')
    )
    
    # Métricas
    file_size_bytes = models.BigIntegerField(
        null=True,
        blank=True,
        verbose_name=_('Tamaño de Archivo (bytes)'),
        help_text=_('Tamaño del archivo generado en bytes')
    )
    
    row_count = models.IntegerField(
        null=True,
        blank=True,
        verbose_name=_('Cantidad de Filas'),
        help_text=_('Número de filas en el reporte')
    )
    
    processing_time_seconds = models.IntegerField(
        null=True,
        blank=True,
        verbose_name=_('Tiempo de Procesamiento (seg)'),
        help_text=_('Tiempo que tomó generar el reporte')
    )
    
    # Error (si aplica)
    error_message = models.TextField(
        blank=True,
        null=True,
        verbose_name=_('Mensaje de Error'),
        help_text=_('Mensaje de error si la generación falló')
    )
    
    # Timestamp de completado
    completed_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('Completado en')
    )
    
    class Meta:
        db_table = 'reports_generated'
        ordering = ['-created_at']
        verbose_name = _('Reporte Generado')
        verbose_name_plural = _('Reportes Generados')
        indexes = [
            models.Index(fields=['institution', 'scope', 'status']),
            models.Index(fields=['requested_by', 'created_at']),
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['generation_source', 'status']),
        ]
    
    def __str__(self):
        return f'{self.report_type} - {self.status} ({self.created_at})'
    
    def mark_as_processing(self):
        """Marca el reporte como en procesamiento."""
        self.status = self.StatusChoices.PROCESSING
        self.save(update_fields=['status', 'updated_at'])
    
    def mark_as_completed(self, file_resource, row_count, processing_time, file_size_bytes=None):
        """Marca el reporte como completado."""
        from django.utils import timezone
        
        self.status = self.StatusChoices.COMPLETED
        self.file_resource = file_resource
        self.row_count = row_count
        self.processing_time_seconds = processing_time
        self.file_size_bytes = file_size_bytes or (file_resource.size if file_resource else None)
        self.completed_at = timezone.now()
        self.save(update_fields=[
            'status', 'file_resource', 'row_count',
            'processing_time_seconds', 'file_size_bytes', 'completed_at', 'updated_at'
        ])
    
    def mark_as_failed(self, error_message):
        """Marca el reporte como fallido."""
        from django.utils import timezone
        
        self.status = self.StatusChoices.FAILED
        self.error_message = error_message
        self.completed_at = timezone.now()
        self.save(update_fields=['status', 'error_message', 'completed_at', 'updated_at'])


class VoiceReportRequest(TimeStampedModel):
    """
    Solicitud de reporte mediante voz.
    
    Almacena la transcripción, interpretación y validación
    de una orden de voz para generar un reporte.
    """
    
    class ScopeChoices(models.TextChoices):
        TENANT = 'TENANT', _('Tenant')
        SAAS = 'SAAS', _('SaaS')
    
    class ValidationStatusChoices(models.TextChoices):
        VALID = 'VALID', _('Válido')
        NEEDS_REVIEW = 'NEEDS_REVIEW', _('Necesita Revisión')
        INVALID = 'INVALID', _('Inválido')
    
    # Relación con tenant (nullable para reportes SAAS)
    institution = models.ForeignKey(
        'tenants.FinancialInstitution',
        on_delete=models.CASCADE,
        related_name='voice_report_requests',
        null=True,
        blank=True,
        verbose_name=_('Institución')
    )
    
    # Scope del reporte
    scope = models.CharField(
        max_length=10,
        choices=ScopeChoices.choices,
        verbose_name=_('Scope')
    )
    
    # Usuario que solicitó el reporte
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='voice_report_requests',
        verbose_name=_('Solicitado por')
    )
    
    # Archivo de audio
    audio_file_resource = models.ForeignKey(
        'storage.FileResource',
        on_delete=models.SET_NULL,
        related_name='voice_report_requests',
        null=True,
        blank=True,
        verbose_name=_('Archivo de Audio')
    )
    
    audio_duration_seconds = models.IntegerField(
        default=0,
        verbose_name=_('Duración de Audio (seg)')
    )
    
    # Transcripción
    transcription = models.TextField(
        blank=True,
        null=True,
        verbose_name=_('Transcripción'),
        help_text=_('Texto transcrito del audio')
    )
    
    transcription_language = models.CharField(
        max_length=10,
        blank=True,
        null=True,
        verbose_name=_('Idioma de Transcripción')
    )
    
    # Intención parseada
    parsed_intent_json = models.JSONField(
        blank=True,
        null=True,
        verbose_name=_('Intención Parseada JSON'),
        help_text=_('Intención interpretada por IA en formato JSON')
    )
    
    # Validación
    validation_status = models.CharField(
        max_length=20,
        choices=ValidationStatusChoices.choices,
        default=ValidationStatusChoices.NEEDS_REVIEW,
        verbose_name=_('Estado de Validación')
    )
    
    missing_fields_json = models.JSONField(
        blank=True,
        null=True,
        verbose_name=_('Campos Faltantes JSON'),
        help_text=_('Lista de campos faltantes en la configuración')
    )
    
    unsupported_terms_json = models.JSONField(
        blank=True,
        null=True,
        verbose_name=_('Términos No Soportados JSON'),
        help_text=_('Lista de términos no soportados detectados')
    )
    
    # Error (si aplica)
    error_message = models.TextField(
        blank=True,
        null=True,
        verbose_name=_('Mensaje de Error')
    )
    
    # Modelos de Groq utilizados
    groq_transcription_model = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name=_('Modelo de Transcripción Groq')
    )
    
    groq_chat_model = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name=_('Modelo de Chat Groq')
    )
    
    # Tiempo de procesamiento
    processing_time_seconds = models.IntegerField(
        default=0,
        verbose_name=_('Tiempo de Procesamiento (seg)')
    )
    
    class Meta:
        db_table = 'reports_voice_request'
        ordering = ['-created_at']
        verbose_name = _('Solicitud de Reporte por Voz')
        verbose_name_plural = _('Solicitudes de Reportes por Voz')
        indexes = [
            models.Index(fields=['institution', 'validation_status']),
            models.Index(fields=['requested_by', 'created_at']),
            models.Index(fields=['validation_status', 'created_at']),
        ]
    
    def __str__(self):
        return f'Voice Request {self.id} - {self.validation_status} ({self.created_at})'
