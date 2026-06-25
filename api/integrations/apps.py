"""
App configuration for integrations module
"""

from django.apps import AppConfig


class IntegrationsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'api.integrations'
    verbose_name = 'Integraciones Externas'
