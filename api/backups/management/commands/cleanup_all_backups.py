"""
Management command para limpiar TODOS los registros de backups.
Útil cuando se eliminan carpetas de storage y se necesita sincronizar la BD.
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from api.backups.models import TenantBackup, BackupAuditLog, BackupManifest


class Command(BaseCommand):
    help = 'Elimina TODOS los registros de backups y logs de auditoría de la base de datos'

    def add_arguments(self, parser):
        parser.add_argument(
            '--confirm',
            action='store_true',
            help='Confirmar que deseas eliminar TODOS los backups',
        )

    def handle(self, *args, **options):
        if not options['confirm']:
            self.stdout.write(
                self.style.WARNING(
                    '\n⚠️  ADVERTENCIA: Este comando eliminará TODOS los registros de backups.\n'
                    'Para confirmar, ejecuta el comando con --confirm:\n'
                    'python manage.py cleanup_all_backups --confirm\n'
                )
            )
            return

        self.stdout.write(self.style.WARNING('\n🗑️  Iniciando limpieza de backups...\n'))

        try:
            with transaction.atomic():
                # Contar registros antes de eliminar
                backup_count = TenantBackup.objects.count()
                manifest_count = BackupManifest.objects.count()
                audit_count = BackupAuditLog.objects.count()

                self.stdout.write(f'📊 Registros encontrados:')
                self.stdout.write(f'   - Backups: {backup_count}')
                self.stdout.write(f'   - Manifests: {manifest_count}')
                self.stdout.write(f'   - Logs de auditoría: {audit_count}')
                self.stdout.write('')

                # Eliminar en orden (por las foreign keys)
                self.stdout.write('🗑️  Eliminando logs de auditoría...')
                BackupAuditLog.objects.all().delete()
                self.stdout.write(self.style.SUCCESS(f'   ✅ {audit_count} logs eliminados'))

                self.stdout.write('🗑️  Eliminando manifests...')
                BackupManifest.objects.all().delete()
                self.stdout.write(self.style.SUCCESS(f'   ✅ {manifest_count} manifests eliminados'))

                self.stdout.write('🗑️  Eliminando backups...')
                TenantBackup.objects.all().delete()
                self.stdout.write(self.style.SUCCESS(f'   ✅ {backup_count} backups eliminados'))

                self.stdout.write('')
                self.stdout.write(
                    self.style.SUCCESS(
                        '✅ Limpieza completada exitosamente!\n'
                        'Todos los registros de backups han sido eliminados de la base de datos.\n'
                    )
                )

        except Exception as e:
            self.stdout.write(
                self.style.ERROR(
                    f'\n❌ Error durante la limpieza: {str(e)}\n'
                )
            )
            raise
