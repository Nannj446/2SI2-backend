# Script para crear permisos SP3
import os, sys
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

import django
django.setup()

from api.roles.models import Permission, Role

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
for code, name in perms_data:
    p, new = Permission.objects.get_or_create(code=code, defaults={'name': name, 'description': name})
    if new:
        print(f'CREADO: {code}')

for role in Role.objects.filter(name__icontains='admin'):
    for code, name in perms_data:
        perm = Permission.objects.get(code=code)
        role.permissions.add(perm)
    print(f'Asignado a: {role.name}')

print('Permisos SP3 creados y asignados.')
