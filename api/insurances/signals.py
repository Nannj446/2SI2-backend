"""
Django signals para Insurances.
"""
from django.db.models.signals import post_save, pre_delete
from django.dispatch import receiver

from .models import CreditInsurance, CreditInsuranceStatus


@receiver(post_save, sender=CreditInsurance)
def credit_insurance_post_save(sender, instance, created, **kwargs):
    """
    Actualizar estado del crédito cuando cambia el seguro.
    """
    pass  # Logic temporarily disabled - method check_insurance_compliance doesn't exist yet


@receiver(pre_delete, sender=CreditInsurance)
def credit_insurance_pre_delete(sender, instance, **kwargs):
    """
    Validar antes de eliminar un seguro de crédito.
    """
    if instance.status == CreditInsuranceStatus.ACTIVE:
        raise ValueError(
            "No se puede eliminar un seguro activo. "
            "Primero debe cancelarlo o marcarlo como suspendido."
        )
