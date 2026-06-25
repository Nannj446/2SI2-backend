"""
Cliente Didit para comunicación con API de verificación de identidad.

Responsabilidades:
- Crear sesiones de verificación
- Consultar el estado de sesiones
- Procesar respuestas y normalizarlas
- Manejar errores y timeouts
"""
import os
import logging
import requests
from typing import Optional, Dict, Any
from dataclasses import dataclass
from django.conf import settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CreateSessionInput:
	"""Input para crear una sesión de verificación"""
	workflow_id: str
	return_url: str
	vendor_data: Optional[str] = None
	metadata: Optional[Dict[str, Any]] = None
	language: str = 'es'
	callback_method: str = 'initiator'
	contact_email: Optional[str] = None


@dataclass(frozen=True)
class CreateSessionResult:
	"""Resultado de crear una sesión"""
	success: bool
	session_id: Optional[str] = None
	session_token: Optional[str] = None
	verification_url: Optional[str] = None
	error: Optional[str] = None
	error_code: Optional[str] = None
	raw_response: Optional[Dict[str, Any]] = None


@dataclass(frozen=True)
class RetrieveSessionInput:
	"""Input para consultar el estado de una sesión"""
	session_id: str


@dataclass(frozen=True)
class RetrieveSessionResult:
	"""Resultado de consultar el estado"""
	success: bool
	session_id: Optional[str] = None
	status: Optional[str] = None
	decision: Optional[str] = None
	verification_result: Optional[Dict[str, Any]] = None
	error: Optional[str] = None
	error_code: Optional[str] = None
	raw_response: Optional[Dict[str, Any]] = None


