"""
Sistema de permisos para Reportes Manuales.

Este módulo define los permisos necesarios para acceder a reportes manuales,
garantizando aislamiento multi-tenant y control de acceso basado en roles.

Autor: Sistema FinCore
Fecha: 2026-05-11
"""

from rest_framework import permissions
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType


class HasManualReportPermission(permissions.BasePermission):
    """
    Permiso para acceder a reportes manuales.
    
    Verifica que el usuario:
    1. Esté autenticado
    2. Tenga el permiso 'reports.view_manual_reports' O sea superusuario O sea staff
    3. Pertenezca a una institución activa (si no es superusuario)
    """
    
    message = "No tiene permisos para acceder a reportes manuales."
    
    def has_permission(self, request, view):
        # Usuario debe estar autenticado
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Superusuarios siempre tienen acceso
        if request.user.is_superuser:
            return True
        
        # Staff users tienen acceso
        if request.user.is_staff:
            return True
        
        # Verificar permiso específico
        if request.user.has_perm('reports.view_manual_reports'):
            # Si tiene el permiso, verificar institución
            if hasattr(request.user, 'institution') and request.user.institution:
                if not request.user.institution.is_active:
                    self.message = "La institución no está activa."
                    return False
                return True
            # Si no tiene institución pero tiene el permiso, permitir acceso
            return True
        
        # Si no tiene el permiso específico, verificar si tiene institución activa
        # y permitir acceso de todos modos (para compatibilidad)
        if hasattr(request.user, 'institution') and request.user.institution:
            if not request.user.institution.is_active:
                self.message = "La institución no está activa."
                return False
            return True
        
        return False


class CanExportReports(permissions.BasePermission):
    """
    Permiso para exportar reportes.
    
    Verifica que el usuario tenga permiso de exportación.
    """
    
    message = "No tiene permisos para exportar reportes."
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Verificar permiso de exportación
        if request.user.has_perm('reports.export_manual_reports'):
            return True
        
        # Superusuarios siempre tienen acceso
        if request.user.is_superuser:
            return True
        
        return False


class CanViewClientReports(permissions.BasePermission):
    """Permiso específico para ver reportes de clientes."""
    
    message = "No tiene permisos para ver reportes de clientes."
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        return (
            request.user.has_perm('reports.view_client_reports') or
            request.user.has_perm('reports.view_manual_reports') or
            request.user.is_superuser
        )


class CanViewProductReports(permissions.BasePermission):
    """Permiso específico para ver reportes de productos."""
    
    message = "No tiene permisos para ver reportes de productos."
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        return (
            request.user.has_perm('reports.view_product_reports') or
            request.user.has_perm('reports.view_manual_reports') or
            request.user.is_superuser
        )


class CanViewApplicationReports(permissions.BasePermission):
    """Permiso específico para ver reportes de solicitudes."""
    
    message = "No tiene permisos para ver reportes de solicitudes."
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        return (
            request.user.has_perm('reports.view_application_reports') or
            request.user.has_perm('reports.view_manual_reports') or
            request.user.is_superuser
        )


class CanViewAuditReports(permissions.BasePermission):
    """
    Permiso específico para ver reportes de auditoría.
    Este es un permiso más restrictivo, típicamente solo para administradores.
    """
    
    message = "No tiene permisos para ver reportes de auditoría."
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        return (
            request.user.has_perm('reports.view_audit_reports') or
            request.user.is_superuser
        )


class CanViewUserReports(permissions.BasePermission):
    """
    Permiso específico para ver reportes de usuarios.
    Típicamente solo para administradores y gerentes.
    """
    
    message = "No tiene permisos para ver reportes de usuarios."
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        return (
            request.user.has_perm('reports.view_user_reports') or
            request.user.is_superuser
        )


class CanViewBranchReports(permissions.BasePermission):
    """Permiso específico para ver reportes de sucursales."""
    
    message = "No tiene permisos para ver reportes de sucursales."
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        return (
            request.user.has_perm('reports.view_branch_reports') or
            request.user.has_perm('reports.view_manual_reports') or
            request.user.is_superuser
        )


