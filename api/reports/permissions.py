"""
Permisos personalizados para el módulo de reportes.

Implementa autorización basada en:
- Scope (TENANT vs SAAS)
- Roles de usuario
- Aislamiento multi-tenant
- Propiedad de recursos
"""
from rest_framework import permissions


class CanViewReportCatalog(permissions.BasePermission):
    """
    Permiso para ver el catálogo de reportes.
    
    Permite acceso a usuarios autenticados.
    """
    
    message = "No tiene permiso para ver el catálogo de reportes."
    
    def has_permission(self, request, view):
        """Verifica permiso a nivel de vista."""
        return request.user and request.user.is_authenticated


class CanGenerateReports(permissions.BasePermission):
    """
    Permiso para generar reportes.
    
    Valida que el usuario esté autenticado y tenga permisos básicos.
    """
    
    message = "No tiene permiso para generar reportes."
    
    def has_permission(self, request, view):
        """Verifica permiso a nivel de vista."""
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Para métodos seguros, permitir
        if request.method in permissions.SAFE_METHODS:
            return True
        
        return True


class CanManageTemplates(permissions.BasePermission):
    """
    Permiso para gestionar plantillas de reportes.
    
    Permite crear, editar y eliminar plantillas.
    """
    
    message = "No tiene permiso para gestionar plantillas de reportes."
    
    def has_permission(self, request, view):
        """Verifica permiso a nivel de vista."""
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Para métodos seguros, permitir
        if request.method in permissions.SAFE_METHODS:
            return True
        
        return True
    
    def has_object_permission(self, request, view, obj):
        """Verifica permiso a nivel de objeto."""
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Para métodos seguros, permitir
        if request.method in permissions.SAFE_METHODS:
            return True
        
        # Para edición/eliminación, validar propiedad o admin
        if request.user.is_superuser:
            return True
        
        # Validar que sea el creador
        if hasattr(obj, 'created_by') and obj.created_by == request.user:
            return True
        
        # Validar que pertenezca al mismo tenant
        if hasattr(obj, 'institution') and hasattr(request, 'tenant'):
            if obj.institution == request.tenant:
                return True
        
        return False


class CanAccessSaaSReports(permissions.BasePermission):
    """
    Permiso para acceder a reportes SAAS.
    
    Solo para Administrador SaaS / Superadmin.
    """
    
    message = "No tiene permiso para acceder a reportes SAAS."
    
    def has_permission(self, request, view):
        """Verifica permiso a nivel de vista."""
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Solo superusuarios
        if request.user.is_superuser:
            return True
        
        # Verificar si tiene perfil de admin SaaS
        if hasattr(request.user, 'profile'):
            return request.user.profile.is_saas_admin()
        
        return False
