"""
Comando para sincronizar los límites de las suscripciones con sus planes
"""
from django.core.management.base import BaseCommand
from api.saas.models import Subscription


class Command(BaseCommand):
    help = 'Sincroniza los límites de las suscripciones con los límites actuales de sus planes'

    def add_arguments(self, parser):
        parser.add_argument(
            '--plan-slug',
            type=str,
            help='Sincronizar solo suscripciones de un plan específico (por slug)',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Mostrar qué se actualizaría sin hacer cambios',
        )

    def handle(self, *args, **options):
        plan_slug = options.get('plan_slug')
        dry_run = options.get('dry_run', False)
        
        self.stdout.write(self.style.SUCCESS('\n=== SINCRONIZACIÓN DE LÍMITES DE SUSCRIPCIONES ===\n'))
        
        if dry_run:
            self.stdout.write(self.style.WARNING('MODO DRY-RUN: No se harán cambios reales\n'))
        
        # Obtener suscripciones a sincronizar
        subscriptions = Subscription.objects.select_related('plan', 'institution').all()
        
        if plan_slug:
            subscriptions = subscriptions.filter(plan__slug=plan_slug)
            self.stdout.write(f'Filtrando por plan: {plan_slug}\n')
        
        if not subscriptions.exists():
            self.stdout.write(self.style.WARNING('No se encontraron suscripciones para sincronizar'))
            return
        
        updated_count = 0
        no_changes_count = 0
        
        for subscription in subscriptions:
            plan = subscription.plan
            institution = subscription.institution
            
            # Verificar si hay cambios necesarios
            changes = []
            
            # Nota: Las suscripciones no almacenan los límites, solo referencian al plan
            # Pero podemos verificar si el plan ha cambiado
            
            self.stdout.write(f'\n--- {institution.name} ---')
            self.stdout.write(f'Plan: {plan.name}')
            self.stdout.write(f'Estado: {subscription.get_status_display()}')
            
            self.stdout.write('\nLÍMITES DEL PLAN ACTUAL:')
            self.stdout.write(f'  - Usuarios: {plan.max_users}')
            self.stdout.write(f'  - Sucursales: {plan.max_branches}')
            self.stdout.write(f'  - Productos: {plan.max_products}')
            self.stdout.write(f'  - Préstamos/mes: {plan.max_loans_per_month}')
            self.stdout.write(f'  - Almacenamiento: {plan.max_storage_gb} GB')
            
            self.stdout.write('\nUSO ACTUAL:')
            self.stdout.write(f'  - Usuarios: {subscription.current_users}/{plan.max_users}')
            self.stdout.write(f'  - Sucursales: {subscription.current_branches}/{plan.max_branches}')
            self.stdout.write(f'  - Productos: {subscription.current_products}/{plan.max_products}')
            self.stdout.write(f'  - Préstamos/mes: {subscription.current_month_loans}/{plan.max_loans_per_month}')
            self.stdout.write(f'  - Almacenamiento: {subscription.current_storage_gb}/{plan.max_storage_gb} GB')
            
            # Verificar si está dentro de los límites
            is_within = subscription.is_within_limits()
            if is_within:
                self.stdout.write(self.style.SUCCESS('✓ Dentro de los límites'))
            else:
                self.stdout.write(self.style.ERROR('✗ EXCEDE LOS LÍMITES'))
            
            no_changes_count += 1
        
        self.stdout.write(self.style.SUCCESS(f'\n\n=== RESUMEN ==='))
        self.stdout.write(f'Total de suscripciones revisadas: {subscriptions.count()}')
        self.stdout.write(f'Suscripciones actualizadas: {updated_count}')
        self.stdout.write(f'Sin cambios necesarios: {no_changes_count}')
        
        if not dry_run and updated_count > 0:
            self.stdout.write(self.style.SUCCESS('\n✓ Sincronización completada'))
        elif dry_run:
            self.stdout.write(self.style.WARNING('\nModo dry-run: No se realizaron cambios'))
        else:
            self.stdout.write('\nNo hubo cambios que realizar')
        
        # Información adicional
        self.stdout.write(self.style.SUCCESS('\n\n=== NOTA IMPORTANTE ==='))
        self.stdout.write('Las suscripciones NO almacenan los límites directamente.')
        self.stdout.write('Los límites se obtienen del plan asociado en tiempo real.')
        self.stdout.write('Si actualizaste un plan, los cambios ya están activos para todas')
        self.stdout.write('las suscripciones que usan ese plan.')
        self.stdout.write('\nLo que SÍ debes verificar es que el uso actual (current_users, etc.)')
        self.stdout.write('esté correctamente actualizado en cada suscripción.')
