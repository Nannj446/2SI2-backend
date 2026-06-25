"""
Mapeo de nombres de columnas técnicos a etiquetas amigables en español.

Autor: Sistema FinCore
Fecha: 2026-05-11
"""

# Mapeo global de columnas comunes
COMMON_COLUMN_LABELS = {
    'id': 'ID',
    'created_at': 'Fecha de Creación',
    'updated_at': 'Fecha de Actualización',
    'is_active': 'Activo',
    'status': 'Estado',
    'name': 'Nombre',
    'code': 'Código',
    'description': 'Descripción',
}

# Mapeo específico por tipo de reporte
REPORT_COLUMN_LABELS = {
    'clients': {
        'id': 'ID',
        'full_name': 'Nombre Completo',
        'document_number': 'Número de Documento',
        'email': 'Correo Electrónico',
        'status': 'Estado',
        'kyc_status': 'Estado KYC',
        'risk_level': 'Nivel de Riesgo',
        'monthly_income': 'Ingreso Mensual (Bs)',
        'city': 'Ciudad',
        'created_at': 'Fecha de Registro',
    },
    'products': {
        'id': 'ID',
        'name': 'Nombre del Producto',
        'code': 'Código',
        'product_type': 'Tipo de Producto',
        'status': 'Estado',
        'min_amount': 'Monto Mínimo (Bs)',
        'max_amount': 'Monto Máximo (Bs)',
        'min_interest_rate': 'Tasa Mínima (%)',
        'max_interest_rate': 'Tasa Máxima (%)',
        'interest_type': 'Tipo de Tasa',
        'min_term_months': 'Plazo Mínimo (meses)',
        'max_term_months': 'Plazo Máximo (meses)',
        'created_at': 'Fecha de Creación',
    },
    'applications': {
        'id': 'ID',
        'application_number': 'Número de Solicitud',
        'client_name': 'Cliente',
        'client_document': 'Documento del Cliente',
        'product_name': 'Producto',
        'status': 'Estado',
        'requested_amount': 'Monto Solicitado (Bs)',
        'approved_amount': 'Monto Aprobado (Bs)',
        'term_months': 'Plazo (meses)',
        'risk_level': 'Nivel de Riesgo',
        'branch': 'Sucursal',
        'assigned_to': 'Asignado a',
        'created_at': 'Fecha de Creación',
        'submitted_at': 'Fecha de Envío',
        'approved_at': 'Fecha de Aprobación',
    },
    'audit': {
        'id': 'ID',
        'user': 'Usuario',
        'action': 'Acción',
        'resource_type': 'Tipo de Recurso',
        'resource_id': 'ID del Recurso',
        'description': 'Descripción',
        'severity': 'Severidad',
        'ip_address': 'Dirección IP',
        'timestamp': 'Fecha y Hora',
    },
    'users': {
        'id': 'ID',
        'full_name': 'Nombre Completo',
        'email': 'Correo Electrónico',
        'role': 'Rol',
        'is_active': 'Activo',
        'date_joined': 'Fecha de Registro',
        'last_login': 'Último Acceso',
    },
    'branches': {
        'id': 'ID',
        'name': 'Nombre',
        'city': 'Ciudad',
        'address': 'Dirección',
        'is_active': 'Activo',
        'applications_count': 'Número de Solicitudes',
        'users_count': 'Número de Usuarios',
        'created_at': 'Fecha de Creación',
    },
}


def get_column_label(report_type, column_name):
    """
    Obtiene la etiqueta amigable para una columna.
    
    Args:
        report_type: Tipo de reporte
        column_name: Nombre técnico de la columna
    
    Returns:
        str: Etiqueta amigable en español
    """
    # Buscar en mapeo específico del reporte
    if report_type in REPORT_COLUMN_LABELS:
        if column_name in REPORT_COLUMN_LABELS[report_type]:
            return REPORT_COLUMN_LABELS[report_type][column_name]
    
    # Buscar en mapeo común
    if column_name in COMMON_COLUMN_LABELS:
        return COMMON_COLUMN_LABELS[column_name]
    
    # Fallback: capitalizar y reemplazar guiones bajos
    return column_name.replace('_', ' ').title()


def get_all_labels_for_report(report_type):
    """
    Obtiene todos los labels para un tipo de reporte.
    
    Args:
        report_type: Tipo de reporte
    
    Returns:
        dict: Diccionario con mapeo de columnas a labels
    """
    return REPORT_COLUMN_LABELS.get(report_type, {})


def translate_row_keys(report_type, row):
    """
    Traduce las claves de un diccionario de fila a español.
    
    Args:
        report_type: Tipo de reporte
        row: Diccionario con datos de la fila
    
    Returns:
        dict: Diccionario con claves traducidas
    """
    translated = {}
    for key, value in row.items():
        label = get_column_label(report_type, key)
        translated[label] = value
    return translated


def get_ordered_columns(report_type):
    """
    Obtiene el orden de columnas para un tipo de reporte.
    
    Args:
        report_type: Tipo de reporte
    
    Returns:
        list: Lista de nombres de columnas en orden
    """
    if report_type in REPORT_COLUMN_LABELS:
        return list(REPORT_COLUMN_LABELS[report_type].keys())
    return []

