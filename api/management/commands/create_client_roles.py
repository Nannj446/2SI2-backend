"""
Management command para crear rol "Cliente" con permisos limitados en cada institución.
"""
from django.core.management.base import BaseCommand
from api.models import FinancialInstitution
from api.roles.models import Role, Permission


class Command(BaseCommand):
    help = 'Crea rol "Cliente" con permisos limitados en cada institución financiera'

    def handle(self, *args, **options):
        self.stdout.write('👥 Creando roles de Cliente para instituciones...\n')

        # Obtener todos los permisos de cliente
        client_permissions = Permission.objects.filter(
            code__startswith='client.',
            is_active=True
        )

        if not client_permissions.exists():
            self.stdout.write(
                self.style.ERROR('❌ No se encontraron permisos de cliente.')
            )
            self.stdout.write(
                self.style.WARNING('   Ejecuta primero: python manage.py create_client_permissions')
            )
            return

        self.stdout.write(f'📋 Permisos de cliente encontrados: {client_permissions.count()}\n')

        # Obtener todas las instituciones activas
        institutions = FinancialInstitution.objects.filter(is_active=True)

        if not institutions.exists():
            self.stdout.write(
                self.style.ERROR('❌ No se encontraron instituciones financieras activas.')
            )
            return

        created_count = 0
        existing_count = 0

        for institution in institutions:
            # Crear o obtener rol "Cliente"
            role, created = Role.objects.get_or_create(
                institution=institution,
                name='Cliente',
                defaults={
                    'description': 'Rol para clientes/prestatarios con acceso móvil limitado',
                    'is_active': True
                }
            )

            if created:
                # Asignar todos los permisos de cliente al rol
                role.permissions.set(client_permissions)
                
                self.stdout.write(
                    self.style.SUCCESS(
                        f'   ✅ Creado rol "Cliente" para: {institution.name}'
                    )
                )
                self.stdout.write(
                    f'      Permisos asignados: {role.permissions.count()}'
                )
                created_count += 1
            else:
                # Actualizar permisos si el rol ya existe
                current_perms = role.permissions.count()
                role.permissions.set(client_permissions)
                
                self.stdout.write(
                    self.style.WARNING(
                        f'   ⚠️  Ya existe rol "Cliente" para: {institution.name}'
                    )
                )
                self.stdout.write(
                    f'      Permisos actualizados: {current_perms} → {role.permissions.count()}'
                )
                existing_count += 1

        self.stdout.write('\n' + '='*60)
        self.stdout.write(self.style.SUCCESS(f'✅ Roles creados: {created_count}'))
        self.stdout.write(self.style.WARNING(f'⚠️  Roles actualizados: {existing_count}'))
        self.stdout.write('='*60 + '\n')
