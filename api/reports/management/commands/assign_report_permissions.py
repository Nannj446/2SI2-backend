"""
Script para asignar permisos de reportes a roles existentes.
Ejecutar con: python manage.py assign_report_permissions
"""
from django.core.management.base import BaseCommand
from django.contrib.auth.models import Permission as DjangoPermission
from django.contrib.contenttypes.models import ContentType
from api.roles.models import Role, Permission


class Command(BaseCommand):
    help = 'Asigna permisos de reportes a roles existentes'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Iniciando asignación de permisos de reportes...'))
        
        try:
            # Crear o obtener permisos personalizados en el modelo Permission
            report_permissions = {}
            
            permissions_data = [
                ('reports.view_report_catalog', 'Ver catálogo de reportes'),
                ('reports.generate_report', 'Generar reportes'),
                ('reports.export_report', 'Exportar reportes'),
                ('reports.manage_templates', 'Gestionar plantillas de reportes'),
                ('reports.use_voice_reports', 'Usar reportes por voz'),
                ('reports.view_all_reports', 'Ver todos los reportes del tenant'),
                ('reports.access_tenant_reports', 'Acceder a reportes TENANT'),
                ('reports.access_saas_reports', 'Acceder a reportes SAAS'),
            ]
            
            for code, name in permissions_data:
                permission, created = Permission.objects.get_or_create(
                    code=code,
                    defaults={'name': name, 'is_active': True}
                )
                report_permissions[code.split('.')[-1]] = permission
                if created:
                    self.stdout.write(f'  ✓ Permiso creado: {code}')
            
            self.stdout.write(f'✓ Encontrados/creados {len(report_permissions)} permisos de reportes')
            
            # Configuración de permisos por rol
            role_permissions_map = {
                # Administrador de Institución - Acceso completo a reportes TENANT
                'Administrador de Institución': [
                    'view_report_catalog',
                    'generate_report',
                    'export_report',
                    'manage_templates',
                    'use_voice_reports',
                    'view_all_reports',
                    'access_tenant_reports',
                ],
                # Gerente - Acceso completo a reportes TENANT
                'Gerente': [
                    'view_report_catalog',
                    'generate_report',
                    'export_report',
                    'manage_templates',
                    'use_voice_reports',
                    'view_all_reports',
                    'access_tenant_reports',
                ],
                # Analista de Crédito - Puede ver y generar reportes
                'Analista de Crédito': [
                    'view_report_catalog',
                    'generate_report',
                    'export_report',
                    'manage_templates',  # Agregado para poder ver plantillas
                    'access_tenant_reports',
                ],
                # Oficial de Crédito - Puede ver y generar reportes básicos
                'Oficial de Crédito': [
                    'view_report_catalog',
                    'generate_report',
                    'export_report',
                    'manage_templates',  # Agregado para poder ver plantillas
                    'access_tenant_reports',
                ],
                # Auditor - Solo lectura de reportes
                'Auditor': [
                    'view_report_catalog',
                    'view_all_reports',
                    'manage_templates',  # Agregado para poder ver plantillas
                    'access_tenant_reports',
                ],
                # Superadmin - Acceso solo a reportes SAAS (administración de plataforma)
                # NO tiene acceso a reportes TENANT porque contienen datos privados
                # de cada institución financiera
                'Superadmin': [
                    'view_report_catalog',
                    'generate_report',
                    'export_report',
                    'manage_templates',
                    'use_voice_reports',
                    # NO incluir: 'view_all_reports' (datos privados del tenant)
                    # NO incluir: 'access_tenant_reports' (datos privados del tenant)
                    'access_saas_reports',  # Solo reportes de administración
                ],
            }
            
            # Asignar permisos a cada rol
            roles_updated = 0
            permissions_assigned = 0
            
            for role_name, permission_codenames in role_permissions_map.items():
                try:
                    # Buscar el rol (puede estar en diferentes tenants)
                    roles = Role.objects.filter(name=role_name)
                    
                    if not roles.exists():
                        self.stdout.write(
                            self.style.WARNING(f'⚠ Rol "{role_name}" no encontrado, saltando...')
                        )
                        continue
                    
                    for role in roles:
                        # Asignar permisos al rol
                        for codename in permission_codenames:
                            permission = report_permissions[codename]
                            role.permissions.add(permission)
                            permissions_assigned += 1
                        
                        roles_updated += 1
                        tenant_info = f" (Tenant: {role.tenant.name})" if hasattr(role, 'tenant') and role.tenant else ""
                        self.stdout.write(
                            self.style.SUCCESS(
                                f'✓ Permisos asignados a "{role_name}"{tenant_info}: '
                                f'{len(permission_codenames)} permisos'
                            )
                        )
                
                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(f'✗ Error asignando permisos a "{role_name}": {str(e)}')
                    )
            
            self.stdout.write(
                self.style.SUCCESS(
                    f'\n✓ Proceso completado: {roles_updated} roles actualizados, '
                    f'{permissions_assigned} permisos asignados'
                )
            )
            
        except ContentType.DoesNotExist:
            self.stdout.write(
                self.style.ERROR(
                    '✗ Error: ContentType de reportes no encontrado. '
                    'Asegúrate de haber ejecutado las migraciones.'
                )
            )
        except Permission.DoesNotExist as e:
            self.stdout.write(
                self.style.ERROR(
                    f'✗ Error: Permiso no encontrado: {str(e)}. '
                    'Asegúrate de haber ejecutado las migraciones.'
                )
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'✗ Error inesperado: {str(e)}')
            )
