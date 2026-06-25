"""
Archivo de compatibilidad para imports de modelos.

Este módulo evita importar modelos concretos en tiempo de carga de Django,
porque hacerlo registraba duplicados bajo la app ``api``. Para código nuevo,
importar directamente desde los módulos específicos.
"""

from importlib import import_module
from typing import TYPE_CHECKING

from api.core.models import TimeStampedModel, TenantModel

_LAZY_IMPORTS = {
    'FinancialInstitution': 'api.tenants.models',
    'FinancialInstitutionMembership': 'api.tenants.models',
    'TenantBranding': 'api.tenants.models',
    'PasswordResetToken': 'api.authentication.models',
    'LoginAttempt': 'api.authentication.models',
    'AuthChallenge': 'api.authentication.models',
    'EmailTwoFactorCode': 'api.authentication.models',
    'TwoFactorAuth': 'api.authentication.models',
    'Permission': 'api.roles.models',
    'Role': 'api.roles.models',
    'UserRole': 'api.roles.models',
    'UserProfile': 'api.users.models',
    'Collateral': 'api.garantias.models',
    'Guarantor': 'api.garantias.models',
    'CollateralDocument': 'api.garantias.models',
    'CollateralValuation': 'api.garantias.models',
    'Client': 'api.clients.models',
    'ClientDocument': 'api.clients.models',
    'Branch': 'api.branches.models',
    'CreditProduct': 'api.products.models',
    'ProductRequirement': 'api.products.models',
    'AuditLog': 'api.audit.models',
    'SecurityEvent': 'api.audit.models',
    'SubscriptionPlan': 'api.saas.models',
    'Subscription': 'api.saas.models',
}

if TYPE_CHECKING:
    from api.authentication.models import AuthChallenge, EmailTwoFactorCode, LoginAttempt, PasswordResetToken, TwoFactorAuth
    from api.audit.models import AuditLog, SecurityEvent
    from api.branches.models import Branch
    from api.clients.models import Client, ClientDocument
    from api.garantias.models import Collateral, CollateralDocument, CollateralValuation, Guarantor
    from api.products.models import CreditProduct, ProductRequirement
    from api.roles.models import Permission, Role, UserRole
    from api.saas.models import Subscription, SubscriptionPlan
    from api.tenants.models import FinancialInstitution, FinancialInstitutionMembership, TenantBranding
    from api.users.models import UserProfile


def __getattr__(name: str):
    if name in _LAZY_IMPORTS:
        module = import_module(_LAZY_IMPORTS[name])
        value = getattr(module, name)
        globals()[name] = value
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__():
    return sorted(set(globals()) | set(_LAZY_IMPORTS))


# ============================================================
# MODELOS DE CONTRATOS
# ============================================================
from api.contracts.models import (
    Contract,
    ContractTemplate,
    ContractSignature,
    ContractAmortizationSchedule,
    ContractDocument,
)

# ============================================================
# MODELOS DE SUSCRIPCIONES SAAS
# ============================================================
from api.saas.models import (
    SubscriptionPlan,
    Subscription,
)

# ============================================================
# EXPORTAR TODOS LOS MODELOS
# ============================================================
__all__ = [
    'TimeStampedModel',
    'TenantModel',
    *sorted(_LAZY_IMPORTS),
    # Contracts
    'Contract',
    'ContractTemplate',
    'ContractSignature',
    'ContractAmortizationSchedule',
    'ContractDocument',
]
