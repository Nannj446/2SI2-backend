"""
Comando para crear plantilla de contrato por defecto

Uso:
    python manage.py create_default_contract_template --institution-id=1
"""

from django.core.management.base import BaseCommand
from django.template.loader import render_to_string
from api.contracts.models import ContractTemplate
from api.products.models import CreditProduct
from api.tenants.models import FinancialInstitution


class Command(BaseCommand):
    help = 'Crea una plantilla de contrato por defecto para una institución'

    def add_arguments(self, parser):
        parser.add_argument(
            '--institution-id',
            type=int,
            required=True,
            help='ID de la institución financiera'
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Sobrescribir plantilla existente si ya existe'
        )

    def handle(self, *args, **options):
        institution_id = options['institution_id']
        force = options.get('force', False)

        try:
            institution = FinancialInstitution.objects.get(id=institution_id)
        except FinancialInstitution.DoesNotExist:
            self.stdout.write(
                self.style.ERROR(
                    f'Institución con ID {institution_id} no encontrada'
                )
            )
            return

        # Verificar si ya existe una plantilla por defecto
        existing = ContractTemplate.objects.filter(
            institution=institution,
            is_default=True
        ).first()

        if existing and not force:
            self.stdout.write(
                self.style.WARNING(
                    f'Ya existe una plantilla por defecto para {institution.name}. '
                    f'Use --force para sobrescribir.'
                )
            )
            return

        # Leer plantilla HTML desde archivo
        try:
            with open(
                'api/contracts/templates/contracts/default_contract_template.html',
                'r',
                encoding='utf-8'
            ) as f:
                template_content = f.read()
        except FileNotFoundError:
            self.stdout.write(
                self.style.ERROR(
                    'Archivo de plantilla no encontrado: '
                    'api/contracts/templates/contracts/default_contract_template.html'
                )
            )
            return

        # Variables disponibles
        available_variables = [
            'institution_name',
            'institution_address',
            'institution_nit',
            'institution_phone',
            'institution_email',
            'borrower_name',
            'borrower_document',
            'borrower_address',
            'borrower_email',
            'borrower_phone',
            'contract_number',
            'contract_date',
            'start_date',
            'end_date',
            'principal_amount',
            'principal_amount_raw',
            'interest_rate',
            'interest_rate_raw',
            'term_months',
            'monthly_payment',
            'monthly_payment_raw',
            'total_amount',
            'total_amount_raw',
            'first_payment_date',
            'last_payment_date',
            'product_name',
            'product_description',
        ]

        # Términos y condiciones por defecto
        terms_and_conditions = """
TÉRMINOS Y CONDICIONES GENERALES

1. El presente contrato se rige por las leyes vigentes en el país.
2. Cualquier modificación al presente contrato debe ser acordada por escrito por ambas partes.
3. El prestatario acepta que la institución puede ceder sus derechos sobre este contrato a terceros.
4. En caso de controversia, las partes se someten a la jurisdicción de los tribunales competentes.
5. El prestatario declara que la información proporcionada es veraz y completa.
        """.strip()

        # Cláusulas legales
        legal_clauses = [
            {
                'title': 'Protección de Datos',
                'content': 'El prestatario autoriza el tratamiento de sus datos personales conforme a la ley de protección de datos.'
            },
            {
                'title': 'Reporte a Centrales de Riesgo',
                'content': 'La institución reportará el comportamiento de pago a las centrales de riesgo crediticio.'
            },
        ]

        # Buscar un producto existente para asociar la plantilla
        product = CreditProduct.objects.filter(institution=institution).first()
        if not product:
            self.stdout.write(
                self.style.ERROR(
                    f'La institucion {institution.name} no tiene productos. '
                    f'Cree un producto primero o ejecute populate_tenant_data.'
                )
            )
            return

        if existing and force:
            # Actualizar plantilla existente
            existing.template_content = template_content
            existing.available_variables = available_variables
            existing.terms_and_conditions = terms_and_conditions
            existing.legal_clauses = legal_clauses
            existing.save()

            self.stdout.write(
                self.style.SUCCESS(
                    f'Plantilla por defecto actualizada para {institution.name}'
                )
            )
        else:
            # Crear nueva plantilla
            template = ContractTemplate.objects.create(
                institution=institution,
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
                description='Plantilla estandar para creditos generales',
                version='1.0'
            )

            self.stdout.write(
                self.style.SUCCESS(
                    f'Plantilla por defecto creada exitosamente para {institution.name} '
                    f'(ID: {template.id})'
                )
            )
