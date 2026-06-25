"""
Management command para crear permisos específicos para clientes/prestatarios.
"""
from django.core.management.base import BaseCommand
from api.roles.models import Permission


class Command(BaseCommand):
    help = 'Crea permisos específicos para clientes/prestatarios'

    def handle(self, *args, **options):
        self.stdout.write('🔐 Creando permisos para clientes...\n')

        # Definir permisos para clientes
        client_permissions = [
            {
                'code': 'client.view_own_profile',
                'name': 'Ver Perfil Propio',
                'description': 'Permite al cliente ver su propio perfil'
            },
            {
                'code': 'client.update_own_profile',
                'name': 'Actualizar Perfil Propio',
                'description': 'Permite al cliente actualizar su propio perfil'
            },
            {
                'code': 'client.view_products',
                'name': 'Ver Productos Crediticios',
                'description': 'Permite al cliente ver productos crediticios disponibles'
            },
            {
                'code': 'client.create_credit_request',
                'name': 'Crear Solicitud de Crédito',
                'description': 'Permite al cliente crear solicitudes de crédito'
            },
            {
                'code': 'client.view_own_requests',
                'name': 'Ver Solicitudes Propias',
                'description': 'Permite al cliente ver sus propias solicitudes de crédito'
            },
            {
                'code': 'client.upload_documents',
                'name': 'Subir Documentos',
                'description': 'Permite al cliente subir documentos para sus solicitudes'
            },
            {
                'code': 'client.view_own_credits',
                'name': 'Ver Créditos Propios',
                'description': 'Permite al cliente ver sus créditos activos'
            },
            {
                'code': 'client.view_payment_schedule',
                'name': 'Ver Cronograma de Pagos',
                'description': 'Permite al cliente ver el cronograma de pagos de sus créditos'
            },
            {
                'code': 'client.view_account_statement',
                'name': 'Ver Estado de Cuenta',
                'description': 'Permite al cliente consultar su estado de cuenta'
            },
        ]

        created_count = 0
        existing_count = 0

        for perm_data in client_permissions:
            permission, created = Permission.objects.get_or_create(
                code=perm_data['code'],
                defaults={
                    'name': perm_data['name'],
                    'description': perm_data['description'],
                    'is_active': True
                }
            )

            if created:
                self.stdout.write(
                    self.style.SUCCESS(f'   ✅ Creado: {permission.code} - {permission.name}')
                )
                created_count += 1
            else:
                self.stdout.write(
                    self.style.WARNING(f'   ⚠️  Ya existe: {permission.code}')
                )
                existing_count += 1

        self.stdout.write('\n' + '='*60)
        self.stdout.write(self.style.SUCCESS(f'✅ Permisos creados: {created_count}'))
        self.stdout.write(self.style.WARNING(f'⚠️  Permisos existentes: {existing_count}'))
        self.stdout.write('='*60 + '\n')
