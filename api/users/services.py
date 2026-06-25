"""
Servicio para gestión de usuarios internos del sistema.

Este servicio maneja la creación, actualización, desactivación y asignación de roles
a usuarios del sistema (empleados de instituciones financieras).
"""

from dataclasses import dataclass
from typing import Optional

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from rest_framework import serializers

from api.models import (
    FinancialInstitution,
    FinancialInstitutionMembership,
    Role,
    UserProfile,
    UserRole,
)
from api.saas.services import (
    CheckSubscriptionLimitsService,
    CheckSubscriptionLimitsInput,
    UpdateUsageCountersService,
    UpdateUsageCountersInput
)

User = get_user_model()


@dataclass(frozen=True)
class CreateUserInput:
	"""Input para crear un nuevo usuario."""
	email: str
	first_name: str
	last_name: str
	password: str
	institution_id: int
	role_ids: list[int]
	phone: str = ''
	position: str = ''
	department: str = ''


@dataclass(frozen=True)
class UpdateUserInput:
	"""Input para actualizar un usuario existente."""
	first_name: Optional[str] = None
	last_name: Optional[str] = None
	phone: Optional[str] = None
	position: Optional[str] = None
	department: Optional[str] = None
	is_active: Optional[bool] = None


class UserManagementService:
	"""Servicio para gestión de usuarios internos."""
	
	def create_user(self, payload: CreateUserInput, created_by: User) -> User:
		"""
		Crea un nuevo usuario en el sistema.
		
		Args:
			payload: Datos del usuario a crear
			created_by: Usuario que está creando el nuevo usuario
		
		Returns:
			User: Usuario creado
		
		Raises:
			PermissionDenied: Si el usuario no tiene permiso para crear usuarios
			serializers.ValidationError: Si los datos son inválidos
		"""
		# Obtener institución
		try:
			institution = FinancialInstitution.objects.get(id=payload.institution_id)
		except FinancialInstitution.DoesNotExist:
			raise serializers.ValidationError(
				{'institution_id': 'Institución no encontrada.'},
				code='institution_not_found'
			)
		
		# Verificar permisos del creador
		if not (hasattr(created_by, 'profile') and created_by.profile.is_saas_admin()):
			# No es superadmin, verificar permiso en la institución
			if not created_by.profile.has_permission('users.create', institution):
				raise PermissionDenied('No tiene permiso para crear usuarios en esta institución.')
		
		# Verificar límites de suscripción antes de crear el usuario
		limits_service = CheckSubscriptionLimitsService()
		limits_result = limits_service.execute(CheckSubscriptionLimitsInput(
			institution=institution,
			action='add_user'
		))
		
		if not limits_result.allowed:
			raise serializers.ValidationError(
				{'subscription': limits_result.message},
				code='subscription_limit_exceeded'
			)
		
		# Verificar que el email no esté en uso
		if User.objects.filter(email__iexact=payload.email).exists():
			raise serializers.ValidationError(
				{'email': 'Este email ya está registrado.'},
				code='email_exists'
			)
		
		# Verificar que los roles existan y pertenezcan a la institución
		roles = Role.objects.filter(
			id__in=payload.role_ids,
			institution=institution,
			is_active=True
		)
		
		if roles.count() != len(payload.role_ids):
			raise serializers.ValidationError(
				{'role_ids': 'Uno o más roles no son válidos para esta institución.'},
				code='invalid_roles'
			)
		
		# Crear usuario
		user = User.objects.create_user(
			username=payload.email,
			email=payload.email,
			first_name=payload.first_name,
			last_name=payload.last_name,
			password=payload.password
		)
		
		# Actualizar perfil (el signal ya lo creó)
		profile = UserProfile.objects.get(user=user)
		profile.user_type = 'tenant_user'
		profile.phone = payload.phone
		profile.position = payload.position
		profile.department = payload.department
		profile.save()
		
		# Crear membership
		FinancialInstitutionMembership.objects.create(
			user=user,
			institution=institution,
			is_active=True
		)
		
		# Asignar roles
		for role in roles:
			UserRole.objects.create(
				user=user,
				role=role,
				institution=institution,
				assigned_by=created_by,
				is_active=True
			)
		
		# Actualizar contadores de suscripción
		usage_service = UpdateUsageCountersService()
		usage_service.execute(UpdateUsageCountersInput(
			institution=institution,
			users_delta=1  # Incrementar contador de usuarios
		))
		
		return user
	
	def update_user(self, user_id: int, payload: UpdateUserInput, updated_by: User) -> User:
		"""
		Actualiza un usuario existente.
		
		Args:
			user_id: ID del usuario a actualizar
			payload: Datos a actualizar
			updated_by: Usuario que está realizando la actualización
		
		Returns:
			User: Usuario actualizado
		
		Raises:
			PermissionDenied: Si el usuario no tiene permiso para editar usuarios
			serializers.ValidationError: Si el usuario no existe
		"""
		# Obtener usuario
		try:
			user = User.objects.get(id=user_id)
		except User.DoesNotExist:
			raise serializers.ValidationError(
				{'detail': 'Usuario no encontrado.'},
				code='user_not_found'
			)
		
		# Obtener institución del usuario
		membership = user.institution_memberships.filter(is_active=True).first()
		if not membership:
			raise serializers.ValidationError(
				{'detail': 'Usuario no tiene institución activa.'},
				code='no_active_institution'
			)
		
		# Verificar permisos del actualizador
		if not (hasattr(updated_by, 'profile') and updated_by.profile.is_saas_admin()):
			# No es superadmin, verificar permiso en la institución
			if not updated_by.profile.has_permission('users.edit', membership.institution):
				raise PermissionDenied('No tiene permiso para editar usuarios en esta institución.')
		
		# Actualizar datos del usuario
		if payload.first_name is not None:
			user.first_name = payload.first_name
		
		if payload.last_name is not None:
			user.last_name = payload.last_name
		
		if payload.is_active is not None:
			user.is_active = payload.is_active
		
		user.save()
		
		# Actualizar perfil
		profile = user.profile
		
		if payload.phone is not None:
			profile.phone = payload.phone
		
		if payload.position is not None:
			profile.position = payload.position
		
		if payload.department is not None:
			profile.department = payload.department
		
		profile.save()
		
		return user
	
	def deactivate_user(self, user_id: int, deactivated_by: User) -> User:
		"""
		Desactiva un usuario.
		
		Args:
			user_id: ID del usuario a desactivar
			deactivated_by: Usuario que está desactivando
		
		Returns:
			User: Usuario desactivado
		
		Raises:
			PermissionDenied: Si el usuario no tiene permiso para desactivar usuarios
			serializers.ValidationError: Si el usuario no existe
		"""
		# Obtener usuario
		try:
			user = User.objects.get(id=user_id)
		except User.DoesNotExist:
			raise serializers.ValidationError(
				{'detail': 'Usuario no encontrado.'},
				code='user_not_found'
			)
		
		# Obtener institución del usuario
		membership = user.institution_memberships.filter(is_active=True).first()
		if not membership:
			raise serializers.ValidationError(
				{'detail': 'Usuario no tiene institución activa.'},
				code='no_active_institution'
			)
		
		# Verificar permisos del desactivador
		if not (hasattr(deactivated_by, 'profile') and deactivated_by.profile.is_saas_admin()):
			# No es superadmin, verificar permiso en la institución
			if not deactivated_by.profile.has_permission('users.deactivate', membership.institution):
				raise PermissionDenied('No tiene permiso para desactivar usuarios en esta institución.')
		
		# Desactivar usuario
		user.is_active = False
		user.save()
		
		# Actualizar contadores de suscripción (decrementar usuarios)
		usage_service = UpdateUsageCountersService()
		usage_service.execute(UpdateUsageCountersInput(
			institution=membership.institution,
			users_delta=-1  # Decrementar contador de usuarios
		))
		
		return user
	
	def assign_roles(
		self,
		user_id: int,
		role_ids: list[int],
		institution: FinancialInstitution,
		assigned_by: User
	) -> User:
		"""
		Asigna roles a un usuario en una institución.
		
		Args:
			user_id: ID del usuario
			role_ids: Lista de IDs de roles a asignar
			institution: Institución en la que se asignan los roles
			assigned_by: Usuario que está asignando los roles
		
		Returns:
			User: Usuario con roles actualizados
		
		Raises:
			PermissionDenied: Si el usuario no tiene permiso para asignar roles
			serializers.ValidationError: Si los datos son inválidos
		"""
		# Obtener usuario
		try:
			user = User.objects.get(id=user_id)
		except User.DoesNotExist:
			raise serializers.ValidationError(
				{'detail': 'Usuario no encontrado.'},
				code='user_not_found'
			)
		
		# Verificar permisos del asignador
		if not (hasattr(assigned_by, 'profile') and assigned_by.profile.is_saas_admin()):
			# No es superadmin, verificar permiso en la institución
			if not assigned_by.profile.has_permission('users.assign_roles', institution):
				raise PermissionDenied('No tiene permiso para asignar roles en esta institución.')
		
		# Verificar que los roles existan y pertenezcan a la institución
		roles = Role.objects.filter(
			id__in=role_ids,
			institution=institution,
			is_active=True
		)
		
		if roles.count() != len(role_ids):
			raise serializers.ValidationError(
				{'role_ids': 'Uno o más roles no son válidos para esta institución.'},
				code='invalid_roles'
			)
		
		# Desactivar roles actuales del usuario en esta institución
		UserRole.objects.filter(
			user=user,
			institution=institution
		).update(is_active=False)
		
		# Asignar nuevos roles
		for role in roles:
			UserRole.objects.update_or_create(
				user=user,
				role=role,
				institution=institution,
				defaults={
					'is_active': True,
					'assigned_by': assigned_by
				}
			)
		
		return user
