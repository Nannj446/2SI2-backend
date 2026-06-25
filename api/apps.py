from django.apps import AppConfig


class ApiConfig(AppConfig):
    name = 'api'
    default_auto_field = 'django.db.models.BigAutoField'
    
    def ready(self):
        """
        Importa los signals cuando la aplicación está lista.
        
        Nota: Los signals específicos de cada app se importan en sus propios apps.py
        """
        pass  # Los signals se importan en cada app individual
