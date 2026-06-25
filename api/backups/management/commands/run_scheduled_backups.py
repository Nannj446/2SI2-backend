"""
Comando de Django para ejecutar backups programados.

Est

app.conf.beat_schedule = {
    'run-scheduled-backups': {
        'task': 'api.backups.tasks.run_scheduled_backups',
        'schedule': crontab(minute='*'),  # Cada minuto
    },
}
"""
import logging
from django.core.management.base import BaseCommand
from django.utils import timezone

from api.backups.services.scheduler_service import BackupSchedulerService

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Ejecuta backups programados que están pendientes'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Simula la ejecución sin ejecutar backups reales',
        )
        
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Muestra información detallada',
        )
    
    def handle(self, *args, **options):
        dry_run = options['dry_run']
        verbose = options['verbose']
        
        start_time = timezone.now()
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING('=== MODO DRY RUN - No se ejecutarán backups reales ===')
            )
        
        self.stdout.write(
            self.style.SUCCESS(f'Iniciando verificación de backups programados: {start_time}')
        )
        
        try:
            scheduler_service = BackupSchedulerService()
            
            if dry_run:
                # En dry run, solo mostrar qué se ejecutaría
                from api.backups.scheduled_models import BackupScheduleConfig
                
                pending_configs = BackupScheduleConfig.objects.filter(
                    is_enabled=True,
                    next_run_at__lte=timezone.now()
                ).select_related('tenant')
                
                if pending_configs.exists():
                    self.stdout.write(
                        self.style.WARNING(
                            f'\nSe ejecutarían {pending_configs.count()} backups:'
                        )
                    )
                    
                    for config in pending_configs:
                        self.stdout.write(
                            f'  - Tenant: {config.tenant.name} '
                            f'({config.schedule_description})'
                        )
                else:
                    self.stdout.write(
                        self.style.SUCCESS('\nNo hay backups pendientes para ejecutar')
                    )
                
                return
            
            # Ejecutar backups pendientes
            results = scheduler_service.run_pending_backups()
            
            # Mostrar resumen
            self.stdout.write('\n' + '=' * 60)
            self.stdout.write(self.style.SUCCESS('RESUMEN DE EJECUCIÓN'))
            self.stdout.write('=' * 60)
            self.stdout.write(f"Configuraciones verificadas: {results['total_checked']}")
            self.stdout.write(f"Backups ejecutados: {results['executed']}")
            self.stdout.write(
                self.style.SUCCESS(f"  ✓ Exitosos: {results['successful']}")
            )
            
            if results['failed'] > 0:
                self.stdout.write(
                    self.style.ERROR(f"  ✗ Fallidos: {results['failed']}")
                )
            
            if results['skipped'] > 0:
                self.stdout.write(
                    self.style.WARNING(f"  ⊘ Omitidos: {results['skipped']}")
                )
            
            # Mostrar detalles si verbose
            if verbose and results['results']:
                self.stdout.write('\n' + '=' * 60)
                self.stdout.write('DETALLES')
                self.stdout.write('=' * 60)
                
                for result in results['results']:
                    tenant_name = result['tenant_name']
                    status_result = result['status']
                    
                    if status_result == 'success':
                        style = self.style.SUCCESS
                        icon = '✓'
                        extra = f"(backup_id: {result['backup_id']}, {result['duration_seconds']:.2f}s)"
                    elif status_result == 'failed':
                        style = self.style.ERROR
                        icon = '✗'
                        extra = f"(error: {result['error']})"
                    else:  # skipped
                        style = self.style.WARNING
                        icon = '⊘'
                        extra = f"(razón: {result['error']})"
                    
                    self.stdout.write(
                        style(f"{icon} {tenant_name}: {status_result} {extra}")
                    )
            
            # Tiempo total
            end_time = timezone.now()
            duration = (end_time - start_time).total_seconds()
            
            self.stdout.write('\n' + '=' * 60)
            self.stdout.write(
                self.style.SUCCESS(
                    f'Verificación completada en {duration:.2f} segundos'
                )
            )
            
            # Exit code basado en resultados
            if results['failed'] > 0:
                self.stdout.write(
                    self.style.WARNING(
                        '\nAlgunos backups fallaron. Revise los logs para más detalles.'
                    )
                )
                # No usar exit code != 0 para no detener el cron
                # exit(1)
        
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'\nError ejecutando backups programados: {str(e)}')
            )
            logger.exception("Error en comando run_scheduled_backups")
            raise
