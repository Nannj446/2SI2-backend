"""
Management command: Crear permisos para SP3.

Uso: python manage.py create_sp3_permissions
"""

from django.core.management.base import BaseCommand
from api.roles.models import Permission, Role


class Command(BaseCommand):
    help = 'Crea los permisos necesarios para SP3 (Créditos Activos y Pagos) y los asigna a roles admin'

    def handle(self, *args, **options):
        perms_data = [
            ('active_credits.view', 'Ver Créditos Activos'),
            ('active_credits.manage', 'Gestionar Créditos Activos'),
            ('active_credits.apply_grace_period', 'Aplicar Período de Gracia'),
            ('active_credits.restructure', 'Reestructurar Créditos'),
            ('payments.view', 'Ver Pagos'),
            ('payments.create', 'Registrar Pagos'),
            ('payments.confirm', 'Confirmar Pagos'),
            ('payments.reverse', 'Reversar Pagos'),
        ]

        created = 0
        for code, name in perms_data:
            p, is_new = Permission.objects.get_or_create(
                code=code,
                defaults={'name': name, 'description': name}
            )
            if is_new:
                self.stdout.write(self.style.SUCCESS(f'  + {code}'))
                created += 1
            else:
                self.stdout.write(f'    {code} (ya existe)')

        self.stdout.write(f'\n{created} permisos nuevos creados.')

        # Asignar a roles admin
        admin_roles = Role.objects.filter(name__icontains='admin')
        count = 0
        for role in admin_roles:
            for code, name in perms_data:
                perm = Permission.objects.get(code=code)
                if not role.permissions.filter(id=perm.id).exists():
                    role.permissions.add(perm)
                    count += 1
            self.stdout.write(f'  Asignados permisos a: {role.name} (tenant {role.institution_id})')

        self.stdout.write(self.style.SUCCESS(f'\nTotal: {created} creados, {count} asignaciones'))
