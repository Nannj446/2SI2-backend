"""
Constantes para el sistema de almacenamiento de archivos.
Define categorías, tipos de recursos y validaciones.
"""

# ============================================================================
# TIPOS DE RECURSOS (resource_type)
# ============================================================================

RESOURCE_TYPE_BRANDING = 'branding'
RESOURCE_TYPE_CUSTOMER_DOCUMENT = 'customer_document'
RESOURCE_TYPE_LOAN_DOCUMENT = 'loan_document'
RESOURCE_TYPE_GENERAL = 'general'

RESOURCE_TYPES = [
    (RESOURCE_TYPE_BRANDING, 'Branding'),
    (RESOURCE_TYPE_CUSTOMER_DOCUMENT, 'Documento de Cliente'),
    (RESOURCE_TYPE_LOAN_DOCUMENT, 'Documento de Crédito'),
    (RESOURCE_TYPE_GENERAL, 'General'),
]

# ============================================================================
# CATEGORÍAS DE BRANDING
# ============================================================================

BRANDING_LOGO = 'logo'
BRANDING_FAVICON = 'favicon'
BRANDING_COVER = 'cover'

BRANDING_CATEGORIES = [
    BRANDING_LOGO,
    BRANDING_FAVICON,
    BRANDING_COVER,
]

# ============================================================================
# CATEGORÍAS DE DOCUMENTOS DE CLIENTES
# ============================================================================

# Documentos de identidad
CUSTOMER_IDENTITY_FRONT = 'identity_front'
CUSTOMER_IDENTITY_BACK = 'identity_back'
CUSTOMER_IDENTITY_SELFIE = 'identity_selfie'

# Documentos de ingresos
CUSTOMER_INCOME_PROOF = 'income_proof'
CUSTOMER_BANK_STATEMENT = 'bank_statement'
CUSTOMER_TAX_RETURN = 'tax_return'

# Documentos de garantía
CUSTOMER_COLLATERAL_DEED = 'collateral_deed'
CUSTOMER_COLLATERAL_PHOTO = 'collateral_photo'
CUSTOMER_COLLATERAL_APPRAISAL = 'collateral_appraisal'

# Otros documentos
CUSTOMER_PROOF_OF_ADDRESS = 'proof_of_address'
CUSTOMER_REFERENCE_LETTER = 'reference_letter'
CUSTOMER_OTHER = 'other'

CUSTOMER_DOCUMENT_CATEGORIES = [
    # Identidad
    (CUSTOMER_IDENTITY_FRONT, 'Identificación (Frente)'),
    (CUSTOMER_IDENTITY_BACK, 'Identificación (Reverso)'),
    (CUSTOMER_IDENTITY_SELFIE, 'Selfie con Identificación'),
    
    # Ingresos
    (CUSTOMER_INCOME_PROOF, 'Comprobante de Ingresos'),
    (CUSTOMER_BANK_STATEMENT, 'Estado de Cuenta Bancario'),
    (CUSTOMER_TAX_RETURN, 'Declaración de Impuestos'),
    
    # Garantía
    (CUSTOMER_COLLATERAL_DEED, 'Escritura de Garantía'),
    (CUSTOMER_COLLATERAL_PHOTO, 'Foto de Garantía'),
    (CUSTOMER_COLLATERAL_APPRAISAL, 'Avalúo de Garantía'),
    
    # Otros
    (CUSTOMER_PROOF_OF_ADDRESS, 'Comprobante de Domicilio'),
    (CUSTOMER_REFERENCE_LETTER, 'Carta de Referencia'),
    (CUSTOMER_OTHER, 'Otro Documento'),
]

# ============================================================================
# CATEGORÍAS DE DOCUMENTOS DE CRÉDITOS
# ============================================================================

# Solicitud
LOAN_APPLICATION = 'application'
LOAN_APPLICATION_FORM = 'application_form'

# Contratos
LOAN_CONTRACT_TEMPLATE = 'contract_template'
LOAN_CONTRACT_GENERATED = 'contract_generated'
LOAN_CONTRACT_SIGNED = 'contract_signed'

# Pagarés
LOAN_PROMISSORY_NOTE = 'promissory_note'
LOAN_PROMISSORY_NOTE_SIGNED = 'promissory_note_signed'

# Pagos
LOAN_PAYMENT_RECEIPT = 'payment_receipt'
LOAN_PAYMENT_PROOF = 'payment_proof'

# Garantías
LOAN_COLLATERAL_DOCUMENT = 'collateral_document'
LOAN_COLLATERAL_INSURANCE = 'collateral_insurance'

