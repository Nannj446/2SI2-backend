"""
Permisos para gestión de backups.
"""
from rest_framework import permissions
import logging

logger = logging.getLogger(__name__)


class IsBackupAdmin(permissions.BasePermission):
    """
    Permiso para gestionar configuraciones de backups programados.
    
    Reglas:
    - Superadmin: puede gestionar todas las configuraciones
    - Admin Tenant: solo puede gestionar configuraciones de su propio tenant
    - Otros usuarios: sin acceso
    """
    
    def has_permission(self, request, view):
        """Verifica si el usuario tiene permiso para acceder."""
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Superadmin puede todo
        if request.user.is_superuser:
            return True
        
        # Verificar que tenga perfil
        if not hasattr(request.user, 'profile'):
            return False
        
        # Superadmin SaaS puede todo
        if request.user.profile.user_type == 'saas_admin':
            return True
        
        # Obtener la institución del usuario a través de su membresía activa
        membership = request.user.institution_memberships.filter(is_active=True).first()
        if not membership:
            return False
        
        # Verificar que sea admin del tenant
        from api.roles.models import UserRole
        
        is_admin = UserRole.objects.filter(
            user=request.user,
            institution=membership.institution,
            is_active=True,
            role__name__icontains='administrador'
        ).exists()
        
        return is_admin
    
    def has_object_permission(self, request, view, obj):
        """Verifica si el usuario tiene permiso para acceder a un objeto específico."""
        # Superadmin puede acceder a todo
        if request.user.is_superuser:
            return True
        
        # Superadmin SaaS puede acceder a todo
        if hasattr(request.user, 'profile') and request.user.profile.user_type == 'saas_admin':
            return True
        
        # Admin tenant solo puede acceder a configuraciones de su tenant
        membership = request.user.institution_memberships.filter(is_active=True).first()
        if membership:
            return obj.tenant == membership.institution
        
        return False


class CanManageBackups(permissions.BasePermission):
    """
    Permiso para gestionar backups de tenants.
    
    Reglas:
    - Superadmin SaaS: puede gestionar backups de cualquier tenant
    - Admin Tenant: solo puede ver y crear backups de su propio tenant
    - Otros usuarios: sin acceso
    """
    
    def has_permission(self, request, view):
        """
        Verifica si el usuario tiene permiso para acceder al endpoint.
        
        Args:
            request: Request object
            view: View object
        
        Returns:
            True si tiene permiso, False si no
        """
        # Usuario debe estar autenticado
        if not request.user or not request.user.is_authenticated:
            logger.warning("Usuario no autenticado intentó acceder a backups")
            return False
        
        # Obtener tipo de usuario
        user_type = None
        if hasattr(request.user, 'profile'):
            user_type = request.user.profile.user_type
        
        # Log para debugging
        logger.debug(f"Usuario {request.user.email} con tipo {user_type} accediendo a backups")
        
        # Superadmin SaaS puede todo
        if user_type == 'saas_admin':
            logger.debug(f"Superadmin {request.user.email} accediendo a backups")
            return True
        
        # Admin de tenant
        if user_type == 'tenant_user':
            tenant_id = view.kwargs.get('tenant_id')
            
            if not tenant_id:
                logger.warning("No se proporcionó tenant_id en la ruta")
                return False
            
            # Verificar que es su propio tenant
            user_institution_id = None
            
            # Obtener la institución del usuario a través de su membresía activa
            membership = request.user.institution_memberships.filter(is_active=True).first()
            if membership:
                user_institution_id = membership.institution.id
            
            if user_institution_id != int(tenant_id):
                logger.warning(
                    f"Usuario {request.user.email} intentó acceder a backups "
                    f"de tenant {tenant_id} (su tenant: {user_institution_id})"
                )
                return False
            
            # Verificar que tiene rol admin en la institución
            from api.roles.models import UserRole
            
            is_admin = UserRole.objects.filter(
                user=request.user,
                institution_id=user_institution_id,
                is_active=True,
                role__name__icontains='administrador'
            ).exists()
            
            if not is_admin:
                logger.warning(
                    f"Usuario {request.user.email} no es admin de su tenant {user_institution_id}"
                )
                return False
            
            # Admin tenant no puede eliminar backups
            if request.method == 'DELETE':
                logger.warning(
                    f"Admin tenant {request.user.email} intentó eliminar backup"
                )
                return False
            
            logger.debug(
                f"Admin tenant {request.user.email} accediendo a backups "
                f"de su tenant {tenant_id}"
            )
            return True
        
        logger.warning(
            f"Usuario {request.user.email} con tipo {user_type} "
            f"intentó acceder a backups"
        )
        return False
    
    def has_object_permission(self, request, view, obj):
        """
        Verifica si el usuario tiene permiso para acceder a un backup específico.
        
        Args:
            request: Request object
            view: View object
            obj: TenantBackup object
        
        Returns:
            True si tiene permiso, False si no
        """
        # Obtener tipo de usuario
        user_type = None
        if hasattr(request.user, 'profile'):
            user_type = request.user.profile.user_type
        
        # Superadmin puede acceder a cualquier backup
        if user_type == 'saas_admin':
            return True
        
        # Admin tenant solo puede acceder a backups de su tenant
        if user_type == 'tenant_user':
            # Obtener la institución del usuario
            membership = request.user.institution_memberships.filter(is_active=True).first()
            user_institution_id = membership.institution.id if membership else None
            
            if obj.tenant_id != user_institution_id:
                logger.warning(
                    f"Usuario {request.user.email} intentó acceder a backup "
                    f"de otro tenant (backup tenant: {obj.tenant_id}, "
                    f"user tenant: {user_institution_id})"
                )
                return False
            
            # Verificar que es admin
            from api.roles.models import UserRole
            is_admin = UserRole.objects.filter(
                user=request.user,
                institution_id=user_institution_id,
                is_active=True,
                role__name__icontains='administrador'
            ).exists()
            
            if not is_admin:
                return False
            
            # No puede eliminar
            if request.method == 'DELETE':
                return False
            
            return True
        
        return False