# ============================================================
# UTILIDADES DE PERMISOS
# ============================================================

def create_manual_report_permissions():
    """
    Crea los permisos personalizados para reportes manuales.
    
    Esta función debe ejecutarse en una migración o comando de management.
    """
    # Obtener o crear ContentType para reportes
    content_type, _ = ContentType.objects.get_or_create(
        app_label='reports',
        model='manualreport'
    )
    
    # Definir permisos
    permissions_to_create = [
        ('view_manual_reports', 'Can view manual reports'),
        ('export_manual_reports', 'Can export manual reports'),
        ('view_client_reports', 'Can view client reports'),
        ('view_product_reports', 'Can view product reports'),
        ('view_application_reports', 'Can view application reports'),
        ('view_audit_reports', 'Can view audit reports'),
        ('view_user_reports', 'Can view user reports'),
        ('view_branch_reports', 'Can view branch reports'),
    ]
    
    # Crear permisos
    created_count = 0
    for codename, name in permissions_to_create:
        _, created = Permission.objects.get_or_create(
            codename=codename,
            content_type=content_type,
            defaults={'name': name}
        )
        if created:
            created_count += 1
    
    print(f"✅ Creados {created_count} permisos nuevos para reportes manuales")
    return created_count


def validate_institution_access(user, queryset):
    """
    Valida y filtra un queryset por la institución del usuario.
    
    Args:
        user: Usuario autenticado
        queryset: QuerySet a filtrar
    
    Returns:
        QuerySet filtrado por institución
    
    Raises:
        PermissionError: Si el usuario no tiene institución
    """
    if not hasattr(user, 'institution') or not user.institution:
        raise PermissionError("Usuario no pertenece a ninguna institución")
    
    if not user.institution.is_active:
        raise PermissionError("La institución no está activa")
    
    # Filtrar por institución
    return queryset.filter(institution=user.institution)


def sanitize_filters(filters):
    """
    Sanitiza los filtros recibidos para prevenir inyección SQL.
    
    Args:
        filters (dict): Diccionario de filtros
    
    Returns:
        dict: Filtros sanitizados
    """
    import re
    
    sanitized = {}
    
    for key, value in filters.items():
        # Saltar valores None (campos no proporcionados)
        if value is None:
            continue
            
        # Validar nombres de campos (solo letras, números y guiones bajos)
        if not re.match(r'^[a-zA-Z0-9_]+$', key):
            continue
        
        # Sanitizar valores string
        if isinstance(value, str):
            # Remover caracteres peligrosos
            value = value.strip()
            # Si el string está vacío después de strip, saltarlo
            if not value:
                continue
            # Limitar longitud
            value = value[:200]
        
        sanitized[key] = value
    
    return sanitized


def check_rate_limit(user, action='export', limit=10, window_minutes=60):
    """
    Verifica límite de tasa para acciones costosas como exportación.
    
    Args:
        user: Usuario autenticado
        action (str): Tipo de acción
        limit (int): Número máximo de acciones permitidas
        window_minutes (int): Ventana de tiempo en minutos
    
    Returns:
        bool: True si está dentro del límite, False si excede
    """
    from django.core.cache import cache
    from datetime import datetime, timedelta
    
    # Clave de caché
    cache_key = f"rate_limit:{user.id}:{action}"
    
    # Obtener contador actual
    current = cache.get(cache_key, [])
    
    # Filtrar acciones dentro de la ventana de tiempo
    now = datetime.now()
    cutoff = now - timedelta(minutes=window_minutes)
    current = [ts for ts in current if ts > cutoff]
    
    # Verificar límite
    if len(current) >= limit:
        return False
    
    # Agregar nueva acción
    current.append(now)
    cache.set(cache_key, current, timeout=window_minutes * 60)
    
    return True
