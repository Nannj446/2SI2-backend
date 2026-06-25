"""
Comando de Django para limpiar backups expirados y fallidos.
"""
from django.core.management.base import BaseCommand, CommandError
from api.backups.services.cleanup_service import BackupCleanupService


class Command(BaseCommand):
    help = 'Limpia backups expirados y fallidos antiguos'
    
    def add_arguments(self, parser):
        """Agregar argumentos al comando."""
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Simula la limpieza sin eliminar archivos'
        )
        
        parser.add_argument(
            '--failed-only',
            action='store_true',
            help='Solo limpia backups fallidos'
        )
        
        parser.add_argument(
            '--expired-only',
            action='store_true',
            help='Solo limpia backups expirados'
        )
        
        parser.add_argument(
            '--days',
            type=int,
            default=7,
            help='Días de antigüedad para backups fallidos (default: 7)'
        )
        
        parser.add_argument(
            '--stats',
            action='store_true',
            help='Solo muestra estadísticas sin limpiar'
        )
    
    def handle(self, *args, **options):
        """Ejecutar comando."""
        dry_run = options['dry_run']
        failed_only = options['failed_only']
        expired_only = options['expired_only']
        days = options['days']
        stats_only = options['stats']
        
        cleanup_service = BackupCleanupService()
        
        # Mostrar encabezado
        self.stdout.write(self.style.HTTP_INFO('=' * 70))
        self.stdout.write(
            self.style.HTTP_INFO('  LIMPIEZA DE BACKUPS')
        )
        self.stdout.write(self.style.HTTP_INFO('=' * 70))
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING('\n⚠️  Modo DRY RUN - No se eliminarán archivos\n')
            )
        
        # Solo mostrar estadísticas
        if stats_only:
            self._show_stats(cleanup_service)
            return
        
        # Limpiar backups expirados
        if not failed_only:
            self.stdout.write('\n📦 Limpiando backups expirados...')
            try:
                result = cleanup_service.cleanup_expired_backups(dry_run=dry_run)
                self._print_expired_result(result)
            except Exception as e:
                raise CommandError(f'Error limpiando backups expirados: {str(e)}')
        
        # Limpiar backups fallidos
        if not expired_only:
            self.stdout.write(f'\n❌ Limpiando backups fallidos (>{days} días)...')
            try:
                result = cleanup_service.cleanup_failed_backups(
                    days_old=days,
                    dry_run=dry_run
                )
                self._print_failed_result(result)
            except Exception as e:
                raise CommandError(f'Error limpiando backups fallidos: {str(e)}')
        
        # Resumen final
        self.stdout.write('\n' + '=' * 70)
        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    '✅ Simulación completada. Ejecuta sin --dry-run para eliminar.'
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS('✅ Limpieza completada exitosamente')
            )
        self.stdout.write('=' * 70 + '\n')
    
    def _show_stats(self, cleanup_service):
        """Muestra estadísticas de limpieza."""
        self.stdout.write('\n📊 Estadísticas de Backups:\n')
        
        try:
            stats = cleanup_service.get_cleanup_stats()
            
            # Backups expirados
            self.stdout.write(
                f"  Expirados: {stats['expired']['count']} backups "
                f"({stats['expired']['size_mb']} MB)"
            )
            
            # Backups fallidos antiguos
            self.stdout.write(
                f"  Fallidos antiguos: {stats['failed_old']['count']} backups"
            )
            
            # Próximos a expirar
            self.stdout.write(
                f"  Expiran pronto (7 días): {stats['expiring_soon']['count']} backups"
            )
            
            self.stdout.write(
                f"\n  Timestamp: {stats['timestamp']}"
            )
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error obteniendo estadísticas: {str(e)}')
            )
    
    def _print_expired_result(self, result):
        """Imprime resultado de limpieza de expirados."""
        total = result['total_expired']
        deleted = result['deleted']
        errors = result['errors']
        freed_mb = result['freed_mb']
        
        if total == 0:
            self.stdout.write(
                self.style.SUCCESS('  ✓ No hay backups expirados')
            )
        else:
            self.stdout.write(
                f"  Total encontrados: {total}"
            )
            self.stdout.write(
                self.style.SUCCESS(f"  ✓ Eliminados: {deleted}")
            )
            if errors > 0:
                self.stdout.write(
                    self.style.ERROR(f"  ✗ Errores: {errors}")
                )
            self.stdout.write(
                f"  💾 Espacio liberado: {freed_mb} MB"
            )
    
    def _print_failed_result(self, result):
        """Imprime resultado de limpieza de fallidos."""
        total = result['total_deleted']
        days = result['days_old']
        
        if total == 0:
            self.stdout.write(
                self.style.SUCCESS(f'  ✓ No hay backups fallidos de más de {days} días')
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(f"  ✓ Eliminados: {total} backups fallidos")
            )
            self.stdout.write(
                f"  📅 Fecha de corte: {result['cutoff_date']}"
            )
