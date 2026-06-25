"""
Configuración de la aplicación de reportes.
"""
from django.apps import AppConfig


class ReportsConfig(AppConfig):
    """Configuración del módulo de reportes."""
    
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'api.reports'
    verbose_name = 'Reportes'
    
    def ready(self):
        """
        Ejecuta código cuando la aplicación está lista.
        Importa signals si existen.
        """
        try:
            import api.reports.signals  # noqa
        except ImportError:
            pass
