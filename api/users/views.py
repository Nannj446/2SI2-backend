"""
Vistas para gestión de usuarios internos del sistema.
"""

from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema, OpenApiParameter
from drf_spectacular.types import OpenApiTypes

from api.core.permissions import require_permission

from .serializers import (
    AssignRolesSerializer,
    CreateUserSerializer,
    UpdateUserSerializer,
    UserSerializer,
)

User = get_user_model()


class UserListCreateAPIView(APIView):
	"""Vista para listar y crear usuarios."""
	
	permission_classes = [IsAuthenticated, require_permission('users.view')]
	
	@extend_schema(
		tags=['Usuarios'],
		summary='Listar usuarios',
		description='Lista usuarios de la institución. SaaS Admin puede ver todos los usuarios.',
		responses={
			200: UserSerializer(many=True),
			401: OpenApiTypes.OBJECT,
			403: OpenApiTypes.OBJECT,
		}
	)
	def get(self, request):
		"""
		Lista usuarios filtrados por tenant.
		
		Superadmin SaaS puede ver todos los usuarios.
		Usuarios de tenant solo ven usuarios de su institución.
		
		Response (200 OK):
			[
				{
					"id": 1,
					"email": "usuario@ejemplo.com",
					"first_name": "Juan",
					"last_name": "Pérez",
					"is_active": true,
					"date_joined": "2026-03-30T10:00:00Z",
					"profile": {...},
					"institution": {...},
					"roles": [...]
				}
			]
		"""
		# Filtrar por tenant si no es superadmin
		if hasattr(request.user, 'profile') and request.user.profile.is_saas_admin():
			# Superadmin puede ver todos los usuarios
			users = User.objects.all().select_related('profile').prefetch_related(
				'institution_memberships__institution',
				'user_roles__role'
			)
		else:
			if not request.tenant:
				# Usuario sin tenant no puede ver usuarios
				return Response([], status=status.HTTP_200_OK)
			
			# Filtrar usuarios por tenant
			users = User.objects.filter(
				institution_memberships__institution=request.tenant,
				institution_memberships__is_active=True
			).distinct().select_related('profile').prefetch_related(
				'institution_memberships__institution',
				'user_roles__role'
			)
		
		serializer = UserSerializer(users, many=True, context={'request': request})
		return Response(serializer.data)
	
	@extend_schema(
		tags=['Usuarios'],
		summary='Crear usuario',
		description='Crea un nuevo usuario en la institución.',
		request=CreateUserSerializer,
		responses={
			201: UserSerializer,
			400: OpenApiTypes.OBJECT,
			401: OpenApiTypes.OBJECT,
			403: OpenApiTypes.OBJECT,
		}
	)
	def post(self, request):
		"""
		Crea un nuevo usuario.
		
		Requiere permiso 'users.create'.
		El usuario se crea en la institución del creador (tenant).
		
		Request body:
			{
				"email": "nuevo@ejemplo.com",
				"first_name": "Nuevo",
				"last_name": "Usuario",
				"password": "contraseña123",
				"role_ids": [1, 2],
				"phone": "+591 12345678",
				"position": "Analista",
				"department": "Créditos"
			}
		
		Response (201 Created):
			{
				"id": 2,
				"email": "nuevo@ejemplo.com",
				...
			}
		"""
		# Verificar permiso de creación
		if not (hasattr(request.user, 'profile') and 
				(request.user.profile.is_saas_admin() or 
				 request.user.profile.has_permission('users.create', request.tenant))):
			return Response(
				{'error': 'No tiene permiso para crear usuarios'},
				status=status.HTTP_403_FORBIDDEN
			)
		
		# Validar que el usuario tenga tenant (excepto superadmin)
		if not (hasattr(request.user, 'profile') and request.user.profile.is_saas_admin()):
			if not request.tenant:
				return Response(
					{'error': 'Tenant requerido para crear usuarios'},
					status=status.HTTP_400_BAD_REQUEST
				)
		
		serializer = CreateUserSerializer(data=request.data, context={'request': request})
		serializer.is_valid(raise_exception=True)
		user = serializer.save()
		
		response_serializer = UserSerializer(user, context={'request': request})
		return Response(response_serializer.data, status=status.HTTP_201_CREATED)


