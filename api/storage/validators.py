"""
Validadores para archivos.
"""
import io
import re
from typing import Optional

from PIL import Image

from .constants import CATEGORY_VALIDATIONS, EXTENSION_TO_MIME
from .exceptions import FileTooLargeException, InvalidFileTypeException

# Intentar importar python-magic, si no está disponible usar fallback
try:
    import magic
    MAGIC_AVAILABLE = True
except ImportError:
    MAGIC_AVAILABLE = False


def validate_real_mime_type(file, allowed_types: set) -> str:
    """
    Validar tipo MIME real del archivo usando python-magic.
    Si magic no está disponible, usa la extensión como fallback.
    
    Args:
        file: Archivo subido
        allowed_types: Set de tipos MIME permitidos
    
    Returns:
        Tipo MIME real
    
    Raises:
        InvalidFileTypeException: Si el tipo no está permitido
    """
    # Intentar detectar MIME real
    mime_type = None
    
    if MAGIC_AVAILABLE:
        try:
            # Leer primeros 2KB para detectar tipo
            file.seek(0)
            content = file.read(2048)
            file.seek(0)
            
            # Detectar MIME real
            mime_type = magic.from_buffer(content, mime=True)
        except Exception:
            # Si falla magic, usar extensión
            pass
    
    # Fallback: usar extensión del archivo
    if not mime_type:
        extension = file.name.rsplit('.', 1)[-1].lower() if '.' in file.name else ''
        mime_type = EXTENSION_TO_MIME.get(extension, 'application/octet-stream')
    
    if mime_type not in allowed_types:
        raise InvalidFileTypeException(
            f"Tipo de archivo no permitido: {mime_type}. "
            f"Tipos aceptados: {', '.join(allowed_types)}"
        )
    
    return mime_type


def validate_file_size(file, max_size: int) -> int:
    """
    Validar tamaño del archivo.
    
    Args:
        file: Archivo subido
        max_size: Tamaño máximo en bytes
    
    Returns:
        Tamaño del archivo
    
    Raises:
        FileTooLargeException: Si el archivo es muy grande
    """
    file.seek(0, 2)  # Ir al final
    size = file.tell()
    file.seek(0)  # Volver al inicio
    
    if size > max_size:
        max_size_mb = max_size / (1024 * 1024)
        raise FileTooLargeException(
            f"Archivo muy grande. Tamaño máximo: {max_size_mb:.1f} MB"
        )
    
    return size


def validate_file_extension(filename: str, allowed_extensions: set) -> str:
    """
    Validar extensión del archivo.
    
    Args:
        filename: Nombre del archivo
        allowed_extensions: Set de extensiones permitidas (sin punto)
    
    Returns:
        Extensión del archivo (sin punto)
    
    Raises:
        InvalidFileTypeException: Si la extensión no está permitida
    """
    if not filename or '.' not in filename:
        raise InvalidFileTypeException("Archivo sin extensión")
    
    extension = filename.rsplit('.', 1)[1].lower()
    
    if extension not in allowed_extensions:
        raise InvalidFileTypeException(
            f"Extensión no permitida: .{extension}. "
            f"Extensiones aceptadas: {', '.join(f'.{ext}' for ext in allowed_extensions)}"
        )
    
    return extension


def validate_image_content(file) -> tuple[Optional[int], Optional[int]]:
    """
    Validar que el archivo es una imagen válida.
    
    Args:
        file: Archivo subido
    
    Returns:
        Tupla (width, height)
    
    Raises:
        InvalidFileTypeException: Si no es una imagen válida
    """
    try:
        file.seek(0)
        content = file.read()
        file.seek(0)
        
        # Abrir imagen
        image = Image.open(io.BytesIO(content))
        
        # Verificar integridad
        image.verify()
        
        # Reabrir para obtener dimensiones (verify() cierra la imagen)
        image = Image.open(io.BytesIO(content))
        width, height = image.size
        
        return width, height
        
    except Exception as e:
        raise InvalidFileTypeException(
            f"El archivo no es una imagen válida: {str(e)}"
        )


