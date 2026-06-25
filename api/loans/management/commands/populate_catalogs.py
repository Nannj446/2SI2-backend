"""
Comando para poblar catálogos con datos iniciales.
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from api.tenants.models import FinancialInstitution
from api.loans.models_catalogs import (
    DocumentType,
    ProductType,
    PaymentFrequency,
    AmortizationSystem,
    Currency
)


class Command(BaseCommand):
    help = 'Pobla los catálogos centralizados con datos iniciales'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--tenant',
            type=str,
            help='Código del tenant específico (opcional, si no se especifica se poblan todos)'
        )
    
    def handle(self, *args, **options):
        tenant_code = options.get('tenant')
        
        if tenant_code:
            try:
                tenants = [FinancialInstitution.objects.get(slug=tenant_code)]
                self.stdout.write(f'Poblando catálogos para tenant: {tenant_code}')
            except FinancialInstitution.DoesNotExist:
                self.stdout.write(self.style.ERROR(f'Tenant {tenant_code} no encontrado'))
                return
        else:
            tenants = FinancialInstitution.objects.all()
            self.stdout.write(f'Poblando catálogos para {tenants.count()} tenants')
        
        for tenant in tenants:
            self.stdout.write(f'\n📦 Procesando tenant: {tenant.name}')
            with transaction.atomic():
                self.populate_document_types(tenant)
                self.populate_product_types(tenant)
                self.populate_payment_frequencies(tenant)
                self.populate_amortization_systems(tenant)
                self.populate_currencies(tenant)
        
        self.stdout.write(self.style.SUCCESS('\n✅ Catálogos poblados exitosamente'))
    
    def populate_document_types(self, tenant):
        """Poblar tipos de documento."""
        document_types = [
            {
                'code': 'ID_DOCUMENT',
                'name': 'Cédula de Identidad',
                'description': 'Documento de identidad vigente',
                'category': 'IDENTITY',
                'default_formats': ['PDF', 'JPG', 'PNG'],
                'default_max_size_mb': 5.0,
                'default_validity_days': None,
                'icon': 'id-card',
                'display_order': 1,
            },
            {
                'code': 'INCOME_PROOF',
                'name': 'Comprobante de Ingresos',
                'description': 'Boletas de pago o certificado de ingresos',
                'category': 'FINANCIAL',
                'default_formats': ['PDF'],
                'default_max_size_mb': 10.0,
                'default_validity_days': 30,
                'icon': 'file-text',
                'display_order': 2,
            },
            {
                'code': 'BANK_STATEMENT',
                'name': 'Estados de Cuenta Bancarios',
                'description': 'Últimos 3 meses de movimientos bancarios',
                'category': 'FINANCIAL',
                'default_formats': ['PDF'],
                'default_max_size_mb': 15.0,
                'default_validity_days': 90,
                'icon': 'building',
                'display_order': 3,
            },
            {
                'code': 'TAX_RETURN',
                'name': 'Declaración de Impuestos',
                'description': 'Última declaración de impuestos',
                'category': 'FINANCIAL',
                'default_formats': ['PDF'],
                'default_max_size_mb': 10.0,
                'default_validity_days': 365,
                'icon': 'receipt',
                'display_order': 4,
            },
            {
                'code': 'EMPLOYMENT_LETTER',
                'name': 'Carta de Trabajo',
                'description': 'Carta de la empresa certificando relación laboral',
                'category': 'FINANCIAL',
                'default_formats': ['PDF'],
                'default_max_size_mb': 5.0,
                'default_validity_days': 30,
                'icon': 'briefcase',
                'display_order': 5,
            },
            {
                'code': 'PROPERTY_TITLE',
                'name': 'Título de Propiedad',
                'description': 'Folio real o título de propiedad',
                'category': 'COLLATERAL',
                'default_formats': ['PDF'],
                'default_max_size_mb': 20.0,
                'default_validity_days': None,
                'icon': 'home',
                'display_order': 6,
            },
            {
                'code': 'VEHICLE_REGISTRATION',
                'name': 'Registro Vehicular',
                'description': 'RUAT o documento de registro del vehículo',
                'category': 'COLLATERAL',
                'default_formats': ['PDF', 'JPG'],
                'default_max_size_mb': 10.0,
                'default_validity_days': None,
                'icon': 'car',
                'display_order': 7,
            },
        ]
        
        created = 0
        for data in document_types:
            obj, created_flag = DocumentType.objects.get_or_create(
                institution=tenant,
                code=data['code'],
                defaults=data
            )
            if created_flag:
                created += 1
        
        self.stdout.write(f'  ✓ Tipos de documento: {created} creados')
    
    def populate_product_types(self, tenant):
        """Poblar tipos de producto."""
        product_types = [
            {
                'code': 'PERSONAL',
                'name': 'Crédito Personal/Consumo',
                'description': 'Crédito para gastos personales y consumo',
                'category': 'CONSUMER',
                'icon': 'user',
                'color': 'blue',
                'display_order': 1,
            },
            {
                'code': 'VEHICULAR',
                'name': 'Crédito Vehicular',
                'description': 'Crédito para compra de vehículos',
                'category': 'CONSUMER',
                'icon': 'car',
                'color': 'green',
                'display_order': 2,
            },
            {
                'code': 'HIPOTECARIO',
                'name': 'Crédito Hipotecario',
                'description': 'Crédito para compra de vivienda',
                'category': 'MORTGAGE',
                'icon': 'home',
                'color': 'purple',
                'display_order': 3,
            },
            {
                'code': 'PYME',
                'name': 'Crédito PYME',
                'description': 'Crédito para pequeñas y medianas empresas',
                'category': 'COMMERCIAL',
                'icon': 'briefcase',
                'color': 'orange',
                'display_order': 4,
            },
        ]
        
        created = 0
        for data in product_types:
            obj, created_flag = ProductType.objects.get_or_create(
                institution=tenant,
                code=data['code'],
                defaults=data
            )
            if created_flag:
                created += 1
        
        self.stdout.write(f'  ✓ Tipos de producto: {created} creados')
    
    def populate_payment_frequencies(self, tenant):
        """Poblar frecuencias de pago."""
        frequencies = [
            {
                'code': 'MONTHLY',
                'name': 'Mensual',
                'days_between_payments': 30,
                'payments_per_year': 12,
                'display_order': 1,
            },
            {
                'code': 'BIWEEKLY',
                'name': 'Quincenal',
                'days_between_payments': 15,
                'payments_per_year': 24,
                'display_order': 2,
            },
            {
                'code': 'WEEKLY',
                'name': 'Semanal',
                'days_between_payments': 7,
                'payments_per_year': 52,
                'display_order': 3,
            },
        ]
        
        created = 0
        for data in frequencies:
            obj, created_flag = PaymentFrequency.objects.get_or_create(
                institution=tenant,
                code=data['code'],
                defaults=data
            )
            if created_flag:
                created += 1
        
        self.stdout.write(f'  ✓ Frecuencias de pago: {created} creadas')
    
    def populate_amortization_systems(self, tenant):
        """Poblar sistemas de amortización."""
        systems = [
            {
                'code': 'FRENCH',
                'name': 'Sistema Francés (Cuota Fija)',
                'description': 'Cuotas constantes durante todo el plazo',
                'formula_type': 'FRENCH',
                'display_order': 1,
            },
            {
                'code': 'GERMAN',
                'name': 'Sistema Alemán (Cuota Decreciente)',
                'description': 'Amortización constante, cuotas decrecientes',
                'formula_type': 'GERMAN',
                'display_order': 2,
            },
            {
                'code': 'AMERICAN',
                'name': 'Sistema Americano (Solo Intereses)',
                'description': 'Pago de intereses periódicos, capital al final',
                'formula_type': 'AMERICAN',
                'display_order': 3,
            },
        ]
        
        created = 0
        for data in systems:
            obj, created_flag = AmortizationSystem.objects.get_or_create(
                institution=tenant,
                code=data['code'],
                defaults=data
            )
            if created_flag:
                created += 1
        
        self.stdout.write(f'  ✓ Sistemas de amortización: {created} creados')
    
    def populate_currencies(self, tenant):
        """Poblar monedas."""
        currencies = [
            {
                'code': 'BOB',
                'name': 'Boliviano',
                'symbol': 'Bs',
                'exchange_rate_to_base': 1.0000,
                'is_base_currency': True,
                'display_order': 1,
            },
            {
                'code': 'USD',
                'name': 'Dólar Estadounidense',
                'symbol': '$',
                'exchange_rate_to_base': 6.9600,
                'is_base_currency': False,
                'display_order': 2,
            },
        ]
        
        created = 0
        for data in currencies:
            obj, created_flag = Currency.objects.get_or_create(
                institution=tenant,
                code=data['code'],
                defaults=data
            )
            if created_flag:
                created += 1
        
        self.stdout.write(f'  ✓ Monedas: {created} creadas')
