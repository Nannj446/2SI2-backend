"""
Servicios de lógica de negocio para Tenant Branding.
"""
from typing import Optional
from uuid import UUID

from django.core.files.uploadedfile import UploadedFile
from django.db import transaction

from api.storage.models import FileResource
from api.storage.services import StorageService
from api.tenants.models import FinancialInstitution, TenantBranding


class BrandingService:
    """Servicio para gestionar branding white-label con StorageService."""
    
    def __init__(self):
        self.storage_service = StorageService()
    
    def upload_branding_file(
        self,
        tenant: FinancialInstitution,
        uploaded_file: UploadedFile,
        category: str,  # 'logo', 'favicon', 'cover'
        uploaded_by,
    ) -> FileResource:
        """
        Subir archivo de branding (logo, favicon, cover) a Supabase Storage.
        
        Args:
            tenant: Institución financiera
            uploaded_file: Archivo subido
            category: Tipo de archivo ('logo', 'favicon', 'cover')
            uploaded_by: Usuario que sube el archivo
        
        Returns:
            FileResource creado
        
        Raises:
            StorageUploadException: Si falla la subida
        """
        # Leer contenido del archivo
        file_content = uploaded_file.read()
        
        # Calcular checksum
        checksum = self.storage_service.calculate_checksum(file_content)
        
        # Obtener extensión
        original_name = uploaded_file.name
        extension = original_name.rsplit('.', 1)[-1].lower() if '.' in original_name else 'png'
        
        # Construir ruta en storage
        file_path = self.storage_service.build_storage_path(
            tenant_id=str(tenant.id),
            resource_type='branding',
            category=category,
            file_extension=extension,
        )
        
        # Subir a Supabase Storage
        self.storage_service.upload_to_storage(file_path, file_content, uploaded_file.content_type or 'image/png')
        
        # Crear registro en base de datos
        file_resource = FileResource.objects.create(
            tenant=tenant,
            resource_type=FileResource.ResourceType.BRANDING,
            entity_type='tenant_branding',
            entity_id=tenant.id,
            original_name=original_name,
            stored_name=file_path.split('/')[-1],
            file_path=file_path,
            bucket=self.storage_service.bucket,
            mime_type=uploaded_file.content_type or 'application/octet-stream',
            extension=extension,
            size=uploaded_file.size,
            category=category,
            visibility=FileResource.Visibility.PUBLIC,
            uploaded_by=uploaded_by,
            status=FileResource.Status.ACTIVE,
            checksum=checksum,
        )
        
        return file_resource
    
    def replace_branding_file(
        self,
        tenant: FinancialInstitution,
        old_file: Optional[FileResource],
        new_uploaded_file: UploadedFile,
        category: str,
        uploaded_by,
    ) -> FileResource:
        """
        Reemplazar archivo de branding existente.
        
        Args:
            tenant: Institución financiera
            old_file: FileResource anterior (puede ser None)
            new_uploaded_file: Nuevo archivo subido
            category: Tipo de archivo ('logo', 'favicon', 'cover')
            uploaded_by: Usuario que sube el archivo
        
        Returns:
            Nuevo FileResource creado
        """
        with transaction.atomic():
            # Subir nuevo archivo
            new_file = self.upload_branding_file(
                tenant=tenant,
                uploaded_file=new_uploaded_file,
                category=category,
                uploaded_by=uploaded_by,
            )
            
            # Marcar archivo anterior como reemplazado
            if old_file:
                old_file.mark_as_replaced(new_file)
            
            return new_file
    
    def delete_branding_file(self, file_resource: FileResource) -> None:
        """
        Eliminar archivo de branding (soft delete + eliminación física).
        
        Args:
            file_resource: FileResource a eliminar
        """
        with transaction.atomic():
            # Marcar como eliminado en BD
            file_resource.mark_as_deleted()
            
            # Eliminar físicamente de Supabase Storage
            try:
                self.storage_service.delete_from_storage(file_resource.file_path)
            except Exception as e:
                # Log error pero no fallar la transacción
                print(f"Error eliminando archivo físico: {e}")
    
    def update_branding_with_files(
        self,
        branding: TenantBranding,
        logo_file: Optional[UploadedFile] = None,
        favicon_file: Optional[UploadedFile] = None,
        cover_file: Optional[UploadedFile] = None,
        uploaded_by = None,
    ) -> TenantBranding:
        """
        Actualizar branding con nuevos archivos.
        
        Args:
            branding: Instancia de TenantBranding
            logo_file: Nuevo logo (opcional)
            favicon_file: Nuevo favicon (opcional)
            cover_file: Nueva imagen de portada (opcional)
            uploaded_by: Usuario que realiza la actualización
        
        Returns:
            TenantBranding actualizado
        """
        with transaction.atomic():
            # Actualizar logo
            if logo_file:
                new_logo = self.replace_branding_file(
                    tenant=branding.institution,
                    old_file=branding.logo_file,
                    new_uploaded_file=logo_file,
                    category='logo',
                    uploaded_by=uploaded_by,
                )
                branding.logo_file = new_logo
            
            # Actualizar favicon
            if favicon_file:
                new_favicon = self.replace_branding_file(
                    tenant=branding.institution,
                    old_file=branding.favicon_file,
                    new_uploaded_file=favicon_file,
                    category='favicon',
                    uploaded_by=uploaded_by,
                )
                branding.favicon_file = new_favicon
            
            # Actualizar cover
            if cover_file:
                new_cover = self.replace_branding_file(
                    tenant=branding.institution,
                    old_file=branding.cover_file,
                    new_uploaded_file=cover_file,
                    category='cover',
                    uploaded_by=uploaded_by,
                )
                branding.cover_file = new_cover
            
            branding.save()
            return branding
    
    def get_branding_by_slug(self, slug: str) -> Optional[TenantBranding]:
        """
        Obtener branding por slug del tenant.
        
        Args:
            slug: Slug de la institución financiera
        
        Returns:
            TenantBranding o None si no existe
        """
        try:
            return TenantBranding.objects.select_related(
                'institution',
                'logo_file',
                'favicon_file',
                'cover_file',
            ).get(
                institution__slug=slug,
                is_active=True,
            )
        except TenantBranding.DoesNotExist:
            return None
