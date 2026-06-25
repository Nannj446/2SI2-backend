"""
Modelos relacionados con roles y permisos.
"""
from django.conf import settings
from django.db import models
from api.core.models import TimeStampedModel, TenantModel


class Permission(TimeStampedModel):
	"""
	Permiso global del sistema.
	
	Los permisos son globales y se asignan a roles.
	Cada rol puede tener múltiples permisos.
	"""
	code = models.CharField(max_length=80, unique=True, verbose_name='Código')
	name = models.CharField(max_length=120, verbose_name='Nombre')
	description = models.TextField(blank=True, verbose_name='Descripción')
	is_active = models.BooleanField(default=True, verbose_name='Activo')

	class Meta:
		db_table = 'permissions'
		ordering = ['name']
		verbose_name = 'Permiso'
		verbose_name_plural = 'Permisos'

	def __str__(self) -> str:
		return f'{self.code} - {self.name}'


class Role(TenantModel):
	"""
	Rol dinámico con permisos asignables.
	
	Hereda de TenantModel para aislamiento automático por tenant.
	El campo institution se hereda de TenantModel.
	"""
	name = models.CharField(max_length=100, verbose_name='Nombre')
	description = models.TextField(blank=True, verbose_name='Descripción')
	is_active = models.BooleanField(default=True, verbose_name='Activo')
	permissions = models.ManyToManyField(
		Permission,
		blank=True,
		related_name='roles',
		verbose_name='Permisos'
	)

	class Meta:
		db_table = 'roles'
		ordering = ['name']
		constraints = [
			models.UniqueConstraint(
				fields=['institution', 'name'],
				name='uniq_role_name_per_institution',
			)
		]
		verbose_name = 'Rol'
		verbose_name_plural = 'Roles'

	def __str__(self) -> str:
		return f'{self.name} ({self.institution.slug})'


class UserRole(TimeStampedModel):
	"""
	Asignación de roles a usuarios en instituciones específicas.
	
	Un usuario puede tener múltiples roles en una institución.
	Reemplaza el campo 'role' hardcoded de FinancialInstitutionMembership.
	"""
	user = models.ForeignKey(
		settings.AUTH_USER_MODEL,
		on_delete=models.CASCADE,
		related_name='user_roles',
		verbose_name='Usuario'
	)
	role = models.ForeignKey(
		Role,
		on_delete=models.CASCADE,
		related_name='user_assignments',
		verbose_name='Rol'
	)
	institution = models.ForeignKey(
		'tenants.FinancialInstitution',
		on_delete=models.CASCADE,
		related_name='user_role_assignments',
		verbose_name='Institución'
	)
	is_active = models.BooleanField(default=True, verbose_name='Activo')
	assigned_by = models.ForeignKey(
		settings.AUTH_USER_MODEL,
		null=True,
		blank=True,
		on_delete=models.SET_NULL,
		related_name='role_assignments_made',
		verbose_name='Asignado por',
		help_text='Usuario que asignó este rol'
	)
	
	class Meta:
		db_table = 'user_roles'
		ordering = ['-created_at']
		constraints = [
			models.UniqueConstraint(
				fields=['user', 'role', 'institution'],
				name='uniq_user_role_institution'
			)
		]
		indexes = [
			models.Index(fields=['user', 'institution', 'is_active']),
			models.Index(fields=['role', 'is_active']),
		]
		verbose_name = 'Asignación de Rol'
		verbose_name_plural = 'Asignaciones de Roles'
	
	def __str__(self) -> str:
		return f'{self.user.email} -> {self.role.name} @ {self.institution.slug}'
