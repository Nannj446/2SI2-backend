"""
Excepciones personalizadas para el módulo de storage.
"""


class StorageException(Exception):
    """Excepción base para errores de storage."""
    pass


class InvalidFileTypeException(StorageException):
    """Excepción cuando el tipo de archivo no es válido."""
    pass


class FileTooLargeException(StorageException):
    """Excepción cuando el archivo es muy grande."""
    pass


class StorageUploadException(StorageException):
    """Excepción cuando falla la subida a storage."""
    pass


class StorageDeleteException(StorageException):
    """Excepción cuando falla la eliminación de storage."""
    pass


class FileNotFoundException(StorageException):
    """Excepción cuando no se encuentra el archivo."""
    pass


class InvalidPathException(StorageException):
    """Excepción cuando la ruta es inválida."""
    pass
