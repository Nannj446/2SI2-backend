"""
Comando para crear suscripciones de prueba.
"""
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from api.tenants.models import FinancialInstitution
from api.saas.models import SubscriptionPlan, Subscription
from decimal import Decimal

User = get_user_model()


class Command(BaseCommand):
    help = 'Crea suscripciones de prueba para instituciones sin suscripción'

    def add_arguments(self, parser):
        parser.add_argument(
            '--institution-id',
            type=int,
            help='ID de la institución específica'
        )
        parser.add_argument(
            '--all',
            action='store_true',
            help='Crear suscripciones para todas las instituciones sin suscripción'
        )

    def handle(self, *args, **options):
        # Buscar plan básico existente o crear uno nuevo
        basic_plan = SubscriptionPlan.objects.filter(
            name__icontains='básico'
        ).first()
        
        if not basic_plan:
            basic_plan = SubscriptionPlan.objects.filter(
                slug='basic'
            ).first()
        
        if not basic_plan:
            # Crear plan básico si no existe
            try:
                basic_plan = SubscriptionPlan.objects.create(
                    name='Plan Básico de Prueba',
                    slug='basic-test',
                    description='Plan básico para pruebas',
                    price=Decimal('99.00'),
                    billing_cycle='MONTHLY',
                    trial_days=30,
                    max_users=10,
                    max_branches=2,
                    max_products=5,
                    max_loans_per_month=100,
                    max_storage_gb=5,
                    is_active=True,
                )
                self.stdout.write(
                    self.style.SUCCESS(f'Plan básico creado: {basic_plan.name}')
                )
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'Error creando plan: {str(e)}')
                )
                return
        else:
            self.stdout.write(
                self.style.SUCCESS(f'Plan básico encontrado: {basic_plan.name}')
            )

        if options['institution_id']:
            # Crear para institución específica
            try:
                institution = FinancialInstitution.objects.get(id=options['institution_id'])
                self._create_subscription_for_institution(institution, basic_plan)
            except FinancialInstitution.DoesNotExist:
                self.stdout.write(
                    self.style.ERROR(f'Institución con ID {options["institution_id"]} no encontrada')
                )
        elif options['all']:
            # Crear para todas las instituciones sin suscripción
            institutions_without_subscription = FinancialInstitution.objects.exclude(
                subscription__status__in=['TRIAL', 'ACTIVE']
            )
            
            for institution in institutions_without_subscription:
                self._create_subscription_for_institution(institution, basic_plan)
        else:
            self.stdout.write(
                self.style.WARNING('Usa --institution-id <ID> o --all para crear suscripciones')
            )

    def _create_subscription_for_institution(self, institution, plan):
        """Crea una suscripción para una institución."""
        try:
            # Verificar si ya tiene suscripción activa
            existing = Subscription.objects.filter(
                institution=institution,
                status__in=['TRIAL', 'ACTIVE']
            ).first()
            
            if existing:
                self.stdout.write(
                    self.style.WARNING(
                        f'{institution.name} ya tiene suscripción activa: {existing.status}'
                    )
                )
                return
            
            # Crear nueva suscripción
            subscription = Subscription.objects.create(
                institution=institution,
                plan=plan
            )
            subscription.activate_trial()
            
            self.stdout.write(
                self.style.SUCCESS(
                    f'Suscripción creada para {institution.name}: '
                    f'{subscription.status} hasta {subscription.trial_end_date}'
                )
            )
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(
                    f'Error creando suscripción para {institution.name}: {str(e)}'
                )
            )