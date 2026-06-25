"""
Comando de Django para migrar logos existentes del campo 'logo' al nuevo sistema de storage.
"""
from django.core.management.base import BaseCommand
from django.db import transaction

from api.storage.models import FileResource
from api.storage.services import StorageService
from api.tenants.models import TenantBranding


class Command(BaseCommand):
    help = 'Migrar logos existentes del campo logo al nuevo sistema de storage (logo_file)'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Ejecutar en modo simulación sin hacer cambios reales',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Forzar migración incluso si ya existe logo_file',
        )
    
    def handle(self, *args, **options):
        dry_run = options['dry_run']
        force = options['force']
        
        if dry_run:
            self.stdout.write(self.style.WARNING('🔍 Modo DRY-RUN activado - No se harán cambios reales'))
        
        # Obtener todos los brandings con logo pero sin logo_file
        if force:
            brandings = TenantBranding.objects.filter(logo__isnull=False).exclude(logo='')
            self.stdout.write(f'📊 Encontrados {brandings.count()} brandings con logo (modo FORCE)')
        else:
            brandings = TenantBranding.objects.filter(
                logo__isnull=False,
                logo_file__isnull=True,
            ).exclude(logo='')
            self.stdout.write(f'📊 Encontrados {brandings.count()} brandings con logo sin migrar')
        
        if not brandings.exists():
            self.stdout.write(self.style.SUCCESS('✅ No hay logos para migrar'))
            return
        
        storage_service = StorageService()
        migrated_count = 0
        error_count = 0
        
        for branding in brandings:
            tenant_name = branding.institution.name
            tenant_slug = branding.institution.slug
            
            try:
                self.stdout.write(f'\n🔄 Procesando: {tenant_name} ({tenant_slug})')
                
                # Leer archivo existente
                logo_file = branding.logo
                if not logo_file:
                    self.stdout.write(self.style.WARNING(f'  ⚠️  Logo vacío, saltando...'))
                    continue
                
                # Obtener información del archivo
                try:
                    file_content = logo_file.read()
                    original_name = logo_file.name.split('/')[-1]
                    file_size = len(file_content)
                    
                    self.stdout.write(f'  📄 Archivo: {original_name} ({file_size} bytes)')
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f'  ❌ Error leyendo archivo: {e}'))
                    error_count += 1
                    continue
                
                if dry_run:
                    self.stdout.write(self.style.SUCCESS(f'  ✓ [DRY-RUN] Se migraría correctamente'))
                    migrated_count += 1
                    continue
                
                # Migrar a storage
                with transaction.atomic():
                    # Calcular checksum
                    checksum = storage_service.calculate_checksum(file_content)
                    
                    # Obtener extensión
                    extension = original_name.rsplit('.', 1)[-1].lower() if '.' in original_name else 'png'
                    
                    # Construir ruta en storage
                    file_path = storage_service.build_storage_path(
                        tenant_id=str(branding.institution.id),
                        resource_type='branding',
                        category='logo',
                        file_extension=extension,
                    )
                    
                    # Subir a Supabase Storage
                    self.stdout.write(f'  ☁️  Subiendo a Supabase: {file_path}')
                    storage_service.upload_to_storage(file_path, file_content)
                    
                    # Crear FileResource
                    file_resource = FileResource.objects.create(
                        tenant=branding.institution,
                        resource_type=FileResource.ResourceType.BRANDING,
                        entity_type='tenant_branding',
                        entity_id=branding.institution.id,
                        original_name=original_name,
                        stored_name=file_path.split('/')[-1],
                        file_path=file_path,
                        bucket=storage_service.bucket,
                        mime_type='image/png',  # Asumir PNG por defecto
                        extension=extension,
                        size=file_size,
                        category='logo',
                        visibility=FileResource.Visibility.PUBLIC,
                        uploaded_by=branding.institution.created_by,
                        status=FileResource.Status.ACTIVE,
                        checksum=checksum,
                        metadata={'migrated_from_legacy': True},
                    )
                    
                    # Actualizar branding
                    branding.logo_file = file_resource
                    branding.save(update_fields=['logo_file', 'updated_at'])
                    
                    self.stdout.write(self.style.SUCCESS(f'  ✅ Migrado exitosamente'))
                    migrated_count += 1
            
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'  ❌ Error: {e}'))
                error_count += 1
                continue
        
        # Resumen
        self.stdout.write('\n' + '='*60)
        self.stdout.write(self.style.SUCCESS(f'✅ Migrados: {migrated_count}'))
        if error_count > 0:
            self.stdout.write(self.style.ERROR(f'❌ Errores: {error_count}'))
        self.stdout.write('='*60)
        
        if dry_run:
            self.stdout.write(self.style.WARNING('\n⚠️  Modo DRY-RUN - No se realizaron cambios reales'))
            self.stdout.write('Ejecuta sin --dry-run para aplicar los cambios')
