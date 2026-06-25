"""
Comando para limpiar restores que quedaron en estado 'en progreso'.
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from api.backups.models import BackupAuditLog


class Command(BaseCommand):
    help = 'Limpia restores que quedaron en estado "en progreso"'

    def add_arguments(self, parser):
        parser.add_argument(
            '--tenant-id',
            type=int,
            help='ID del tenant específico (opcional)',
        )
        parser.add_argument(
            '--minutes',
            type=int,
            default=30,
            help='Minutos de antigüedad para considerar un restore como atascado (default: 30)',
        )

    def handle(self, *args, **options):
        tenant_id = options.get('tenant_id')
        minutes = options.get('minutes')
        
        cutoff_time = timezone.now() - timedelta(minutes=minutes)
        
        self.stdout.write(f"Buscando restores atascados (más de {minutes} minutos)...")
        
        # Buscar restores iniciados sin completar/fallar
        query = BackupAuditLog.objects.filter(
            action=BackupAuditLog.Action.RESTORE_STARTED,
            created_at__lt=cutoff_time
        )
        
        if tenant_id:
            query = query.filter(tenant_id=tenant_id)
        
        stuck_restores = []
        for restore_log in query:
            # Verificar si tiene un log de completado/fallido posterior
            has_completion = BackupAuditLog.objects.filter(
                tenant=restore_log.tenant,
                backup=restore_log.backup,
                action__in=[
                    BackupAuditLog.Action.RESTORE_COMPLETED,
                    BackupAuditLog.Action.RESTORE_FAILED
                ],
                created_at__gt=restore_log.created_at
            ).exists()
            
            if not has_completion:
                stuck_restores.append(restore_log)
        
        if not stuck_restores:
            self.stdout.write(self.style.SUCCESS('✓ No hay restores atascados'))
            return
        
        self.stdout.write(f"Encontrados {len(stuck_restores)} restores atascados:")
        
        for restore_log in stuck_restores:
            self.stdout.write(
                f"  - Tenant {restore_log.tenant.id} ({restore_log.tenant.name}), "
                f"Backup {restore_log.backup.id}, "
                f"Iniciado: {restore_log.created_at}"
            )
        
        # Crear logs de fallo para estos restores
        self.stdout.write("\nCreando logs de fallo...")
        
        for restore_log in stuck_restores:
            BackupAuditLog.objects.create(
                tenant=restore_log.tenant,
                backup=restore_log.backup,
                actor=restore_log.actor,
                action=BackupAuditLog.Action.RESTORE_FAILED,
                severity=BackupAuditLog.Severity.ERROR,
                description='Restauración marcada como fallida por timeout (limpieza automática)',
                ip_address=restore_log.ip_address,
                metadata={
                    'reason': 'stuck_restore_cleanup',
                    'original_start_time': restore_log.created_at.isoformat(),
                    'cleanup_time': timezone.now().isoformat()
                }
            )
            
            self.stdout.write(
                self.style.SUCCESS(
                    f"  ✓ Marcado como fallido: Tenant {restore_log.tenant.id}, Backup {restore_log.backup.id}"
                )
            )
        
        self.stdout.write(
            self.style.SUCCESS(
                f"\n✓ {len(stuck_restores)} restores limpiados exitosamente"
            )
        )
