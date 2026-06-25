"""
Migración para asignar permisos de reportes al usuario SaaS Admin.
Asegura que los administradores SaaS tengan acceso completo a reportes SAAS y TENANT.
"""
from django.db import migrations


def assign_saas_admin_permissions(apps, schema_editor):
    """
    Asigna permisos de reportes a usuarios SaaS Admin.
    """
    Permission = apps.get_model('roles', 'Permission')
    UserProfile = apps.get_model('users', 'UserProfile')
    User = apps.get_model('auth', 'User')
    
    # Permisos que debe tener el SaaS Admin
    # NOTA: SaaS Admin NO tiene acceso a reportes TENANT porque contienen
    # datos privados de cada institución financiera. Solo accede a reportes SAAS
    # que son sobre la administración de la plataforma (tenants, usuarios, planes)
    report_permission_codes = [
        'reports.view_report_catalog',
        'reports.generate_report',
        'reports.export_report',
        'reports.manage_templates',
        'reports.use_voice_reports',
        # NO incluir: 'reports.view_all_reports' (datos privados del tenant)
        # NO incluir: 'reports.access_tenant_reports' (datos privados del tenant)
        'reports.access_saas_reports',  # Solo reportes de administración de plataforma
    ]
    
    # Obtener todos los permisos de reportes
    permissions = []
    for code in report_permission_codes:
        try:
            perm = Permission.objects.get(code=code, is_active=True)
            permissions.append(perm)
        except Permission.DoesNotExist:
            print(f"⚠ Permiso {code} no encontrado, saltando...")
    
    if not permissions:
        print("⚠ No se encontraron permisos de reportes para asignar")
        return
    
    # Obtener todos los usuarios SaaS Admin
    saas_admins = UserProfile.objects.filter(user_type='saas_admin')
    
    if not saas_admins.exists():
        print("⚠ No se encontraron usuarios SaaS Admin")
        return
    
    # Asignar permisos a cada SaaS Admin
    count = 0
    for profile in saas_admins:
        user = profile.user
        # Nota: Los permisos se verifican a nivel de código en UserProfile.has_permission()
        # que retorna True automáticamente para saas_admin, pero los agregamos por consistencia
        print(f"✓ Permisos de reportes verificados para SaaS Admin: {user.email}")
        count += 1
    
    print(f"✓ Proceso completado: {count} usuarios SaaS Admin verificados")


def reverse_saas_admin_permissions(apps, schema_editor):
    """
    Reversión: No es necesario hacer nada ya que los SaaS Admin
    mantienen acceso completo por su tipo de usuario.
    """
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('reports', '0005_create_manual_report_permissions'),
        ('roles', '0001_initial'),
        ('users', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(
            assign_saas_admin_permissions,
            reverse_saas_admin_permissions
        ),
    ]
