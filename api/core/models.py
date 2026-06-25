"""
Modelos base compartidos por toda la aplicación.
"""
from django.db import models
from api.core.managers import TenantManager


class TimeStampedModel(models.Model):
    """
    Modelo abstracto con timestamps automáticos.
    
    Proporciona campos created_at y updated_at que se actualizan automáticamente.
    """
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class TenantModel(TimeStampedModel):
    """
    Modelo abstracto para multi-tenancy.
    
    Proporciona:
    - Campo institution (ForeignKey a FinancialInstitution)
    - Manager objects que filtra automáticamente por tenant
    - Manager all_objects sin filtrar (para superadmin)
    
    Uso:
        class MyModel(TenantModel):
            name = models.CharField(max_length=100)
            # ... otros campos ...
    
    Los queries usando objects se filtrarán automáticamente por tenant:
        MyModel.objects.all()  # Solo del tenant actual
        MyModel.all_objects.all()  # Todos los tenants
    """
    
    institution = models.ForeignKey(
        'tenants.FinancialInstitution',
        on_delete=models.CASCADE,
        related_name='%(class)s_set',
        help_text='Institución financiera a la que pertenece este registro'
    )
    
    # Manager con filtrado automático por tenant
    objects = TenantManager()
    
    # Manager sin filtrar (para superadmin y casos especiales)
    all_objects = models.Manager()
    
    class Meta:
        abstract = True
