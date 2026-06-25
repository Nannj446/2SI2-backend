"""
Configuración de la aplicación tenants.
"""
from django.apps import AppConfig


class TenantsConfig(AppConfig):
    """Configuración de la app tenants."""
    
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'api.tenants'
    verbose_name = 'Tenants'
    
    def ready(self):
        """Importa las señales cuando la app está lista."""
        import api.tenants.signals  # noqa