"""
Módulo identity_verification - Verificación de identidad de prestatarios con Didit.

IMPORTANTE: No importamos modelos ni servicios aquí para evitar problemas de carga circular.
Los modelos y servicios deben importarse directamente desde sus módulos:
    from api.identity_verification.models import IdentityVerification
    from api.identity_verification.services.identity_verification_service import IdentityVerificationService
    from api.identity_verification.services.didit_client import DiditClient
"""

default_app_config = 'api.identity_verification.apps.IdentityVerificationConfig'