# Otros
LOAN_AMENDMENT = 'amendment'
LOAN_RESTRUCTURING = 'restructuring'
LOAN_LEGAL_NOTICE = 'legal_notice'
LOAN_OTHER = 'other'

LOAN_DOCUMENT_CATEGORIES = [
    # Solicitud
    (LOAN_APPLICATION, 'Solicitud de Crédito'),
    (LOAN_APPLICATION_FORM, 'Formulario de Solicitud'),
    
    # Contratos
    (LOAN_CONTRACT_TEMPLATE, 'Plantilla de Contrato'),
    (LOAN_CONTRACT_GENERATED, 'Contrato Generado'),
    (LOAN_CONTRACT_SIGNED, 'Contrato Firmado'),
    
    # Pagarés
    (LOAN_PROMISSORY_NOTE, 'Pagaré'),
    (LOAN_PROMISSORY_NOTE_SIGNED, 'Pagaré Firmado'),
    
    # Pagos
    (LOAN_PAYMENT_RECEIPT, 'Recibo de Pago'),
    (LOAN_PAYMENT_PROOF, 'Comprobante de Pago'),
    
    # Garantías
    (LOAN_COLLATERAL_DOCUMENT, 'Documento de Garantía'),
    (LOAN_COLLATERAL_INSURANCE, 'Seguro de Garantía'),
    
    # Otros
    (LOAN_AMENDMENT, 'Modificación de Contrato'),
    (LOAN_RESTRUCTURING, 'Reestructuración'),
    (LOAN_LEGAL_NOTICE, 'Notificación Legal'),
    (LOAN_OTHER, 'Otro Documento'),
]

# ============================================================================
# VALIDACIONES POR CATEGORÍA
# ============================================================================

# Tipos MIME permitidos
IMAGE_MIME_TYPES = [
    'image/jpeg',
    'image/jpg',
    'image/png',
    'image/webp',
    'image/svg+xml',
]

PDF_MIME_TYPES = [
    'application/pdf',
]

DOCUMENT_MIME_TYPES = [
    'application/pdf',
    'application/msword',  # .doc
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',  # .docx
    'application/vnd.ms-excel',  # .xls
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',  # .xlsx
]

AUDIO_MIME_TYPES = [
    'audio/mpeg',      # MP3
    'audio/mp3',       # MP3 (alternativo)
    'audio/wav',       # WAV
    'audio/x-wav',     # WAV (alternativo)
    'audio/wave',      # WAV (alternativo)
    'audio/x-m4a',     # M4A
    'audio/mp4',       # M4A/MP4
    'audio/ogg',       # OGG
    'audio/webm',      # WebM (usado por navegadores modernos)
]

ALL_DOCUMENT_MIME_TYPES = IMAGE_MIME_TYPES + DOCUMENT_MIME_TYPES

# Tamaños máximos (en bytes)
SIZE_1MB = 1 * 1024 * 1024
SIZE_5MB = 5 * 1024 * 1024
SIZE_10MB = 10 * 1024 * 1024
SIZE_20MB = 20 * 1024 * 1024

