"""
Modelos para el sistema de backups por tenant.
"""
from django.db import models
from django.conf import settings
from api.core.models import TimeStampedModel


class TenantBackup(TimeStampedModel):
    """
    Registro de un backup generado para un tenant.
    
    Almacena metadata del backup: estado, rutas, métricas, tiempos.
    """
    
    class BackupType(models.TextChoices):
        FULL = 'full', 'Completo'
        METADATA_ONLY = 'metadata_only', 'Solo Metadatos'
        STORAGE_ONLY = 'storage_only', 'Solo Archivos'
    
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pendiente'
        RUNNING = 'running', 'Ejecutando'
        COMPLETED = 'completed', 'Completado'
        FAILED = 'failed', 'Fallido'
        EXPIRED = 'expired', 'Expirado'
    
    # Relaciones
    tenant = models.ForeignKey(
        'tenants.FinancialInstitution',
        on_delete=models.CASCADE,
        related_name='backups',
        verbose_name='Institución Financiera'
    )
    
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='requested_backups',
        verbose_name='Solicitado por'
    )
    
    # Configuración
    backup_type = models.CharField(
        max_length=20,
        choices=BackupType.choices,
        default=BackupType.FULL,
        verbose_name='Tipo de Backup'
    )
    
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        verbose_name='Estado',
        db_index=True
    )
    
    # Storage
    backup_path = models.CharField(
        max_length=500,
        blank=True,
        null=True,
        verbose_name='Ruta en Storage',
        help_text='Ruta completa del archivo en Supabase Storage'
    )
    
    manifest_path = models.CharField(
        max_length=500,
        blank=True,
        null=True,
        verbose_name='Ruta del Manifest',
        help_text='Ruta del archivo manifest.json'
    )
    
    # Métricas
    record_count = models.JSONField(
        default=dict,
        blank=True,
        verbose_name='Conteo de Registros',
        help_text='Diccionario con cantidad de registros por tabla'
    )
    
    file_count = models.PositiveIntegerField(
        default=0,
        verbose_name='Cantidad de Archivos'
    )
    
    total_size_bytes = models.BigIntegerField(
        default=0,
        verbose_name='Tamaño Total (bytes)'
    )
    
    # Tiempos
    started_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Fecha de Inicio'
    )
    
    completed_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Fecha de Completado'
    )
    
    expires_at = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
        verbose_name='Fecha de Expiración',
        help_text='Fecha después de la cual el backup será eliminado'
    )
    
    # Error
    error_message = models.TextField(
        blank=True,
        null=True,
        verbose_name='Mensaje de Error'
    )
    
    # Integridad
    checksum = models.CharField(
        max_length=64,
        blank=True,
        null=True,
        verbose_name='Checksum SHA-256',
        help_text='Hash SHA-256 del archivo de backup'
    )
    
    # Notas
    notes = models.TextField(
        blank=True,
        verbose_name='Notas',
        help_text='Notas adicionales sobre el backup'
    )
    
    class Meta:
        db_table = 'tenant_backups'
        ordering = ['-created_at']
        verbose_name = 'Backup de Tenant'
        verbose_name_plural = 'Backups de Tenants'
        indexes = [
            models.Index(fields=['tenant', '-created_at']),
            models.Index(fields=['status']),
            models.Index(fields=['expires_at']),
        ]
    
    def __str__(self):
        return f"Backup {self.id} - {self.tenant.name} ({self.status})"
    
    @property
    def duration_seconds(self):
        """Duración del backup en segundos."""
        if self.started_at and self.completed_at:
            delta = self.completed_at - self.started_at
            return delta.total_seconds()
        return None
    
    @property
    def is_expired(self):
        """Verifica si el backup ha expirado."""
        if self.expires_at:
            from django.utils import timezone
            return timezone.now() > self.expires_at
        return False
    
    @property
    def total_size_mb(self):
        """Tamaño total en MB."""
        return round(self.total_size_bytes / (1024 * 1024), 2)


