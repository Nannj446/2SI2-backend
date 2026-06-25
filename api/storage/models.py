"""
Modelos para gestión de archivos en Supabase Storage.
"""
from uuid import uuid4

from django.conf import settings
from django.db import models

from api.core.models import TimeStampedModel


class FileResource(TimeStampedModel):
    """
    Modelo genérico para recursos/archivos almacenados en Supabase Storage.
    
    Soporta múltiples tipos de recursos:
    - Branding white-label (logos, favicons, covers)
    - Documentos de clientes (identidad, ingresos, garantías)
    - Documentos de créditos (solicitudes, contratos, pagos)
    - Archivos de usuarios (perfil, documentos)
    - Backups y exportaciones
    """
    
    class ResourceType(models.TextChoices):
        """Tipos de recursos soportados."""
        BRANDING = 'branding', 'Branding White-Label'
        USER_PROFILE = 'user_profile', 'Perfil de Usuario'
        USER_DOCUMENT = 'user_document', 'Documento de Usuario'
        CUSTOMER_DOCUMENT = 'customer_document', 'Documento de Cliente'
        LOAN_APPLICATION = 'loan_application', 'Solicitud de Crédito'
        LOAN_CONTRACT = 'loan_contract', 'Contrato de Crédito'
        PAYMENT_RECEIPT = 'payment_receipt', 'Comprobante de Pago'
        IDENTITY_DOCUMENT = 'identity_document', 'Documento de Identidad'
        INCOME_PROOF = 'income_proof', 'Comprobante de Ingresos'
        COLLATERAL = 'collateral', 'Garantía'
        BACKUP = 'backup', 'Respaldo'
        EXPORT = 'export', 'Exportación'
        REPORT = 'report', 'Reporte'
    
    class Visibility(models.TextChoices):
        """Niveles de visibilidad del archivo."""
        PRIVATE = 'private', 'Privado (requiere signed URL)'
        PUBLIC = 'public', 'Público'
        TENANT_ONLY = 'tenant_only', 'Solo miembros del tenant'
    
    class Status(models.TextChoices):
        """Estados del archivo."""
        ACTIVE = 'active', 'Activo'
        REPLACED = 'replaced', 'Reemplazado'
        DELETED = 'deleted', 'Eliminado'
        ORPHANED = 'orphaned', 'Huérfano'
    
    # === Identificación ===
    id = models.UUIDField(
        primary_key=True,
        default=uuid4,
        editable=False,
        verbose_name='ID',
    )
    
    tenant = models.ForeignKey(
        'tenants.FinancialInstitution',
        on_delete=models.CASCADE,
        related_name='file_resources',
        verbose_name='Tenant',
        db_index=True,
    )
    
    resource_type = models.CharField(
        max_length=30,
        choices=ResourceType.choices,
        verbose_name='Tipo de Recurso',
        db_index=True,
    )
    
    # === Entidad Relacionada (Opcional) ===
    # Para archivos vinculados a entidades específicas
    entity_type = models.CharField(
        max_length=50,
        blank=True,
        verbose_name='Tipo de Entidad',
        help_text='Ejemplo: tenant_branding, user, customer, loan',
    )
    
    entity_id = models.UUIDField(
        null=True,
        blank=True,
        verbose_name='ID de Entidad',
        help_text='UUID de la entidad relacionada',
    )
    
    # === Metadata del Archivo ===
    original_name = models.CharField(
        max_length=255,
        verbose_name='Nombre Original',
        help_text='Nombre del archivo subido por el usuario',
    )
    
    stored_name = models.CharField(
        max_length=255,
        unique=True,
        verbose_name='Nombre Almacenado',
        help_text='Nombre único generado (UUID)',
    )
    
    file_path = models.CharField(
        max_length=500,
        unique=True,
        verbose_name='Ruta en Storage',
        help_text='Ruta completa en Supabase Storage',
    )
    
    bucket = models.CharField(
        max_length=100,
        default='uploads',
        verbose_name='Bucket',
    )
    
    mime_type = models.CharField(
        max_length=100,
        verbose_name='Tipo MIME',
        help_text='Tipo MIME real del archivo',
    )
    
    extension = models.CharField(
        max_length=20,
        verbose_name='Extensión',
        help_text='Extensión del archivo sin punto',
    )
    
    size = models.BigIntegerField(
        verbose_name='Tamaño (bytes)',
        help_text='Tamaño del archivo en bytes',
    )
    
    category = models.CharField(
        max_length=50,
        blank=True,
        verbose_name='Categoría',
        help_text='Subcategoría del recurso: logo, favicon, cover, identity, contract, etc.',
        db_index=True,
    )
    
    # === Control de Acceso ===
    visibility = models.CharField(
        max_length=20,
        choices=Visibility.choices,
        default=Visibility.PRIVATE,
        verbose_name='Visibilidad',
    )
    
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='uploaded_files',
        verbose_name='Subido por',
        db_index=True,
    )
    
    # === Estado y Versionado ===
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE,
        verbose_name='Estado',
        db_index=True,
    )
    
    replaced_by = models.ForeignKey(
        'self',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='replacement_history',
        verbose_name='Reemplazado por',
    )
    
    # === Integridad ===
    checksum = models.CharField(
        max_length=64,
        blank=True,
        verbose_name='Checksum SHA-256',
        help_text='Hash SHA-256 del archivo para verificar integridad',
    )
    
    # === Metadata Adicional ===
    metadata = models.JSONField(
        default=dict,
        blank=True,
        verbose_name='Metadata Adicional',
        help_text='Metadata adicional en formato JSON',
    )
    
    class Meta:
        db_table = 'file_resources'
        ordering = ['-created_at']
        verbose_name = 'Recurso de Archivo'
        verbose_name_plural = 'Recursos de Archivos'
        indexes = [
            models.Index(fields=['tenant', 'resource_type']),
            models.Index(fields=['tenant', 'status']),
            models.Index(fields=['entity_type', 'entity_id']),
            models.Index(fields=['uploaded_by', 'created_at']),
            models.Index(fields=['category']),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(size__gte=0),
                name='file_resource_size_positive',
            ),
        ]
    
    def __str__(self) -> str:
        return f"{self.resource_type}/{self.category}/{self.stored_name}"
    
    def get_signed_url(self, expires_in: int = 3600) -> str | None:
        """
        Obtener URL firmada para acceso temporal.
        
        Args:
            expires_in: Segundos hasta expiración (default: 1 hora)
        
        Returns:
            URL firmada o None si el archivo no existe
        """
        from api.storage.services import StorageService
        from api.storage.exceptions import FileNotFoundException
        
        service = StorageService()
        try:
            return service.get_signed_url(self.file_path, expires_in)
        except FileNotFoundException:
            # Archivo no existe en storage, retornar None
            return None
    
    def mark_as_replaced(self, new_file: 'FileResource') -> None:
        """Marcar este archivo como reemplazado por otro."""
        self.status = self.Status.REPLACED
        self.replaced_by = new_file
        self.save(update_fields=['status', 'replaced_by', 'updated_at'])
    
    def mark_as_deleted(self) -> None:
        """Marcar archivo como eliminado (soft delete)."""
        self.status = self.Status.DELETED
        self.save(update_fields=['status', 'updated_at'])
    
    def mark_as_orphaned(self) -> None:
        """Marcar archivo como huérfano."""
        self.status = self.Status.ORPHANED
        self.save(update_fields=['status', 'updated_at'])