# Validaciones por categoría
CATEGORY_VALIDATIONS = {
    # Branding
    BRANDING_LOGO: {
        'allowed_types': IMAGE_MIME_TYPES,
        'max_size': SIZE_5MB,
        'description': 'Logo de la institución (PNG, JPG, WEBP, SVG)',
    },
    BRANDING_FAVICON: {
        'allowed_types': IMAGE_MIME_TYPES,
        'max_size': SIZE_1MB,
        'description': 'Favicon (PNG, JPG, WEBP, SVG)',
    },
    BRANDING_COVER: {
        'allowed_types': IMAGE_MIME_TYPES,
        'max_size': SIZE_10MB,
        'description': 'Imagen de portada (PNG, JPG, WEBP)',
    },
    
    # Documentos de identidad (solo imágenes)
    CUSTOMER_IDENTITY_FRONT: {
        'allowed_types': IMAGE_MIME_TYPES,
        'max_size': SIZE_5MB,
        'description': 'Foto del frente de la identificación',
    },
    CUSTOMER_IDENTITY_BACK: {
        'allowed_types': IMAGE_MIME_TYPES,
        'max_size': SIZE_5MB,
        'description': 'Foto del reverso de la identificación',
    },
    CUSTOMER_IDENTITY_SELFIE: {
        'allowed_types': IMAGE_MIME_TYPES,
        'max_size': SIZE_5MB,
        'description': 'Selfie con identificación',
    },
    
    # Documentos de ingresos (imágenes o PDFs)
    CUSTOMER_INCOME_PROOF: {
        'allowed_types': ALL_DOCUMENT_MIME_TYPES,
        'max_size': SIZE_10MB,
        'description': 'Comprobante de ingresos (PDF, imagen o documento)',
    },
    CUSTOMER_BANK_STATEMENT: {
        'allowed_types': ALL_DOCUMENT_MIME_TYPES,
        'max_size': SIZE_10MB,
        'description': 'Estado de cuenta bancario',
    },
    CUSTOMER_TAX_RETURN: {
        'allowed_types': ALL_DOCUMENT_MIME_TYPES,
        'max_size': SIZE_10MB,
        'description': 'Declaración de impuestos',
    },
    
    # Documentos de garantía
    CUSTOMER_COLLATERAL_DEED: {
        'allowed_types': ALL_DOCUMENT_MIME_TYPES,
        'max_size': SIZE_20MB,
        'description': 'Escritura de garantía',
    },
    CUSTOMER_COLLATERAL_PHOTO: {
        'allowed_types': IMAGE_MIME_TYPES,
        'max_size': SIZE_10MB,
        'description': 'Foto de la garantía',
    },
    CUSTOMER_COLLATERAL_APPRAISAL: {
        'allowed_types': ALL_DOCUMENT_MIME_TYPES,
        'max_size': SIZE_10MB,
        'description': 'Avalúo de la garantía',
    },
    
    # Otros documentos de cliente
    CUSTOMER_PROOF_OF_ADDRESS: {
        'allowed_types': ALL_DOCUMENT_MIME_TYPES,
        'max_size': SIZE_5MB,
        'description': 'Comprobante de domicilio',
    },
    CUSTOMER_REFERENCE_LETTER: {
        'allowed_types': ALL_DOCUMENT_MIME_TYPES,
        'max_size': SIZE_5MB,
        'description': 'Carta de referencia',
    },
    CUSTOMER_OTHER: {
        'allowed_types': ALL_DOCUMENT_MIME_TYPES,
        'max_size': SIZE_10MB,
        'description': 'Otro documento del cliente',
    },
    
    # Documentos de crédito (principalmente PDFs)
    LOAN_APPLICATION: {
        'allowed_types': PDF_MIME_TYPES,
        'max_size': SIZE_10MB,
        'description': 'Solicitud de crédito (PDF)',
    },
    LOAN_APPLICATION_FORM: {
        'allowed_types': ALL_DOCUMENT_MIME_TYPES,
        'max_size': SIZE_10MB,
        'description': 'Formulario de solicitud',
    },
    LOAN_CONTRACT_TEMPLATE: {
        'allowed_types': DOCUMENT_MIME_TYPES,
        'max_size': SIZE_5MB,
        'description': 'Plantilla de contrato',
    },
    LOAN_CONTRACT_GENERATED: {
        'allowed_types': PDF_MIME_TYPES,
        'max_size': SIZE_10MB,
        'description': 'Contrato generado (PDF)',
    },
    LOAN_CONTRACT_SIGNED: {
        'allowed_types': PDF_MIME_TYPES,
        'max_size': SIZE_20MB,
        'description': 'Contrato firmado (PDF)',
    },
    LOAN_PROMISSORY_NOTE: {
        'allowed_types': PDF_MIME_TYPES,
        'max_size': SIZE_5MB,
        'description': 'Pagaré (PDF)',
    },
    LOAN_PROMISSORY_NOTE_SIGNED: {
        'allowed_types': PDF_MIME_TYPES,
        'max_size': SIZE_10MB,
        'description': 'Pagaré firmado (PDF)',
    },
    LOAN_PAYMENT_RECEIPT: {
        'allowed_types': ALL_DOCUMENT_MIME_TYPES,
        'max_size': SIZE_5MB,
        'description': 'Recibo de pago',
    },
    LOAN_PAYMENT_PROOF: {
        'allowed_types': ALL_DOCUMENT_MIME_TYPES,
        'max_size': SIZE_5MB,
        'description': 'Comprobante de pago',
    },
    LOAN_COLLATERAL_DOCUMENT: {
        'allowed_types': ALL_DOCUMENT_MIME_TYPES,
        'max_size': SIZE_20MB,
        'description': 'Documento de garantía',
    },
    LOAN_COLLATERAL_INSURANCE: {
        'allowed_types': ALL_DOCUMENT_MIME_TYPES,
        'max_size': SIZE_10MB,
        'description': 'Seguro de garantía',
    },
    LOAN_AMENDMENT: {
        'allowed_types': PDF_MIME_TYPES,
        'max_size': SIZE_10MB,
        'description': 'Modificación de contrato (PDF)',
    },
    LOAN_RESTRUCTURING: {
        'allowed_types': PDF_MIME_TYPES,
        'max_size': SIZE_10MB,
        'description': 'Documento de reestructuración (PDF)',
    },
    LOAN_LEGAL_NOTICE: {
        'allowed_types': PDF_MIME_TYPES,
        'max_size': SIZE_5MB,
        'description': 'Notificación legal (PDF)',
    },
    LOAN_OTHER: {
        'allowed_types': ALL_DOCUMENT_MIME_TYPES,
        'max_size': SIZE_10MB,
        'description': 'Otro documento del crédito',
    },
}

