"""
Serializers para gestión de usuarios internos.
"""

from django.contrib.auth import get_user_model
from rest_framework import serializers

from api.models import UserProfile, UserRole
from api.users.services import (
    CreateUserInput,
    UpdateUserInput,
    UserManagementService,
)

User = get_user_model()


class UserProfileSerializer(serializers.ModelSerializer):
	"""Serializer para perfil de usuario."""
	
	class Meta:
		model = UserProfile
		fields = [
			'user_type',
			'phone',
			'position',
			'department',
			'timezone',
			'language',
		]
		read_only_fields = ['user_type']


class UserSerializer(serializers.ModelSerializer):
	"""Serializer para usuario con perfil y roles."""
	
	profile = UserProfileSerializer(read_only=True)
	institution = serializers.SerializerMethodField()
	roles = serializers.SerializerMethodField()
	
	class Meta:
		model = User
		fields = [
			'id',
			'email',
			'first_name',
			'last_name',
			'is_active',
			'date_joined',
			'profile',
			'institution',
			'roles',
		]
		read_only_fields = ['id', 'email', 'date_joined']
	
	def get_institution(self, obj):
		"""Obtiene la institución activa del usuario."""
		membership = obj.institution_memberships.filter(is_active=True).first()
		if membership:
			return {
				'id': membership.institution.id,
				'name': membership.institution.name,
				'slug': membership.institution.slug,
				'institution_type': membership.institution.institution_type,
			}
		return None
	
	def get_roles(self, obj):
		"""Obtiene los roles del usuario en su institución."""
		request = self.context.get('request')
		
		# Si hay tenant en el request, filtrar por ese tenant
		if request and request.tenant:
			user_roles = obj.user_roles.filter(
				institution=request.tenant,
				is_active=True
			).select_related('role', 'institution')
			return [
				{
					'id': ur.role.id,
					'name': ur.role.name,
					'description': ur.role.description,
					'institution': ur.institution.name,
				}
				for ur in user_roles
			]
		
		# Si no hay tenant (SaaS admin), mostrar todos los roles del usuario
		# agrupados por institución
		user_roles = obj.user_roles.filter(
			is_active=True
		).select_related('role', 'institution')
		
		return [
			{
				'id': ur.role.id,
				'name': ur.role.name,
				'description': ur.role.description,
				'institution': ur.institution.name,
			}
			for ur in user_roles
		]


class CreateUserSerializer(serializers.Serializer):
	"""Serializer para crear un nuevo usuario."""
	
	email = serializers.EmailField(
		required=True,
		error_messages={
			'required': 'El email es obligatorio.',
			'invalid': 'Ingresa un email válido.',
		}
	)
	first_name = serializers.CharField(
		max_length=150,
		required=True,
		error_messages={
			'required': 'El nombre es obligatorio.',
			'blank': 'El nombre no puede estar vacío.',
		}
	)
	last_name = serializers.CharField(
		max_length=150,
		required=True,
		error_messages={
			'required': 'El apellido es obligatorio.',
			'blank': 'El apellido no puede estar vacío.',
		}
	)
	password = serializers.CharField(
		write_only=True,
		required=True,
		min_length=8,
		error_messages={
			'required': 'La contraseña es obligatoria.',
			'min_length': 'La contraseña debe tener al menos 8 caracteres.',
		}
	)
	role_ids = serializers.ListField(
		child=serializers.IntegerField(),
		required=True,
		min_length=1,
		error_messages={
			'required': 'Debe asignar al menos un rol.',
			'min_length': 'Debe asignar al menos un rol.',
		}
	)
	phone = serializers.CharField(
		max_length=20,
		required=False,
		allow_blank=True,
		default=''
	)
	position = serializers.CharField(
		max_length=100,
		required=False,
		allow_blank=True,
		default=''
	)
	department = serializers.CharField(
		max_length=100,
		required=False,
		allow_blank=True,
		default=''
	)
	
	def validate_email(self, value):
		"""Valida que el email no esté en uso."""
		normalized = value.strip().lower()
		if User.objects.filter(email__iexact=normalized).exists():
			raise serializers.ValidationError('Este email ya está registrado.')
		return normalized
	
	def create(self, validated_data):
		"""Crea el usuario usando el servicio."""
		request = self.context.get('request')
		
		# Crear input para el servicio
		input_data = CreateUserInput(
			email=validated_data['email'],
			first_name=validated_data['first_name'],
			last_name=validated_data['last_name'],
			password=validated_data['password'],
			institution_id=request.tenant.id,
			role_ids=validated_data['role_ids'],
			phone=validated_data.get('phone', ''),
			position=validated_data.get('position', ''),
			department=validated_data.get('department', ''),
		)
		
		# Ejecutar servicio
		service = UserManagementService()
		return service.create_user(input_data, request.user)


class UpdateUserSerializer(serializers.Serializer):
	"""Serializer para actualizar un usuario."""
	
	first_name = serializers.CharField(
		max_length=150,
		required=False,
		allow_blank=False
	)
	last_name = serializers.CharField(
		max_length=150,
		required=False,
		allow_blank=False
	)
	phone = serializers.CharField(
		max_length=20,
		required=False,
		allow_blank=True
	)
	position = serializers.CharField(
		max_length=100,
		required=False,
		allow_blank=True
	)
	department = serializers.CharField(
		max_length=100,
		required=False,
		allow_blank=True
	)
	is_active = serializers.BooleanField(required=False)
	
	def update(self, instance, validated_data):
		"""Actualiza el usuario usando el servicio."""
		request = self.context.get('request')
		
		# Crear input para el servicio
		input_data = UpdateUserInput(
			first_name=validated_data.get('first_name'),
			last_name=validated_data.get('last_name'),
			phone=validated_data.get('phone'),
			position=validated_data.get('position'),
			department=validated_data.get('department'),
			is_active=validated_data.get('is_active'),
		)
		
		# Ejecutar servicio
		service = UserManagementService()
		return service.update_user(instance.id, input_data, request.user)


class AssignRolesSerializer(serializers.Serializer):
	"""Serializer para asignar roles a un usuario."""
	
	role_ids = serializers.ListField(
		child=serializers.IntegerField(),
		required=True,
		min_length=1,
		error_messages={
			'required': 'Debe asignar al menos un rol.',
			'min_length': 'Debe asignar al menos un rol.',
		}
	)
	
	def save(self, user):
		"""Asigna los roles al usuario usando el servicio."""
		request = self.context.get('request')
		
		# Ejecutar servicio
		service = UserManagementService()
		return service.assign_roles(
			user_id=user.id,
			role_ids=self.validated_data['role_ids'],
			institution=request.tenant,
			assigned_by=request.user
		)
