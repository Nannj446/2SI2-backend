"""
Comando para crear motivos de rechazo iniciales.

SP3-99: Aprobación o Rechazo de Créditos
"""

from django.core.management.base import BaseCommand
from api.loans.models_rejection import RejectionReason
from api.tenants.models import FinancialInstitution


class Command(BaseCommand):
    help = 'Crea motivos de rechazo iniciales para todas las instituciones'

    def handle(self, *args, **options):
        institutions = FinancialInstitution.objects.all()
        
        if not institutions.exists():
            self.stdout.write(
                self.style.WARNING('No hay instituciones en el sistema')
            )
            return
        
        reasons = [
            {
                'code': 'INSUFFICIENT_INCOME',
                'name': 'Ingresos Insuficientes',
                'description': 'Los ingresos del solicitante no son suficientes para el monto solicitado',
                'category': 'FINANCIAL',
                'display_order': 1,
                'requires_notes': False
            },
            {
                'code': 'HIGH_DEBT_RATIO',
                'name': 'Alto Ratio de Endeudamiento',
                'description': 'El ratio deuda/ingreso excede los límites permitidos',
                'category': 'FINANCIAL',
                'display_order': 2,
                'requires_notes': False
            },
            {
                'code': 'POOR_CREDIT_HISTORY',
                'name': 'Historial Crediticio Negativo',
                'description': 'El historial crediticio presenta morosidad o incumplimientos',
                'category': 'CREDIT_HISTORY',
                'display_order': 3,
                'requires_notes': False
            },
            {
                'code': 'LOW_CREDIT_SCORE',
                'name': 'Score Crediticio Bajo',
                'description': 'El score crediticio está por debajo del mínimo requerido',
                'category': 'CREDIT_HISTORY',
                'display_order': 4,
                'requires_notes': False
            },
            {
                'code': 'INCOMPLETE_DOCUMENTATION',
                'name': 'Documentación Incompleta',
                'description': 'Faltan documentos obligatorios o están incompletos',
                'category': 'DOCUMENTATION',
                'display_order': 5,
                'requires_notes': True
            },
            {
                'code': 'INVALID_DOCUMENTATION',
                'name': 'Documentación Inválida',
                'description': 'Los documentos presentados no son válidos o están vencidos',
                'category': 'DOCUMENTATION',
                'display_order': 6,
                'requires_notes': True
            },
            {
                'code': 'POLICY_VIOLATION',
                'name': 'Violación de Política',
                'description': 'La solicitud no cumple con las políticas de crédito',
                'category': 'POLICY',
                'display_order': 7,
                'requires_notes': True
            },
            {
                'code': 'HIGH_RISK_PROFILE',
                'name': 'Perfil de Alto Riesgo',
                'description': 'El perfil del solicitante presenta alto riesgo',
                'category': 'RISK',
                'display_order': 8,
                'requires_notes': False
            },
            {
                'code': 'FRAUDULENT_INFORMATION',
                'name': 'Información Fraudulenta',
                'description': 'Se detectó información falsa o fraudulenta',
                'category': 'RISK',
                'display_order': 9,
                'requires_notes': True
            },
            {
                'code': 'OTHER',
                'name': 'Otro Motivo',
                'description': 'Otro motivo no especificado',
                'category': 'OTHER',
                'display_order': 10,
                'requires_notes': True
            },
        ]
        
        created_count = 0
        existing_count = 0
        
        for institution in institutions:
            self.stdout.write(f'\nProcesando institución: {institution.name}')
            
            for reason_data in reasons:
                reason, created = RejectionReason.objects.get_or_create(
                    institution=institution,
                    code=reason_data['code'],
                    defaults=reason_data
                )
                
                if created:
                    created_count += 1
                    self.stdout.write(
                        self.style.SUCCESS(f'  ✓ Creado: {reason.name}')
                    )
                else:
                    existing_count += 1
                    self.stdout.write(
                        self.style.WARNING(f'  - Ya existe: {reason.name}')
                    )
        
        self.stdout.write('\n' + '='*50)
        self.stdout.write(
            self.style.SUCCESS(
                f'\n✓ Proceso completado:'
                f'\n  - Instituciones procesadas: {institutions.count()}'
                f'\n  - Motivos creados: {created_count}'
                f'\n  - Motivos existentes: {existing_count}'
            )
        )
