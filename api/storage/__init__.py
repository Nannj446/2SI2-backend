"""
Módulo de storage para gestión de archivos en Supabase Storage.
"""

# No importar modelos en __init__.py para evitar importaciones circulares
# Los modelos deben importarse directamente: from api.storage.models import FileResource

__all__ = [
    # Models (importar desde .models)
    'FileResource',
    'FileAccessLog',
    # Services (importar desde .services)
    'StorageService',
    # Validators (importar desde .validators)
    'validate_branding_file',
    'validate_file_size',
    # Exceptions (importar desde .exceptions)
    'StorageException',
    'InvalidFileTypeException',
    'FileTooLargeException',
    'StorageUploadException',
    # Constants (importar desde .constants)
    'ALLOWED_IMAGE_TYPES',
    'ALLOWED_DOCUMENT_TYPES',
    'ALLOWED_AUDIO_TYPES',
    'MAX_IMAGE_SIZE',
    'MAX_FAVICON_SIZE',
    'MAX_COVER_SIZE',
    'MAX_DOCUMENT_SIZE',
    'MAX_AUDIO_SIZE',
    'CATEGORY_LOGO',
    'CATEGORY_FAVICON',
    'CATEGORY_COVER',
]
