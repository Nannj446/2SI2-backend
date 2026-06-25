"""
Comando para verificar los datos de los planes
"""
from django.core.management.base import BaseCommand
from api.saas.models import SubscriptionPlan
import json


class Command(BaseCommand):
    help = 'Verifica los datos de los planes de suscripción'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('\n=== PLANES DE SUSCRIPCIÓN ===\n'))
        
        plans = SubscriptionPlan.objects.all().order_by('display_order')
        
        if not plans.exists():
            self.stdout.write(self.style.WARNING('No hay planes registrados'))
            return
        
        for plan in plans:
            self.stdout.write(self.style.SUCCESS(f'\n--- {plan.name} (ID: {plan.id}) ---'))
            self.stdout.write(f'Slug: {plan.slug}')
            self.stdout.write(f'Precio: Bs {plan.price}')
            self.stdout.write(f'Ciclo: {plan.billing_cycle}')
            self.stdout.write(f'Activo: {plan.is_active}')
            
            self.stdout.write('\nLÍMITES:')
            self.stdout.write(f'  - Usuarios: {plan.max_users}')
            self.stdout.write(f'  - Sucursales: {plan.max_branches}')
            self.stdout.write(f'  - Productos: {plan.max_products}')
            self.stdout.write(f'  - Préstamos/mes: {plan.max_loans_per_month}')
            self.stdout.write(f'  - Almacenamiento: {plan.max_storage_gb} GB')
            
            self.stdout.write('\nCARACTERÍSTICAS:')
            self.stdout.write(f'  - AI Scoring: {plan.has_ai_scoring}')
            self.stdout.write(f'  - Workflows: {plan.has_workflows}')
            self.stdout.write(f'  - Reportes: {plan.has_reporting}')
            self.stdout.write(f'  - App Móvil: {plan.has_mobile_app}')
            self.stdout.write(f'  - API: {plan.has_api_access}')
            self.stdout.write(f'  - White Label: {plan.has_white_label}')
            self.stdout.write(f'  - Integraciones: {plan.has_custom_integrations}')
            self.stdout.write(f'  - Soporte: {plan.has_priority_support}')
        
        self.stdout.write(self.style.SUCCESS(f'\n\nTotal de planes: {plans.count()}'))
