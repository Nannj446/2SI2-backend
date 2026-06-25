"""
Comando para corregir estados de contratos que están ACTIVE sin firmas.

Este comando cambia contratos en estado ACTIVE que no tienen firmas
al estado correcto PENDING_SIGNATURE.

Uso:
    python manage.py fix_contract_states
    python manage.py fix_contract_states --dry-run  # Ver qué se cambiaría sin aplicar
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from api.contracts.models import Contract


class Command(BaseCommand):
    help = 'Corrige estados de contratos ACTIVE sin firmas a PENDING_SIGNATURE'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Muestra qué contratos se cambiarían sin aplicar los cambios',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        self.stdout.write(self.style.WARNING('=' * 70))
        self.stdout.write(self.style.WARNING('Corrección de Estados de Contratos'))
        self.stdout.write(self.style.WARNING('=' * 70))
        self.stdout.write('')
        
        if dry_run:
            self.stdout.write(self.style.NOTICE('🔍 MODO DRY-RUN: No se aplicarán cambios'))
            self.stdout.write('')
        
        # Buscar contratos ACTIVE sin firmas
        contracts_to_fix = Contract.objects.filter(
            status=Contract.Status.ACTIVE,
            borrower_signed_at__isnull=True
        ).select_related(
            'loan_application',
            'loan_application__client'
        )
        
        total_contracts = contracts_to_fix.count()
        
        if total_contracts == 0:
            self.stdout.write(self.style.SUCCESS('✅ No hay contratos que necesiten corrección'))
            return
        
        self.stdout.write(
            self.style.WARNING(f'📋 Encontrados {total_contracts} contratos que necesitan corrección:')
        )
        self.stdout.write('')
        
        # Mostrar contratos a corregir
        for i, contract in enumerate(contracts_to_fix, 1):
            client_name = 'N/A'
            if hasattr(contract.loan_application, 'client'):
                client = contract.loan_application.client
                client_name = f"{client.first_name} {client.last_name}"
            
            self.stdout.write(
                f"  {i}. {contract.contract_number} - "
                f"Cliente: {client_name} - "
                f"Monto: Bs. {contract.principal_amount:,.2f}"
            )
        
        self.stdout.write('')
        
        if dry_run:
            self.stdout.write(
                self.style.NOTICE(
                    f'🔍 Se cambiarían {total_contracts} contratos de ACTIVE → PENDING_SIGNATURE'
                )
            )
            self.stdout.write(
                self.style.NOTICE('   Ejecuta sin --dry-run para aplicar los cambios')
            )
            return
        
        # Confirmar antes de aplicar cambios
        self.stdout.write(
            self.style.WARNING(
                f'⚠️  Se cambiarán {total_contracts} contratos de ACTIVE → PENDING_SIGNATURE'
            )
        )
        
        # Aplicar cambios
        try:
            with transaction.atomic():
                updated_count = contracts_to_fix.update(status=Contract.Status.PENDING_SIGNATURE)
                
                self.stdout.write('')
                self.stdout.write(
                    self.style.SUCCESS(
                        f'✅ Se actualizaron {updated_count} contratos exitosamente'
                    )
                )
                self.stdout.write('')
                self.stdout.write(self.style.SUCCESS('Cambios aplicados:'))
                self.stdout.write(f'  • Estado: ACTIVE → PENDING_SIGNATURE')
                self.stdout.write(f'  • Contratos afectados: {updated_count}')
                self.stdout.write('')
                self.stdout.write(
                    self.style.SUCCESS(
                        '🎉 Los contratos ahora pueden ser firmados correctamente'
                    )
                )
                
        except Exception as e:
            self.stdout.write('')
            self.stdout.write(
                self.style.ERROR(f'❌ Error al actualizar contratos: {str(e)}')
            )
            raise
        
        self.stdout.write('')
        self.stdout.write(self.style.WARNING('=' * 70))
