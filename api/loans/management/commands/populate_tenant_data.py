"""
Comando para poblar datos iniciales por tenant:
- Plantillas de contrato por defecto
- Aseguradoras
- Seguros (catálogo)

Uso:
    python manage.py populate_tenant_data
    python manage.py populate_tenant_data --tenant=nombre-del-tenant
    python manage.py populate_tenant_data --dry-run
"""

from pathlib import Path

from django.core.management.base import BaseCommand
from django.db import transaction

from api.tenants.models import FinancialInstitution


class Command(BaseCommand):
    help = 'Pobla datos iniciales para tenants: contratos, aseguradoras y seguros'

    def add_arguments(self, parser):
        parser.add_argument(
            '--tenant',
            type=str,
            help='Slug del tenant específico (opcional)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Solo muestra lo que se crearía sin aplicar cambios'
        )
        parser.add_argument(
            '--skip-contracts',
            action='store_true',
            help='Saltar creación de plantillas de contrato'
        )
        parser.add_argument(
            '--skip-insurers',
            action='store_true',
            help='Saltar creación de aseguradoras'
        )
        parser.add_argument(
            '--skip-insurances',
            action='store_true',
            help='Saltar creación de seguros'
        )

    def handle(self, *args, **options):
        tenant_slug = options.get('tenant')
        dry_run = options['dry_run']
        skip_contracts = options['skip_contracts']
        skip_insurers = options['skip_insurers']
        skip_insurances = options['skip_insurances']

        if tenant_slug:
            try:
                tenants = [FinancialInstitution.objects.get(slug=tenant_slug)]
            except FinancialInstitution.DoesNotExist:
                self.stdout.write(self.style.ERROR(
                    f'Tenant "{tenant_slug}" no encontrado'
                ))
                return
        else:
            tenants = list(FinancialInstitution.objects.all())

        mode = 'DRY RUN - ' if dry_run else ''
        self.stdout.write(f'{mode}Poblando datos para {len(tenants)} tenant(s)')

        for tenant in tenants:
            self.stdout.write(f'\n--- Tenant: {tenant.name} (slug: {tenant.slug}) ---')

            try:
                with transaction.atomic():
                    if not skip_contracts:
                        self._create_contract_template(tenant, dry_run)
                    if not skip_insurers:
                        self._create_insurers(tenant, dry_run)
                    if not skip_insurances:
                        self._create_insurances(tenant, dry_run)

                    if dry_run:
                        transaction.set_rollback(True)
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'  [ERROR] {e}'))

        self.stdout.write(self.style.SUCCESS(f'\n{">>> Proceso completado <<<"}'))

    # ─── CONTRACT TEMPLATE ────────────────────────────────────────────

    def _create_contract_template(self, tenant, dry_run):
        from api.contracts.models import ContractTemplate
        from api.products.models import CreditProduct

        if ContractTemplate.objects.filter(
            institution=tenant, is_default=True
        ).exists():
            self.stdout.write('  Contrato: ya tiene plantilla por defecto')
            return

        product = CreditProduct.objects.filter(institution=tenant).first()
        if not product:
            self.stdout.write('  Contrato: no hay productos, no se puede crear plantilla')
            return

        template_path = (
            Path(__file__).resolve().parents[4]
            / 'api' / 'contracts' / 'templates' / 'contracts'
            / 'default_contract_template.html'
        )

        try:
            template_content = template_path.read_text(encoding='utf-8')
        except FileNotFoundError:
            self.stdout.write('  ! Contrato: archivo de plantilla HTML no encontrado, saltando')
            return

        available_variables = [
            'institution_name', 'institution_address', 'institution_nit',
            'institution_phone', 'institution_email',
            'borrower_name', 'borrower_document', 'borrower_address',
            'borrower_email', 'borrower_phone',
            'contract_number', 'contract_date', 'start_date', 'end_date',
            'principal_amount', 'principal_amount_raw',
            'interest_rate', 'interest_rate_raw',
            'term_months', 'monthly_payment', 'monthly_payment_raw',
            'total_amount', 'total_amount_raw',
            'first_payment_date', 'last_payment_date',
            'product_name', 'product_description',
        ]

        terms_and_conditions = (
            'TÉRMINOS Y CONDICIONES GENERALES\n\n'
            '1. El presente contrato se rige por las leyes vigentes.\n'
            '2. Cualquier modificación debe ser acordada por escrito.\n'
            '3. La institución puede ceder sus derechos sobre este contrato.\n'
            '4. Las partes se someten a la jurisdicción de los tribunales competentes.\n'
            '5. El prestatario declara que la información proporcionada es veraz.'
        )

        legal_clauses = [
            {
                'title': 'Protección de Datos',
                'content': 'El prestatario autoriza el tratamiento de sus datos personales.'
            },
            {
                'title': 'Reporte a Centrales de Riesgo',
                'content': 'La institución reportará el comportamiento de pago a centrales de riesgo.'
            },
        ]

        if dry_run:
            self.stdout.write('  [DRY] Contrato: se crearia plantilla por defecto')
            return

        ContractTemplate.objects.create(
            institution=tenant,
            product=product,
            name='Plantilla de Contrato Estandar',
            code='DEFAULT_TEMPLATE',
            template_content=template_content,
            available_variables=available_variables,
            is_active=True,
            is_default=True,
            requires_guarantor_signature=False,
            terms_and_conditions=terms_and_conditions,
            legal_clauses=legal_clauses,
            description='Plantilla estándar para créditos generales',
            version='1.0',
        )
        self.stdout.write('  Contrato: plantilla por defecto creada')

    # ─── INSURERS ─────────────────────────────────────────────────────

    def _create_insurers(self, tenant, dry_run):
        from api.insurances.models import Insurer

        insurers_data = [
            {
                'name': 'Seguros Bolívar',
                'code': 'SEG_BOLIVAR',
                'nit': '1000000001',
                'phone': '800-10-1000',
                'email': 'info@segurosbolivar.com',
            },
            {
                'name': 'La Vitalicia Seguros',
                'code': 'LA_VITALICIA',
                'nit': '1000000002',
                'phone': '800-10-2000',
                'email': 'contacto@lavitalicia.com',
            },
            {
                'name': 'BNB Seguros',
                'code': 'BNB_SEGUROS',
                'nit': '1000000003',
                'phone': '800-10-3000',
                'email': 'seguros@bnb.com.bo',
            },
            {
                'name': 'Fortaleza Seguros',
                'code': 'FORTALEZA',
                'nit': '1000000004',
                'phone': '800-10-4000',
                'email': 'atencion@fortaleza.bo',
            },
            {
                'name': 'Protección Familiar',
                'code': 'PROTECCION_FAMILIAR',
                'nit': '1000000005',
                'phone': '800-10-5000',
                'email': 'info@proteccionfamiliar.bo',
            },
        ]

        existing_codes = set(
            Insurer.objects.filter(institution=tenant).values_list('code', flat=True)
        )

        created = 0
        for data in insurers_data:
            if data['code'] in existing_codes:
                continue
            if dry_run:
                created += 1
                continue
            Insurer.objects.create(institution=tenant, **data)

        if dry_run and created:
            self.stdout.write(f'  [DRY] Aseguradoras: {created} se crearian')
        elif created:
            self.stdout.write(f'  Aseguradoras: {created} creadas')
        else:
            self.stdout.write('  Aseguradoras: ya existian')

    # ─── INSURANCES ───────────────────────────────────────────────────

    def _create_insurances(self, tenant, dry_run):
        from api.insurances.models import Insurance, Insurer

        insurers = list(Insurer.objects.filter(institution=tenant))
        if not insurers:
            self.stdout.write(self.style.WARNING(
                '  ! Seguros: no hay aseguradoras, ejecute sin --skip-insurers primero'
            ))
            return

        default_insurer = insurers[0]
        # Intentar usar una aseguradora específica como default
        for insurer in insurers:
            if insurer.code == 'LA_VITALICIA':
                default_insurer = insurer
                break

        insurances_data = [
            {
                'name': 'Seguro de Desgravamen',
                'code': 'SEG_DESGRAVAMEN',
                'insurance_type': 'DESGRAVAMEN',
                'description': 'Cubre el saldo del crédito en caso de fallecimiento del titular.',
                'insurer_code': 'LA_VITALICIA',
                'is_mandatory': True,
                'coverage_type': 'PORCENTAJE_SALDO',
                'coverage_value': 100.0000,
                'max_coverage_amount': 500_000.00,
                'min_term_months': 1,
                'max_term_months': 360,
                'is_renewable': True,
                'grace_period_days': 30,
                'premium_type': 'BALANCE',
                'base_premium': 0.0500,
                'requires_medical_exam': False,
                'has_deductible': False,
            },
            {
                'name': 'Seguro de Vida',
                'code': 'SEG_VIDA',
                'insurance_type': 'VIDA',
                'description': 'Cobertura de vida para el titular del crédito.',
                'insurer_code': 'LA_VITALICIA',
                'is_mandatory': False,
                'coverage_type': 'MONTO_FIJO',
                'coverage_value': 100_000.00,
                'max_coverage_amount': 1_000_000.00,
                'min_term_months': 12,
                'max_term_months': 360,
                'is_renewable': True,
                'grace_period_days': 30,
                'premium_type': 'MONTHLY',
                'base_premium': 0.1500,
                'requires_medical_exam': True,
                'has_deductible': False,
            },
            {
                'name': 'Seguro de Incendio',
                'code': 'SEG_INCENDIO',
                'insurance_type': 'INCENDIO',
                'description': 'Cubre daños por incendio en bienes hipotecados.',
                'insurer_code': 'BNB_SEGUROS',
                'is_mandatory': False,
                'coverage_type': 'PORCENTAJE_MONTO',
                'coverage_value': 80.0000,
                'max_coverage_amount': 2_000_000.00,
                'min_term_months': 12,
                'max_term_months': 360,
                'is_renewable': True,
                'grace_period_days': 30,
                'premium_type': 'ANNUAL',
                'base_premium': 0.2500,
                'requires_medical_exam': False,
                'has_deductible': True,
                'deductible_percentage': 10.00,
            },
            {
                'name': 'Seguro Vehicular',
                'code': 'SEG_VEHICULAR',
                'insurance_type': 'VEHICULAR',
                'description': 'Cubre daños y robo del vehículo financiado.',
                'insurer_code': 'SEG_BOLIVAR',
                'is_mandatory': True,
                'coverage_type': 'PORCENTAJE_MONTO',
                'coverage_value': 90.0000,
                'max_coverage_amount': 500_000.00,
                'min_term_months': 12,
                'max_term_months': 120,
                'is_renewable': True,
                'grace_period_days': 15,
                'premium_type': 'ANNUAL',
                'base_premium': 3.5000,
                'requires_medical_exam': False,
                'has_deductible': True,
                'deductible_percentage': 15.00,
            },
            {
                'name': 'Seguro Hipotecario',
                'code': 'SEG_HIPOTECARIO',
                'insurance_type': 'HIPOTECARIO',
                'description': 'Cubre el inmueble hipotecado contra riesgos estructurales.',
                'insurer_code': 'BNB_SEGUROS',
                'is_mandatory': True,
                'coverage_type': 'PORCENTAJE_MONTO',
                'coverage_value': 100.0000,
                'max_coverage_amount': 3_000_000.00,
                'min_term_months': 60,
                'max_term_months': 360,
                'is_renewable': True,
                'grace_period_days': 30,
                'premium_type': 'ANNUAL',
                'base_premium': 0.3500,
                'requires_medical_exam': False,
                'has_deductible': True,
                'deductible_percentage': 5.00,
            },
            {
                'name': 'Seguro Agrícola',
                'code': 'SEG_AGRICOLA',
                'insurance_type': 'AGRICOLA',
                'description': 'Cubre pérdidas por fenómenos climáticos en créditos agropecuarios.',
                'insurer_code': 'FORTALEZA',
                'is_mandatory': False,
                'coverage_type': 'PORCENTAJE_MONTO',
                'coverage_value': 70.0000,
                'max_coverage_amount': 1_000_000.00,
                'min_term_months': 6,
                'max_term_months': 60,
                'is_renewable': True,
                'grace_period_days': 30,
                'premium_type': 'ANNUAL',
                'base_premium': 2.0000,
                'requires_medical_exam': False,
                'has_deductible': True,
                'deductible_percentage': 20.00,
            },
        ]

        # Mapa de código de aseguradora a instancia
        insurer_by_code = {i.code: i for i in insurers}

        existing_codes = set(
            Insurance.objects.filter(institution=tenant).values_list('code', flat=True)
        )

        created = 0
        for data in insurances_data:
            if data['code'] in existing_codes:
                continue

            insurer_code = data.pop('insurer_code')
            insurer = insurer_by_code.get(insurer_code, default_insurer)

            if dry_run:
                created += 1
                continue

            Insurance.objects.create(
                institution=tenant,
                insurer=insurer,
                **data,
            )

        if dry_run and created:
            self.stdout.write(f'  [DRY] Seguros: {created} se crearian')
        elif created:
            self.stdout.write(f'  Seguros: {created} creados')
        else:
            self.stdout.write('  Seguros: ya existian')
