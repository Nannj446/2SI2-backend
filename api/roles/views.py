from django.shortcuts import get_object_or_404
from django.db.models import Q
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from api.models import Permission, Role
from api.core.permissions import require_permission

from .serializers import (
    PermissionSerializer,
    RolePermissionAssignmentSerializer,
    RoleSerializer,
)


# Parte erick sprint 0
class RoleListCreateAPIView(APIView):
    permission_classes = [IsAuthenticated, require_permission('roles.view')]
    
    def get(self, request):
        """
        Lista roles filtrados por tenant.
        
        Superadmin SaaS puede ver todos los roles.
        Usuarios de tenant solo ven roles de su institución.
        """
        include_inactive = str(request.query_params.get('include_inactive', 'false')).lower() == 'true'
        queryset = Role.objects.select_related('institution').prefetch_related('permissions').order_by('name')

        # Filtrar por tenant si no es superadmin
        if not (hasattr(request.user, 'profile') and request.user.profile.is_saas_admin()):
            if request.tenant:
                queryset = queryset.filter(institution=request.tenant)
            else:
                # Usuario sin tenant no puede ver roles
                return Response([], status=status.HTTP_200_OK)

        if not include_inactive:
            queryset = queryset.filter(is_active=True)

        serializer = RoleSerializer(queryset, many=True)
        return Response(serializer.data)

    def post(self, request):
        """
        Crea un nuevo rol.
        
        Requiere permiso 'roles.create'.
        El rol se crea en la institución del usuario (tenant).
        """
        # Verificar permiso de creación
        if not (hasattr(request.user, 'profile') and 
                (request.user.profile.is_saas_admin() or 
                 request.user.profile.has_permission('roles.create', request.tenant))):
            return Response(
                {'error': 'No tiene permiso para crear roles'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Validar que el usuario tenga tenant (excepto superadmin)
        if not request.user.profile.is_saas_admin() and not request.tenant:
            return Response(
                {'error': 'Tenant requerido para crear roles'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Asegurar que el rol se cree en el tenant del usuario
        data = request.data.copy()
        if not request.user.profile.is_saas_admin():
            data['institution'] = request.tenant.id
        
        serializer = RoleSerializer(data=data)
        serializer.is_valid(raise_exception=True)
        role = serializer.save()
        response_serializer = RoleSerializer(role)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)


class RoleDetailAPIView(APIView):
    permission_classes = [IsAuthenticated, require_permission('roles.view')]
    
    def get(self, request, role_id: int):
        """
        Obtiene detalles de un rol.
        
        Verifica que el rol pertenezca al tenant del usuario.
        """
        role = get_object_or_404(Role.objects.prefetch_related('permissions'), pk=role_id)
        
        # Verificar acceso al rol
        if not (hasattr(request.user, 'profile') and request.user.profile.is_saas_admin()):
            if not request.tenant or role.institution != request.tenant:
                return Response(
                    {'error': 'Rol no encontrado'},
                    status=status.HTTP_404_NOT_FOUND
                )
        
        serializer = RoleSerializer(role)
        return Response(serializer.data)

    def patch(self, request, role_id: int):
        """
        Actualiza un rol.
        
        Requiere permiso 'roles.edit'.
        """
        # Verificar permiso de edición
        if not (hasattr(request.user, 'profile') and 
                (request.user.profile.is_saas_admin() or 
                 request.user.profile.has_permission('roles.edit', request.tenant))):
            return Response(
                {'error': 'No tiene permiso para editar roles'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        role = get_object_or_404(Role.objects.prefetch_related('permissions'), pk=role_id)
        
        # Verificar acceso al rol
        if not request.user.profile.is_saas_admin():
            if not request.tenant or role.institution != request.tenant:
                return Response(
                    {'error': 'Rol no encontrado'},
                    status=status.HTTP_404_NOT_FOUND
                )
        
        serializer = RoleSerializer(role, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        role = serializer.save()
        response_serializer = RoleSerializer(role)
        return Response(response_serializer.data)

    def delete(self, request, role_id: int):
        """
        Desactiva un rol.
        
        Requiere permiso 'roles.delete'.
        """
        # Verificar permiso de eliminación
        if not (hasattr(request.user, 'profile') and 
                (request.user.profile.is_saas_admin() or 
                 request.user.profile.has_permission('roles.delete', request.tenant))):
            return Response(
                {'error': 'No tiene permiso para eliminar roles'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        role = get_object_or_404(Role, pk=role_id)
        
        # Verificar acceso al rol
        if not request.user.profile.is_saas_admin():
            if not request.tenant or role.institution != request.tenant:
                return Response(
                    {'error': 'Rol no encontrado'},
                    status=status.HTTP_404_NOT_FOUND
                )
        
        role.is_active = False
        role.save(update_fields=['is_active', 'updated_at'])
        return Response({'message': 'Rol desactivado correctamente.'}, status=status.HTTP_200_OK)


class PermissionListAPIView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """
        Lista todos los permisos disponibles.
        
        Todos los usuarios autenticados pueden ver la lista de permisos.
        """
        queryset = Permission.objects.filter(is_active=True).order_by('name')
        serializer = PermissionSerializer(queryset, many=True)
        return Response(serializer.data)


class RolePermissionAssignmentAPIView(APIView):
    permission_classes = [IsAuthenticated, require_permission('roles.assign_permissions')]
    
    def put(self, request, role_id: int):
        """
        Asigna permisos a un rol.
        
        Requiere permiso 'roles.assign_permissions'.
        """
        role = get_object_or_404(Role.objects.prefetch_related('permissions'), pk=role_id)
        
        # Verificar acceso al rol
        if not (hasattr(request.user, 'profile') and request.user.profile.is_saas_admin()):
            if not request.tenant or role.institution != request.tenant:
                return Response(
                    {'error': 'Rol no encontrado'},
                    status=status.HTTP_404_NOT_FOUND
                )
        
        serializer = RolePermissionAssignmentSerializer(data=request.data, context={'role': role})
        serializer.is_valid(raise_exception=True)
        role = serializer.save()
        response_serializer = RoleSerializer(role)
        return Response(response_serializer.data)


class RolePermissionDetailAPIView(APIView):
    permission_classes = [IsAuthenticated, require_permission('roles.assign_permissions')]
    
    def delete(self, request, role_id: int, permission_id: int):
        """
        Remueve un permiso de un rol.
        
        Requiere permiso 'roles.assign_permissions'.
        """
        role = get_object_or_404(Role.objects.prefetch_related('permissions'), pk=role_id)
        
        # Verificar acceso al rol
        if not (hasattr(request.user, 'profile') and request.user.profile.is_saas_admin()):
            if not request.tenant or role.institution != request.tenant:
                return Response(
                    {'error': 'Rol no encontrado'},
                    status=status.HTTP_404_NOT_FOUND
                )
        
        permission = get_object_or_404(Permission.objects.filter(is_active=True), pk=permission_id)

        role.permissions.remove(permission)
        response_serializer = RoleSerializer(role)
        return Response(response_serializer.data)



# ============================================================
# SPRINT 8: Endpoints Adicionales para Asignación de Permisos
# ============================================================

from .serializers import RolePermissionSerializer, AvailablePermissionSerializer


class RolePermissionsAPIView(APIView):
    """
    Vista para obtener permisos de un rol específico.
    """
    permission_classes = [IsAuthenticated, require_permission('roles.view')]
    
    def get(self, request, role_id: int):
        """
        Lista los permisos asignados a un rol.
        
        Response:
        {
            "role": {
                "id": 1,
                "name": "Administrador"
            },
            "permissions": [...]
        }
        """
        role = get_object_or_404(Role, pk=role_id)
        
        # Verificar acceso al rol
        if not (hasattr(request.user, 'profile') and request.user.profile.is_saas_admin()):
            if not request.tenant or role.institution != request.tenant:
                return Response(
                    {'error': 'Rol no encontrado'},
                    status=status.HTTP_404_NOT_FOUND
                )
        
        permissions = role.permissions.filter(is_active=True).order_by('code')
        serializer = PermissionSerializer(permissions, many=True)
        
        return Response({
            'role': {
                'id': role.id,
                'name': role.name,
                'description': role.description
            },
            'permissions': serializer.data
        })


class RolePermissionsAssignAPIView(APIView):
    """
    Vista para asignar permisos a un rol (versión simplificada).
    """
    permission_classes = [IsAuthenticated, require_permission('roles.assign_permissions')]
    
    def post(self, request, role_id: int):
        """
        Asigna permisos a un rol.
        
        Body:
        {
            "permission_ids": [1, 2, 3, 15, 42]
        }
        
        Response:
        {
            "message": "Permisos asignados exitosamente",
            "role": {
                "id": 1,
                "name": "Contador",
                "permissions_count": 5
            }
        }
        """
        role = get_object_or_404(Role, pk=role_id)
        
        # Verificar acceso al rol
        if not (hasattr(request.user, 'profile') and request.user.profile.is_saas_admin()):
            if not request.tenant or role.institution != request.tenant:
                return Response(
                    {'error': 'Rol no encontrado'},
                    status=status.HTTP_404_NOT_FOUND
                )
        
        serializer = RolePermissionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        permission_ids = serializer.validated_data['permission_ids']
        permissions = Permission.objects.filter(
            id__in=permission_ids,
            is_active=True
        )
        
        # Asignar permisos al rol
        role.permissions.set(permissions)
        
        return Response({
            'message': 'Permisos asignados exitosamente',
            'role': {
                'id': role.id,
                'name': role.name,
                'description': role.description,
                'permissions_count': permissions.count()
            }
        })


class AvailablePermissionsAPIView(APIView):
    """
    Vista para listar todos los permisos disponibles para asignar.
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """
        Lista todos los permisos disponibles.
        
        Query params:
            - role_id: Si se proporciona, marca los permisos ya asignados al rol
            - search: Buscar por código, nombre o descripción
        
        Response:
        [
            {
                "id": 1,
                "code": "users.view",
                "name": "Ver Usuarios",
                "description": "...",
                "is_active": true,
                "is_assigned": true
            }
        ]
        """
        permissions = Permission.objects.filter(is_active=True).order_by('code')
        
        # Filtro de búsqueda
        search = request.query_params.get('search')
        if search:
            permissions = permissions.filter(
                Q(code__icontains=search) |
                Q(name__icontains=search) |
                Q(description__icontains=search)
            )
        
        # Contexto para marcar permisos asignados
        context = {}
        role_id = request.query_params.get('role_id')
        if role_id:
            try:
                role = Role.objects.get(pk=role_id)
                # Verificar acceso al rol
                if hasattr(request.user, 'profile') and request.user.profile.is_saas_admin():
                    context['role'] = role
                elif request.tenant and role.institution == request.tenant:
                    context['role'] = role
            except Role.DoesNotExist:
                pass
        
        serializer = AvailablePermissionSerializer(permissions, many=True, context=context)
        return Response(serializer.data)
