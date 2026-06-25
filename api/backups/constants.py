"""
Constantes para el sistema de backups.
Define rutas, tipos, límites y configuraciones centralizadas.
"""

from datetime import datetime
from typing import Dict, Any

# ============================================================================
# TIPOS DE BACKUP
# ============================================================================

BACKUP_TYPE_FULL = 'full'
BACKUP_TYPE_METADATA_ONLY = 'metadata_only'
BACKUP_TYPE_STORAGE_ONLY = 'storage_only'

BACKUP_TYPES = [
    (BACKUP_TYPE_FULL, 'Backup Completo (Datos + Archivos)'),
    (BACKUP_TYPE_METADATA_ONLY, 'Solo Metadatos (Base de Datos)'),
    (BACKUP_TYPE_STORAGE_ONLY, 'Solo Archivos (Storage)'),
]

# ============================================================================
# ESTADOS DE BACKUP
# ============================================================================

BACKUP_STATUS_PENDING = 'pending'
BACKUP_STATUS_RUNNING = 'running'
BACKUP_STATUS_COMPLETED = 'completed'
BACKUP_STATUS_FAILED = 'failed'
BACKUP_STATUS_EXPIRED = 'expired'

BACKUP_STATUSES = [
    (BACKUP_STATUS_PENDING, 'Pendiente'),
    (BACKUP_STATUS_RUNNING, 'En Ejecución'),
    (BACKUP_STATUS_COMPLETED, 'Completado'),
    (BACKUP_STATUS_FAILED, 'Fallido'),
    (BACKUP_STATUS_EXPIRED, 'Expirado'),
]

# ============================================================================
# ESTRUCTURA DE RUTAS EN STORAGE
# ============================================================================

# Plantilla de ruta base para backups
# Formato: tenants/{tenant_id}/backups/{year}/{month}/{day}/backup_{backup_id}/
BACKUP_PATH_TEMPLATE = "tenants/{tenant_id}/backups/{year}/{month}/{day}/backup_{backup_id}"

# Nombres de archivos dentro del backup
BACKUP_DATA_FILENAME = 'data.json'
BACKUP_MANIFEST_FILENAME = 'manifest.json'
BACKUP_ZIP_FILENAME = 'backup.zip'

# ============================================================================
# LÍMITES Y CONFIGURACIONES
# ============================================================================

# Rate limiting
MAX_BACKUPS_PER_HOUR = 5
MAX_BACKUPS_PER_DAY = 20

# Tamaños
MAX_BACKUP_SIZE_MB = 500  # 500 MB por backup
MAX_BACKUP_SIZE_BYTES = MAX_BACKUP_SIZE_MB * 1024 * 1024

# Retención
DEFAULT_RETENTION_DAYS = 30
MIN_RETENTION_DAYS = 7
MAX_RETENTION_DAYS = 365

# Expiración de URLs firmadas
DEFAULT_SIGNED_URL_EXPIRATION = 3600  # 1 hora en segundos
MAX_SIGNED_URL_EXPIRATION = 86400  # 24 horas en segundos

# ============================================================================
# ACCIONES DE AUDITORÍA
# ============================================================================

AUDIT_ACTION_REQUESTED = 'backup_requested'
AUDIT_ACTION_STARTED = 'backup_started'
AUDIT_ACTION_COMPLETED = 'backup_completed'
AUDIT_ACTION_FAILED = 'backup_failed'
AUDIT_ACTION_DOWNLOADED = 'backup_downloaded'
AUDIT_ACTION_DELETED = 'backup_deleted'
AUDIT_ACTION_EXPIRED = 'backup_expired'
AUDIT_ACTION_RESTORE_STARTED = 'restore_started'
AUDIT_ACTION_RESTORE_COMPLETED = 'restore_completed'
AUDIT_ACTION_RESTORE_FAILED = 'restore_failed'
AUDIT_ACTION_ACCESS_DENIED = 'backup_access_denied'
AUDIT_ACTION_UNAUTHORIZED = 'backup_unauthorized_attempt'

AUDIT_ACTIONS = [
    (AUDIT_ACTION_REQUESTED, 'Backup Solicitado'),
    (AUDIT_ACTION_STARTED, 'Backup Iniciado'),
    (AUDIT_ACTION_COMPLETED, 'Backup Completado'),
    (AUDIT_ACTION_FAILED, 'Backup Fallido'),
    (AUDIT_ACTION_DOWNLOADED, 'Backup Descargado'),
    (AUDIT_ACTION_DELETED, 'Backup Eliminado'),
    (AUDIT_ACTION_EXPIRED, 'Backup Expirado'),
    (AUDIT_ACTION_RESTORE_STARTED, 'Restauración Iniciada'),
    (AUDIT_ACTION_RESTORE_COMPLETED, 'Restauración Completada'),
    (AUDIT_ACTION_RESTORE_FAILED, 'Restauración Fallida'),
    (AUDIT_ACTION_ACCESS_DENIED, 'Acceso Denegado'),
    (AUDIT_ACTION_UNAUTHORIZED, 'Intento No Autorizado'),
]

