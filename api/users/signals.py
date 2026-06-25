"""
Signals para el módulo API.

Maneja la creación automática de perfiles de usuario y otras acciones
que deben ejecutarse en respuesta a eventos del modelo.
"""
from django.contrib.auth import get_user_model
from django.db.models.signals import post_save
from django.dispatch import receiver

from api.users.models import UserProfile

User = get_user_model()


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
	"""
	Crea automáticamente un UserProfile cuando se crea un nuevo User.
	
	Args:
		sender: Modelo User
		instance: Instancia del usuario creado
		created: True si es una nueva instancia
		**kwargs: Argumentos adicionales
	"""
	if created:
		UserProfile.objects.create(user=instance)


@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
	"""
	Guarda el UserProfile cuando se guarda el User.
	
	Args:
		sender: Modelo User
		instance: Instancia del usuario
		**kwargs: Argumentos adicionales
	"""
	if hasattr(instance, 'profile'):
		instance.profile.save()