# ============================================================================
# HELPERS
# ============================================================================

def get_validation_rules(category: str) -> dict:
    """
    Obtiene las reglas de validación para una categoría específica.
    
    Args:
        category: Categoría del archivo
        
    Returns:
        Dict con allowed_types, max_size y description
        
    Raises:
        ValueError: Si la categoría no existe
    """
    if category not in CATEGORY_VALIDATIONS:
        raise ValueError(f'Categoría inválida: {category}')
    
    return CATEGORY_VALIDATIONS[category]


def is_valid_category(resource_type: str, category: str) -> bool:
    """
    Verifica si una categoría es válida para un tipo de recurso.
    
    Args:
        resource_type: Tipo de recurso (branding, customer_document, etc.)
        category: Categoría a validar
        
    Returns:
        True si la categoría es válida para el tipo de recurso
    """
    if resource_type == RESOURCE_TYPE_BRANDING:
        return category in BRANDING_CATEGORIES
    elif resource_type == RESOURCE_TYPE_CUSTOMER_DOCUMENT:
        return category in [cat[0] for cat in CUSTOMER_DOCUMENT_CATEGORIES]
    elif resource_type == RESOURCE_TYPE_LOAN_DOCUMENT:
        return category in [cat[0] for cat in LOAN_DOCUMENT_CATEGORIES]
    elif resource_type == RESOURCE_TYPE_GENERAL:
        return True  # General acepta cualquier categoría
    
    return False


def get_categories_for_resource_type(resource_type: str) -> list:
    """
    Obtiene las categorías disponibles para un tipo de recurso.
    
    Args:
        resource_type: Tipo de recurso
        
    Returns:
        Lista de tuplas (value, label) con las categorías disponibles
    """
    if resource_type == RESOURCE_TYPE_BRANDING:
        return [(cat, cat.replace('_', ' ').title()) for cat in BRANDING_CATEGORIES]
    elif resource_type == RESOURCE_TYPE_CUSTOMER_DOCUMENT:
        return CUSTOMER_DOCUMENT_CATEGORIES
    elif resource_type == RESOURCE_TYPE_LOAN_DOCUMENT:
        return LOAN_DOCUMENT_CATEGORIES
    elif resource_type == RESOURCE_TYPE_GENERAL:
        return [('general', 'General')]
    
    return []


def format_file_size(size_bytes: int) -> str:
    """
    Formatea un tamaño de archivo en bytes a formato legible.
    
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
# ============================================================================
# MAPA DE EXTENSIONES A TIPOS MIME (FALLBACK CUANDO MAGIC NO ESTÁ DISPONIBLE)
# ============================================================================

EXTENSION_TO_MIME = {
    # Imágenes
    'jpg': 'image/jpeg',
    'jpeg': 'image/jpeg',
    'png': 'image/png',
    'webp': 'image/webp',
    'svg': 'image/svg+xml',
    'gif': 'image/gif',
    'bmp': 'image/bmp',
    'tiff': 'image/tiff',
    'tif': 'image/tiff',
    # Documentos
    'pdf': 'application/pdf',
    'doc': 'application/msword',
    'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'xls': 'application/vnd.ms-excel',
    'xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    # Audio
    'mp3': 'audio/mpeg',
    'wav': 'audio/wav',
    'm4a': 'audio/x-m4a',
    'ogg': 'audio/ogg',
    'webm': 'audio/webm',
    'oga': 'audio/ogg',
    # Otros
    'txt': 'text/plain',
    'csv': 'text/csv',
    'json': 'application/json',
    'xml': 'application/xml',
    'zip': 'application/zip',
}