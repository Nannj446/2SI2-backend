"""
Permisos personalizados para el módulo de contratos
"""

from rest_framework import permissions


def _get_request_tenant(request):
    tenant = getattr(request, 'tenant', None)
    if tenant:
        return tenant

    user = getattr(request, 'user', None)
    if not user or not user.is_authenticated:
        return None
    
    # Intentar obtener desde user.institution (si existe)
    if hasattr(user, 'institution'):
        return user.institution

    # Intentar obtener desde user.institution_memberships (si existe)
    if hasattr(user, 'institution_memberships'):
        membership = user.institution_memberships.filter(is_active=True).first()
        if membership:
            return membership.institution
    
    # Obtener desde UserRole (sistema actual)
    from api.roles.models import UserRole
    user_role = UserRole.objects.filter(
        user=user,
        is_active=True
    ).select_related('institution').first()
    
    if user_role:
        return user_role.institution

    return None


def _has_custom_permission(request, permission_code: str) -> bool:
    if not request.user or not request.user.is_authenticated:
        return False

    if not hasattr(request.user, 'profile'):
        return False

    if request.user.profile.is_saas_admin():
        return True

    tenant = _get_request_tenant(request)
    if not tenant:
        return False

    return request.user.profile.has_permission(permission_code, tenant)


class CanViewContract(permissions.BasePermission):
    """
    Permiso para ver contratos basado en permisos del sistema.
    """
    
    def has_permission(self, request, view):
        return _has_custom_permission(request, 'contracts.view')
    
    def has_object_permission(self, request, view, obj):
        tenant = _get_request_tenant(request)
        return bool(tenant and obj.institution == tenant)


class CanGenerateContract(permissions.BasePermission):
    """
    Permiso para generar contratos basado en permisos del sistema.
    """
    
    def has_permission(self, request, view):
        return _has_custom_permission(request, 'contracts.generate')


class CanManageContractTemplates(permissions.BasePermission):
    """
    Permiso para gestionar plantillas de contratos.
    Solo administradores.
    """
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Verificar permiso personalizado según la acción
        if view.action == 'create':
            return _has_custom_permission(request, 'contract_templates.create')
        elif view.action in ['update', 'partial_update']:
            return _has_custom_permission(request, 'contract_templates.edit')
        elif view.action == 'destroy':
            return _has_custom_permission(request, 'contract_templates.delete')
        elif view.action in ['list', 'retrieve']:
            return _has_custom_permission(request, 'contract_templates.view')
        
        # Por defecto, verificar permiso de ver
        return _has_custom_permission(request, 'contract_templates.view')


class CanSignContract(permissions.BasePermission):
    """
    Permiso para firmar contratos basado en permisos del sistema.
    """
    
    def has_permission(self, request, view):
        return _has_custom_permission(request, 'contracts.sign')
    
    def has_object_permission(self, request, view, obj):
        tenant = _get_request_tenant(request)
        return bool(tenant and obj.institution == tenant)


class CanCancelContract(permissions.BasePermission):
    """
    Permiso para cancelar contratos basado en permisos del sistema.
    """
    
    def has_permission(self, request, view):
        return _has_custom_permission(request, 'contracts.cancel')
    
    def has_object_permission(self, request, view, obj):
        # Verificar que el contrato pueda ser cancelado
        if not obj.can_be_cancelled():
            return False
        
        # Verificar que pertenezca al mismo tenant
        tenant = _get_request_tenant(request)
        return bool(tenant and obj.institution == tenant)


class CanPublishContract(permissions.BasePermission):
    """
    Permiso para publicar contratos basado en permisos del sistema.
    """
    
    def has_permission(self, request, view):
        return _has_custom_permission(request, 'contracts.publish')
    
    def has_object_permission(self, request, view, obj):
        # Solo contratos en DRAFT pueden ser publicados
        if obj.status != obj.Status.DRAFT:
            return False
        
        # Verificar que pertenezca al mismo tenant
        tenant = _get_request_tenant(request)
        return bool(tenant and obj.institution == tenant)


class CanDownloadContractPDF(permissions.BasePermission):
    """
    Permiso para descargar el PDF del contrato basado en permisos del sistema.
    """
    
    def has_permission(self, request, view):
        return _has_custom_permission(request, 'contracts.download')
    
    def has_object_permission(self, request, view, obj):
        tenant = _get_request_tenant(request)
        return bool(tenant and obj.institution == tenant)
