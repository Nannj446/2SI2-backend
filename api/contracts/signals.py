"""
Signals para el módulo de contratos

Maneja eventos automáticos relacionados con contratos.
"""

import logging
from django.db.models.signals import post_save
from django.dispatch import receiver
from api.contracts.models import Contract, ContractSignature

logger = logging.getLogger(__name__)


@receiver(post_save, sender=ContractSignature)
def update_contract_status_after_signature(sender, instance, created, **kwargs):
    """
    Actualiza el estado del contrato después de registrar una firma.
    
    Se ejecuta automáticamente cuando se crea una nueva firma.
    """
    if created:
        contract = instance.contract
        
        # Actualizar estado del contrato según las firmas
        contract.update_status_after_signature()
        
        logger.info(
            f"Estado del contrato {contract.contract_number} actualizado "
            f"después de firma de {instance.get_signer_name()}"
        )
