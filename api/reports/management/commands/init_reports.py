"""
Comando para inicializar datos de reportes.
"""
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission, Group
from django.contrib.contenttypes.models import ContentType

User = get_user_model()


class Command(BaseCommand):
    help = 'Inicializa datos necesarios para el módulo de reportes'

    def handle(self, *args, **options):
        self.stdout.write('Inicializando módulo de reportes...')
        
        # Crear permisos si no existen
        self.create_permissions()
        
        # Asignar permisos a roles
        self.assign_permissions_to_roles()
        
        self.stdout.write(self.style.SUCCESS('✓ Módulo de reportes inicializado correctamente'))

    def create_permissions(self):
        """Crea permisos personalizados."""
        self.stdout.write('Creando permisos...')
        
        try:
            from api.reports.models import GeneratedReport
            content_type = ContentType.objects.get_for_model(GeneratedReport)
        except:
            self.stdout.write(self.style.WARNING('No se pudo obtener ContentType para reportes'))
            return
        
        permissions = [
            ('view_report_catalog', 'Can view report catalog'),
            ('generate_report', 'Can generate reports'),
            ('export_report', 'Can export reports'),
            ('manage_templates', 'Can manage report templates'),
            ('use_voice_reports', 'Can use voice reports'),
            ('view_all_reports', 'Can view all reports in tenant'),
            ('access_saas_reports', 'Can access SAAS reports'),
            ('access_tenant_reports', 'Can access TENANT reports'),
        ]
        
        for codename, name in permissions:
            permission, created = Permission.objects.get_or_create(
                codename=codename,
                content_type=content_type,
                defaults={'name': name}
            )
            if created:
                self.stdout.write(f'  ✓ Permiso creado: {codename}')

    def assign_permissions_to_roles(self):
        """Asigna permisos a roles."""
        self.stdout.write('Asignando permisos a roles...')
        
        try:
            from api.reports.models import GeneratedReport
            content_type = ContentType.objects.get_for_model(GeneratedReport)
        except:
            return
        
        role_permissions = {
            'ADMIN': [
                'view_report_catalog', 'generate_report', 'export_report',
                'manage_templates', 'use_voice_reports', 'view_all_reports',
                'access_saas_reports', 'access_tenant_reports',
            ],
            'MANAGER': [
                'view_report_catalog', 'generate_report', 'export_report',
                'manage_templates', 'use_voice_reports', 'view_all_reports',
                'access_tenant_reports',
            ],
            'ANALYST': [
                'view_report_catalog', 'generate_report', 'export_report',
                'use_voice_reports', 'access_tenant_reports',
            ],
            'OFFICER': [
                'view_report_catalog', 'generate_report', 'export_report',
                'access_tenant_reports',
            ],
        }
        
        for role_name, permission_codenames in role_permissions.items():
            group, created = Group.objects.get_or_create(name=role_name)
            
            for codename in permission_codenames:
                try:
                    permission = Permission.objects.get(
                        codename=codename,
                        content_type=content_type
                    )
                    group.permissions.add(permission)
                except Permission.DoesNotExist:
                    pass
            
            self.stdout.write(f'  ✓ Permisos asignados a: {role_name}')
