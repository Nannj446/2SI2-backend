"""
Modelos para motivos de rechazo parametrizados.

SP3-99: Aprobación o Rechazo de Créditos
"""

from django.db import models
from api.core.models import TenantModel


class RejectionReason(TenantModel):
    """
    Motivos de rechazo parametrizados.
    
    Permite definir motivos estándar de rechazo que los analistas
    deben seleccionar al rechazar una solicitud.
    """
    
    code = models.CharField(
        max_length=50,
        verbose_name='Código',
        help_text='Código único del motivo (ej: INSUFFICIENT_INCOME)'
    )
    
    name = models.CharField(
        max_length=200,
        verbose_name='Nombre',
        help_text='Nombre descriptivo del motivo'
    )
    
    description = models.TextField(
        blank=True,
        verbose_name='Descripción',
        help_text='Descripción detallada del motivo'
    )
    
    category = models.CharField(
        max_length=50,
        choices=[
            ('FINANCIAL', 'Financiero'),
            ('DOCUMENTATION', 'Documentación'),
            ('CREDIT_HISTORY', 'Historial Crediticio'),
            ('POLICY', 'Política'),
            ('RISK', 'Riesgo'),
            ('OTHER', 'Otro'),
        ],
        default='OTHER',
        verbose_name='Categoría'
    )
    
    is_active = models.BooleanField(
        default=True,
        verbose_name='Activo',
        help_text='Si está activo para ser seleccionado'
    )
    
    display_order = models.IntegerField(
        default=0,
        verbose_name='Orden de Visualización',
        help_text='Orden en que aparece en la lista'
    )
    
    requires_notes = models.BooleanField(
        default=False,
        verbose_name='Requiere Notas',
        help_text='Si requiere que el analista agregue notas adicionales'
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'loans_rejection_reason'
        verbose_name = 'Motivo de Rechazo'
        verbose_name_plural = 'Motivos de Rechazo'
        ordering = ['display_order', 'name']
        constraints = [
            models.UniqueConstraint(
                fields=['institution', 'code'],
                name='unique_institution_rejection_code'
            )
        ]
    
    def __str__(self):
        return f"{self.name}"
