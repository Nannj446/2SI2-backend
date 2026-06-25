"""
Rate limiting para el módulo de reportes.

Implementa throttling para prevenir abuso de recursos:
- Generación de reportes
- Interpretación de voz
- Exportación de archivos
"""
from rest_framework.throttling import UserRateThrottle, AnonRateThrottle


class ReportGenerationThrottle(UserRateThrottle):
    """
    Rate limit para generación de reportes.
    
    Límites:
    - Usuarios autenticados: 30 reportes por hora
    - Usuarios anónimos: 0 (no permitido)
    """
    scope = 'report_generation'
    rate = '30/hour'


class ReportPreviewThrottle(UserRateThrottle):
    """
    Rate limit para vista previa de reportes.
    
    Límites:
    - Usuarios autenticados: 60 vistas previas por hora
    - Usuarios anónimos: 0 (no permitido)
    """
    scope = 'report_preview'
    rate = '60/hour'


class VoiceInterpretationThrottle(UserRateThrottle):
    """
    Rate limit para interpretación de voz.
    
    Límites:
    - Usuarios autenticados: 20 interpretaciones por hora
    - Usuarios anónimos: 0 (no permitido)
    
    Nota: Más restrictivo debido al costo de la API de Groq
    """
    scope = 'voice_interpretation'
    rate = '20/hour'


class ReportDownloadThrottle(UserRateThrottle):
    """
    Rate limit para descarga de reportes.
    
    Límites:
    - Usuarios autenticados: 100 descargas por hora
    - Usuarios anónimos: 0 (no permitido)
    """
    scope = 'report_download'
    rate = '100/hour'


class ReportCatalogThrottle(UserRateThrottle):
    """
    Rate limit para consulta de catálogo.
    
    Límites:
    - Usuarios autenticados: 120 consultas por hora
    - Usuarios anónimos: 0 (no permitido)
    """
    scope = 'report_catalog'
    rate = '120/hour'


# Throttles para usuarios SaaS Admin (más permisivos)
class SaaSReportGenerationThrottle(UserRateThrottle):
    """
    Rate limit para generación de reportes SAAS.
    
    Límites más permisivos para administradores SaaS.
    """
    scope = 'saas_report_generation'
    rate = '100/hour'


class SaaSVoiceInterpretationThrottle(UserRateThrottle):
    """
    Rate limit para interpretación de voz SAAS.
    
    Límites más permisivos para administradores SaaS.
    """
    scope = 'saas_voice_interpretation'
    rate = '50/hour'
