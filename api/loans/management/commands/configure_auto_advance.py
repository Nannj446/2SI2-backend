"""
Comando para configurar el avance automático en workflows.

Uso:
    python manage.py configure_auto_advance --check
    python manage.py configure_auto_advance --fix
"""

from django.core.management.base import BaseCommand
from api.loans.models_rules import TenantRuleSet, WorkflowStageDefinition


class Command(BaseCommand):
    help = 'Configura el avance automático en workflows existentes'

    def add_arguments(self, parser):
        parser.add_argument(
            '--check',
            action='store_true',
            help='Solo verificar configuración sin hacer cambios',
        )
        parser.add_argument(
            '--fix',
            action='store_true',
            help='Corregir configuración de workflows',
        )
        parser.add_argument(
            '--rule-set-id',
            type=int,
            help='ID específico de TenantRuleSet a configurar',
        )

    def handle(self, *args, **options):
        check_only = options['check']
        fix = options['fix']
        rule_set_id = options.get('rule_set_id')

        if not check_only and not fix:
            self.stdout.write(
                self.style.WARNING(
                    'Debes especificar --check o --fix'
                )
            )
            return

        # Obtener rule sets
        if rule_set_id:
            rule_sets = TenantRuleSet.objects.filter(id=rule_set_id)
        else:
            # Filtrar por status = 'ACTIVE' en lugar de is_active
            rule_sets = TenantRuleSet.objects.filter(status='ACTIVE')

        if not rule_sets.exists():
            self.stdout.write(
                self.style.WARNING('No se encontraron Rule Sets activos')
            )
            return

        self.stdout.write(
            self.style.SUCCESS(
                f'\n{"="*60}\n'
                f'Analizando {rule_sets.count()} Rule Set(s)\n'
                f'{"="*60}\n'
            )
        )

        for rule_set in rule_sets:
            self.stdout.write(
                f'\n📋 Rule Set: {rule_set.name} (ID: {rule_set.id})'
            )
            self.stdout.write(f'   Institución: {rule_set.institution.name}')
            self.stdout.write(f'   Versión: {rule_set.version}')
            
            stages = rule_set.workflow_stages.all().order_by('stage_order')
            
            if not stages.exists():
                self.stdout.write(
                    self.style.WARNING('   ⚠️  No tiene workflow stages configuradas')
                )
                continue

            self.stdout.write(f'\n   Etapas del workflow:')
            
            issues_found = False
            
            for stage in stages:
                self.stdout.write(f'\n   {stage.stage_order}. {stage.stage_name} ({stage.stage_code})')
                
                # Verificar configuración
                issues = []
                
                if stage.stage_code in ['DOCUMENTS', 'KYC', 'SCORING']:
                    # Estas etapas deberían tener auto-advance
                    if not stage.auto_advance_enabled:
                        issues.append('❌ auto_advance_enabled = False')
                    else:
                        self.stdout.write('      ✅ auto_advance_enabled = True')
                    
                    if stage.requires_manual_approval:
                        issues.append('❌ requires_manual_approval = True')
                    else:
                        self.stdout.write('      ✅ requires_manual_approval = False')
                    
                    if not stage.auto_advance_conditions:
                        issues.append('❌ auto_advance_conditions no configurado')
                    else:
                        self.stdout.write(f'      ✅ auto_advance_conditions = {stage.auto_advance_conditions}')
                    
                    if not stage.next_stage_on_success:
                        issues.append('❌ next_stage_on_success no configurado')
                    else:
                        self.stdout.write(f'      ✅ next_stage_on_success = {stage.next_stage_on_success}')
                
                if issues:
                    issues_found = True
                    for issue in issues:
                        self.stdout.write(f'      {issue}')
                    
                    if fix:
                        self.stdout.write('      🔧 Corrigiendo...')
                        self._fix_stage(stage)
                        self.stdout.write('      ✅ Corregido')

            if not issues_found:
                self.stdout.write(
                    self.style.SUCCESS('\n   ✅ Configuración correcta')
                )
            elif check_only:
                self.stdout.write(
                    self.style.WARNING(
                        '\n   ⚠️  Se encontraron problemas. '
                        'Ejecuta con --fix para corregir'
                    )
                )

        self.stdout.write(
            self.style.SUCCESS(
                f'\n{"="*60}\n'
                f'Análisis completado\n'
                f'{"="*60}\n'
            )
        )

    def _fix_stage(self, stage):
        """Corrige la configuración de una etapa"""
        
        if stage.stage_code == 'DOCUMENTS':
            stage.auto_advance_enabled = True
            stage.requires_manual_approval = False
            stage.auto_advance_conditions = {"documents_complete": True}
            if not stage.next_stage_on_success:
                stage.next_stage_on_success = 'KYC'
        
        elif stage.stage_code == 'KYC':
            stage.auto_advance_enabled = True
            stage.requires_manual_approval = False
            stage.auto_advance_conditions = {"kyc_approved": True}
            if not stage.next_stage_on_success:
                stage.next_stage_on_success = 'SCORING'
        
        elif stage.stage_code == 'SCORING':
            stage.auto_advance_enabled = True
            stage.requires_manual_approval = False
            stage.auto_advance_conditions = {
                "score_calculated": True,
                "min_score": 600
            }
            if not stage.next_stage_on_success:
                stage.next_stage_on_success = 'APPROVED'
        
        stage.save()
