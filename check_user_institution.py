import os
import django
import sys

# Configurar Django
sys.path.insert(0, os.path.dirname(__file__))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

try:
    django.setup()
    
    from django.contrib.auth import get_user_model
    from api.contracts.models import Contract
    from api.roles.models import UserRole
    
    User = get_user_model()
    
    # Buscar el usuario
    user = User.objects.filter(email='vallejosgabriel446@gmail.com').first()
    
    if not user:
        print("\nNo se encontró el usuario con ese email.")
        sys.exit(1)
    
    print(f"\n{'='*80}")
    print(f"INFORMACIÓN DEL USUARIO")
    print(f"{'='*80}\n")
    
    print(f"Email: {user.email}")
    print(f"Nombre: {user.get_full_name()}")
    print(f"Es staff: {user.is_staff}")
    print(f"Es superuser: {user.is_superuser}")
    
    # Verificar roles en instituciones
    user_roles = UserRole.objects.filter(user=user, is_active=True).select_related('institution', 'role')
    
    print(f"\nRoles en instituciones:")
    if user_roles.exists():
        for ur in user_roles:
            print(f"  - {ur.institution.name} (ID: {ur.institution.id}): {ur.role.name}")
    else:
        print(f"  ⚠ No tiene roles asignados en ninguna institución")
    
    # Verificar permisos de contratos
    print(f"\nPermisos relacionados con contratos:")
    contract_perms = user.get_all_permissions()
    contract_related = [p for p in contract_perms if 'contract' in p.lower()]
    
    if contract_related:
        for perm in contract_related:
            print(f"  ✓ {perm}")
    else:
        print(f"  ⚠ No tiene permisos específicos de contratos")
    
    # Verificar contratos de sus instituciones
    if user_roles.exists():
        for ur in user_roles:
            contracts_count = Contract.objects.filter(institution=ur.institution).count()
            print(f"\nContratos en {ur.institution.name}: {contracts_count}")
            
            if contracts_count > 0:
                print(f"Primeros 5 contratos:")
                contracts = Contract.objects.filter(institution=ur.institution)[:5]
                for contract in contracts:
                    print(f"  - {contract.contract_number} ({contract.get_status_display()})")
    
    print(f"\n{'='*80}\n")
    
except Exception as e:
    print(f"\nError: {str(e)}")
    import traceback
    traceback.print_exc()
