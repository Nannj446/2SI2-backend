"""
Señales para el manejo automático de suscripciones.
"""
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
import logging

from .models import FinancialInstitution
from api.saas.services import AssignFreePlanService, AssignFreePlanInput

logger = logging.getLogger(__name__)


@receiver(post_save, sender=FinancialInstitution)
def assign_free_plan_to_new_institution(sender, instance, created, **kwargs):
    """
    Asigna automáticamente el plan gratuito a nuevas instituciones.
    
    Se ejecuta cada vez que se crea una nueva institución financiera.
    """
    if created:  # Solo para instituciones recién creadas
        try:
            service = AssignFreePlanService()
            result = service.execute(AssignFreePlanInput(institution=instance))
            
            if result.is_new:
                logger.info(
                    f"Plan gratuito asignado automáticamente a la institución '{instance.name}' "
                    f"(ID: {instance.id}). Suscripción ID: {result.subscription.id}"
                )
            else:
                logger.info(
                    f"La institución '{instance.name}' (ID: {instance.id}) ya tenía una suscripción. "
                    f"Suscripción ID: {result.subscription.id}"
                )
                
        except Exception as e:
            logger.error(
                f"Error al asignar plan gratuito a la institución '{instance.name}' "
                f"(ID: {instance.id}): {str(e)}"
            )
            # No re-lanzamos la excepción para no interrumpir la creación de la institución