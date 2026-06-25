"""
Comando para crear planes de suscripción de ejemplo.

Uso:
    python manage.py seed_subscription_plans
"""

from django.core.management.base import BaseCommand
from api.saas.models import SubscriptionPlan


class Command(BaseCommand):
    help = 'Crea planes de suscripción de ejemplo para el sistema SaaS'

    def handle(self, *args, **options):
        self.stdout.write('Creando planes de suscripción...\n')
        
        plans_data = [
            {
                'name': 'Plan Básico',
                'slug': 'basico',
                'description': 'Plan ideal para instituciones pequeñas que están comenzando',
                'price': 500.00,
                'billing_cycle': 'MONTHLY',
                'trial_days': 30,
                'setup_fee': 0,
                'max_users': 10,
                'max_branches': 1,
                'max_products': 5,
                'max_loans_per_month': 100,
                'max_storage_gb': 10,
                'has_ai_scoring': False,
                'has_workflows': False,
                'has_reporting': True,
                'has_mobile_app': True,
                'has_api_access': False,
                'has_white_label': False,
                'has_priority_support': False,
                'has_custom_integrations': False,
                'is_active': True,
                'is_featured': False,
                'display_order': 1,
                'features_list': [
                    'Hasta 10 usuarios',
                    '1 sucursal',
                    '5 productos crediticios',
                    '100 créditos por mes',
                    '10 GB de almacenamiento',
                    'Reportes básicos',
                    'App móvil incluida',
                    'Soporte por email'
                ]
            },
            {
                'name': 'Plan Profesional',
                'slug': 'profesional',
                'description': 'Plan completo para instituciones en crecimiento',
                'price': 1200.00,
                'billing_cycle': 'MONTHLY',
                'trial_days': 30,
                'setup_fee': 500.00,
                'max_users': 50,
                'max_branches': 5,
                'max_products': 20,
                'max_loans_per_month': 500,
                'max_storage_gb': 50,
                'has_ai_scoring': True,
                'has_workflows': True,
                'has_reporting': True,
                'has_mobile_app': True,
                'has_api_access': True,
                'has_white_label': False,
                'has_priority_support': True,
                'has_custom_integrations': False,
                'is_active': True,
                'is_featured': True,
                'display_order': 2,
                'features_list': [
                    'Hasta 50 usuarios',
                    '5 sucursales',
                    '20 productos crediticios',
                    '500 créditos por mes',
                    '50 GB de almacenamiento',
                    'Scoring con IA',
                    'Workflows configurables',
                    'Reportes avanzados',
                    'App móvil incluida',
                    'Acceso API REST',
                    'Soporte prioritario'
                ]
            },
            {
                'name': 'Plan Empresarial',
                'slug': 'empresarial',
                'description': 'Plan premium para grandes instituciones financieras',
                'price': 3000.00,
                'billing_cycle': 'MONTHLY',
                'trial_days': 30,
                'setup_fee': 2000.00,
                'max_users': 200,
                'max_branches': 20,
                'max_products': 100,
                'max_loans_per_month': 2000,
                'max_storage_gb': 200,
                'has_ai_scoring': True,
                'has_workflows': True,
                'has_reporting': True,
                'has_mobile_app': True,
                'has_api_access': True,
                'has_white_label': True,
                'has_priority_support': True,
                'has_custom_integrations': True,
                'is_active': True,
                'is_featured': False,
                'display_order': 3,
                'features_list': [
                    'Hasta 200 usuarios',
                    '20 sucursales',
                    '100 productos crediticios',
                    '2000 créditos por mes',
                    '200 GB de almacenamiento',
                    'Scoring con IA avanzado',
                    'Workflows personalizados',
                    'Reportes y analítica completa',
                    'App móvil white label',
                    'Acceso API completo',
                    'Integraciones personalizadas',
                    'Soporte 24/7',
                    'Gerente de cuenta dedicado'
                ]
            },
            {
                'name': 'Plan Anual Básico',
                'slug': 'basico-anual',
                'description': 'Plan básico con facturación anual (2 meses gratis)',
                'price': 5000.00,
                'billing_cycle': 'ANNUAL',
                'trial_days': 30,
                'setup_fee': 0,
                'max_users': 10,
                'max_branches': 1,
                'max_products': 5,
                'max_loans_per_month': 100,
                'max_storage_gb': 10,
                'has_ai_scoring': False,
                'has_workflows': False,
                'has_reporting': True,
                'has_mobile_app': True,
                'has_api_access': False,
                'has_white_label': False,
                'has_priority_support': False,
                'has_custom_integrations': False,
                'is_active': True,
                'is_featured': False,
                'display_order': 4,
                'features_list': [
                    'Hasta 10 usuarios',
                    '1 sucursal',
                    '5 productos crediticios',
                    '100 créditos por mes',
                    '10 GB de almacenamiento',
                    'Reportes básicos',
                    'App móvil incluida',
                    'Soporte por email',
                    '2 meses gratis (paga 10, usa 12)'
                ]
            },
        ]
        
        created_count = 0
        updated_count = 0
        
        for plan_data in plans_data:
            plan, created = SubscriptionPlan.objects.update_or_create(
                slug=plan_data['slug'],
                defaults=plan_data
            )
            
            if created:
                created_count += 1
                self.stdout.write(
                    self.style.SUCCESS(f'✓ Creado: {plan.name}')
                )
            else:
                updated_count += 1
                self.stdout.write(
                    self.style.WARNING(f'↻ Actualizado: {plan.name}')
                )
        
        self.stdout.write('\n' + '='*50)
        self.stdout.write(
            self.style.SUCCESS(
                f'\n✓ Proceso completado:\n'
                f'  - Planes creados: {created_count}\n'
                f'  - Planes actualizados: {updated_count}\n'
                f'  - Total: {created_count + updated_count}\n'
            )
        )
