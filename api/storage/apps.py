"""
Configuración de la aplicación storage.
"""
from django.apps import AppConfig


class StorageConfig(AppConfig):
    """Configuración de la app storage."""
    
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'api.storage'
    verbose_name = 'Storage'
