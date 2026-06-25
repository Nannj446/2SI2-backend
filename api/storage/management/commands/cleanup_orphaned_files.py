"""
Comando de Django para limpiar archivos huérfanos en Supabase Storage.

Archivos huérfanos son aquellos que:
1. Están marcados como DELETED pero aún existen físicamente
2. Están marcados como REPLACED y han pasado más de X días
3. Existen en storage pero no tienen registro en BD
4. Tienen status UPLOADING por más de 24 horas (uploads fallidos)

Uso:
    python manage.py cleanup_orphaned_files --dry-run
    python manage.py cleanup_orphaned_files --days=30
    python manage.py cleanup_orphaned_files --force
"""
from datetime import timedelta
from typing import List, Tuple

from django.core.management.base import BaseCommand
from django.db.models import Q
from django.utils import timezone

from api.storage.models import FileResource
from api.storage.services import StorageService


class Command(BaseCommand):
    help = 'Limpia archivos huérfanos en Supabase Storage'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Simula la limpieza sin eliminar archivos',
        )
        parser.add_argument(
            '--days',
            type=int,
            default=30,
            help='Días de antigüedad para archivos REPLACED (default: 30)',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Fuerza la eliminación sin confirmación',
        )
        parser.add_argument(
            '--tenant',
            type=str,
            help='Limitar limpieza a un tenant específico (UUID)',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        days = options['days']
        force = options['force']
        tenant_id = options.get('tenant')

        self.stdout.write(self.style.SUCCESS('=' * 70))
        self.stdout.write(self.style.SUCCESS('LIMPIEZA DE ARCHIVOS HUÉRFANOS'))
        self.stdout.write(self.style.SUCCESS('=' * 70))
        
        if dry_run:
            self.stdout.write(self.style.WARNING('\n[MODO DRY-RUN] No se eliminarán archivos\n'))
        
        storage_service = StorageService()
        
        # 1. Archivos marcados como DELETED
        deleted_files = self._find_deleted_files(tenant_id)
        self.stdout.write(f'\n1. Archivos marcados como DELETED: {len(deleted_files)}')
        
        # 2. Archivos REPLACED antiguos
        replaced_files = self._find_old_replaced_files(days, tenant_id)
        self.stdout.write(f'2. Archivos REPLACED (>{days} días): {len(replaced_files)}')
        
        # 3. Uploads fallidos
        failed_uploads = self._find_failed_uploads(tenant_id)
        self.stdout.write(f'3. Uploads fallidos (>24h): {len(failed_uploads)}')
        
        total_files = len(deleted_files) + len(replaced_files) + len(failed_uploads)
        
        if total_files == 0:
            self.stdout.write(self.style.SUCCESS('\n✓ No hay archivos huérfanos para limpiar'))
            return
        
        # Calcular espacio a liberar
        total_size = sum(f.size or 0 for f in deleted_files + replaced_files + failed_uploads)
        self.stdout.write(f'\nEspacio a liberar: {self._format_size(total_size)}')
        
        # Confirmación
        if not dry_run and not force:
            confirm = input(f'\n¿Eliminar {total_files} archivos? (yes/no): ')
            if confirm.lower() != 'yes':
                self.stdout.write(self.style.WARNING('Operación cancelada'))
                return
        
        # Ejecutar limpieza
        self.stdout.write('\n' + '=' * 70)
        self.stdout.write('EJECUTANDO LIMPIEZA...')
        self.stdout.write('=' * 70 + '\n')
        
        deleted_count = 0
        error_count = 0
        
        # Limpiar archivos DELETED
        if deleted_files:
            self.stdout.write('\n[1/3] Limpiando archivos DELETED...')
            count, errors = self._cleanup_files(deleted_files, storage_service, dry_run)
            deleted_count += count
            error_count += errors
        
        # Limpiar archivos REPLACED
        if replaced_files:
            self.stdout.write('\n[2/3] Limpiando archivos REPLACED antiguos...')
            count, errors = self._cleanup_files(replaced_files, storage_service, dry_run)
            deleted_count += count
            error_count += errors
        
        # Limpiar uploads fallidos
        if failed_uploads:
            self.stdout.write('\n[3/3] Limpiando uploads fallidos...')
            count, errors = self._cleanup_files(failed_uploads, storage_service, dry_run)
            deleted_count += count
            error_count += errors
        
        # Resumen
        self.stdout.write('\n' + '=' * 70)
        self.stdout.write('RESUMEN')
        self.stdout.write('=' * 70)
        self.stdout.write(f'Archivos procesados: {deleted_count}')
        self.stdout.write(f'Errores: {error_count}')
        self.stdout.write(f'Espacio liberado: {self._format_size(total_size)}')
        
        if dry_run:
            self.stdout.write(self.style.WARNING('\n[DRY-RUN] Ningún archivo fue eliminado'))
        else:
            self.stdout.write(self.style.SUCCESS('\n✓ Limpieza completada'))

    def _find_deleted_files(self, tenant_id=None) -> List[FileResource]:
        """Encuentra archivos marcados como DELETED."""
        queryset = FileResource.objects.filter(status=FileResource.Status.DELETED)
        
        if tenant_id:
            queryset = queryset.filter(tenant_id=tenant_id)
        
        return list(queryset.select_related('tenant'))

    def _find_old_replaced_files(self, days: int, tenant_id=None) -> List[FileResource]:
        """Encuentra archivos REPLACED con más de X días."""
        cutoff_date = timezone.now() - timedelta(days=days)
        
        queryset = FileResource.objects.filter(
            status=FileResource.Status.REPLACED,
            updated_at__lt=cutoff_date,
        )
        
        if tenant_id:
            queryset = queryset.filter(tenant_id=tenant_id)
        
        return list(queryset.select_related('tenant'))

    def _find_failed_uploads(self, tenant_id=None) -> List[FileResource]:
        """Encuentra uploads que quedaron en estado UPLOADING por más de 24h."""
        cutoff_date = timezone.now() - timedelta(hours=24)
        
        queryset = FileResource.objects.filter(
            status=FileResource.Status.UPLOADING,
            created_at__lt=cutoff_date,
        )
        
        if tenant_id:
            queryset = queryset.filter(tenant_id=tenant_id)
        
        return list(queryset.select_related('tenant'))

    def _cleanup_files(
        self,
        files: List[FileResource],
        storage_service: StorageService,
        dry_run: bool,
    ) -> Tuple[int, int]:
        """
        Limpia una lista de archivos.
        
        Returns:
            Tuple[deleted_count, error_count]
        """
        deleted_count = 0
        error_count = 0
        
        for file_resource in files:
            try:
                if dry_run:
                    self.stdout.write(
                        f'  [DRY-RUN] {file_resource.file_path} '
                        f'({self._format_size(file_resource.size or 0)})'
                    )
                else:
                    # Eliminar de storage
                    try:
                        storage_service.delete_from_storage(file_resource.file_path)
                    except Exception as storage_error:
                        self.stdout.write(
                            self.style.WARNING(
                                f'  ⚠ Error eliminando de storage: {file_resource.file_path}'
                            )
                        )
                    
                    # Eliminar registro de BD
                    file_resource.delete()
                    
                    self.stdout.write(
                        f'  ✓ {file_resource.file_path} '
                        f'({self._format_size(file_resource.size or 0)})'
                    )
                
                deleted_count += 1
                
            except Exception as e:
                error_count += 1
                self.stdout.write(
                    self.style.ERROR(f'  ✗ Error: {file_resource.file_path} - {str(e)}')
                )
        
        return deleted_count, error_count

    def _format_size(self, size_bytes: int) -> str:
        """Formatea tamaño en bytes a formato legible."""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024.0:
                return f'{size_bytes:.2f} {unit}'
            size_bytes /= 1024.0
        return f'{size_bytes:.2f} TB'
