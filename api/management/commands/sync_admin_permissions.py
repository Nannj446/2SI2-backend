"""
Comando para sincronizar permisos con roles de Administrador de Institución.
"""

from django.core.management.base import BaseCommand

from api.roles.services import PermissionService


class Command(BaseCommand):
    help = 'Sincroniza todos los permisos activos con los roles de Administrador de Institución'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Muestra qué se haría sin aplicar cambios'
        )
        
        parser.add_argument(
            '--coverage',
            action='store_true',
            help='Muestra solo el reporte de cobertura sin sincronizar'
        )
    
    def handle(self, *args, **options):
        dry_run = options['dry_run']
        show_coverage = options['coverage']
        
        service = PermissionService()
        
        if show_coverage:
            self._show_coverage(service)
            return
        
        self.stdout.write(f"\n{'='*70}")
        self.stdout.write("SINCRONIZACIÓN DE PERMISOS")
        self.stdout.write(f"{'='*70}\n")
        
        if dry_run:
            self.stdout.write(self.style.WARNING("MODO DRY-RUN: No se aplicarán cambios\n"))
        
        # Ejecutar sincronización
        results = service.sync_all_admin_permissions(dry_run=dry_run)
        
        # Mostrar resultados
        self.stdout.write(f"Total de permisos en catálogo: {results['total_permissions']}")
        self.stdout.write(f"Roles de administrador encontrados: {results['total_roles']}\n")
        
        for role_info in results['roles_detail']:
            if role_info['missing_permissions'] > 0:
                status = "→" if not dry_run else "→ (dry-run)"
                self.stdout.write(
                    f"  • {role_info['institution']}: "
                    f"{role_info['current_permissions']} permisos {status} "
                    f"{role_info['current_permissions'] + role_info['missing_permissions']} permisos "
                    f"(+{role_info['missing_permissions']})"
                )
            else:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"  ✓ {role_info['institution']}: "
                        f"{role_info['current_permissions']} permisos (actualizado)"
                    )
                )
        
        self.stdout.write(f"\n{'='*70}")
        self.stdout.write(f"Roles actualizados: {results['updated_roles']}")
        self.stdout.write(f"Roles ya sincronizados: {results['already_synced']}")
        
        if dry_run:
            self.stdout.write(self.style.WARNING(
                f"\nEjecuta sin --dry-run para aplicar los cambios"
            ))
        else:
            self.stdout.write(self.style.SUCCESS("\n✓ Sincronización completada"))
        
        self.stdout.write(f"{'='*70}\n")
    
    def _show_coverage(self, service: PermissionService):
        """Muestra reporte de cobertura de permisos."""
        self.stdout.write(f"\n{'='*70}")
        self.stdout.write("REPORTE DE COBERTURA DE PERMISOS")
        self.stdout.write(f"{'='*70}\n")
        
        coverage = service.get_permission_coverage()
        
        self.stdout.write(f"Total de permisos en catálogo: {coverage['total_permissions']}\n")
        
        complete_count = sum(1 for t in coverage['tenants'] if t['is_complete'])
        incomplete_count = len(coverage['tenants']) - complete_count
        
        if incomplete_count > 0:
            self.stdout.write(self.style.WARNING(
                f"⚠️  {incomplete_count} tenant(s) con permisos incompletos:\n"
            ))
        
        for tenant in coverage['tenants']:
            if tenant['is_complete']:
                self.stdout.write(self.style.SUCCESS(
                    f"  ✓ {tenant['institution']}: "
                    f"{tenant['permissions_count']} permisos ({tenant['coverage_percentage']}%)"
                ))
            else:
                self.stdout.write(self.style.ERROR(
                    f"  ✗ {tenant['institution']}: "
                    f"{tenant['permissions_count']} permisos ({tenant['coverage_percentage']}%) "
                    f"- INCOMPLETO"
                ))
        
        self.stdout.write(f"\n{'='*70}")
        self.stdout.write(f"Tenants con cobertura completa: {complete_count}/{len(coverage['tenants'])}")
        
        if incomplete_count > 0:
            self.stdout.write(self.style.WARNING(
                f"\nEjecuta 'python manage.py sync_admin_permissions' para sincronizar"
            ))
        else:
            self.stdout.write(self.style.SUCCESS("\n✓ Todos los tenants tienen cobertura completa"))
        
        self.stdout.write(f"{'='*70}\n")
