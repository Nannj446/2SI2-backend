"""
Comando para eliminar todos los backups de la base de datos y storage.
"""
from django.core.management.base import BaseCommand
from api.backups.models import TenantBackup, BackupAuditLog
from api.backups.storage_service import BackupStorageService


class Command(BaseCommand):
    help = 'Elimina todos los backups de la base de datos y storage'

    def add_arguments(self, parser):
        parser.add_argument(
            '--tenant-id',
            type=int,
            help='ID del tenant específico (opcional, si no se especifica elimina todos)',
        )
        parser.add_argument(
            '--confirm',
            action='store_true',
            help='Confirmar eliminación sin preguntar',
        )

    def handle(self, *args, **options):
        tenant_id = options.get('tenant_id')
        confirm = options.get('confirm')
        
        # Buscar backups
        backups_query = TenantBackup.objects.all()
        
        if tenant_id:
            backups_query = backups_query.filter(tenant_id=tenant_id)
            self.stdout.write(f"Buscando backups del tenant {tenant_id}...")
        else:
            self.stdout.write("Buscando todos los backups...")
        
        backups = list(backups_query)
        
        if not backups:
            self.stdout.write(self.style.SUCCESS('✓ No hay backups para eliminar'))
            return
        
        self.stdout.write(f"\nEncontrados {len(backups)} backups:")
        for backup in backups:
            size_mb = (backup.total_size_bytes / (1024*1024)) if backup.total_size_bytes else 0
            self.stdout.write(
                f"  - ID: {backup.id}, Tenant: {backup.tenant.name}, "
                f"Fecha: {backup.created_at}, Tamaño: {size_mb:.2f} MB"
            )
        
        # Confirmar
        if not confirm:
            response = input(f"\n⚠️  ¿Estás seguro de eliminar {len(backups)} backups? (yes/no): ")
            if response.lower() != 'yes':
                self.stdout.write(self.style.WARNING('Operación cancelada'))
                return
        
        # Eliminar backups
        storage_service = BackupStorageService()
        deleted_count = 0
        error_count = 0
        
        self.stdout.write("\nEliminando backups...")
        
        for backup in backups:
            try:
                # Eliminar archivo de storage si existe
                if backup.backup_path:
                    try:
                        storage_service.delete_file(backup.backup_path)
                        self.stdout.write(f"  ✓ Archivo eliminado: {backup.backup_path}")
                    except Exception as e:
                        self.stdout.write(
                            self.style.WARNING(f"  ⚠️  Error eliminando archivo: {str(e)}")
                        )
                
                # Eliminar logs de auditoría relacionados
                audit_logs = BackupAuditLog.objects.filter(backup=backup)
                audit_count = audit_logs.count()
                audit_logs.delete()
                
                # Eliminar backup de BD
                backup_id = backup.id
                backup.delete()
                
                self.stdout.write(
                    self.style.SUCCESS(
                        f"  ✓ Backup {backup_id} eliminado ({audit_count} logs de auditoría)"
                    )
                )
                deleted_count += 1
                
            except Exception as e:
                error_count += 1
                self.stdout.write(
                    self.style.ERROR(f"  ✗ Error eliminando backup {backup.id}: {str(e)}")
                )
        
        # Resumen
        self.stdout.write("\n" + "=" * 60)
        self.stdout.write(self.style.SUCCESS(f"✓ {deleted_count} backups eliminados"))
        
        if error_count > 0:
            self.stdout.write(self.style.ERROR(f"✗ {error_count} errores"))
        
        self.stdout.write("\n💡 Ahora puedes crear nuevos backups desde el frontend")
