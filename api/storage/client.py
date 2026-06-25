"""
Cliente singleton de Supabase para operaciones de Storage.
"""
from supabase import create_client, Client
from django.conf import settings
from typing import Optional
import logging

logger = logging.getLogger(__name__)

_supabase_client: Optional[Client] = None


def get_supabase_client() -> Client:
    """
    Obtiene instancia singleton del cliente de Supabase.
    
    Returns:
        Cliente de Supabase configurado con service_role_key
    
    Raises:
        ValueError: Si las credenciales de Supabase no están configuradas
    """
    global _supabase_client
    
    if _supabase_client is None:
        # Validar que las credenciales estén configuradas
        if not settings.SUPABASE_URL:
            raise ValueError(
                "SUPABASE_URL no está configurado. "
                "Verifica tu archivo .env"
            )
        
        if not settings.SUPABASE_SERVICE_ROLE_KEY:
            raise ValueError(
                "SUPABASE_SERVICE_ROLE_KEY no está configurado. "
                "Verifica tu archivo .env"
            )
        
        logger.info("Inicializando cliente de Supabase...")
        
        _supabase_client = create_client(
            supabase_url=settings.SUPABASE_URL,
            supabase_key=settings.SUPABASE_SERVICE_ROLE_KEY
        )
        
        logger.info("Cliente de Supabase inicializado correctamente")
    
    return _supabase_client


def reset_supabase_client():
    """
    Resetea el cliente singleton.
    
    Útil para tests o cuando se necesita reinicializar la conexión.
    """
    global _supabase_client
    _supabase_client = None
    logger.info("Cliente de Supabase reseteado")
