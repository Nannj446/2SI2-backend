"""
Modelos relacionados con perfiles de usuario.
"""
from django.conf import settings
from django.db import models
from api.core.models import TimeStampedModel


class UserProfile(TimeStampedModel):
	"""
	Perfil extendido de usuario con tipo de usuario y datos adicionales.
	
	Tipos de usuario:
	- saas_admin: Superadministrador SaaS (gestiona toda la plataforma)
	- tenant_user: Usuario de tenant (pertenece a una institución financiera)
	"""
	user = models.OneToOneField(
		settings.AUTH_USER_MODEL,
		on_delete=models.CASCADE,
		related_name='profile',
		verbose_name='Usuario'
	)
	user_type = models.CharField(
		max_length=20,
		choices=[
			('saas_admin', 'Superadministrador SaaS'),
			('tenant_user', 'Usuario de Tenant'),
			('client', 'Cliente/Prestatario'),
		],
		default='tenant_user',
		verbose_name='Tipo de Usuario',
		help_text='Tipo de usuario en el sistema'
	)
	
	# Datos de contacto
	phone = models.CharField(max_length=20, blank=True, verbose_name='Teléfono')
	
	# Datos laborales
	position = models.CharField(
		max_length=100,
		blank=True,
		verbose_name='Cargo',
		help_text='Cargo o posición'
	)
	department = models.CharField(
		max_length=100,
		blank=True,
		verbose_name='Departamento',
		help_text='Departamento'
	)
	
	# Preferencias
	avatar = models.ImageField(
		upload_to='avatars/',
		blank=True,
		null=True,
		verbose_name='Avatar'
	)
	timezone = models.CharField(
		max_length=50,
		default='America/La_Paz',
		verbose_name='Zona Horaria'
	)
	language = models.CharField(
		max_length=10,
		default='es',
		verbose_name='Idioma'
	)
	notification_preferences = models.JSONField(
		default=dict,
		blank=True,
		verbose_name='Preferencias de Notificación'
	)
	
	class Meta:
		db_table = 'user_profiles'
		ordering = ['-created_at']
		verbose_name = 'Perfil de Usuario'
		verbose_name_plural = 'Perfiles de Usuarios'
	
	def __str__(self) -> str:
		return f'Profile: {self.user.email} ({self.user_type})'
	
	def is_saas_admin(self) -> bool:
		"""
		Verifica si el usuario es superadministrador SaaS.
		
		Returns:
			bool: True si es superadmin SaaS
		"""
		return self.user_type == 'saas_admin'
	
	def is_client(self) -> bool:
		"""
		Verifica si el usuario es un cliente/prestatario.
		
		Returns:
			bool: True si es cliente
		"""
		return self.user_type == 'client'
	
	def get_permissions_in_institution(self, institution):
		"""
		Obtiene todos los permisos del usuario en una institución específica.
		
		Args:
			institution: Instancia de FinancialInstitution
		
		Returns:
			QuerySet de Permission
		"""
		from api.roles.models import Permission
		
		if self.is_saas_admin():
			# Superadmin tiene todos los permisos
			return Permission.objects.filter(is_active=True)
		
		# Obtener roles activos del usuario en la institución
		user_roles = self.user.user_roles.filter(
			institution=institution,
			is_active=True
		)
		
		# Obtener permisos únicos de todos los roles
		return Permission.objects.filter(
			roles__user_assignments__in=user_roles,
			is_active=True
		).distinct()
	
	def has_permission(self, permission_code: str, institution) -> bool:
		"""
		Verifica si el usuario tiene un permiso específico en una institución.
		
		Args:
			permission_code: Código del permiso (ej: 'users.view')
			institution: Instancia de FinancialInstitution
		
		Returns:
			bool: True si tiene el permiso
		"""
		if self.is_saas_admin():
			return True
		
		return self.get_permissions_in_institution(institution).filter(
			code=permission_code
		).exists()
