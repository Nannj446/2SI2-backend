"""
Comando para corregir fechas nulas en contratos.

Este comando identifica contratos con fechas nulas y las corrige
usando fechas de la solicitud de crédito o fechas por defecto.

Uso:
    python manage.py fix_contract_dates
    python manage.py fix_contract_dates --dry-run  # Ver qué se cambiaría sin aplicar
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from datetime import timedelta
from api.contracts.models import Contract


class Command(BaseCommand):
    help = 'Corrige fechas nulas en contratos'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Muestra qué contratos se cambiarían sin aplicar los cambios',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        self.stdout.write(self.style.WARNING('=' * 70))
        self.stdout.write(self.style.WARNING('Corrección de Fechas Nulas en Contratos'))
        self.stdout.write(self.style.WARNING('=' * 70))
        self.stdout.write('')
        
        if dry_run:
            self.stdout.write(self.style.NOTICE('🔍 MODO DRY-RUN: No se aplicarán cambios'))
            self.stdout.write('')
        
        # Buscar contratos con fechas nulas
        contracts_with_null_dates = Contract.objects.filter(
            contract_date__isnull=True
        ) | Contract.objects.filter(
            start_date__isnull=True
        ) | Contract.objects.filter(
            end_date__isnull=True
        ) | Contract.objects.filter(
            first_payment_date__isnull=True
        )
        
        contracts_with_null_dates = contracts_with_null_dates.select_related(
            'loan_application',
            'loan_application__client'
        ).distinct()
        
        total_contracts = contracts_with_null_dates.count()
        
        if total_contracts == 0:
            self.stdout.write(self.style.SUCCESS('✅ No hay contratos con fechas nulas'))
            return
        
        self.stdout.write(
            self.style.WARNING(f'📋 Encontrados {total_contracts} contratos con fechas nulas:')
        )
        self.stdout.write('')
        
        # Mostrar contratos a corregir
        contracts_to_fix = []
        for i, contract in enumerate(contracts_with_null_dates, 1):
            client_name = 'N/A'
            if hasattr(contract.loan_application, 'client'):
                client = contract.loan_application.client
                client_name = f"{client.first_name} {client.last_name}"
            
            issues = []
            if contract.contract_date is None:
                issues.append('contract_date')
            if contract.start_date is None:
                issues.append('start_date')
            if contract.end_date is None:
                issues.append('end_date')
            if contract.first_payment_date is None:
                issues.append('first_payment_date')
            
            self.stdout.write(
                f"  {i}. {contract.contract_number} - "
                f"Cliente: {client_name} - "
                f"Fechas nulas: {', '.join(issues)}"
            )
            
            # Calcular fechas de corrección
            fixes = self._calculate_fixes(contract)
            contracts_to_fix.append((contract, fixes))
        
        self.stdout.write('')
        
        if dry_run:
            self.stdout.write(
                self.style.NOTICE(
                    f'🔍 Se corregirían {total_contracts} contratos'
                )
            )
            self.stdout.write('')
            self.stdout.write(self.style.NOTICE('Fechas que se aplicarían:'))
            for contract, fixes in contracts_to_fix[:5]:  # Mostrar solo los primeros 5
                self.stdout.write(f"  • {contract.contract_number}:")
                for field, value in fixes.items():
                    self.stdout.write(f"    - {field}: {value}")
            if total_contracts > 5:
                self.stdout.write(f"  ... y {total_contracts - 5} más")
            self.stdout.write('')
            self.stdout.write(
                self.style.NOTICE('   Ejecuta sin --dry-run para aplicar los cambios')
            )
            return
        
        # Confirmar antes de aplicar cambios
        self.stdout.write(
            self.style.WARNING(
                f'⚠️  Se corregirán {total_contracts} contratos'
            )
        )
        
        # Aplicar cambios
        try:
            with transaction.atomic():
                updated_count = 0
                for contract, fixes in contracts_to_fix:
                    for field, value in fixes.items():
                        setattr(contract, field, value)
                    contract.save()
                    updated_count += 1
                
                self.stdout.write('')
                self.stdout.write(
                    self.style.SUCCESS(
                        f'✅ Se actualizaron {updated_count} contratos exitosamente'
                    )
                )
                self.stdout.write('')
                self.stdout.write(
                    self.style.SUCCESS(
                        '🎉 Las fechas nulas han sido corregidas'
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
    
    def _calculate_fixes(self, contract):
        """
        Calcula las fechas de corrección para un contrato.
        
        Prioridad:
        1. Usar fechas de la solicitud de crédito si están disponibles
        2. Usar fecha de creación del contrato
        3. Usar fecha actual como último recurso
        """
        fixes = {}
        
        # Fecha base: usar created_at del contrato o fecha actual
        base_date = contract.created_at.date() if contract.created_at else timezone.now().date()
        
        # Corregir contract_date
        if contract.contract_date is None:
            # Intentar usar fecha de aprobación de la solicitud
            if hasattr(contract.loan_application, 'approved_at') and contract.loan_application.approved_at:
                fixes['contract_date'] = contract.loan_application.approved_at.date()
            else:
                fixes['contract_date'] = base_date
        
        # Corregir start_date
        if contract.start_date is None:
            # La fecha de inicio suele ser la misma que la fecha del contrato o un día después
            contract_date = fixes.get('contract_date', contract.contract_date or base_date)
            fixes['start_date'] = contract_date
        
        # Corregir end_date
        if contract.end_date is None:
            # Calcular fecha de fin basada en el plazo en meses
            start_date = fixes.get('start_date', contract.start_date or base_date)
            term_months = contract.term_months or 12  # Por defecto 12 meses si no está definido
            # Aproximación: 30 días por mes
            fixes['end_date'] = start_date + timedelta(days=term_months * 30)
        
        # Corregir first_payment_date
        if contract.first_payment_date is None:
            # El primer pago suele ser 30 días después de la fecha de inicio
            start_date = fixes.get('start_date', contract.start_date or base_date)
            fixes['first_payment_date'] = start_date + timedelta(days=30)
        
        return fixes
