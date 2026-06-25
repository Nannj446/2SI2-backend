"""
Servicio de Storage específico para backups de tenants.
"""
import hashlib
import logging
from typing import Optional
from django.conf import settings
from api.storage.client import get_supabase_client

logger = logging.getLogger(__name__)


class BackupStorageService:
    """
    Servicio para operaciones de Storage específicas de backups.
    
    Maneja subida, descarga, eliminación y generación de signed URLs
    para archivos de backup en el bucket dedicado.
    """
    
    def __init__(self, bucket: str = None):
        """
        Inicializa el servicio.
        
        Args:
            bucket: Nombre del bucket (default: settings.SUPABASE_BACKUP_BUCKET)
        """
        self.client = get_supabase_client()
        self.bucket = bucket or settings.SUPABASE_BACKUP_BUCKET
        logger.debug(f"BackupStorageService inicializado con bucket: {self.bucket}")
    
    def upload_file(
        self, 
        file_path: str, 
        file_content: bytes,
        content_type: str = 'application/octet-stream',
        upsert: bool = False
    ) -> dict:
        """
        Sube un archivo de backup a Supabase Storage.
        
        Args:
            file_path: Ruta del archivo en el bucket (ej: 'tenants/1/backup_20260506.zip')
            file_content: Contenido del archivo en bytes
            content_type: Tipo MIME del archivo
            upsert: Si True, sobrescribe si existe
        
        Returns:
            Diccionario con información del archivo subido:
            {
                'success': True,
                'path': 'tenants/1/backup.zip',
                'bucket': 'backups',
                'size': 1024,
                'checksum': 'abc123...'
            }
        
        Raises:
            Exception: Si falla la subida
        """
        try:
            logger.info(f"Subiendo backup a {self.bucket}/{file_path} ({len(file_content)} bytes)")
            
            # Calcular checksum antes de subir
            checksum = self.calculate_checksum(file_content)
            
            response = self.client.storage.from_(self.bucket).upload(
                path=file_path,
                file=file_content,
                file_options={
                    "content-type": content_type,
                    "upsert": str(upsert).lower()
                }
            )
            
            logger.info(f"Backup subido exitosamente: {file_path}")
            
            return {
                'success': True,
                'path': file_path,
                'bucket': self.bucket,
                'size': len(file_content),
                'checksum': checksum
            }
        
        except Exception as e:
            logger.error(f"Error subiendo backup {file_path}: {str(e)}")
            raise
    
    def download_file(self, file_path: str) -> bytes:
        """
        Descarga un archivo de backup de Supabase Storage.
        
        Args:
            file_path: Ruta del archivo en el bucket
        
        Returns:
            Contenido del archivo en bytes
        
        Raises:
            Exception: Si falla la descarga
        """
        try:
            logger.info(f"Descargando backup de {self.bucket}/{file_path}")
            
            response = self.client.storage.from_(self.bucket).download(file_path)
            
            logger.info(f"Backup descargado exitosamente: {file_path} ({len(response)} bytes)")
            
            return response
        
        except Exception as e:
            logger.error(f"Error descargando backup {file_path}: {str(e)}")
            raise
    
    def delete_file(self, file_path: str) -> bool:
        """
        Elimina un archivo de backup de Supabase Storage.
        
        Args:
            file_path: Ruta del archivo en el bucket
        
        Returns:
            True si se eliminó correctamente
        
        Raises:
            Exception: Si falla la eliminación
        """
        try:
            logger.info(f"Eliminando backup {self.bucket}/{file_path}")
            
            response = self.client.storage.from_(self.bucket).remove([file_path])
            
            logger.info(f"Backup eliminado exitosamente: {file_path}")
            
            return True
        
        except Exception as e:
            logger.error(f"Error eliminando backup {file_path}: {str(e)}")
            raise
    
    def file_exists(self, file_path: str) -> bool:
        """
        Verifica si un archivo de backup existe en Storage.
        
        Args:
            file_path: Ruta del archivo en el bucket
        
        Returns:
            True si existe, False si no
        """
        try:
            # Intentar listar el archivo específico
            response = self.client.storage.from_(self.bucket).list(
                path=file_path
            )
            return len(response) > 0
        
        except Exception as e:
            logger.debug(f"Archivo no existe o error verificando: {file_path} - {str(e)}")
            return False
    
    def generate_signed_url(
        self, 
        file_path: str, 
        expires_in: int = None
    ) -> str:
        """
        Genera una URL firmada para descarga segura de backup.
        
        Args:
            file_path: Ruta del archivo en el bucket
            expires_in: Segundos de expiración (default: settings.BACKUP_SIGNED_URL_EXPIRATION)
        
        Returns:
            URL firmada con expiración
        
        Raises:
            Exception: Si falla la generación
        """
        try:
            if expires_in is None:
                expires_in = settings.BACKUP_SIGNED_URL_EXPIRATION
            
            logger.info(f"Generando signed URL para {file_path} (expira en {expires_in}s)")
            
            response = self.client.storage.from_(self.bucket).create_signed_url(
                path=file_path,
                expires_in=expires_in
            )
            
            # Extraer la URL firmada de la respuesta
            if isinstance(response, dict):
                signed_url = response.get('signedURL') or response.get('signedUrl')
            else:
                signed_url = response
            
            if not signed_url:
                raise ValueError("No se pudo obtener signed URL de la respuesta")
            
            logger.info(f"Signed URL generada exitosamente para {file_path}")
            
            return signed_url
        
        except Exception as e:
            logger.error(f"Error generando signed URL para {file_path}: {str(e)}")
            raise
    
    def list_files(self, path: str = '', limit: int = 100) -> list:
        """
        Lista archivos de backup en una ruta del bucket.
        
        Args:
            path: Ruta base (ej: 'tenants/1/')
            limit: Máximo de archivos a retornar
        
        Returns:
            Lista de archivos con metadata
        """
        try:
            logger.debug(f"Listando archivos en {self.bucket}/{path}")
            
            response = self.client.storage.from_(self.bucket).list(
                path=path,
                options={'limit': limit}
            )
            
            logger.debug(f"Encontrados {len(response)} archivos en {path}")
            
            return response
        
        except Exception as e:
            logger.error(f"Error listando archivos en {path}: {str(e)}")
            raise
    
    def get_file_metadata(self, file_path: str) -> dict:
        """
        Obtiene metadata de un archivo de backup.
        
        Args:
            file_path: Ruta del archivo en el bucket
        
        Returns:
            Diccionario con metadata del archivo
        """
        try:
            # Extraer el directorio y nombre del archivo
            parts = file_path.rsplit('/', 1)
            if len(parts) == 2:
                directory, filename = parts
            else:
                directory = ''
                filename = file_path
            
            # Listar archivos en el directorio
            files = self.list_files(directory)
            
            # Buscar el archivo específico
            for file_info in files:
                if file_info.get('name') == filename:
                    return file_info
            
            raise FileNotFoundError(f"Archivo no encontrado: {file_path}")
        
        except Exception as e:
            logger.error(f"Error obteniendo metadata de {file_path}: {str(e)}")
            raise
    
    @staticmethod
    def calculate_checksum(content: bytes) -> str:
        """
        Calcula checksum SHA-256 de contenido.
        
        Args:
            content: Contenido en bytes
        
        Returns:
            Checksum hexadecimal (64 caracteres)
        """
        return hashlib.sha256(content).hexdigest()
    
    @staticmethod
    def verify_checksum(content: bytes, expected_checksum: str) -> bool:
        """
        Verifica que el checksum del contenido coincida con el esperado.
        
        Args:
            content: Contenido en bytes
            expected_checksum: Checksum esperado
        
        Returns:
            True si coincide, False si no
        """
        actual_checksum = BackupStorageService.calculate_checksum(content)
        return actual_checksum == expected_checksum
