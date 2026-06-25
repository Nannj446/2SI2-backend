"""
Configuración del app identity_verification
"""
from django.apps import AppConfig


class IdentityVerificationConfig(AppConfig):
	name = 'api.identity_verification'
	verbose_name = 'Verificación de Identidad'
	default_auto_field = 'django.db.models.BigAutoField'

	def ready(self):
		"""
		Llamado cuando Django inicia el app.
		Useful for app initialization, signal registration, etc.
		"""
		pass
