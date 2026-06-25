from django.apps import AppConfig


class LoansConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'api.loans'
    verbose_name = 'Solicitudes de Crédito'

    def ready(self):
        """Importar signals cuando la app esté lista"""
        import api.loans.signals  # noqa
