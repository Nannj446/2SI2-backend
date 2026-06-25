"""
Servicio centralizado para operaciones con Supabase Storage.
"""
import hashlib
from typing import Optional
from uuid import uuid4

from django.conf import settings
from supabase import Client, create_client

from .exceptions import (
    FileNotFoundException,
    StorageDeleteException,
    StorageUploadException,
)
from .validators import sanitize_path_component


class StorageService:
    """Servicio centralizado para operaciones con Supabase Storage."""
    
    def __init__(self):
        """Inicializar cliente de Supabase."""
        self.url = settings.SUPABASE_URL
        self.key = settings.SUPABASE_SERVICE_ROLE_KEY
        self.bucket = settings.SUPABASE_BUCKET
        
        if not self.url or not self.key:
            raise ValueError(
                "SUPABASE_URL y SUPABASE_SERVICE_ROLE_KEY deben estar configurados"
            )
        
        self._client: Optional[Client] = None
    
    @property
    def client(self) -> Client:
        """Obtener cliente de Supabase (lazy loading)."""
        if self._client is None:
            self._client = create_client(self.url, self.key)
        return self._client
    
    def build_storage_path(
        self,
        tenant_id: str,
        resource_type: str,
        category: str,
        file_extension: str,
        entity_id: Optional[str] = None,
        subcategory: Optional[str] = None,
    ) -> str:
        """
        Construir ruta de almacenamiento en Supabase Storage.
        
        Args:
            tenant_id: UUID del tenant
            resource_type: 'branding', 'customer', 'loan', 'user', 'backup'
            category: 'logos', 'identity', 'contracts', etc.
            file_extension: 'png', 'pdf', 'jpg', etc.
            entity_id: UUID de la entidad (customer_id, loan_id, etc.)
            subcategory: Subcategoría opcional ('front', 'back', 'signed', etc.)
        
        Returns:
            Ruta completa en storage
        """
        # Sanitizar componentes
        tenant_id = sanitize_path_component(str(tenant_id))
        resource_type = sanitize_path_component(resource_type)
        category = sanitize_path_component(category)
        file_extension = sanitize_path_component(file_extension)
        
        # Generar UUID único para el archivo
        file_uuid = str(uuid4())
        
        # Branding white-label
        if resource_type == 'branding':
            return f"tenants/{tenant_id}/branding/{category}/{file_uuid}.{file_extension}"
        
        # Documentos de clientes
        elif resource_type == 'customer':
            entity_id = sanitize_path_component(str(entity_id))
            if subcategory:
                subcategory = sanitize_path_component(subcategory)
                return f"tenants/{tenant_id}/customers/{entity_id}/{category}/{subcategory}/{file_uuid}.{file_extension}"
            return f"tenants/{tenant_id}/customers/{entity_id}/{category}/{file_uuid}.{file_extension}"
        
        # Documentos de créditos
        elif resource_type == 'loan':
            entity_id = sanitize_path_component(str(entity_id))
            if subcategory:
                subcategory = sanitize_path_component(subcategory)
                return f"tenants/{tenant_id}/loans/{entity_id}/{category}/{subcategory}/{file_uuid}.{file_extension}"
            return f"tenants/{tenant_id}/loans/{entity_id}/{category}/{file_uuid}.{file_extension}"
        
        # Usuarios
        elif resource_type == 'user':
            entity_id = sanitize_path_component(str(entity_id))
            return f"tenants/{tenant_id}/users/{entity_id}/{category}/{file_uuid}.{file_extension}"
        
        # Backups
        elif resource_type == 'backup':
            from datetime import datetime
            now = datetime.now()
            year = now.strftime("%Y")
            month = now.strftime("%m")
            timestamp = now.strftime("%Y%m%d_%H%M%S")
            return f"tenants/{tenant_id}/backups/{year}/{month}/{category}/backup_{timestamp}.{file_extension}"
        
        # Fallback
        else:
            return f"tenants/{tenant_id}/temp/{file_uuid}.{file_extension}"
    
    def upload_to_storage(self, file_path: str, file_content: bytes, content_type: str = "image/png", bucket: Optional[str] = None) -> dict:
        """
        Subir archivo a Supabase Storage.
        
        Args:
            file_path: Ruta completa en storage
            file_content: Contenido del archivo en bytes
            content_type: Tipo MIME del archivo (default: image/png)
            bucket: Bucket de Supabase (default: self.bucket)
        
        Returns:
            Respuesta de Supabase
        
        Raises:
            StorageUploadException: Si falla la subida
        """
        try:
            bucket_name = bucket or self.bucket
            response = self.client.storage.from_(bucket_name).upload(
                path=file_path,
                file=file_content,
                file_options={"content-type": content_type}
            )
            
            return response
            
        except Exception as e:
            raise StorageUploadException(
                f"Error subiendo archivo a storage: {str(e)}"
            )
    
    def delete_from_storage(self, file_path: str) -> dict:
        """
        Eliminar archivo de Supabase Storage.
        
        Args:
            file_path: Ruta completa en storage
        
        Returns:
            Respuesta de Supabase
        
        Raises:
            StorageDeleteException: Si falla la eliminación
        """
        try:
            response = self.client.storage.from_(self.bucket).remove([file_path])
            return response
            
        except Exception as e:
            raise StorageDeleteException(
                f"Error eliminando archivo de storage: {str(e)}"
            )
    
    def get_signed_url(self, file_path: str, expires_in: int = 3600) -> str:
        """
        Generar URL firmada para acceso temporal.
        
        Args:
            file_path: Ruta completa en storage
            expires_in: Segundos hasta expiración (default: 1 hora)
        
        Returns:
            URL firmada
        
        Raises:
            FileNotFoundException: Si el archivo no existe
        """
        try:
            response = self.client.storage.from_(self.bucket).create_signed_url(
                path=file_path,
                expires_in=expires_in,
            )
            
            if isinstance(response, dict) and 'signedURL' in response:
                return response['signedURL']
            
            raise FileNotFoundException(f"No se pudo generar signed URL para: {file_path}")
            
        except Exception as e:
            raise FileNotFoundException(
                f"Error generando signed URL: {str(e)}"
            )
    
    def get_public_url(self, file_path: str) -> str:
        """
        Obtener URL pública del archivo.
        
        Args:
            file_path: Ruta completa en storage
        
        Returns:
            URL pública
        """
        response = self.client.storage.from_(self.bucket).get_public_url(file_path)
        return response
    
    def download_file(self, file_path: str) -> bytes:
        """
        Descargar archivo desde Supabase Storage.
        
        Args:
            file_path: Ruta completa en storage
        
        Returns:
            Contenido del archivo en bytes
        
        Raises:
            FileNotFoundException: Si el archivo no existe
        """
        try:
            response = self.client.storage.from_(self.bucket).download(file_path)
            
            if response:
                return response
            
            raise FileNotFoundException(f"Archivo no encontrado: {file_path}")
            
        except Exception as e:
            raise FileNotFoundException(
                f"Error descargando archivo {file_path}: {str(e)}"
            )
    
    def file_exists(self, file_path: str) -> bool:
        """
        Verificar si un archivo existe en storage.
        
        Args:
            file_path: Ruta completa en storage
        
        Returns:
            True si existe, False si no
        """
        try:
            # Intentar obtener metadata del archivo
            self.client.storage.from_(self.bucket).list(file_path)
            return True
        except Exception:
            return False
    
    @staticmethod
    def calculate_checksum(file_content: bytes) -> str:
        """
        Calcular checksum SHA-256 del archivo.
        
        Args:
            file_content: Contenido del archivo en bytes
        
        Returns:
            Hash SHA-256 en hexadecimal
        """
        return hashlib.sha256(file_content).hexdigest()
    
    @staticmethod
    def verify_file_integrity(checksum_stored: str, file_content: bytes) -> bool:
        """
        Verificar integridad del archivo.
        
        Args:
            checksum_stored: Checksum almacenado
            file_content: Contenido del archivo
        
        Returns:
            True si el checksum coincide
        """
        calculated_checksum = StorageService.calculate_checksum(file_content)
        return calculated_checksum == checksum_stored
