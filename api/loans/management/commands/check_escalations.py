"""
Comando de Django para verificar y escalar etapas vencidas.

Uso:
    python manage.py check_escalations
    python manage.py check_escalations --institution-id=1
    python manage.py check_escalations --dry-run

Este comando puede ejecutarse:
1. Manualmente desde la línea de comandos
2. Como tarea programada (cron)
3. Como tarea de Celery periódica
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from api.loans.services.escalation_service import EscalationService


class Command(BaseCommand):
    help = 'Verifica y escala automáticamente etapas de workflow que han excedido su SLA'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--institution-id',
            type=int,
            help='ID de institución para filtrar (opcional)',
        )
        
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Simula la ejecución sin realizar cambios',
        )
    
    def handle(self, *args, **options):
        institution_id = options.get('institution_id')
        dry_run = options.get('dry_run', False)
        
        self.stdout.write(
            self.style.SUCCESS(
                f'\n{"="*60}\n'
                f'Verificación de Escalamientos - {timezone.now().strftime("%Y-%m-%d %H:%M:%S")}\n'
                f'{"="*60}\n'
            )
        )
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING('MODO DRY-RUN: No se realizarán cambios\n')
            )
        
        if institution_id:
            self.stdout.write(f'Filtrando por institución ID: {institution_id}\n')
        
        try:
            if dry_run:
                # Solo obtener las etapas que se escalarían
                from api.loans.services.workflow_engine import WorkflowEngine
                
                overdue_stages = WorkflowEngine.check_escalations(institution_id)
                
                self.stdout.write(
                    self.style.SUCCESS(
                        f'\nSe encontraron {len(overdue_stages)} etapas para escalar:\n'
                    )
                )
                
                for stage_execution in overdue_stages:
                    loan_app = stage_execution.workflow_execution.loan_application
                    time_overdue = (
                        timezone.now() - stage_execution.entered_at
                    ).total_seconds() / 3600 - stage_execution.stage_definition.time_limit_hours
                    
                    self.stdout.write(
                        f'  - Solicitud: {loan_app.application_number}\n'
                        f'    Etapa: {stage_execution.stage_definition.stage_name}\n'
                        f'    Tiempo excedido: {time_overdue:.2f} horas\n'
                        f'    SLA: {stage_execution.stage_definition.time_limit_hours}h\n'
                    )
                
                result = {
                    'total_checked': len(overdue_stages),
                    'escalated_count': 0,
                    'failed_count': 0,
                    'escalated_stages': []
                }
            else:
                # Ejecutar escalamiento real
                result = EscalationService.check_and_escalate_all(institution_id)
            
            # Mostrar resultados
            self.stdout.write(
                self.style.SUCCESS(
                    f'\n{"="*60}\n'
                    f'RESULTADOS:\n'
                    f'{"="*60}\n'
                    f'Total revisadas: {result["total_checked"]}\n'
                    f'Escaladas exitosamente: {result["escalated_count"]}\n'
                    f'Fallidas: {result["failed_count"]}\n'
                )
            )
            
            if result['escalated_stages']:
                self.stdout.write(
                    self.style.SUCCESS('\nEtapas escaladas:\n')
                )
                
                for stage_info in result['escalated_stages']:
                    self.stdout.write(
                        f'  ✓ Solicitud: {stage_info["application_number"]}\n'
                        f'    Etapa: {stage_info["stage_name"]}\n'
                        f'    Tiempo excedido: {stage_info["time_overdue_hours"]}h\n'
                    )
            
            if result['escalated_count'] > 0:
                self.stdout.write(
                    self.style.SUCCESS(
                        f'\n✓ Escalamiento completado exitosamente\n'
                    )
                )
            elif result['total_checked'] == 0:
                self.stdout.write(
                    self.style.SUCCESS(
                        f'\n✓ No hay etapas que requieran escalamiento\n'
                    )
                )
            else:
                self.stdout.write(
                    self.style.WARNING(
                        f'\n⚠ Se encontraron etapas pero no se escalaron\n'
                    )
                )
        
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(
                    f'\n✗ Error durante la verificación: {str(e)}\n'
                )
            )
            raise