# ============================================================================
# SEVERIDADES DE AUDITORÍA
# ============================================================================

AUDIT_SEVERITY_INFO = 'info'
AUDIT_SEVERITY_WARNING = 'warning'
AUDIT_SEVERITY_ERROR = 'error'
AUDIT_SEVERITY_CRITICAL = 'critical'

AUDIT_SEVERITIES = [
    (AUDIT_SEVERITY_INFO, 'Información'),
    (AUDIT_SEVERITY_WARNING, 'Advertencia'),
    (AUDIT_SEVERITY_ERROR, 'Error'),
    (AUDIT_SEVERITY_CRITICAL, 'Crítico'),
]

# ============================================================================
# HELPERS
# ============================================================================

def build_backup_path(tenant_id: int, backup_id: int, timestamp: datetime = None) -> str:
    """
    Construye la ruta completa de un backup en Storage.
    
    Args:
        tenant_id: ID del tenant
        backup_id: ID del backup
        timestamp: Fecha/hora del backup (default: ahora)
        
    Returns:
        Ruta completa del backup
        
    Example:
        >>> build_backup_path(1, 42)
        'tenants/1/backups/2026/05/06/backup_42'
    """
    if timestamp is None:
        timestamp = datetime.now()
    
    return BACKUP_PATH_TEMPLATE.format(
        tenant_id=tenant_id,
        year=timestamp.year,
        month=f"{timestamp.month:02d}",
        day=f"{timestamp.day:02d}",
        backup_id=backup_id
    )


def build_backup_data_path(tenant_id: int, backup_id: int, timestamp: datetime = None) -> str:
    """
    Construye la ruta completa del archivo data.json.
    
    Args:
        tenant_id: ID del tenant
        backup_id: ID del backup
        timestamp: Fecha/hora del backup (default: ahora)
        
    Returns:
        Ruta completa del archivo data.json
        
    Example:
        >>> build_backup_data_path(1, 42)
        'tenants/1/backups/2026/05/06/backup_42/data.json'
    """
    base_path = build_backup_path(tenant_id, backup_id, timestamp)
    return f"{base_path}/{BACKUP_DATA_FILENAME}"


def build_backup_manifest_path(tenant_id: int, backup_id: int, timestamp: datetime = None) -> str:
    """
    Construye la ruta completa del archivo manifest.json.
    
    Args:
        tenant_id: ID del tenant
        backup_id: ID del backup
        timestamp: Fecha/hora del backup (default: ahora)
        
    Returns:
        Ruta completa del archivo manifest.json
        
    Example:
        >>> build_backup_manifest_path(1, 42)
        'tenants/1/backups/2026/05/06/backup_42/manifest.json'
    """
    base_path = build_backup_path(tenant_id, backup_id, timestamp)
    return f"{base_path}/{BACKUP_MANIFEST_FILENAME}"


def build_backup_zip_path(tenant_id: int, backup_id: int, timestamp: datetime = None) -> str:
    """
    Construye la ruta completa del archivo backup.zip.
    
    Args:
        tenant_id: ID del tenant
        backup_id: ID del backup
        timestamp: Fecha/hora del backup (default: ahora)
        
    Returns:
        Ruta completa del archivo backup.zip
        
    Example:
        >>> build_backup_zip_path(1, 42)
        'tenants/1/backups/2026/05/06/backup_42/backup.zip'
    """
    base_path = build_backup_path(tenant_id, backup_id, timestamp)
    return f"{base_path}/{BACKUP_ZIP_FILENAME}"


def get_backup_type_label(backup_type: str) -> str:
    """
    Obtiene la etiqueta legible de un tipo de backup.
    
    Args:
        backup_type: Tipo de backup
        
    Returns:
        Etiqueta legible
    """
    for value, label in BACKUP_TYPES:
        if value == backup_type:
            return label
    return backup_type


def get_backup_status_label(status: str) -> str:
    """
    Obtiene la etiqueta legible de un estado de backup.
    
    Args:
        status: Estado del backup
        
    Returns:
        Etiqueta legible
    """
    for value, label in BACKUP_STATUSES:
        if value == status:
            return label
    return status


def is_backup_type_valid(backup_type: str) -> bool:
    """
    Verifica si un tipo de backup es válido.
    
    Args:
        backup_type: Tipo de backup a validar
        
    Returns:
        True si es válido, False si no
    """
    return backup_type in [value for value, _ in BACKUP_TYPES]


def is_backup_status_valid(status: str) -> bool:
    """
    Verifica si un estado de backup es válido.
    
    Args:
        status: Estado a validar
        
    Returns:
        True si es válido, False si no
    """
    return status in [value for value, _ in BACKUP_STATUSES]


def format_backup_size(size_bytes: int) -> str:
    """
    Formatea un tamaño de backup en bytes a formato legible.
    
    Args:
        size_bytes: Tamaño en bytes
        
    Returns:
        String formateado (ej: "5.2 MB")
    """
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"
