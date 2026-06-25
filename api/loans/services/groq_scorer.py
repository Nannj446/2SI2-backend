"""
Scorer crediticio con GroqCloud API (Llama 3.3 70B Versatile).

Envía los datos del solicitante a Groq para que un LLM experto
en análisis de crédito evalúe el riesgo y emita un score.

En caso de fallo de la API, el ScoringService usará el fallback heurístico.
"""

import os
import json
import logging
import requests
from typing import Dict, Any, Optional

from api.reports.services.circuit_breaker import CircuitBreaker, CircuitBreakerError

logger = logging.getLogger(__name__)

# Circuit breaker específico para scoring
groq_scoring_breaker = CircuitBreaker(
    failure_threshold=3,
    recovery_timeout=60,
    expected_exception=Exception,
    name='GroqScoring'
)


class GroqScoringError(Exception):
    """Error en la evaluación con Groq."""
    pass


class GroqScorer:
    """
    Cliente ligero para evaluación crediticia con Groq.

    Usa el modelo llama-3.3-70b-versatile con response_format json_object
    para obtener una evaluación estructurada del riesgo crediticio.
    """

    BASE_URL = 'https://api.groq.com/openai/v1'
    CHAT_MODEL = 'llama-3.3-70b-versatile'
    CHAT_TIMEOUT = 30  # segundos (más tiempo que el chat normal)
    MAX_TOKENS = 2000
    TEMPERATURE = 0.1  # Determinístico para scoring

    def __init__(self):
        self.api_key = self._get_api_key()

    def _get_api_key(self) -> str:
        api_key = os.getenv('GROQ_API_KEY')
        if not api_key:
            raise GroqScoringError(
                'GROQ_API_KEY no configurada. '
                'Agregar a variables de entorno.'
            )
        return api_key

    def evaluate_credit(self, features: Dict[str, Any]) -> Dict[str, Any]:
        """
        Evalúa una solicitud de crédito usando Groq LLM.

        Args:
            features: Diccionario con los features del solicitante

        Returns:
            {
                'score_ia': 720,
                'sub_scores': {
                    'payment_capacity': 85,
                    'employment_stability': 70,
                    'credit_history': 65,
                    'debt_burden': 80,
                    'demographic': 65
                },
                'auto_decision': 'MANUAL_REVIEW',
                'auto_decision_reason': '...',
                'analysis_summary': '...',
                'risk_factors': [...],
                'mitigants': [...],
                'model_version': 'groq-llama-3.3-70b'
            }

        Raises:
            GroqScoringError: Si falla la llamada a Groq
        """
        return groq_scoring_breaker.call(
            self._evaluate_credit_internal,
            features
        )

    def _evaluate_credit_internal(self, features: Dict[str, Any]) -> Dict[str, Any]:
        """Implementación interna protegida por circuit breaker."""
        from api.loans.prompts import build_scoring_prompt
        from api.loans.prompts.scoring_prompt import build_scoring_user_prompt

        system_prompt = build_scoring_prompt()
        user_prompt = build_scoring_user_prompt(features)

        url = f'{self.BASE_URL}/chat/completions'
        headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json',
        }
        payload = {
            'model': self.CHAT_MODEL,
            'messages': [
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': user_prompt},
            ],
            'temperature': self.TEMPERATURE,
            'max_tokens': self.MAX_TOKENS,
            'response_format': {'type': 'json_object'},
        }

        logger.info(
            f'[GROQ SCORING] Enviando evaluación para solicitud '
            f'con ingreso={features.get("monthly_income")}, '
            f'monto={features.get("requested_amount")}'
        )

        try:
            response = requests.post(
                url, headers=headers, json=payload, timeout=self.CHAT_TIMEOUT
            )
            response.raise_for_status()
            result = response.json()

            content = result['choices'][0]['message']['content']
            evaluation = json.loads(content)

            # Agregar metadata del modelo
            evaluation['model_version'] = f'groq-{self.CHAT_MODEL}'

            # Validar campos requeridos
            required_fields = ['score_ia', 'sub_scores', 'auto_decision']
            for field in required_fields:
                if field not in evaluation:
                    raise GroqScoringError(
                        f'Respuesta de Groq incompleta: falta "{field}"'
                    )

            # Validar rangos
            score_ia = int(evaluation['score_ia'])
            if score_ia < 0 or score_ia > 1000:
                logger.warning(
                    f'[GROQ SCORING] Score IA fuera de rango: {score_ia}. '
                    f'Recortando a 0-1000.'
                )
                score_ia = max(0, min(1000, score_ia))
            evaluation['score_ia'] = score_ia

            logger.info(
                f'[GROQ SCORING] Evaluación exitosa: score_ia={score_ia}, '
                f'decisión={evaluation.get("auto_decision")}'
            )

            return evaluation

        except requests.exceptions.Timeout:
            logger.error('[GROQ SCORING] Timeout en evaluación')
            raise GroqScoringError('Timeout al evaluar crédito con IA')

        except requests.exceptions.HTTPError as e:
            logger.error(f'[GROQ SCORING] Error HTTP: {e}')
            self._handle_http_error(e.response)

        except json.JSONDecodeError as e:
            logger.error(f'[GROQ SCORING] Error al parsear JSON: {e}')
            raise GroqScoringError('Respuesta inválida del modelo IA')

        except Exception as e:
            logger.error(f'[GROQ SCORING] Error inesperado: {e}')
            raise GroqScoringError(f'Error en evaluación IA: {str(e)}')

    def _handle_http_error(self, response):
        """Maneja errores HTTP de Groq API."""
        status_code = response.status_code

        try:
            error_data = response.json()
            error_message = error_data.get('error', {}).get(
                'message', 'Error desconocido'
            )
        except Exception:
            error_message = response.text

        if status_code == 400:
            raise GroqScoringError(f'Solicitud inválida: {error_message}')
        elif status_code == 401:
            raise GroqScoringError('API key inválida o expirada')
        elif status_code == 429:
            raise GroqScoringError(
                'Límite de rate excedido en Groq. Intente más tarde.'
            )
        elif status_code == 500:
            raise GroqScoringError('Error interno de Groq API')
        else:
            raise GroqScoringError(f'Error HTTP {status_code}: {error_message}')


# Instancia singleton
groq_scorer = GroqScorer()
