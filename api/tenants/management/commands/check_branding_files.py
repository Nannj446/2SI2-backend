"""
Comando para verificar la integridad de archivos de branding en Supabase Storage.
"""
from django.core.management.base import BaseCommand
from django.db.models import Q

from api.tenants.models import TenantBranding
from api.storage.models import FileResource
from api.storage.services import StorageService


class Command(BaseCommand):
    help = 'Verifica la integridad de archivos de branding en Supabase Storage'

    def add_arguments(self, parser):
        parser.add_argument(
            '--fix',
            action='store_true',
            help='Corregir registros huérfanos (marcar como deleted)',
        )
        parser.add_argument(
            '--tenant-id',
            type=int,
            help='Verificar solo un tenant específico',
        )

    def handle(self, *args, **options):
        fix_mode = options['fix']
        tenant_id = options.get('tenant_id')
        
        self.stdout.write(self.style.WARNING('=' * 80))
        self.stdout.write(self.style.WARNING('VERIFICACIÓN DE ARCHIVOS DE BRANDING'))
        self.stdout.write(self.style.WARNING('=' * 80))
        
        # Filtrar por tenant si se especifica
        brandings = TenantBranding.objects.select_related('institution', 'logo_file', 'favicon_file', 'cover_file')
        if tenant_id:
            brandings = brandings.filter(institution_id=tenant_id)
        
        storage_service = StorageService()
        
        total_brandings = brandings.count()
        issues_found = 0
        files_checked = 0
        files_ok = 0
        files_missing = 0
        files_fixed = 0
        
        self.stdout.write(f'\n📊 Total de brandings a verificar: {total_brandings}\n')
        
        for branding in brandings:
            self.stdout.write(f'\n🏢 Tenant: {branding.institution.name} (ID: {branding.institution.id})')
            self.stdout.write(f'   Display Name: {branding.display_name}')
            
            # Verificar logo_file
            if branding.logo_file:
                files_checked += 1
                self.stdout.write(f'\n   🖼️  Logo File:')
                self.stdout.write(f'      - ID: {branding.logo_file.id}')
                self.stdout.write(f'      - Path: {branding.logo_file.file_path}')
                self.stdout.write(f'      - Status: {branding.logo_file.status}')
                
                if branding.logo_file.status == 'active':
                    # Intentar generar signed URL
                    try:
                        url = branding.logo_file.get_signed_url(expires_in=60)
                        if url:
                            self.stdout.write(self.style.SUCCESS(f'      ✅ Archivo existe en storage'))
                            files_ok += 1
                        else:
                            self.stdout.write(self.style.ERROR(f'      ❌ Archivo NO existe en storage'))
                            files_missing += 1
                            issues_found += 1
                            
                            if fix_mode:
                                branding.logo_file.mark_as_deleted()
                                branding.logo_file = None
                                branding.save(update_fields=['logo_file'])
                                files_fixed += 1
                                self.stdout.write(self.style.WARNING(f'      🔧 Registro marcado como deleted y desvinculado'))
                    except Exception as e:
                        self.stdout.write(self.style.ERROR(f'      ❌ Error verificando: {str(e)}'))
                        files_missing += 1
                        issues_found += 1
            
            # Verificar favicon_file
            if branding.favicon_file:
                files_checked += 1
                self.stdout.write(f'\n   🎯 Favicon File:')
                self.stdout.write(f'      - ID: {branding.favicon_file.id}')
                self.stdout.write(f'      - Path: {branding.favicon_file.file_path}')
                self.stdout.write(f'      - Status: {branding.favicon_file.status}')
                
                if branding.favicon_file.status == 'active':
                    try:
                        url = branding.favicon_file.get_signed_url(expires_in=60)
                        if url:
                            self.stdout.write(self.style.SUCCESS(f'      ✅ Archivo existe en storage'))
                            files_ok += 1
                        else:
                            self.stdout.write(self.style.ERROR(f'      ❌ Archivo NO existe en storage'))
                            files_missing += 1
                            issues_found += 1
                            
                            if fix_mode:
                                branding.favicon_file.mark_as_deleted()
                                branding.favicon_file = None
                                branding.save(update_fields=['favicon_file'])
                                files_fixed += 1
                                self.stdout.write(self.style.WARNING(f'      🔧 Registro marcado como deleted y desvinculado'))
                    except Exception as e:
                        self.stdout.write(self.style.ERROR(f'      ❌ Error verificando: {str(e)}'))
                        files_missing += 1
                        issues_found += 1
            
            # Verificar cover_file
            if branding.cover_file:
                files_checked += 1
                self.stdout.write(f'\n   🖼️  Cover File:')
                self.stdout.write(f'      - ID: {branding.cover_file.id}')
                self.stdout.write(f'      - Path: {branding.cover_file.file_path}')
                self.stdout.write(f'      - Status: {branding.cover_file.status}')
                
                if branding.cover_file.status == 'active':
                    try:
                        url = branding.cover_file.get_signed_url(expires_in=60)
                        if url:
                            self.stdout.write(self.style.SUCCESS(f'      ✅ Archivo existe en storage'))
                            files_ok += 1
                        else:
                            self.stdout.write(self.style.ERROR(f'      ❌ Archivo NO existe en storage'))
                            files_missing += 1
                            issues_found += 1
                            
                            if fix_mode:
                                branding.cover_file.mark_as_deleted()
                                branding.cover_file = None
                                branding.save(update_fields=['cover_file'])
                                files_fixed += 1
                                self.stdout.write(self.style.WARNING(f'      🔧 Registro marcado como deleted y desvinculado'))
                    except Exception as e:
                        self.stdout.write(self.style.ERROR(f'      ❌ Error verificando: {str(e)}'))
                        files_missing += 1
                        issues_found += 1
            
            # Verificar logo antiguo (deprecado)
            if branding.logo:
                self.stdout.write(f'\n   ⚠️  Logo antiguo (deprecado): {branding.logo.name}')
        
        # Resumen
        self.stdout.write('\n')
        self.stdout.write(self.style.WARNING('=' * 80))
        self.stdout.write(self.style.WARNING('RESUMEN'))
        self.stdout.write(self.style.WARNING('=' * 80))
        self.stdout.write(f'\n📊 Estadísticas:')
        self.stdout.write(f'   - Brandings verificados: {total_brandings}')
        self.stdout.write(f'   - Archivos verificados: {files_checked}')
        self.stdout.write(f'   - Archivos OK: {files_ok}')
        self.stdout.write(f'   - Archivos faltantes: {files_missing}')
        
        if fix_mode:
            self.stdout.write(f'   - Archivos corregidos: {files_fixed}')
        
        if issues_found > 0:
            self.stdout.write(self.style.ERROR(f'\n❌ Se encontraron {issues_found} problemas'))
            if not fix_mode:
                self.stdout.write(self.style.WARNING('\n💡 Ejecuta con --fix para corregir automáticamente'))
        else:
            self.stdout.write(self.style.SUCCESS(f'\n✅ Todos los archivos están OK'))
        
        self.stdout.write('\n')
