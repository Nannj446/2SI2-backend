"""
Comando para procesar solicitudes atascadas que deberían haber avanzado automáticamente.

Uso:
    python manage.py process_stuck_applications --check
    python manage.py process_stuck_applications --process
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from api.loans.models import LoanApplication
from api.loans.services.workflow_service import WorkflowService


class Command(BaseCommand):
    help = 'Procesa solicitudes atascadas que deberían avanzar automáticamente'

    def add_arguments(self, parser):
        parser.add_argument(
            '--check',
            action='store_true',
            help='Solo verificar solicitudes atascadas sin procesarlas',
        )
        parser.add_argument(
            '--process',
            action='store_true',
            help='Procesar solicitudes atascadas',
        )
        parser.add_argument(
            '--app-id',
            type=int,
            help='ID específico de solicitud a procesar',
        )

    def handle(self, *args, **options):
        check_only = options['check']
        process = options['process']
        app_id = options.get('app_id')

        if not check_only and not process:
            self.stdout.write(
                self.style.WARNING(
                    'Debes especificar --check o --process'
                )
            )
            return

        self.stdout.write(
            self.style.SUCCESS(
                f'\n{"="*70}\n'
                f'Buscando solicitudes atascadas\n'
                f'{"="*70}\n'
            )
        )

        # Obtener solicitudes
        if app_id:
            applications = LoanApplication.objects.filter(id=app_id)
        else:
            # Buscar solicitudes en estados intermedios (no finales)
            applications = LoanApplication.objects.exclude(
                status__in=['APPROVED', 'REJECTED', 'DISBURSED', 'CANCELLED', 'DRAFT']
            )

        if not applications.exists():
            self.stdout.write(
                self.style.WARNING('No se encontraron solicitudes para procesar')
            )
            return

        self.stdout.write(f'Analizando {applications.count()} solicitud(es)...\n')

        stuck_count = 0
        processed_count = 0
        error_count = 0

        for app in applications:
            self.stdout.write(
                f'\n📋 Solicitud #{app.id} - {app.client.get_full_name() if app.client else "Sin cliente"}'
            )
            self.stdout.write(f'   Estado actual: {app.status} ({app.get_status_display()})')
            self.stdout.write(f'   Institución: {app.institution.name}')

            # Verificar si está atascada
            is_stuck, reason = self._check_if_stuck(app)

            if is_stuck:
                stuck_count += 1
                self.stdout.write(
                    self.style.WARNING(f'   ⚠️  ATASCADA: {reason}')
                )

                if process:
                    self.stdout.write('   🔧 Procesando...')
                    success, message = self._process_application(app)
                    
                    if success:
                        processed_count += 1
                        self.stdout.write(
                            self.style.SUCCESS(f'   ✅ {message}')
                        )
                    else:
                        error_count += 1
                        self.stdout.write(
                            self.style.ERROR(f'   ❌ {message}')
                        )
            else:
                self.stdout.write(
                    self.style.SUCCESS('   ✅ No está atascada')
                )

        # Resumen
        self.stdout.write(
            self.style.SUCCESS(
                f'\n{"="*70}\n'
                f'Resumen:\n'
                f'  - Total analizadas: {applications.count()}\n'
                f'  - Atascadas encontradas: {stuck_count}\n'
            )
        )

        if process:
            self.stdout.write(
                f'  - Procesadas exitosamente: {processed_count}\n'
                f'  - Errores: {error_count}\n'
            )
        elif stuck_count > 0:
            self.stdout.write(
                self.style.WARNING(
                    f'\nEjecuta con --process para procesar las solicitudes atascadas'
                )
            )

        self.stdout.write(f'{"="*70}\n')

    def _check_if_stuck(self, app):
        """
        Verifica si una solicitud está atascada.
        
        Returns:
            tuple: (is_stuck: bool, reason: str)
        """
        # Verificar si tiene rule_set_snapshot
        if not app.rule_set_snapshot:
            return False, "No tiene workflow configurado"

        # Obtener la etapa actual
        current_stage = app.rule_set_snapshot.workflow_stages.filter(
            stage_code=app.status
        ).first()

        if not current_stage:
            return False, "Estado no encontrado en workflow"

        # Verificar si la etapa tiene auto-advance habilitado
        if not current_stage.auto_advance_enabled:
            return False, "Etapa no tiene auto-advance habilitado"

        # Verificar si requiere aprobación manual
        if current_stage.requires_manual_approval:
            return False, "Etapa requiere aprobación manual"

        # Verificar condiciones según la etapa
        if app.status == 'DOCUMENTS':
            if app.documents_status == 'COMPLETE':
                return True, "Documentos completos pero no avanzó"
            else:
                return False, f"Documentos no completos (status: {app.documents_status})"

        elif app.status == 'KYC':
            if app.identity_verification_status == 'APPROVED':
                return True, "KYC aprobado pero no avanzó"
            else:
                return False, f"KYC no aprobado (status: {app.identity_verification_status})"

        elif app.status == 'SCORING':
            if hasattr(app, 'credit_score') and app.credit_score:
                return True, "Score calculado pero no avanzó"
            else:
                return False, "Score no calculado"

        return False, "No cumple condiciones para estar atascada"

    @transaction.atomic
    def _process_application(self, app):
        """
        Procesa una solicitud atascada intentando avanzarla.
        
        Returns:
            tuple: (success: bool, message: str)
        """
        try:
            # Intentar avanzar usando el servicio de workflow
            advanced = WorkflowService.check_and_advance_if_ready(
                application=app,
                changed_by=None,  # Sistema
                trigger='manual_recovery'
            )

            if advanced:
                # Refrescar desde DB para obtener el nuevo estado
                app.refresh_from_db()
                return True, f"Avanzó de {app.status} a la siguiente etapa"
            else:
                return False, "No se pudo avanzar (condiciones no cumplidas)"

        except Exception as e:
            return False, f"Error: {str(e)}"
