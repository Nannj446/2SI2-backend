"""
Configuración de la aplicación de Contratos
"""

from django.apps import AppConfig


class ContractsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'api.contracts'
    verbose_name = 'Contratos de Crédito'
    
    def ready(self):
        """
        Importar signals cuando la app esté lista
        """
        try:
            import api.contracts.signals  # noqa
        except ImportError:
            pass
