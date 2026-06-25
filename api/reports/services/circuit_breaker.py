"""
Circuit Breaker para resiliencia de APIs externas.

Implementa el patrón Circuit Breaker para proteger contra
fallos en cascada cuando APIs externas (como Groq) fallan.

Estados:
- CLOSED: Funcionamiento normal, todas las llamadas pasan
- OPEN: Circuito abierto, llamadas fallan inmediatamente
- HALF_OPEN: Probando recuperación, algunas llamadas pasan
"""
import time
import logging
from enum import Enum
from typing import Callable, Any, Optional
from functools import wraps
from threading import Lock

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    """Estados del circuit breaker."""
    CLOSED = "closed"  # Funcionando normalmente
    OPEN = "open"  # Circuito abierto, rechazando llamadas
    HALF_OPEN = "half_open"  # Probando recuperación


class CircuitBreakerError(Exception):
    """Excepción lanzada cuando el circuito está abierto."""
    pass


class CircuitBreaker:
    """
    Circuit Breaker para proteger llamadas a APIs externas.
    
    Parámetros:
    - failure_threshold: Número de fallos antes de abrir el circuito
    - recovery_timeout: Segundos antes de intentar recuperación
    - expected_exception: Tipo de excepción que cuenta como fallo
    - name: Nombre del circuit breaker para logging
    """
    
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        expected_exception: type = Exception,
        name: str = "CircuitBreaker"
    ):
        """Inicializa el circuit breaker."""
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        self.name = name
        
        # Estado interno
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._last_failure_time: Optional[float] = None
        self._lock = Lock()
        
        logger.info(
            f"Circuit Breaker '{self.name}' inicializado: "
            f"threshold={failure_threshold}, timeout={recovery_timeout}s"
        )
    
    @property
    def state(self) -> CircuitState:
        """Obtiene el estado actual del circuito."""
        return self._state
    
    @property
    def failure_count(self) -> int:
        """Obtiene el contador de fallos."""
        return self._failure_count
    
    def call(self, func: Callable, *args, **kwargs) -> Any:
        """
        Ejecuta función protegida por circuit breaker.
        
        Args:
            func: Función a ejecutar
            *args: Argumentos posicionales
            **kwargs: Argumentos nombrados
        
        Returns:
            Resultado de la función
        
        Raises:
            CircuitBreakerError: Si el circuito está abierto
            Exception: Excepción original si la función falla
        """
        with self._lock:
            # Verificar si debemos intentar recuperación
            if self._state == CircuitState.OPEN:
                if self._should_attempt_reset():
                    logger.info(f"Circuit Breaker '{self.name}': Intentando recuperación (HALF_OPEN)")
                    self._state = CircuitState.HALF_OPEN
                else:
                    # Circuito aún abierto
                    time_since_failure = time.time() - (self._last_failure_time or 0)
                    remaining = self.recovery_timeout - time_since_failure
                    logger.warning(
                        f"Circuit Breaker '{self.name}': Circuito ABIERTO. "
                        f"Reintento en {remaining:.0f}s"
                    )
                    raise CircuitBreakerError(
                        f"Circuit breaker '{self.name}' está abierto. "
                        f"Reintente en {remaining:.0f} segundos."
                    )
        
        # Intentar ejecutar la función
        try:
            result = func(*args, **kwargs)
            
            # Éxito: resetear contador
            with self._lock:
                if self._state == CircuitState.HALF_OPEN:
                    logger.info(f"Circuit Breaker '{self.name}': Recuperación exitosa (CLOSED)")
                self._on_success()
            
            return result
        
        except self.expected_exception as e:
            # Fallo esperado: incrementar contador
            with self._lock:
                self._on_failure()
            
            # Re-lanzar excepción original
            raise e
    
    def _should_attempt_reset(self) -> bool:
        """Verifica si es momento de intentar recuperación."""
        if self._last_failure_time is None:
            return True
        
        time_since_failure = time.time() - self._last_failure_time
        return time_since_failure >= self.recovery_timeout
    
    def _on_success(self):
        """Maneja éxito de llamada."""
        self._failure_count = 0
        self._state = CircuitState.CLOSED
    
    def _on_failure(self):
        """Maneja fallo de llamada."""
        self._failure_count += 1
        self._last_failure_time = time.time()
        
        logger.warning(
            f"Circuit Breaker '{self.name}': Fallo {self._failure_count}/{self.failure_threshold}"
        )
        
        # Abrir circuito si se alcanza el threshold
        if self._failure_count >= self.failure_threshold:
            self._state = CircuitState.OPEN
            logger.error(
                f"Circuit Breaker '{self.name}': Circuito ABIERTO después de "
                f"{self._failure_count} fallos"
            )
    
    def reset(self):
        """Resetea manualmente el circuit breaker."""
        with self._lock:
            logger.info(f"Circuit Breaker '{self.name}': Reset manual")
            self._failure_count = 0
            self._state = CircuitState.CLOSED
            self._last_failure_time = None
    
    def get_status(self) -> dict:
        """Obtiene estado actual del circuit breaker."""
        return {
            'name': self.name,
            'state': self._state.value,
            'failure_count': self._failure_count,
            'failure_threshold': self.failure_threshold,
            'last_failure_time': self._last_failure_time,
            'recovery_timeout': self.recovery_timeout
        }