def validate_image_dimensions(
    file,
    min_width: Optional[int] = None,
    min_height: Optional[int] = None,
    max_width: Optional[int] = None,
    max_height: Optional[int] = None,
) -> tuple[int, int]:
    """
    Validar dimensiones de imagen.
    
    Args:
        file: Archivo subido
        min_width: Ancho mínimo (opcional)
        min_height: Alto mínimo (opcional)
        max_width: Ancho máximo (opcional)
        max_height: Alto máximo (opcional)
    
    Returns:
        Tupla (width, height)
    
    Raises:
        InvalidFileTypeException: Si las dimensiones no son válidas
    """
    width, height = validate_image_content(file)
    
    if min_width and width < min_width:
        raise InvalidFileTypeException(
            f"Ancho mínimo: {min_width}px. Actual: {width}px"
        )
    
    if min_height and height < min_height:
        raise InvalidFileTypeException(
            f"Alto mínimo: {min_height}px. Actual: {height}px"
        )
    
    if max_width and width > max_width:
        raise InvalidFileTypeException(
            f"Ancho máximo: {max_width}px. Actual: {width}px"
        )
    
    if max_height and height > max_height:
        raise InvalidFileTypeException(
            f"Alto máximo: {max_height}px. Actual: {height}px"
        )
    
    return width, height


def validate_branding_file(file, category: str) -> dict:
    """
    Validación completa de archivo de branding.
    
    Args:
        file: Archivo subido
        category: 'logo', 'favicon', 'cover'
    
    Returns:
        Dict con metadata validada
    
    Raises:
        InvalidFileTypeException: Si la validación falla
        FileTooLargeException: Si el archivo es muy grande
    """
    cfg = CATEGORY_VALIDATIONS.get(category)
    if not cfg:
        raise ValueError(f"Categoría no válida: {category}")
    
    # Obtener extensiones permitidas desde los tipos MIME
    allowed_extensions = {'png', 'jpg', 'jpeg', 'webp', 'svg'}
    
    # 1. Validar extensión
    extension = validate_file_extension(file.name, allowed_extensions)
    
    # 2. Validar tamaño
    size = validate_file_size(file, cfg['max_size'])
    
    # 3. Validar MIME real
    mime_type = validate_real_mime_type(file, set(cfg['allowed_types']))
    
    # 4. Validar contenido y dimensiones (solo para imágenes raster)
    if mime_type != 'image/svg+xml':
        width, height = validate_image_dimensions(
            file,
            min_width=cfg.get('min_width'),
            min_height=cfg.get('min_height'),
            max_width=cfg.get('max_width'),
            max_height=cfg.get('max_height'),
        )
    else:
        width, height = None, None
    
    return {
        'extension': extension,
        'size': size,
        'mime_type': mime_type,
        'width': width,
        'height': height,
    }


def sanitize_path_component(component: str) -> str:
    """
    Sanitizar componente de ruta para prevenir path traversal.
    
    Args:
        component: Componente de ruta
    
    Returns:
        Componente sanitizado
    """
    # Eliminar caracteres peligrosos
    component = component.replace('..', '')
    component = component.replace('/', '')
    component = component.replace('\\', '')
    component = component.replace('\0', '')
    
    # Eliminar espacios al inicio/final
    component = component.strip()
    
    return component


def generate_safe_filename(extension: str) -> str:
    """
    Generar nombre de archivo seguro con UUID.
    
    Args:
        extension: Extensión del archivo
    
    Returns:
        Nombre seguro con UUID
    """
    from uuid import uuid4
    
    # Generar UUID único
    unique_id = str(uuid4())
    
    # Sanitizar extensión
    extension = re.sub(r'[^a-z0-9]', '', extension.lower())
    
    return f"{unique_id}.{extension}"
