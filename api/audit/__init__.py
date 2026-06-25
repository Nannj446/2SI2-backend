"""
Módulo audit - Sistema de auditoría y logs de seguridad.

IMPORTANTE: No importamos modelos ni servicios aquí para evitar problemas de carga circular.
Los modelos y servicios deben importarse directamente desde sus módulos:
    from api.audit.models import AuditLog, SecurityEvent
    from api.audit.services import AuditService
"""

default_app_config = 'api.audit.apps.AuditConfig'
