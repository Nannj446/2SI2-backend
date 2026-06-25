"""
Comando para limpiar archivos de branding de un tenant en Supabase Storage.
"""
from django.core.management.base import BaseCommand
from django.db import transaction

from api.tenants.models import TenantBranding, FinancialInstitution
from api.storage.models import FileResource
from api.storage.services import StorageService
from api.storage.exceptions import StorageException


class Command(BaseCommand):
    help = 'Limpia archivos de branding de un tenant en Supabase Storage'

    def add_arguments(self, parser):
        parser.add_argument(
            'tenant_id',
            type=int,
            help='ID del tenant a limpiar',
        )
        parser.add_argument(
            '--confirm',
            action='store_true',
            help='Confirmar la eliminación (sin esto solo muestra preview)',
        )
        parser.add_argument(
            '--delete-storage',
            action='store_true',
            help='También eliminar archivos físicos de Supabase Storage',
        )
        parser.add_argument(
            '--reset-colors',
            action='store_true',
            help='Resetear colores a valores por defecto',
        )

    def handle(self, *args, **options):
        tenant_id = options['tenant_id']
        confirm = options['confirm']
        delete_storage = options['delete_storage']
        reset_colors = options['reset_colors']
        
        self.stdout.write(self.style.WARNING('=' * 80))
        self.stdout.write(self.style.WARNING('LIMPIEZA DE ARCHIVOS DE BRANDING'))
        self.stdout.write(self.style.WARNING('=' * 80))
        
        # Validar tenant
        try:
            tenant = FinancialInstitution.objects.get(id=tenant_id)
        except FinancialInstitution.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'\n❌ Tenant {tenant_id} no encontrado'))
            return
        
        self.stdout.write(f'\n🏢 Tenant: {tenant.name} (ID: {tenant.id})')
        
        # Obtener branding
        try:
            branding = TenantBranding.objects.select_related(
                'logo_file', 'favicon_file', 'cover_file'
            ).get(institution=tenant)
        except TenantBranding.DoesNotExist:
            self.stdout.write(self.style.WARNING('\n⚠️  Este tenant no tiene branding configurado'))
            return
        
        # Recopilar archivos a limpiar
        files_to_clean = []
        
        if branding.logo_file:
            files_to_clean.append({
                'type': 'Logo',
                'file_resource': branding.logo_file,
                'field_name': 'logo_file'
            })
        
        if branding.favicon_file:
            files_to_clean.append({
                'type': 'Favicon',
                'file_resource': branding.favicon_file,
                'field_name': 'favicon_file'
            })
        
        if branding.cover_file:
            files_to_clean.append({
                'type': 'Cover',
                'file_resource': branding.cover_file,
                'field_name': 'cover_file'
            })
        
        if branding.logo:
            self.stdout.write(f'\n⚠️  Logo antiguo (deprecado): {branding.logo.name}')
        
        # Mostrar preview
        self.stdout.write(f'\n📊 Archivos encontrados: {len(files_to_clean)}')
        
        if not files_to_clean:
            self.stdout.write(self.style.WARNING('\n⚠️  No hay archivos para limpiar'))
            return
        
        self.stdout.write('\n📋 Archivos a limpiar:')
        for item in files_to_clean:
            file_res = item['file_resource']
            self.stdout.write(f'\n   {item["type"]}:')
            self.stdout.write(f'      - ID: {file_res.id}')
            self.stdout.write(f'      - Path: {file_res.file_path}')
            self.stdout.write(f'      - Status: {file_res.status}')
            self.stdout.write(f'      - Size: {file_res.size} bytes')
        
        # Mostrar colores actuales
        self.stdout.write('\n🎨 Colores actuales:')
        self.stdout.write(f'   - Primary: {branding.primary_color}')
        self.stdout.write(f'   - Secondary: {branding.secondary_color}')
        self.stdout.write(f'   - Accent: {branding.accent_color}')
        self.stdout.write(f'   - Background: {branding.background_color}')
        self.stdout.write(f'   - Text: {branding.text_color}')
        
        # Si no hay confirmación, solo mostrar preview
        if not confirm:
            self.stdout.write('\n')
            self.stdout.write(self.style.WARNING('=' * 80))
            self.stdout.write(self.style.WARNING('PREVIEW MODE'))
            self.stdout.write(self.style.WARNING('=' * 80))
            self.stdout.write('\n💡 Esto es solo un preview. Para ejecutar la limpieza, usa:')
            self.stdout.write(f'   python manage.py clean_branding_files {tenant_id} --confirm')
            
            if delete_storage:
                self.stdout.write('\n⚠️  Con --delete-storage también se eliminarán los archivos físicos de Supabase')
            
            if reset_colors:
                self.stdout.write('\n⚠️  Con --reset-colors se resetearán los colores a valores por defecto')
            
            self.stdout.write('\n')
            return
        
        # Ejecutar limpieza
        self.stdout.write('\n')
        self.stdout.write(self.style.WARNING('=' * 80))
        self.stdout.write(self.style.WARNING('EJECUTANDO LIMPIEZA'))
        self.stdout.write(self.style.WARNING('=' * 80))
        
        storage_service = StorageService()
        files_deleted_db = 0
        files_deleted_storage = 0
        
        with transaction.atomic():
            # Limpiar archivos
            for item in files_to_clean:
                file_res = item['file_resource']
                field_name = item['field_name']
                
                self.stdout.write(f'\n🗑️  Limpiando {item["type"]}...')
                
                # Eliminar de Storage si se solicita
                if delete_storage:
                    try:
                        storage_service.delete_from_storage(file_res.file_path)
                        files_deleted_storage += 1
                        self.stdout.write(self.style.SUCCESS(f'   ✅ Eliminado de Storage: {file_res.file_path}'))
                    except StorageException as e:
                        self.stdout.write(self.style.WARNING(f'   ⚠️  No se pudo eliminar de Storage: {str(e)}'))
                
                # Marcar como deleted en BD
                file_res.mark_as_deleted()
                files_deleted_db += 1
                self.stdout.write(self.style.SUCCESS(f'   ✅ Marcado como deleted en BD'))
                
                # Desvincular del branding
                setattr(branding, field_name, None)
            
            # Limpiar logo antiguo si existe
            if branding.logo:
                branding.logo = None
                self.stdout.write(self.style.SUCCESS('\n   ✅ Logo antiguo (deprecado) eliminado'))
            
            # Resetear colores si se solicita
            if reset_colors:
                from api.tenants.models import (
                    DEFAULT_TENANT_PRIMARY_COLOR,
                    DEFAULT_TENANT_SECONDARY_COLOR,
                    DEFAULT_TENANT_ACCENT_COLOR,
                    DEFAULT_TENANT_BACKGROUND_COLOR,
                    DEFAULT_TENANT_TEXT_COLOR,
                )
                
                branding.primary_color = DEFAULT_TENANT_PRIMARY_COLOR
                branding.secondary_color = DEFAULT_TENANT_SECONDARY_COLOR
                branding.accent_color = DEFAULT_TENANT_ACCENT_COLOR
                branding.background_color = DEFAULT_TENANT_BACKGROUND_COLOR
                branding.text_color = DEFAULT_TENANT_TEXT_COLOR
                
                self.stdout.write(self.style.SUCCESS('\n🎨 Colores reseteados a valores por defecto'))
            
            # Guardar cambios
            branding.save()
        
        # Resumen
        self.stdout.write('\n')
        self.stdout.write(self.style.WARNING('=' * 80))
        self.stdout.write(self.style.WARNING('RESUMEN'))
        self.stdout.write(self.style.WARNING('=' * 80))
        self.stdout.write(f'\n✅ Limpieza completada:')
        self.stdout.write(f'   - Archivos marcados como deleted en BD: {files_deleted_db}')
        
        if delete_storage:
            self.stdout.write(f'   - Archivos eliminados de Storage: {files_deleted_storage}')
        
        if reset_colors:
            self.stdout.write(f'   - Colores reseteados: Sí')
        
        self.stdout.write('\n💡 Ahora puedes hacer un restore para recuperar el branding de un backup')
        self.stdout.write('\n')