class DiditClient:
	"""
	Cliente HTTP para la API de Didit.
	
	Usa sesiones hosted de Didit (el usuario completa todo en el navegador/app de Didit).
	
	Documentation: https://docs.didit.com/
	"""
	
	# Configuración de la API
	BASE_URL = os.getenv('DIDIT_BASE_URL', 'https://verification.didit.me/v3')
	API_KEY = os.getenv('IDENTITY_VERIFICATION_API_KEY', '')
	WORKFLOW_ID = (
		os.getenv('DIDIT_WORKFLOW_ID')
		or os.getenv('WORKFLOW_ID')
		or os.getenv('IDENTITY_VERIFICATION_WORKFLOW_ID')
		or ''
	)
	WEBHOOK_SECRET = os.getenv('DIDIT_WEBHOOK_SECRET', '')
	
	# Timeouts
	REQUEST_TIMEOUT = 10  # segundos
	
	# Headers estándar
	HEADERS = {
		'Content-Type': 'application/json',
		'User-Agent': 'FinCore-SaaS/1.0',
	}
	
	def __init__(self):
		"""Inicializa el cliente"""
		if not self.API_KEY:
			logger.warning('IDENTITY_VERIFICATION_API_KEY no configurada en .env')
		if not self.WORKFLOW_ID:
			logger.warning('DIDIT_WORKFLOW_ID no configurado en .env')
	
	@property
	def auth_headers(self) -> Dict[str, str]:
		"""Construye headers con autenticación"""
		headers = self.HEADERS.copy()
		headers['x-api-key'] = self.API_KEY
		return headers
	
	def create_verification_session(
		self,
		workflow_id: Optional[str],
		webhook_url: Optional[str] = None,
		vendor_data: Optional[str] = None,
		metadata: Optional[Dict[str, Any]] = None,
		redirect_url: Optional[str] = None
	) -> CreateSessionResult:
		"""
		Crea una nueva sesión de verificación en Didit.
		
		Args:
			workflow_id: ID del workflow en Didit
			webhook_url: URL donde Didit enviará los webhooks (callback)
			vendor_data: ID único del usuario para tracking
			metadata: Datos adicionales para asociar con la sesión
			redirect_url: URL opcional para redirección (depende de configuración en Didit)
		
		Returns:
			CreateSessionResult con session_id, verification_url, etc.
		"""
		try:
			resolved_workflow_id = workflow_id or self.WORKFLOW_ID
			if not resolved_workflow_id:
				return CreateSessionResult(
					success=False,
					error='DIDIT_WORKFLOW_ID no configurado',
					error_code='CONFIGURATION_ERROR',
				)

			# Construir payload según API de Didit V3
			# 'callback' es para el WEBHOOK
			payload = {
				'workflow_id': resolved_workflow_id,
				'callback': webhook_url,
				'callback_method': 'initiator',
				'language': 'es',
				'vendor_data': vendor_data or '',
				'metadata': metadata or {},
			}
			
			# Algunos workflows pueden usar redirect_url si está habilitado
			if redirect_url:
				payload['redirect_url'] = redirect_url
			
			# POST /v3/session/
			endpoint = f'{self.BASE_URL}/session/'
			response = requests.post(
				endpoint,
				json=payload,
				headers=self.auth_headers,
				timeout=self.REQUEST_TIMEOUT,
			)
			
			# Log sin exponer API key
			logger.debug(f'Didit create_session request to {endpoint}')
			logger.debug(f'Status: {response.status_code}')
			
			# Manejar respuestas de error HTTP
			if response.status_code == 401:
				error_msg = 'Didit API Key inválida o expirada'
				logger.error(error_msg)
				return CreateSessionResult(
					success=False,
					error=error_msg,
					error_code='UNAUTHORIZED',
					raw_response=response.json() if response.text else {}
				)
			
			if response.status_code == 403:
				error_msg = 'Acceso prohibido a la API de Didit'
				logger.error(error_msg)
				return CreateSessionResult(
					success=False,
					error=error_msg,
					error_code='FORBIDDEN',
					raw_response=response.json() if response.text else {}
				)
			
			if response.status_code >= 400:
				error_msg = f'Error Didit {response.status_code}'
				logger.error(f'{error_msg}: {response.text}')
				return CreateSessionResult(
					success=False,
					error=error_msg,
					error_code='API_ERROR',
					raw_response=response.json() if response.text else {}
				)
			
			# Parsear respuesta exitosa
			data = response.json()
			
			# Normalizar respuesta de Didit
			session_id = data.get('session_id') or data.get('id')
			verification_url = data.get('url') or data.get('verification_url') or data.get('session_url')
			session_token = data.get('session_token') or data.get('token')
			
			if not session_id or not verification_url:
				error_msg = 'Respuesta de Didit incompleta (falta session_id o url)'
				logger.error(f'{error_msg}: {data}')
				return CreateSessionResult(
					success=False,
					error=error_msg,
					error_code='INVALID_RESPONSE',
					raw_response=data
				)
			
			logger.info(f'Didit session creada: {session_id}')
			
			return CreateSessionResult(
				success=True,
				session_id=session_id,
				session_token=session_token,
				verification_url=verification_url,
				raw_response=self._filter_sensitive_data(data)
			)
		
		except requests.Timeout:
			error_msg = 'Timeout conectándose a Didit'
			logger.error(error_msg)
			return CreateSessionResult(
				success=False,
				error=error_msg,
				error_code='TIMEOUT'
			)
		
		except requests.RequestException as e:
			error_msg = f'Error de conexión con Didit: {str(e)}'
			logger.error(error_msg)
			return CreateSessionResult(
				success=False,
				error=error_msg,
				error_code='CONNECTION_ERROR'
			)
		
		except Exception as e:
			error_msg = f'Error inesperado en DiditClient: {str(e)}'
			logger.exception(error_msg)
			return CreateSessionResult(
				success=False,
				error=error_msg,
				error_code='UNEXPECTED_ERROR'
			)
	
	def retrieve_verification_session(
		self,
		session_id: str
	) -> RetrieveSessionResult:
		"""
		Consulta el estado de una sesión de verificación.
		
		Args:
			session_id: ID de la sesión en Didit
		
		Returns:
			RetrieveSessionResult con status, decision, resultado, etc.
		"""
		try:
			# GET /v3/session/{session_id}/decision/
			endpoint = f'{self.BASE_URL}/session/{session_id}/decision/'
			response = requests.get(
				endpoint,
				headers=self.auth_headers,
				timeout=self.REQUEST_TIMEOUT,
			)
			
			logger.debug(f'Didit retrieve_session request to {endpoint}')
			logger.debug(f'Status: {response.status_code}')
			
			# Manejar errores
			if response.status_code == 401:
				error_msg = 'Didit API Key inválida'
				logger.error(error_msg)
				return RetrieveSessionResult(
					success=False,
					error=error_msg,
					error_code='UNAUTHORIZED',
					raw_response=response.json() if response.text else {}
				)
			
			if response.status_code == 404:
				error_msg = f'Sesión {session_id} no encontrada en Didit'
				logger.warning(error_msg)
				return RetrieveSessionResult(
					success=False,
					error=error_msg,
					error_code='NOT_FOUND',
					raw_response=response.json() if response.text else {}
				)
			
			if response.status_code >= 400:
				error_msg = f'Error Didit {response.status_code}'
				logger.error(f'{error_msg}: {response.text}')
				return RetrieveSessionResult(
					success=False,
					error=error_msg,
					error_code='API_ERROR',
					raw_response=response.json() if response.text else {}
				)
			
			# Parsear respuesta
			data = response.json()
			status = (data.get('status') or '').upper()
			decision = (data.get('decision') or '').upper()
			if not decision:
				decision = status
			
			# Extraer resultado de la verificación
			verification_result = data.get('result', {}) or {}
			if not verification_result:
				id_verifications = data.get('id_verifications') or []
				if id_verifications and isinstance(id_verifications, list):
					verification_result = id_verifications[0] if isinstance(id_verifications[0], dict) else {}
			if not status and data.get('session_status'):
				status = str(data.get('session_status')).upper()
			if not status:
				status = 'PENDING'
			
			logger.info(f'Didit session {session_id} status: {status}/{decision}')
			
			return RetrieveSessionResult(
				success=True,
				session_id=session_id,
				status=status,
				decision=decision,
				verification_result=verification_result,
				raw_response=self._filter_sensitive_data(data)
			)
		
		except requests.Timeout:
			error_msg = 'Timeout consultando Didit'
			logger.error(error_msg)
			return RetrieveSessionResult(
				success=False,
				error=error_msg,
				error_code='TIMEOUT'
			)
		
		except requests.RequestException as e:
			error_msg = f'Error de conexión con Didit: {str(e)}'
			logger.error(error_msg)
			return RetrieveSessionResult(
				success=False,
				error=error_msg,
				error_code='CONNECTION_ERROR'
			)
		
		except Exception as e:
			error_msg = f'Error inesperado en DiditClient: {str(e)}'
			logger.exception(error_msg)
			return RetrieveSessionResult(
				success=False,
				error=error_msg,
				error_code='UNEXPECTED_ERROR'
			)
	
	@staticmethod
	def normalize_didit_status(didit_status: str) -> str:
		"""
		Normaliza estados de Didit a estados internos.
		
		Args:
			didit_status: Estado recibido de Didit (e.g., COMPLETED, PENDING, FAILED)
		
		Returns:
			Estado interno (e.g., APPROVED, DECLINED, IN_PROGRESS, ERROR)
		"""
		status_map = {
			'PENDING': 'PENDING',
			'IN_PROGRESS': 'IN_PROGRESS',
			'COMPLETED': 'APPROVED',  # Didit lo completa, interpretamos como aprobado
			'APPROVED': 'APPROVED',
			'DECLINED': 'DECLINED',
			'FAILED': 'ERROR',
			'ERROR': 'ERROR',
			'EXPIRED': 'EXPIRED',
			'NOT STARTED': 'PENDING',
			'NOT_STARTED': 'PENDING',
			'IN REVIEW': 'IN_PROGRESS',
			'REVIEW': 'IN_PROGRESS',
			'REJECTED': 'DECLINED',
		}
		return status_map.get(didit_status.upper(), 'PENDING')
	
	@staticmethod
	def normalize_didit_decision(didit_decision: str) -> str:
		"""
		Normaliza decisiones de Didit a decisiones internas.
		
		Args:
			didit_decision: Decisión de Didit (e.g., APPROVED, DECLINED, PENDING)
		
		Returns:
			Decisión interna
		"""
		decision_map = {
			'APPROVED': 'APPROVED',
			'DECLINED': 'DECLINED',
			'PENDING': 'PENDING',
			'MANUAL_REVIEW': 'MANUAL_REVIEW',
			'IN REVIEW': 'PENDING',
			'NOT STARTED': 'PENDING',
		}
		return decision_map.get(didit_decision.upper(), 'PENDING')
	
	@staticmethod
	def _filter_sensitive_data(data: Dict[str, Any]) -> Dict[str, Any]:
		"""
		Filtra datos sensibles de la respuesta de Didit antes de guardar en BD.
		
		Elimina:
		- Tokens de sesión
		- URLs privadas
		- Documentos/imágenes
		- Datos biométricos
		
		Args:
			data: Respuesta completa de Didit
		
		Returns:
			Respuesta filtrada
		"""
		# Campos a mantener para auditoría y debugging
		keep_fields = {
			'session_id', 'id', 'session_number',
			'status', 'decision', 'session_status',
			'result', 'id_verifications',  # Contiene datos verificados
			'created_at', 'updated_at',
			'expires_at',
			'error', 'error_code', 'error_message',
			'vendor_data', 'workflow_id'
		}
		
		# Filtrar
		filtered = {}
		for key, value in data.items():
			if key in keep_fields:
				# Si es result o id_verifications (lista), filtrar también adentro
				if key == 'result' and isinstance(value, dict):
					result_keep = {
						'full_name', 'document_type', 'document_number',
						'date_of_birth', 'country', 'verified',
					}
					filtered[key] = {k: v for k, v in value.items() if k in result_keep}
				elif key == 'id_verifications' and isinstance(value, list):
					filtered[key] = []
					for item in value:
						if isinstance(item, dict):
							item_keep = {
								'document_type', 'document_number', 'first_name', 'last_name',
								'full_name', 'date_of_birth', 'country', 'verified', 'status'
							}
							filtered[key].append({k: v for k, v in item.items() if k in item_keep})
				else:
					filtered[key] = value
		
		return filtered