def circuit_breaker(
    failure_threshold: int = 5,
    recovery_timeout: int = 60,
    expected_exception: type = Exception,
    name: Optional[str] = None
):
    """
    Decorador para aplicar circuit breaker a funciones.
    
    Uso:
        @circuit_breaker(failure_threshold=3, recovery_timeout=30)
        def call_external_api():
            # código que puede fallar
            pass
    
    Args:
        failure_threshold: Número de fallos antes de abrir circuito
        recovery_timeout: Segundos antes de intentar recuperación
        expected_exception: Tipo de excepción que cuenta como fallo
        name: Nombre del circuit breaker
    """
    def decorator(func: Callable) -> Callable:
        # Crear circuit breaker único para esta función
        breaker_name = name or f"{func.__module__}.{func.__name__}"
        breaker = CircuitBreaker(
            failure_threshold=failure_threshold,
            recovery_timeout=recovery_timeout,
            expected_exception=expected_exception,
            name=breaker_name
        )
        
        @wraps(func)
        def wrapper(*args, **kwargs):
            return breaker.call(func, *args, **kwargs)
        
        # Adjuntar breaker a la función para acceso externo
        wrapper.circuit_breaker = breaker
        
        return wrapper
    
    return decorator


# Circuit breakers globales para servicios comunes
groq_transcription_breaker = CircuitBreaker(
    failure_threshold=3,
    recovery_timeout=60,
    expected_exception=Exception,
    name="GroqTranscription"
)

groq_chat_breaker = CircuitBreaker(
    failure_threshold=3,
    recovery_timeout=60,
    expected_exception=Exception,
    name="GroqChat"
)

storage_breaker = CircuitBreaker(
    failure_threshold=5,
    recovery_timeout=30,
    expected_exception=Exception,
    name="SupabaseStorage"
)


def get_all_breakers() -> dict:
    """
    Obtiene estado de todos los circuit breakers globales.
    
    Returns:
        Diccionario con estado de cada breaker
    """
    return {
        'groq_transcription': groq_transcription_breaker.get_status(),
        'groq_chat': groq_chat_breaker.get_status(),
        'storage': storage_breaker.get_status()
    }


def reset_all_breakers():
    """Resetea todos los circuit breakers globales."""
    groq_transcription_breaker.reset()
    groq_chat_breaker.reset()
    storage_breaker.reset()
    logger.info("Todos los circuit breakers han sido reseteados")
