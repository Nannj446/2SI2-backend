"""
Modelos para CU-12: Gestionar Documentación Crediticia

Este módulo contiene los modelos para gestionar el checklist de documentos
requeridos por solicitud y el historial de revisiones.
"""

from django.db import models
from django.conf import settings
from api.core.models import TenantModel


class LoanApplicationDocumentRequirement(TenantModel):
    """
    Checklist de documentos requeridos para una solicitud específica.
    
    REFACTORIZADO: Ahora usa ProductDocumentRequirement en lugar de DocumentRequirement.
    Se crea automáticamente al crear la solicitud, basándose en los
    ProductDocumentRequirement del producto crediticio.
    """
    
    class Status(models.TextChoices):
        PENDING = 'PENDING', 'Pendiente'
        UPLOADED = 'UPLOADED', 'Cargado'
        UNDER_REVIEW = 'UNDER_REVIEW', 'En Revisión'
        APPROVED = 'APPROVED', 'Aprobado'
        REJECTED = 'REJECTED', 'Rechazado'
    
    loan_application = models.ForeignKey(
        'loans.LoanApplication',
        on_delete=models.CASCADE,
        related_name='document_checklist',
        verbose_name='Solicitud de Crédito'
    )
    
    product_document_requirement = models.ForeignKey(
        'products.ProductDocumentRequirement',
        on_delete=models.PROTECT,
        related_name='application_requirements',
        verbose_name='Documento Requerido del Producto'
    )
    
    file_resource = models.ForeignKey(
        'storage.FileResource',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='loan_documents',
        verbose_name='Archivo'
    )
    
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        verbose_name='Estado',
        db_index=True
    )
    
    uploaded_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Fecha de Carga'
    )
    
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='uploaded_documents',
        verbose_name='Cargado Por'
    )
    
    reviewed_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Fecha de Revisión'
    )
    
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_documents',
        verbose_name='Revisado Por'
    )
    
    rejection_reason = models.TextField(
        blank=True,
        verbose_name='Motivo de Rechazo'
    )
    
    notes = models.TextField(
        blank=True,
        verbose_name='Notas'
    )
    
    class Meta:
        db_table = 'loan_application_document_requirements'
        verbose_name = 'Documento Requerido de Solicitud'
        verbose_name_plural = 'Documentos Requeridos de Solicitudes'
        ordering = ['product_document_requirement__display_order']
        indexes = [
            models.Index(fields=['loan_application', 'status']),
            models.Index(fields=['status', 'reviewed_at']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['loan_application', 'product_document_requirement'],
                name='unique_doc_per_application'
            )
        ]
    
    def __str__(self):
        return f"{self.product_document_requirement.document_type.name} - {self.loan_application.application_number}"
    
    @property
    def is_mandatory(self):
        """Retorna si el documento es obligatorio."""
        return self.product_document_requirement.is_mandatory
    
    @property
    def document_type(self):
        """Retorna el tipo de documento."""
        return self.product_document_requirement.document_type
    
    @property
    def is_complete(self):
        """Retorna si el documento está completo (aprobado o no obligatorio)."""
        if not self.is_mandatory:
            return True
        return self.status == self.Status.APPROVED
    
    def get_signed_url(self, expires_in=3600):
        """Genera URL firmada para descargar el documento."""
        if self.file_resource:
            return self.file_resource.get_signed_url(expires_in=expires_in)
        return None


class DocumentReviewHistory(TenantModel):
    """
    Historial de revisiones de un documento.
    
    Registra todas las revisiones (aprobaciones/rechazos) de un documento.
    """
    
    class Action(models.TextChoices):
        APPROVED = 'APPROVED', 'Aprobado'
        REJECTED = 'REJECTED', 'Rechazado'
        REQUESTED_REUPLOAD = 'REQUESTED_REUPLOAD', 'Solicitó Re-carga'
    
    document_requirement = models.ForeignKey(
        LoanApplicationDocumentRequirement,
        on_delete=models.CASCADE,
        related_name='review_history',
        verbose_name='Documento'
    )
    
    action = models.CharField(
        max_length=20,
        choices=Action.choices,
        verbose_name='Acción'
    )
    
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='document_reviews',
        verbose_name='Revisado Por'
    )
    
    comments = models.TextField(
        blank=True,
        verbose_name='Comentarios'
    )
    
    file_resource_at_review = models.ForeignKey(
        'storage.FileResource',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='Archivo al Momento de Revisión'
    )
    
    class Meta:
        db_table = 'document_review_history'
        verbose_name = 'Historial de Revisión de Documento'
        verbose_name_plural = 'Historiales de Revisión de Documentos'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['document_requirement', 'created_at']),
            models.Index(fields=['reviewed_by', 'created_at']),
        ]
    
    def __str__(self):
        return f"{self.action} - {self.document_requirement} - {self.created_at}"
