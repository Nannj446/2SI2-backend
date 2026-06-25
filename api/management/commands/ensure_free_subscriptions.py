"""
Comando para asegurar que todas las instituciones tengan un plan gratuito.
"""
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from datetime import date, timedelta
from api.tenants.models import FinancialInstitution
from api.saas.models import SubscriptionPlan, Subscription
from decimal import Decimal

User = get_user_model()


class Command(BaseCommand):
    help = 'Asegura que todas las instituciones tengan un plan gratuito asignado'

    def add_arguments(self, parser):
        parser.add_argument(
            '--institution-id',
            type=int,
            help='ID de la institución específica'
        )
        parser.add_argument(
            '--all',
            action='store_true',
            help='Verificar todas las instituciones'
        )
        parser.add_argument(
            '--create-plan',
            action='store_true',
            help='Crear plan gratuito si no existe'
        )

    def handle(self, *args, **options):
        # Verificar o crear plan gratuito
        free_plan = self._ensure_free_plan_exists(options.get('create_plan', False))
        
        if not free_plan:
            self.stdout.write(
                self.style.ERROR('No se pudo obtener o crear un plan gratuito')
            )
            return

        if options['institution_id']:
            # Procesar institución específica
            self._process_institution(options['institution_id'], free_plan)
        elif options['all']:
            # Procesar todas las instituciones
            self._process_all_institutions(free_plan)
        else:
            # Mostrar estado actual
            self._show_current_status()

    def _ensure_free_plan_exists(self, create_if_missing=False):
        """Asegura que existe un plan gratuito."""
        # Buscar plan gratuito existente
        free_plan = SubscriptionPlan.objects.filter(
            price=0,
            is_active=True
        ).first()
        
        if free_plan:
            self.stdout.write(
                self.style.SUCCESS(f'Plan gratuito encontrado: {free_plan.name}')
            )
            return free_plan
        
        if not create_if_missing:
            self.stdout.write(
                self.style.WARNING('No hay plan gratuito. Usa --create-plan para crear uno.')
            )
            return None
        
        # Crear plan gratuito
        try:
            free_plan = SubscriptionPlan.objects.create(
                name='Plan Gratuito',
                slug='gratuito',
                description='Plan gratuito con funcionalidades básicas para empezar',
                price=Decimal('0.00'),
                billing_cycle='MONTHLY',
                trial_days=0,  # Sin período de prueba para plan gratuito
                setup_fee=Decimal('0.00'),
                
                # Límites básicos
                max_users=5,
                max_branches=1,
                max_products=3,
                max_loans_per_month=50,
                max_storage_gb=1,
                
                # Características básicas
                has_ai_scoring=False,
                has_workflows=False,
                has_reporting=True,
                has_mobile_app=True,
                has_api_access=False,
                has_white_label=False,
                has_priority_support=False,
                has_custom_integrations=False,
                
                is_active=True,
                is_featured=False,
                display_order=-1,  # Mostrar primero
            )
            
            self.stdout.write(
                self.style.SUCCESS(f'Plan gratuito creado: {free_plan.name}')
            )
            return free_plan
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error creando plan gratuito: {str(e)}')
            )
            return None

    def _process_institution(self, institution_id, free_plan):
        """Procesa una institución específica."""
        try:
            institution = FinancialInstitution.objects.get(id=institution_id)
            self._ensure_institution_has_subscription(institution, free_plan)
        except FinancialInstitution.DoesNotExist:
            self.stdout.write(
                self.style.ERROR(f'Institución con ID {institution_id} no encontrada')
            )

    def _process_all_institutions(self, free_plan):
        """Procesa todas las instituciones activas."""
        institutions = FinancialInstitution.objects.filter(is_active=True)
        
        self.stdout.write(
            self.style.SUCCESS(f'Procesando {institutions.count()} instituciones...')
        )
        
        created_count = 0
        existing_count = 0
        
        for institution in institutions:
            if self._ensure_institution_has_subscription(institution, free_plan):
                created_count += 1
            else:
                existing_count += 1
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Proceso completado: {created_count} suscripciones creadas, '
                f'{existing_count} ya existían'
            )
        )

    def _ensure_institution_has_subscription(self, institution, free_plan):
        """Asegura que una institución tenga suscripción."""
        # Verificar si ya tiene suscripción activa
        existing_subscription = Subscription.objects.filter(
            institution=institution,
            status__in=['TRIAL', 'ACTIVE']
        ).first()
        
        if existing_subscription:
            self.stdout.write(
                f'✅ {institution.name} → Ya tiene suscripción: '
                f'{existing_subscription.plan.name} ({existing_subscription.status})'
            )
            return False
        
        # Crear suscripción gratuita
        try:
            subscription = Subscription.objects.create(
                institution=institution,
                plan=free_plan
            )
            
            # Activar directamente (sin período de prueba para plan gratuito)
            subscription.status = 'ACTIVE'
            subscription.next_billing_date = date.today() + timedelta(days=30)
            subscription.save()
            
            self.stdout.write(
                self.style.SUCCESS(
                    f'🆕 {institution.name} → Suscripción gratuita creada y activada'
                )
            )
            return True
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(
                    f'❌ Error creando suscripción para {institution.name}: {str(e)}'
                )
            )
            return False

    def _show_current_status(self):
        """Muestra el estado actual de todas las instituciones."""
        institutions = FinancialInstitution.objects.filter(is_active=True)
        
        self.stdout.write('=== ESTADO ACTUAL DE SUSCRIPCIONES ===')
        self.stdout.write(f'Total instituciones activas: {institutions.count()}')
        self.stdout.write('')
        
        with_subscription = 0
        without_subscription = 0
        
        for institution in institutions:
            subscription = Subscription.objects.filter(
                institution=institution,
                status__in=['TRIAL', 'ACTIVE']
            ).first()
            
            if subscription:
                with_subscription += 1
                status_color = self.style.SUCCESS if subscription.status == 'ACTIVE' else self.style.WARNING
                self.stdout.write(
                    status_color(
                        f'✅ {institution.name} → {subscription.plan.name} '
                        f'(${subscription.plan.price}, {subscription.status})'
                    )
                )
            else:
                without_subscription += 1
                self.stdout.write(
                    self.style.ERROR(f'❌ {institution.name} → SIN SUSCRIPCIÓN')
                )
        
        self.stdout.write('')
        self.stdout.write(f'Con suscripción: {with_subscription}')
        self.stdout.write(f'Sin suscripción: {without_subscription}')
        
        if without_subscription > 0:
            self.stdout.write('')
            self.stdout.write(
                self.style.WARNING(
                    'Para crear suscripciones gratuitas automáticamente, ejecuta:'
                )
            )
            self.stdout.write('python manage.py ensure_free_subscriptions --all --create-plan')

        # Mostrar planes gratuitos disponibles
        free_plans = SubscriptionPlan.objects.filter(price=0, is_active=True)
        self.stdout.write('')
        self.stdout.write(f'Planes gratuitos disponibles: {free_plans.count()}')
        for plan in free_plans:
            self.stdout.write(f'  - {plan.name} (${plan.price})')