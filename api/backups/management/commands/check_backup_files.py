"""
Comando para verificar el file_count de los backups.
"""
from django.core.management.base import BaseCommand
from api.backups.models import TenantBackup


class Command(BaseCommand):
    help = 'Verifica el file_count de los backups'

    def add_arguments(self, parser):
        parser.add_argument(
            '--tenant-id',
            type=int,
            help='ID del tenant',
        )

    def handle(self, *args, **options):
        tenant_id = options.get('tenant_id')
        
        backups = TenantBackup.objects.all()
        if tenant_id:
            backups = backups.filter(tenant_id=tenant_id)
        
        backups = backups.order_by('-id')[:10]
        
        self.stdout.write('\n📦 Backups:\n')
        
        for backup in backups:
            self.stdout.write(f'\nBackup #{backup.id}:')
            self.stdout.write(f'   Tenant: {backup.tenant.name} (ID: {backup.tenant_id})')
            self.stdout.write(f'   Tipo: {backup.backup_type}')
            self.stdout.write(f'   File Count: {backup.file_count}')
            self.stdout.write(f'   Path: {backup.backup_path}')
            self.stdout.write(f'   Status: {backup.status}')
            
            # Verificar si es ZIP
            is_zip = backup.backup_path and backup.backup_path.endswith('.zip')
            self.stdout.write(f'   Es ZIP: {"Sí" if is_zip else "No"}')
            
            # Verificar file_list
            if hasattr(backup, 'file_list'):
                file_list_count = len(backup.file_list) if backup.file_list else 0
                self.stdout.write(f'   File List Count: {file_list_count}')
        
        self.stdout.write('\n')
