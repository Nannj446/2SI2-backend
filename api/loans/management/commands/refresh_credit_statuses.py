"""
Management command: Refrescar el estado de todos los créditos activos.

Uso:
    python manage.py refresh_credit_statuses
    python manage.py refresh_credit_statuses --institution-id=5
"""

from django.core.management.base import BaseCommand, CommandError
from api.loans.services.credit_status_service import CreditStatusService


class Command(BaseCommand):
    help = 'Refresca el estado de todos los créditos activos según reglas de negocio'

    def add_arguments(self, parser):
        parser.add_argument(
            '--institution-id',
            type=int,
            help='ID de la institución financiera (opcional, para ejecutar sobre un tenant específico)',
        )

    def handle(self, *args, **options):
        institution_id = options.get('institution_id')
        institution = None

        if institution_id:
            from api.tenants.models import FinancialInstitution
            try:
                institution = FinancialInstitution.objects.get(pk=institution_id)
            except FinancialInstitution.DoesNotExist:
                raise CommandError(f'Institución con ID {institution_id} no encontrada')

        self.stdout.write('Iniciando refresco de estados de créditos activos...')

        if institution:
            self.stdout.write(f'  Institución: {institution.name} (ID: {institution.id})')
        else:
            self.stdout.write('  Todas las instituciones')

        count = CreditStatusService.refresh_all_active_credits(institution=institution)

        self.stdout.write(self.style.SUCCESS(f'{count} créditos actualizados'))
        self.stdout.write('Refresco completado.')