class BackupManifest(TimeStampedModel):
    """
    Metadatos del contenido de un backup.
    
    Almacena información detallada sobre qué contiene el backup:
    tablas, registros, archivos, checksums.
    """
    
    # Relación
    backup = models.OneToOneField(
        TenantBackup,
        on_delete=models.CASCADE,
        related_name='manifest',
        verbose_name='Backup'
    )
    
    # Versión del esquema
    schema_version = models.CharField(
        max_length=20,
        default='1.0',
        verbose_name='Versión del Esquema',
        help_text='Versión del formato de backup'
    )
    
    # Contenido
    included_tables = models.JSONField(
        default=list,
        blank=True,
        verbose_name='Tablas Incluidas',
        help_text='Lista de nombres de tablas incluidas en el backup'
    )
    
    record_counts = models.JSONField(
        default=dict,
        blank=True,
        verbose_name='Conteo de Registros',
        help_text='Diccionario con cantidad de registros por tabla'
    )
    
    storage_paths = models.JSONField(
        default=dict,
        blank=True,
        verbose_name='Rutas de Storage',
        help_text='Diccionario con rutas de archivos en Storage'
    )
    
    file_list = models.JSONField(
        default=list,
        blank=True,
        verbose_name='Lista de Archivos',
        help_text='Lista de archivos físicos incluidos'
    )
    
    # Integridad
    checksums = models.JSONField(
        default=dict,
        blank=True,
        verbose_name='Checksums',
        help_text='Diccionario con checksums SHA-256 por archivo'
    )
    
    # Metadata adicional
    generated_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Fecha de Generación'
    )
    
    metadata = models.JSONField(
        default=dict,
        blank=True,
        verbose_name='Metadata Adicional',
        help_text='Información adicional sobre el backup'
    )
    
    class Meta:
        db_table = 'backup_manifests'
        verbose_name = 'Manifest de Backup'
        verbose_name_plural = 'Manifests de Backups'
    
    def __str__(self):
        return f"Manifest - Backup {self.backup.id}"
    
    @property
    def total_records(self):
        """Total de registros en el backup."""
        return sum(self.record_counts.values())
    
    @property
    def total_files(self):
        """Total de archivos en el backup."""
        return len(self.file_list)



class BackupAuditLog(TimeStampedModel):
    """
    Logs de auditoría específicos para operaciones de backup.
    
    Registra todas las acciones relacionadas con backups:
    creación, descarga, eliminación, restauración.
    """
    
    class Action(models.TextChoices):
        REQUESTED = 'backup_requested', 'Backup Solicitado'
        STARTED = 'backup_started', 'Backup Iniciado'
        COMPLETED = 'backup_completed', 'Backup Completado'
        FAILED = 'backup_failed', 'Backup Fallido'
        DOWNLOADED = 'backup_downloaded', 'Backup Descargado'
        DELETED = 'backup_deleted', 'Backup Eliminado'
        EXPIRED = 'backup_expired', 'Backup Expirado'
        RESTORE_STARTED = 'restore_started', 'Restauración Iniciada'
        RESTORE_COMPLETED = 'restore_completed', 'Restauración Completada'
        RESTORE_FAILED = 'restore_failed', 'Restauración Fallida'
        ACCESS_DENIED = 'backup_access_denied', 'Acceso Denegado'
        UNAUTHORIZED_ATTEMPT = 'backup_unauthorized_attempt', 'Intento No Autorizado'
    
    class Severity(models.TextChoices):
        INFO = 'info', 'Información'
        WARNING = 'warning', 'Advertencia'
        ERROR = 'error', 'Error'
        CRITICAL = 'critical', 'Crítico'
    
    # Relaciones
    tenant = models.ForeignKey(
        'tenants.FinancialInstitution',
        on_delete=models.CASCADE,
        related_name='backup_audit_logs',
        verbose_name='Institución Financiera'
    )
    
    backup = models.ForeignKey(
        TenantBackup,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='audit_logs',
        verbose_name='Backup'
    )
    
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='backup_audit_actions',
        verbose_name='Actor'
    )
    
    # Acción
    action = models.CharField(
        max_length=30,
        choices=Action.choices,
        verbose_name='Acción',
        db_index=True
    )
    
    severity = models.CharField(
        max_length=20,
        choices=Severity.choices,
        default=Severity.INFO,
        verbose_name='Severidad'
    )
    
    description = models.TextField(
        verbose_name='Descripción'
    )
    
    # Contexto
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        verbose_name='Dirección IP'
    )
    
    user_agent = models.TextField(
        blank=True,
        verbose_name='User Agent'
    )
    
    # Metadata
    metadata = models.JSONField(
        default=dict,
        blank=True,
        verbose_name='Datos Adicionales',
        help_text='Información adicional sobre la acción'
    )
    
    class Meta:
        db_table = 'backup_audit_logs'
        ordering = ['-created_at']
        verbose_name = 'Log de Auditoría de Backup'
        verbose_name_plural = 'Logs de Auditoría de Backups'
        indexes = [
            models.Index(fields=['tenant', '-created_at']),
            models.Index(fields=['backup']),
            models.Index(fields=['action']),
            models.Index(fields=['severity']),
        ]
    
    def __str__(self):
        return f"{self.action} - {self.tenant.name} ({self.created_at})"
