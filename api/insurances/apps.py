"""
Django app configuration for insurances.
"""
from django.apps import AppConfig


class InsurancesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'api.insurances'
    verbose_name = 'Gestión de Seguros'

    def ready(self):
        import api.insurances.signals  # noqa: F401