class FileAccessLog(TimeStampedModel):
    """Log de accesos a archivos para auditoría."""
    
    class Action(models.TextChoices):
        UPLOAD = 'upload', 'Subida'
        DOWNLOAD = 'download', 'Descarga'
        DELETE = 'delete', 'Eliminación'
        REPLACE = 'replace', 'Reemplazo'
        VIEW = 'view', 'Visualización'
    
    file_resource = models.ForeignKey(
        FileResource,
        on_delete=models.CASCADE,
        related_name='access_logs',
        verbose_name='Archivo',
    )
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='file_accesses',
        verbose_name='Usuario',
    )
    
    action = models.CharField(
        max_length=20,
        choices=Action.choices,
        verbose_name='Acción',
    )
    
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        verbose_name='Dirección IP',
    )
    
    user_agent = models.TextField(
        blank=True,
        verbose_name='User Agent',
    )
    
    metadata = models.JSONField(
        default=dict,
        blank=True,
        verbose_name='Metadata',
    )
    
    class Meta:
        db_table = 'file_access_logs'
        ordering = ['-created_at']
        verbose_name = 'Log de Acceso a Archivo'
        verbose_name_plural = 'Logs de Acceso a Archivos'
        indexes = [
            models.Index(fields=['file_resource', 'created_at']),
            models.Index(fields=['user', 'action']),
        ]
    
    def __str__(self) -> str:
        return f"{self.action} - {self.file_resource.stored_name} - {self.user}"
