"""
Comando de Django para migrar roles hardcoded a sistema dinámico.

Este comando:
1. Crea roles base para cada institución
2. Asigna permisos a cada rol
3. Migra asignaciones de usuarios desde membership.role a UserRole
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from api.models import (
    FinancialInstitution,
    FinancialInstitutionMembership,
    Role,
    Permission,
    UserRole
)


class Command(BaseCommand):
    help = 'Migra roles hardcoded del campo membership.role a sistema dinámico de roles'
    
    # Mapeo de roles hardcoded a roles dinámicos con sus permisos
    ROLE_MAPPING = {
        'admin': {
            'name': 'Administrador de Institución',
            'description': 'Administrador con acceso completo a la gestión de la institución',
            'permissions': [
                'users.view', 'users.create', 'users.edit', 'users.deactivate',
                'users.assign_roles', 'roles.view', 'roles.create', 'roles.edit',
                'roles.delete', 'roles.assign_permissions', 'institution.view',
                'institution.edit', 'institution.configure'
            ]
        },
        'analyst': {
            'name': 'Analista de Crédito',
            'description': 'Analista con permisos para evaluar solicitudes de crédito',
            'permissions': [
                'credit.request.view', 'credit.request.create',
                'credit.request.edit', 'credit.request.evaluate',
                'credit.approve.up_to_10k', 'reports.view'
            ]
        },
        'loan_officer': {
            'name': 'Oficial de Crédito',
            'description': 'Oficial encargado de gestionar solicitudes de crédito',
            'permissions': [
                'credit.request.view', 'credit.request.create',
                'credit.request.edit', 'reports.view'
            ]
        },
        'manager': {
            'name': 'Gerente de Crédito',
            'description': 'Gerente con permisos de aprobación y supervisión',
            'permissions': [
                'credit.request.view', 'credit.request.evaluate',
                'credit.approve.unlimited', 'credit.reject',
                'credit.disbursement', 'reports.view',
                'reports.export', 'analytics.view'
            ]
        },
        'collector': {
            'name': 'Oficial de Cobranza',
            'description': 'Oficial encargado de gestión de cobranza',
            'permissions': [
                'collection.view', 'collection.manage',
                'collection.contact', 'reports.view'
            ]
        },
        'auditor': {
            'name': 'Auditor',
            'description': 'Auditor con acceso de solo lectura',
            'permissions': [
                'credit.request.view', 'reports.view',
                'reports.export', 'analytics.view', 'audit.view'
            ]
        }
    }
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Ejecuta el comando sin aplicar cambios (modo prueba)',
        )
        parser.add_argument(
            '--institution',
            type=str,
            help='Slug de la institución específica a migrar (opcional)',
        )
    
    def handle(self, *args, **options):
        dry_run = options['dry_run']
        institution_slug = options.get('institution')
        
        if dry_run:
            self.stdout.write(self.style.WARNING('MODO PRUEBA - No se aplicarán cambios'))
        
        self.stdout.write('=' * 70)
        self.stdout.write('Iniciando migración de roles hardcoded a sistema dinámico')
        self.stdout.write('=' * 70)
        
        # Filtrar instituciones si se especificó una
        if institution_slug:
            institutions = FinancialInstitution.objects.filter(slug=institution_slug)
            if not institutions.exists():
                self.stdout.write(
                    self.style.ERROR(f'Institución con slug "{institution_slug}" no encontrada')
                )
                return
        else:
            institutions = FinancialInstitution.objects.all()
        
        total_institutions = institutions.count()
        total_roles_created = 0
        total_users_migrated = 0
        
        # Procesar cada institución
        for idx, institution in enumerate(institutions, 1):
            self.stdout.write('')
            self.stdout.write(f'[{idx}/{total_institutions}] Procesando: {institution.name}')
            self.stdout.write('-' * 70)
            
            try:
                with transaction.atomic():
                    # Crear roles base para la institución
                    roles_created = self._create_roles_for_institution(institution, dry_run)
                    total_roles_created += len(roles_created)
                    
                    # Migrar asignaciones de usuarios
                    users_migrated = self._migrate_user_assignments(
                        institution, roles_created, dry_run
                    )
                    total_users_migrated += users_migrated
                    
                    if dry_run:
                        # Revertir transacción en modo prueba
                        raise Exception('Dry run - revertir cambios')
                        
            except Exception as e:
                if not dry_run:
                    self.stdout.write(
                        self.style.ERROR(f'Error procesando {institution.name}: {str(e)}')
                    )
                    continue
        
        # Resumen final
        self.stdout.write('')
        self.stdout.write('=' * 70)
        self.stdout.write(self.style.SUCCESS('RESUMEN DE MIGRACIÓN'))
        self.stdout.write('=' * 70)
        self.stdout.write(f'Instituciones procesadas: {total_institutions}')
        self.stdout.write(f'Roles creados: {total_roles_created}')
        self.stdout.write(f'Usuarios migrados: {total_users_migrated}')
        
        if dry_run:
            self.stdout.write('')
            self.stdout.write(self.style.WARNING('MODO PRUEBA - Ningún cambio fue aplicado'))
            self.stdout.write('Ejecute sin --dry-run para aplicar los cambios')
        else:
            self.stdout.write('')
            self.stdout.write(self.style.SUCCESS('✓ Migración completada exitosamente'))
    
    def _create_roles_for_institution(self, institution, dry_run):
        """Crea roles base para una institución."""
        roles_created = {}
        
        for role_code, role_data in self.ROLE_MAPPING.items():
            # Verificar si el rol ya existe
            existing_role = Role.objects.filter(
                institution=institution,
                name=role_data['name']
            ).first()
            
            if existing_role:
                self.stdout.write(f'  ⊙ Rol ya existe: {role_data["name"]}')
                roles_created[role_code] = existing_role
                continue
            
            if not dry_run:
                # Crear rol
                role = Role.objects.create(
                    institution=institution,
                    name=role_data['name'],
                    description=role_data['description'],
                    is_active=True
                )
                
                # Asignar permisos (solo los que existan)
                permissions = Permission.objects.filter(
                    code__in=role_data['permissions']
                )
                role.permissions.set(permissions)
                
                roles_created[role_code] = role
                
                self.stdout.write(
                    self.style.SUCCESS(
                        f'  ✓ Rol creado: {role.name} ({permissions.count()} permisos)'
                    )
                )
            else:
                self.stdout.write(f'  [DRY RUN] Crearía rol: {role_data["name"]}')
                roles_created[role_code] = None
        
        return roles_created
    
    def _migrate_user_assignments(self, institution, roles_created, dry_run):
        """Migra asignaciones de usuarios desde membership.role a UserRole."""
        users_migrated = 0
        
        # Obtener memberships activas con rol asignado
        memberships = FinancialInstitutionMembership.objects.filter(
            institution=institution,
            is_active=True
        ).select_related('user')
        
        # Verificar si el campo 'role' existe en el modelo
        if not hasattr(FinancialInstitutionMembership, 'role'):
            self.stdout.write(
                self.style.WARNING(
                    '  ⚠ Campo "role" no existe en Membership - omitiendo migración de usuarios'
                )
            )
            return 0
        
        for membership in memberships:
            old_role = getattr(membership, 'role', None)
            
            if not old_role:
                continue
            
            new_role = roles_created.get(old_role)
            
            if not new_role:
                self.stdout.write(
                    self.style.WARNING(
                        f'  ⚠ Rol "{old_role}" no mapeado para usuario {membership.user.email}'
                    )
                )
                continue
            
            if not dry_run:
                # Crear o actualizar UserRole
                user_role, created = UserRole.objects.get_or_create(
                    user=membership.user,
                    role=new_role,
                    institution=institution,
                    defaults={
                        'is_active': True,
                        'assigned_by': None
                    }
                )
                
                if created:
                    users_migrated += 1
                    self.stdout.write(
                        f'  ✓ Usuario migrado: {membership.user.email} → {new_role.name}'
                    )
                else:
                    self.stdout.write(
                        f'  ⊙ Usuario ya tenía rol: {membership.user.email}'
                    )
            else:
                self.stdout.write(
                    f'  [DRY RUN] Migraría: {membership.user.email} → {roles_created[old_role]}'
                )
                users_migrated += 1
        
        return users_migrated
