"""
Módulo core: Modelos base y utilidades compartidas.

IMPORTANTE: No importamos modelos aquí para evitar problemas de carga circular.
Los modelos deben importarse directamente desde sus módulos:
    from api.core.models import TimeStampedModel, TenantModel
"""

# Managers (seguros de importar)
from .managers import (
    TenantManager,
    TenantQuerySet,
    TenantManagerWithQuerySet,
    set_current_tenant,
    get_current_tenant,
    clear_current_tenant,
)

# Permisos (seguros de importar)
from .permissions import (
    HasPermission,
    require_permission,
)

__all__ = [
    # Managers
    'TenantManager',
    'TenantQuerySet', 
    'TenantManagerWithQuerySet',
    'set_current_tenant',
    'get_current_tenant',
    'clear_current_tenant',
    # Permisos
    'HasPermission',
    'require_permission',
]
