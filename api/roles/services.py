"""
Servicio para gestionar permisos globales del sistema.
"""

from django.db import transaction
from typing import Optional

from api.models import Permission, Role


class PermissionService:
    """
    Servicio para crear y gestionar permisos globales.
    
    Incluye funcionalidad de auto-asignación a roles de administrador
    para mantener consistencia entre tenants.
    """
    
    @transaction.atomic
    def create_permission(
        self,
        code: str,
        name: str,
        description: str = '',
        auto_assign_to_admins: bool = True
    ) -> Permission:
        """
        Crea un nuevo permiso global y opcionalmente lo asigna a todos los
        roles de 'Administrador de Institución'.
        
        Args:
            code: Código único del permiso (ej: 'invoices.export')
            name: Nombre descriptivo del permiso
            description: Descripción detallada del permiso
            auto_assign_to_admins: Si True, asigna automáticamente a todos
                                   los roles de administrador de tenant
        
        Returns:
            Permission: El permiso creado
        
        Raises:
            ValueError: Si el código ya existe
        """
        # Validar que el código no exista
        if Permission.objects.filter(code=code).exists():
            raise ValueError(f"Ya existe un permiso con código '{code}'")
        
        # Crear el permiso
        permission = Permission.objects.create(
            code=code,
            name=name,
            description=description,
            is_active=True
        )
        
        # Auto-asignar a administradores si está habilitado
        if auto_assign_to_admins:
            assigned_count = self._assign_to_admin_roles(permission)
            print(f"✓ Permiso '{code}' creado y asignado a {assigned_count} roles de administrador")
        else:
            print(f"✓ Permiso '{code}' creado (sin auto-asignación)")
        
        return permission
    
    def _assign_to_admin_roles(self, permission: Permission) -> int:
        """
        Asigna un permiso a todos los roles de 'Administrador de Institución'.
        
        Args:
            permission: El permiso a asignar
        
        Returns:
            int: Número de roles actualizados
        """
        admin_roles = Role.objects.filter(
            name='Administrador de Institución',
            is_active=True
        )
        
        assigned_count = 0
        for role in admin_roles:
            # Verificar si ya tiene el permiso
            if not role.permissions.filter(id=permission.id).exists():
                role.permissions.add(permission)
                assigned_count += 1
        
        return assigned_count
    
    def sync_all_admin_permissions(self, dry_run: bool = False) -> dict:
        """
        Sincroniza todos los permisos activos con todos los roles de
        'Administrador de Institución'.
        
        Útil para corregir inconsistencias o después de agregar permisos
        manualmente.
        
        Args:
            dry_run: Si True, solo muestra qué se haría sin aplicar cambios
        
        Returns:
            dict: Resumen de la sincronización con estadísticas
        """
        all_permissions = Permission.objects.filter(is_active=True)
        total_permissions = all_permissions.count()
        
        admin_roles = Role.objects.filter(
            name='Administrador de Institución',
            is_active=True
        )
        
        results = {
            'total_permissions': total_permissions,
            'total_roles': admin_roles.count(),
            'updated_roles': 0,
            'already_synced': 0,
            'roles_detail': []
        }
        
        for role in admin_roles:
            current_perms = role.permissions.count()
            missing_perms = total_permissions - current_perms
            
            role_info = {
                'institution': role.institution.name,
                'current_permissions': current_perms,
                'missing_permissions': missing_perms,
                'updated': False
            }
            
            if missing_perms > 0:
                if not dry_run:
                    role.permissions.set(all_permissions)
                    role_info['updated'] = True
                    results['updated_roles'] += 1
                else:
                    results['updated_roles'] += 1
            else:
                results['already_synced'] += 1
            
            results['roles_detail'].append(role_info)
        
        return results
    
    def get_permission_coverage(self) -> dict:
        """
        Obtiene estadísticas de cobertura de permisos globales.
        
        Returns:
            dict: Estadísticas de cobertura con:
                - total_permissions: Total de permisos en el sistema
                - active_permissions: Permisos activos
                - inactive_permissions: Permisos inactivos
                - admin_roles_with_all_permissions: Roles admin con todos los permisos
                - total_admin_roles: Total de roles de administrador
                - coverage_percentage: Porcentaje de cobertura
                - permissions_by_module: Distribución por módulo
        """
        # Contar permisos
        all_permissions = Permission.objects.all()
        active_permissions = all_permissions.filter(is_active=True)
        total_permissions = all_permissions.count()
        active_count = active_permissions.count()
        inactive_count = total_permissions - active_count
        
        # Contar roles de administrador
        admin_roles = Role.objects.filter(
            name='Administrador de Institución',
            is_active=True
        )
        total_admin_roles = admin_roles.count()
        
        # Contar roles admin con todos los permisos activos
        admin_roles_with_all = 0
        for role in admin_roles:
            if role.permissions.filter(is_active=True).count() == active_count:
                admin_roles_with_all += 1
        
        # Calcular porcentaje de cobertura
        coverage_percentage = 0
        if total_admin_roles > 0:
            coverage_percentage = round((admin_roles_with_all / total_admin_roles) * 100, 2)
        
        # Agrupar permisos por módulo (extraer del código)
        permissions_by_module = {}
        for perm in active_permissions:
            # Extraer módulo del código (ej: "users.view" -> "users")
            parts = perm.code.split('.')
            module = parts[0] if len(parts) > 0 else 'general'
            permissions_by_module[module] = permissions_by_module.get(module, 0) + 1
        
        return {
            'total_permissions': total_permissions,
            'active_permissions': active_count,
            'inactive_permissions': inactive_count,
            'admin_roles_with_all_permissions': admin_roles_with_all,
            'total_admin_roles': total_admin_roles,
            'coverage_percentage': coverage_percentage,
            'permissions_by_module': permissions_by_module,
        }
