"""
Comando para asignar permisos de reportes manuales a usuarios.

Este comando asigna los permisos de Django necesarios para acceder
a los reportes manuales independientes.

Uso:
    python manage.py assign_manual_report_permissions
    python manage.py assign_manual_report_permissions --all-users
    python manage.py assign_manual_report_permissions --user-id 123
"""
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.db import models
from api.reports.permissions_manual import create_manual_report_permissions

User = get_user_model()


class Command(BaseCommand):
    help = 'Asigna permisos de reportes manuales a usuarios'

    def add_arguments(self, parser):
        parser.add_argument(
            '--all-users',
            action='store_true',
            help='Asignar permisos a todos los usuarios activos',
        )
        parser.add_argument(
            '--user-id',
            type=int,
            help='ID del usuario específico',
        )
        parser.add_argument(
            '--staff-only',
            action='store_true',
            help='Solo asignar a usuarios staff',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('=== Asignación de Permisos de Reportes Manuales ===\n'))
        
        # Paso 1: Crear permisos si no existen
        self.stdout.write('Paso 1: Verificando permisos...')
        try:
            created_count = create_manual_report_permissions()
            if created_count > 0:
                self.stdout.write(self.style.SUCCESS(f'✓ Creados {created_count} permisos nuevos'))
            else:
                self.stdout.write(self.style.SUCCESS('✓ Todos los permisos ya existen'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'✗ Error creando permisos: {str(e)}'))
            return
        
        # Paso 2: Obtener permisos
        self.stdout.write('\nPaso 2: Obteniendo permisos...')
        try:
            content_type = ContentType.objects.get(
                app_label='reports',
                model='manualreport'
            )
            
            permissions = {
                'view': Permission.objects.get(
                    codename='view_manual_reports',
                    content_type=content_type
                ),
                'export': Permission.objects.get(
                    codename='export_manual_reports',
                    content_type=content_type
                ),
                'clients': Permission.objects.get(
                    codename='view_client_reports',
                    content_type=content_type
                ),
                'products': Permission.objects.get(
                    codename='view_product_reports',
                    content_type=content_type
                ),
                'applications': Permission.objects.get(
                    codename='view_application_reports',
                    content_type=content_type
                ),
            }
            
            self.stdout.write(self.style.SUCCESS(f'✓ Encontrados {len(permissions)} permisos'))
            
        except ContentType.DoesNotExist:
            self.stdout.write(
                self.style.ERROR(
                    '✗ Error: ContentType no encontrado. '
                    'Ejecuta primero: python manage.py migrate'
                )
            )
            return
        except Permission.DoesNotExist as e:
            self.stdout.write(
                self.style.ERROR(
                    f'✗ Error: Permiso no encontrado: {str(e)}. '
                    'Ejecuta primero la migración 0005_create_manual_report_permissions'
                )
            )
            return
        
        # Paso 3: Seleccionar usuarios
        self.stdout.write('\nPaso 3: Seleccionando usuarios...')
        
        if options['user_id']:
            # Usuario específico
            try:
                users = User.objects.filter(id=options['user_id'])
                if not users.exists():
                    self.stdout.write(
                        self.style.ERROR(f'✗ Usuario con ID {options["user_id"]} no encontrado')
                    )
                    return
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'✗ Error: {str(e)}'))
                return
        
        elif options['all_users']:
            # Todos los usuarios activos
            users = User.objects.filter(is_active=True)
            if options['staff_only']:
                users = users.filter(is_staff=True)
        
        else:
            # Por defecto: usuarios staff y superusuarios
            users = User.objects.filter(
                is_active=True
            ).filter(
                models.Q(is_staff=True) | models.Q(is_superuser=True)
            )
        
        user_count = users.count()
        self.stdout.write(self.style.SUCCESS(f'✓ Seleccionados {user_count} usuarios'))
        
        if user_count == 0:
            self.stdout.write(self.style.WARNING('⚠ No hay usuarios para procesar'))
            return
        
        # Paso 4: Asignar permisos
        self.stdout.write('\nPaso 4: Asignando permisos...')
        
        users_updated = 0
        permissions_assigned = 0
        
        for user in users:
            try:
                # Asignar permisos básicos a todos
                basic_perms = [
                    permissions['view'],
                    permissions['export'],
                    permissions['clients'],
                    permissions['products'],
                    permissions['applications'],
                ]
                
                for perm in basic_perms:
                    if not user.has_perm(f'reports.{perm.codename}'):
                        user.user_permissions.add(perm)
                        permissions_assigned += 1
                
                users_updated += 1
                
                # Mostrar información del usuario
                institution_info = ''
                if hasattr(user, 'institution_memberships'):
                    memberships = user.institution_memberships.filter(is_active=True)
                    if memberships.exists():
                        institutions = [m.institution.name for m in memberships[:2]]
                        institution_info = f' ({", ".join(institutions)})'
                
                self.stdout.write(
                    f'  ✓ {user.username} ({user.email}){institution_info}'
                )
                
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'  ✗ Error con usuario {user.username}: {str(e)}')
                )
        
        # Resumen final
        self.stdout.write(
            self.style.SUCCESS(
                f'\n=== Proceso Completado ===\n'
                f'Usuarios actualizados: {users_updated}\n'
                f'Permisos asignados: {permissions_assigned}\n'
            )
        )
        
        # Instrucciones adicionales
        self.stdout.write(
            self.style.WARNING(
                '\n📝 Nota: Los usuarios deben cerrar sesión y volver a iniciar '
                'para que los permisos surtan efecto.'
            )
        )

