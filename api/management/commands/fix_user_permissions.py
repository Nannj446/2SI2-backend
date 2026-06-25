"""
Management command para asignar permisos básicos a usuarios administradores
"""
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from api.models import UserRole, Role, Permission

User = get_user_model()


class Command(BaseCommand):
    help = 'Asigna permisos básicos a roles de administrador'

    def handle(self, *args, **options):
        """Asigna permisos básicos a roles de administrador"""
        
        self.stdout.write("=" * 70)
        self.stdout.write("ASIGNANDO PERMISOS BÁSICOS A ROLES DE ADMINISTRADOR")
        self.stdout.write("=" * 70)
        self.stdout.write("")
        
        # Permisos básicos que todo administrador debería tener
        basic_permissions = [
            'users.view',
            'users.create',
            'users.edit',
            'users.deactivate',
            'users.assign_roles',
            'roles.view',
            'roles.create',
            'roles.edit',
            'roles.delete',
            'roles.assign_permissions',
        ]
        
        # Obtener todos los roles de administrador
        admin_roles = Role.objects.filter(
            name__icontains='Administrador',
            is_active=True
        )
        
        self.stdout.write(f"Roles de administrador encontrados: {admin_roles.count()}")
        self.stdout.write("")
        
        for role in admin_roles:
            self.stdout.write(f"📋 Procesando: {role.name} ({role.institution.name})")
            
            # Obtener permisos que faltan
            current_permissions = set(role.permissions.values_list('code', flat=True))
            missing_permissions = [p for p in basic_permissions if p not in current_permissions]
            
            if not missing_permissions:
                self.stdout.write(f"   ✅ Ya tiene todos los permisos básicos")
                continue
            
            # Agregar permisos faltantes
            added_count = 0
            for perm_code in missing_permissions:
                try:
                    permission = Permission.objects.get(code=perm_code, is_active=True)
                    role.permissions.add(permission)
                    added_count += 1
                    self.stdout.write(f"   ✓ Agregado: {perm_code}")
                except Permission.DoesNotExist:
                    self.stdout.write(self.style.WARNING(f"   ⚠️  Permiso no encontrado: {perm_code}"))
            
            self.stdout.write(self.style.SUCCESS(f"   ✅ {added_count} permiso(s) agregado(s)"))
            self.stdout.write("")
        
        self.stdout.write("=" * 70)
        self.stdout.write("VERIFICANDO USUARIOS")
        self.stdout.write("=" * 70)
        self.stdout.write("")
        
        # Verificar usuarios con roles de administrador
        admin_user_roles = UserRole.objects.filter(
            role__name__icontains='Administrador',
            is_active=True
        ).select_related('user', 'role', 'institution')
        
        for user_role in admin_user_roles:
            user = user_role.user
            role = user_role.role
            institution = user_role.institution
            
            self.stdout.write(f"👤 {user.email}")
            self.stdout.write(f"   Rol: {role.name}")
            self.stdout.write(f"   Institución: {institution.name}")
            self.stdout.write(f"   Permisos en rol: {role.permissions.count()}")
            
            # Verificar permisos específicos
            has_users_view = role.permissions.filter(code='users.view').exists()
            self.stdout.write(f"   users.view: {'✅' if has_users_view else '❌'}")
            self.stdout.write("")
        
        self.stdout.write("=" * 70)
        self.stdout.write(self.style.SUCCESS("✅ PROCESO COMPLETADO"))
        self.stdout.write("=" * 70)
        self.stdout.write("")
        self.stdout.write(self.style.WARNING("NOTA: Los usuarios deben cerrar sesión y volver a iniciar sesión"))
        self.stdout.write(self.style.WARNING("      para que los nuevos permisos se reflejen en su token JWT."))
        self.stdout.write("")
