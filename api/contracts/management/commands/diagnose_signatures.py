"""
Comando para diagnosticar firmas de contratos y detectar problemas.

Este comando revisa todas las firmas de contratos y detecta:
- Firmas marcadas como INSTITUTION que deberían ser BORROWER
- Firmas con usuarios incorrectos
- Inconsistencias en los datos de firma
"""

from django.core.management.base import BaseCommand
from django.db.models import Q
from api.contracts.models import Contract, ContractSignature
from api.clients.models import Client


class Command(BaseCommand):
    help = 'Diagnostica firmas de contratos y detecta problemas'

    def add_arguments(self, parser):
        parser.add_argument(
            '--fix',
            action='store_true',
            help='Corregir automáticamente las firmas incorrectas',
        )
        parser.add_argument(
            '--contract-id',
            type=int,
            help='Diagnosticar solo un contrato específico',
        )

    def handle(self, *args, **options):
        fix_mode = options['fix']
        contract_id = options.get('contract_id')
        
        self.stdout.write(self.style.WARNING('=' * 80))
        self.stdout.write(self.style.WARNING('DIAGNÓSTICO DE FIRMAS DE CONTRATOS'))
        self.stdout.write(self.style.WARNING('=' * 80))
        self.stdout.write('')
        
        # Filtrar contratos
        if contract_id:
            contracts = Contract.objects.filter(id=contract_id)
            if not contracts.exists():
                self.stdout.write(self.style.ERROR(f'Contrato {contract_id} no encontrado'))
                return
        else:
            contracts = Contract.objects.all()
        
        total_contracts = contracts.count()
        self.stdout.write(f'Analizando {total_contracts} contratos...\n')
        
        problems_found = 0
        problems_fixed = 0
        
        for contract in contracts:
            contract_problems = []
            
            # Obtener el usuario del cliente
            try:
                client_user = contract.loan_application.client.user
            except Exception as e:
                contract_problems.append(f'Error al obtener usuario del cliente: {e}')
                client_user = None
            
            # Revisar firmas del contrato
            signatures = contract.signatures.all()
            
            for signature in signatures:
                # Problema 1: Firma marcada como INSTITUTION pero el usuario es el cliente
                if signature.signer_type == ContractSignature.SignerType.INSTITUTION:
                    if client_user and signature.user == client_user:
                        problem = (
                            f'Firma ID {signature.id}: Marcada como INSTITUTION pero '
                            f'el usuario {signature.user.email} es el cliente del contrato'
                        )
                        contract_problems.append(problem)
                        
                        if fix_mode:
                            # Corregir: cambiar tipo a BORROWER
                            signature.signer_type = ContractSignature.SignerType.BORROWER
                            signature.save(update_fields=['signer_type'])
                            contract_problems.append('  ✓ CORREGIDO: Cambiado a BORROWER')
                            problems_fixed += 1
                
                # Problema 2: Firma marcada como BORROWER pero el usuario NO es el cliente
                if signature.signer_type == ContractSignature.SignerType.BORROWER:
                    if client_user and signature.user != client_user:
                        problem = (
                            f'Firma ID {signature.id}: Marcada como BORROWER pero '
                            f'el usuario {signature.user.email} NO es el cliente '
                            f'(cliente: {client_user.email})'
                        )
                        contract_problems.append(problem)
                
                # Problema 3: Firma de BORROWER sin usuario
                if signature.signer_type == ContractSignature.SignerType.BORROWER:
                    if not signature.user:
                        problem = f'Firma ID {signature.id}: BORROWER sin usuario asociado'
                        contract_problems.append(problem)
                
                # Problema 4: Firma de GUARANTOR sin garante
                if signature.signer_type == ContractSignature.SignerType.GUARANTOR:
                    if not signature.guarantor:
                        problem = f'Firma ID {signature.id}: GUARANTOR sin garante asociado'
                        contract_problems.append(problem)
            
            # Problema 5: Contrato marcado como firmado por prestatario pero sin firma BORROWER
            if contract.is_signed_by_borrower:
                borrower_signatures = signatures.filter(
                    signer_type=ContractSignature.SignerType.BORROWER
                )
                if not borrower_signatures.exists():
                    problem = (
                        'Contrato marcado como firmado por prestatario '
                        '(borrower_signed_at no es NULL) pero no hay firma de tipo BORROWER'
                    )
                    contract_problems.append(problem)
            
            # Mostrar problemas encontrados
            if contract_problems:
                problems_found += len(contract_problems)
                self.stdout.write(self.style.ERROR(f'\n❌ Contrato {contract.contract_number} (ID: {contract.id})'))
                self.stdout.write(f'   Cliente: {contract.loan_application.client.user.email if client_user else "N/A"}')
                self.stdout.write(f'   Estado: {contract.status}')
                self.stdout.write(f'   Firmado por prestatario: {contract.is_signed_by_borrower}')
                self.stdout.write('')
                
                for problem in contract_problems:
                    if '✓ CORREGIDO' in problem:
                        self.stdout.write(self.style.SUCCESS(f'   {problem}'))
                    else:
                        self.stdout.write(f'   • {problem}')
        
        # Resumen
        self.stdout.write('')
        self.stdout.write(self.style.WARNING('=' * 80))
        self.stdout.write(self.style.WARNING('RESUMEN'))
        self.stdout.write(self.style.WARNING('=' * 80))
        self.stdout.write(f'Contratos analizados: {total_contracts}')
        self.stdout.write(f'Problemas encontrados: {problems_found}')
        
        if fix_mode:
            self.stdout.write(self.style.SUCCESS(f'Problemas corregidos: {problems_fixed}'))
        else:
            if problems_found > 0:
                self.stdout.write('')
                self.stdout.write(self.style.WARNING('Para corregir automáticamente, ejecute:'))
                self.stdout.write(self.style.WARNING('python manage.py diagnose_signatures --fix'))
        
        self.stdout.write('')
