"""
Cliente para integración con GroqCloud API.

Proporciona métodos seguros para:
- Speech-to-Text (transcripción de audio)
- Chat Completions (interpretación de intenciones)
"""
import os
import json
import logging
import requests
from typing import Dict, Any
from django.conf import settings

from .circuit_breaker import groq_transcription_breaker, groq_chat_breaker

logger = logging.getLogger(__name__)


class GroqClient:
    """
    Cliente para GroqCloud API.
    
    Maneja autenticación, reintentos y manejo de errores
    para las APIs de Groq.
    """
    
    BASE_URL = "https://api.groq.com/openai/v1"
    
    # Modelos disponibles
    TRANSCRIPTION_MODEL = "whisper-large-v3"
    CHAT_MODEL = "llama-3.3-70b-versatile"
    
    # Límites
    MAX_AUDIO_SIZE_MB = 25
    MAX_AUDIO_DURATION_SECONDS = 300  # 5 minutos
    
    # Timeouts
    TRANSCRIPTION_TIMEOUT = 30  # segundos
    CHAT_TIMEOUT = 15  # segundos
    
    # Reintentos
    MAX_RETRIES = 3
    RETRY_DELAY = 2  # segundos
    
    def __init__(self):
        """Inicializa el cliente Groq."""
        self.api_key = self._get_api_key()
        self.transcription_model = os.getenv(
            'GROQ_TRANSCRIPTION_MODEL',
            self.TRANSCRIPTION_MODEL
        )
        self.chat_model = os.getenv(
            'GROQ_CHAT_MODEL',
            self.CHAT_MODEL
        )
    
    def _get_api_key(self) -> str:
        """Obtiene API key de forma segura."""
        api_key = os.getenv('GROQ_API_KEY')
        if not api_key:
            raise ValueError(
                "GROQ_API_KEY no configurada. "
                "Agregar a variables de entorno."
            )
        return api_key
    
    def transcribe_audio(
        self,
        audio_file_path: str,
        language: str = 'es'
    ) -> Dict[str, Any]:
        """
        Transcribe audio a texto usando Groq Speech-to-Text.
        
        Args:
            audio_file_path: Ruta al archivo de audio
            language: Código de idioma (es, en, etc.)
        
        Returns:
            {
                'text': 'transcripción del audio',
                'language': 'es',
                'duration': 12.5,
                'model': 'whisper-large-v3'
            }
        
        Raises:
            GroqAPIError: Si falla la transcripción
        """
        # Usar circuit breaker para proteger la llamada
        return groq_transcription_breaker.call(
            self._transcribe_audio_internal,
            audio_file_path,
            language
        )
    
    def _transcribe_audio_internal(
        self,
        audio_file_path: str,
        language: str = 'es'
    ) -> Dict[str, Any]:
        """Implementación interna de transcripción (protegida por circuit breaker)."""
        logger.info(f"Transcribiendo audio: {audio_file_path}")
        
        # Validar tamaño del archivo
        file_size_mb = os.path.getsize(audio_file_path) / (1024 * 1024)
        if file_size_mb > self.MAX_AUDIO_SIZE_MB:
            raise ValueError(
                f"Archivo de audio muy grande: {file_size_mb:.2f}MB. "
                f"Máximo permitido: {self.MAX_AUDIO_SIZE_MB}MB"
            )
        
        url = f"{self.BASE_URL}/audio/transcriptions"
        
        headers = {
            'Authorization': f'Bearer {self.api_key}'
        }
        
        with open(audio_file_path, 'rb') as audio_file:
            files = {
                'file': audio_file
            }
            
            data = {
                'model': self.transcription_model,
                'language': language,
                'response_format': 'verbose_json'
            }
            
            try:
                response = requests.post(
                    url,
                    headers=headers,
                    files=files,
                    data=data,
                    timeout=self.TRANSCRIPTION_TIMEOUT
                )
                
                response.raise_for_status()
                result = response.json()
                
                logger.info("Transcripción exitosa")
                
                return {
                    'text': result.get('text', ''),
                    'language': result.get('language', language),
                    'duration': result.get('duration', 0),
                    'model': self.transcription_model
                }
            
            except requests.exceptions.Timeout:
                logger.error("Timeout en transcripción")
                raise GroqAPIError("Timeout al transcribir audio")
            
            except requests.exceptions.HTTPError as e:
                logger.error(f"Error HTTP en transcripción: {e}")
                self._handle_http_error(e.response)
            
            except Exception as e:
                logger.error(f"Error inesperado en transcripción: {e}")
                raise GroqAPIError(f"Error al transcribir audio: {str(e)}")
    
    def interpret_intent(
        self,
        transcription: str,
        user_scope: str,
        available_categories: list
    ) -> Dict[str, Any]:
        """
        Interpreta intención de reporte desde transcripción.
        
        Args:
            transcription: Texto transcrito del audio
            user_scope: TENANT o SAAS
            available_categories: Categorías disponibles para el usuario
        
        Returns:
            {
                'confidence': 0.95,
                'scope': 'TENANT',
                'category': 'CREDITS',
                'report_type': 'loans_by_status',
                'date_range': {...},
                'filters': [...],
                'columns': [...],
                'group_by': [...],
                'sort': [...],
                'format': 'xlsx',
                'missing_fields': [],
                'unsupported_terms': [],
                'interpretation_notes': '...'
            }
        
        Raises:
            GroqAPIError: Si falla la interpretación
        """
        # Usar circuit breaker para proteger la llamada
        return groq_chat_breaker.call(
            self._interpret_intent_internal,
            transcription,
            user_scope,
            available_categories
        )
    
    def _interpret_intent_internal(
        self,
        transcription: str,
        user_scope: str,
        available_categories: list
    ) -> Dict[str, Any]:
        """Implementación interna de interpretación (protegida por circuit breaker)."""
        logger.info(f"Interpretando intención: {transcription[:100]}...")
        
        url = f"{self.BASE_URL}/chat/completions"
        
        headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        }
        
        # Construir prompt del sistema
        system_prompt = self._build_system_prompt(user_scope, available_categories)
        
        payload = {
            'model': self.chat_model,
            'messages': [
                {
                    'role': 'system',
                    'content': system_prompt
                },
                {
                    'role': 'user',
                    'content': transcription
                }
            ],
            'temperature': 0.1,  # Determinístico
            'max_tokens': 2000,
            'response_format': {'type': 'json_object'}
        }
        
        try:
            response = requests.post(
                url,
                headers=headers,
                json=payload,
                timeout=self.CHAT_TIMEOUT
            )
            
            response.raise_for_status()
            result = response.json()
            
            # Extraer contenido JSON
            content = result['choices'][0]['message']['content']
            intent = json.loads(content)
            
            logger.info("Interpretación exitosa")
            
            return intent
        
        except requests.exceptions.Timeout:
            logger.error("Timeout en interpretación")
            raise GroqAPIError("Timeout al interpretar intención")
        
        except requests.exceptions.HTTPError as e:
            logger.error(f"Error HTTP en interpretación: {e}")
            self._handle_http_error(e.response)
        
        except json.JSONDecodeError as e:
            logger.error(f"Error al parsear JSON de respuesta: {e}")
            raise GroqAPIError("Respuesta inválida de IA")
        
        except Exception as e:
            logger.error(f"Error inesperado en interpretación: {e}")
            raise GroqAPIError(f"Error al interpretar intención: {str(e)}")
    
    def _build_system_prompt(
        self,
        user_scope: str,
        available_categories: list
    ) -> str:
        """
        Construye prompt del sistema para interpretación.
        
        Args:
            user_scope: TENANT o SAAS
            available_categories: Categorías disponibles
        
        Returns:
            Prompt del sistema
        """
        from .report_catalog import ReportCatalogService
        from api.reports.prompts import build_system_prompt
        
        catalog = ReportCatalogService()
        
        # Obtener reportes disponibles
        available_reports = catalog.get_available_reports(
            user_scope,
            ['admin', 'manager', 'analyst']  # Roles genéricos
        )
        
        # Usar el prompt del módulo de prompts
        return build_system_prompt(user_scope, available_reports)
    
    def _handle_http_error(self, response):
        """Maneja errores HTTP de Groq API."""
        status_code = response.status_code
        
        try:
            error_data = response.json()
            error_message = error_data.get('error', {}).get('message', 'Error desconocido')
        except:
            error_message = response.text
        
        if status_code == 400:
            raise GroqAPIError(f"Solicitud inválida: {error_message}")
        elif status_code == 401:
            raise GroqAPIError("API key inválida o expirada")
        elif status_code == 429:
            raise GroqAPIError("Límite de rate excedido. Intente más tarde")
        elif status_code == 500:
            raise GroqAPIError("Error interno de Groq API")
        else:
            raise GroqAPIError(f"Error {status_code}: {error_message}")


class GroqAPIError(Exception):
    """Excepción para errores de Groq API."""
    pass