class UserDetailAPIView(APIView):
	"""Vista para obtener, actualizar y desactivar un usuario."""
	
	permission_classes = [IsAuthenticated, require_permission('users.view')]
	
	def get(self, request, user_id: int):
		"""
		Obtiene detalles de un usuario.
		
		Verifica que el usuario pertenezca al tenant del solicitante.
		
		Response (200 OK):
			{
				"id": 1,
				"email": "usuario@ejemplo.com",
				...
			}
		"""
		user = get_object_or_404(
			User.objects.select_related('profile').prefetch_related(
				'institution_memberships__institution',
				'user_roles__role'
			),
			pk=user_id
		)
		
		# Verificar acceso al usuario
		if not (hasattr(request.user, 'profile') and request.user.profile.is_saas_admin()):
			if not request.tenant:
				return Response(
					{'error': 'Usuario no encontrado'},
					status=status.HTTP_404_NOT_FOUND
				)
			
			# Verificar que el usuario pertenezca al tenant
			if not user.institution_memberships.filter(
				institution=request.tenant,
				is_active=True
			).exists():
				return Response(
					{'error': 'Usuario no encontrado'},
					status=status.HTTP_404_NOT_FOUND
				)
		
		serializer = UserSerializer(user, context={'request': request})
		return Response(serializer.data)
	
	def patch(self, request, user_id: int):
		"""
		Actualiza un usuario.
		
		Requiere permiso 'users.edit'.
		
		Request body:
			{
				"first_name": "Nombre Actualizado",
				"phone": "+591 87654321"
			}
		
		Response (200 OK):
			{
				"id": 1,
				"email": "usuario@ejemplo.com",
				...
			}
		"""
		# Verificar permiso de edición
		if not (hasattr(request.user, 'profile') and 
				(request.user.profile.is_saas_admin() or 
				 request.user.profile.has_permission('users.edit', request.tenant))):
			return Response(
				{'error': 'No tiene permiso para editar usuarios'},
				status=status.HTTP_403_FORBIDDEN
			)
		
		user = get_object_or_404(User, pk=user_id)
		
		# Verificar acceso al usuario
		if not (hasattr(request.user, 'profile') and request.user.profile.is_saas_admin()):
			if not request.tenant:
				return Response(
					{'error': 'Usuario no encontrado'},
					status=status.HTTP_404_NOT_FOUND
				)
			
			# Verificar que el usuario pertenezca al tenant
			if not user.institution_memberships.filter(
				institution=request.tenant,
				is_active=True
			).exists():
				return Response(
					{'error': 'Usuario no encontrado'},
					status=status.HTTP_404_NOT_FOUND
				)
		
		serializer = UpdateUserSerializer(
			user,
			data=request.data,
			partial=True,
			context={'request': request}
		)
		serializer.is_valid(raise_exception=True)
		user = serializer.save()
		
		response_serializer = UserSerializer(user, context={'request': request})
		return Response(response_serializer.data)
	
	def delete(self, request, user_id: int):
		"""
		Desactiva un usuario.
		
		Requiere permiso 'users.deactivate'.
		
		Response (204 No Content)
		"""
		# Verificar permiso de desactivación
		if not (hasattr(request.user, 'profile') and 
				(request.user.profile.is_saas_admin() or 
				 request.user.profile.has_permission('users.deactivate', request.tenant))):
			return Response(
				{'error': 'No tiene permiso para desactivar usuarios'},
				status=status.HTTP_403_FORBIDDEN
			)
		
		user = get_object_or_404(User, pk=user_id)
		
		# Verificar acceso al usuario
		if not (hasattr(request.user, 'profile') and request.user.profile.is_saas_admin()):
			if not request.tenant:
				return Response(
					{'error': 'Usuario no encontrado'},
					status=status.HTTP_404_NOT_FOUND
				)
			
			# Verificar que el usuario pertenezca al tenant
			if not user.institution_memberships.filter(
				institution=request.tenant,
				is_active=True
			).exists():
				return Response(
					{'error': 'Usuario no encontrado'},
					status=status.HTTP_404_NOT_FOUND
				)
		
		# Desactivar usuario usando el servicio
		from api.users.services import UserManagementService
		service = UserManagementService()
		service.deactivate_user(user.id, request.user)
		
		return Response(status=status.HTTP_204_NO_CONTENT)


class UserRolesAPIView(APIView):
	"""Vista para asignar roles a un usuario."""
	
	permission_classes = [IsAuthenticated, require_permission('users.assign_roles')]
	
	def put(self, request, user_id: int):
		"""
		Asigna roles a un usuario.
		
		Requiere permiso 'users.assign_roles'.
		Reemplaza los roles actuales del usuario en la institución.
		
		Request body:
			{
				"role_ids": [1, 2, 3]
			}
		
		Response (200 OK):
			{
				"id": 1,
				"email": "usuario@ejemplo.com",
				"roles": [...]
			}
		"""
		user = get_object_or_404(User, pk=user_id)
		
		# Verificar acceso al usuario
		if not (hasattr(request.user, 'profile') and request.user.profile.is_saas_admin()):
			if not request.tenant:
				return Response(
					{'error': 'Usuario no encontrado'},
					status=status.HTTP_404_NOT_FOUND
				)
			
			# Verificar que el usuario pertenezca al tenant
			if not user.institution_memberships.filter(
				institution=request.tenant,
				is_active=True
			).exists():
				return Response(
					{'error': 'Usuario no encontrado'},
					status=status.HTTP_404_NOT_FOUND
				)
		
		serializer = AssignRolesSerializer(data=request.data, context={'request': request})
		serializer.is_valid(raise_exception=True)
		user = serializer.save(user)
		
		response_serializer = UserSerializer(user, context={'request': request})
		return Response(response_serializer.data)
