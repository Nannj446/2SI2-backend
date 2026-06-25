"""
Servicio de dominio para gestionar verificaciones de identidad.

Responsabilidades:
- Validar que el usuario pertenece al tenant
- Evitar duplicados activos
- Crear sesiones en el modelo local
- Llamar a Didit para crear la sesión
- Actualizar estado basado en webhooks/consultas
- Registrar auditoría
- Actualizar solicitud de crédito si es necesario
"""
import logging
from dataclasses import dataclass
from typing import Optional, Dict, Any
from django.db import transaction
from django.utils import timezone
from django.contrib.auth import get_user_model
from api.identity_verification.models import IdentityVerification
from api.identity_verification.services.didit_client import DiditClient
from api.audit.services import AuditService

User = get_user_model()
logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class StartVerificationInput:
	"""Input para iniciar una verificación"""
	user: User
	institution_id: int
	credit_application_id: Optional[int] = None
	branch_id: Optional[int] = None
	return_url: Optional[str] = None
	webhook_url: Optional[str] = None
	metadata: Optional[Dict[str, Any]] = None


@dataclass(frozen=True)
class StartVerificationResult:
	"""Resultado de iniciar una verificación"""
	success: bool
	verification_id: Optional[int] = None
	verification_url: Optional[str] = None
	provider_session_id: Optional[str] = None
	error: Optional[str] = None
	error_code: Optional[str] = None


@dataclass(frozen=True)
class RefreshVerificationInput:
	"""Input para actualizar el estado de una verificación"""
	verification_id: int
	institution_id: int


@dataclass(frozen=True)
class RefreshVerificationResult:
	"""Resultado de actualizar estado"""
	success: bool
	verification_id: Optional[int] = None
	status: Optional[str] = None
	decision: Optional[str] = None
	error: Optional[str] = None


class IdentityVerificationService:
	"""Servicio de dominio para gestionar verificaciones de identidad"""
	
	def __init__(self):
		self.didit_client = DiditClient()
	
	def start_verification(
		self,
		payload: StartVerificationInput,
		request_user = None
	) -> StartVerificationResult:
		"""
		Inicia una verificación de identidad para un usuario.
		
		Proceso:
		1. Validar que el usuario pertenece al tenant
		2. Validar que no hay verificación activa en curso
		3. Crear registro local en estado PENDING
		4. Llamar a Didit para crear sesión
		5. Guardar session_id y verification_url
		6. Registrar auditoría
		
		Args:
			payload: StartVerificationInput con user, institution_id, etc.
			request_user: Usuario que hizo la solicitud (para auditoría)
		
		Returns:
			StartVerificationResult
		"""
		try:
			# Validar que el usuario pertenece a la institución
			from api.tenants.models import FinancialInstitution
			from api.loans.models import LoanApplication
			from api.branches.models import Branch
			
			try:
				institution = FinancialInstitution.objects.get(id=payload.institution_id)
			except FinancialInstitution.DoesNotExist:
				error_msg = 'Institución financiera no encontrada'
				logger.warning(f'{error_msg}: {payload.institution_id}')
				return StartVerificationResult(
					success=False,
					error=error_msg,
					error_code='INSTITUTION_NOT_FOUND'
				)
			
			# Validar relación usuario-institución
			from api.tenants.models import FinancialInstitutionMembership
			membership = FinancialInstitutionMembership.objects.filter(
				user=payload.user,
				institution=institution,
				is_active=True
			).first()
			
			if not membership and not payload.user.is_saas_admin():
				error_msg = 'Usuario no pertenece a esta institución'
				logger.warning(f'{error_msg}: user={payload.user.id}, institution={institution.id}')
				return StartVerificationResult(
					success=False,
					error=error_msg,
					error_code='USER_NOT_IN_INSTITUTION'
				)
			
			
			# Opcionalmente validar credit_application si se proporciona
			credit_application = None
			if payload.credit_application_id:
				try:
					credit_application = LoanApplication.objects.get(
						id=payload.credit_application_id,
						institution=institution,
						client__user=payload.user  # Verificar que es del cliente correcto
					)
				except LoanApplication.DoesNotExist:
					error_msg = 'Solicitud de crédito no encontrada o no pertenece al usuario'
					logger.warning(f'{error_msg}: app={payload.credit_application_id}')
					return StartVerificationResult(
						success=False,
						error=error_msg,
						error_code='CREDIT_APPLICATION_NOT_FOUND'
					)
			
			# Opcionalmente obtener branch si se proporciona
			branch = None
			if payload.branch_id:
				try:
					branch = Branch.objects.get(
						id=payload.branch_id,
						institution=institution
					)
				except Branch.DoesNotExist:
					logger.warning(f'Branch no encontrada: {payload.branch_id}')
			
			# Crear o reutilizar registro local
			with transaction.atomic():
				# Intentar encontrar una verificación activa (PENDING o IN_PROGRESS)
				verification = None
				if credit_application:
					verification = IdentityVerification.objects.filter(
						credit_application=credit_application,
						status__in=[
							IdentityVerification.Status.PENDING,
							IdentityVerification.Status.IN_PROGRESS
						]
					).first()
				
				if not verification:
					verification = IdentityVerification.objects.filter(
						user=payload.user,
						institution=institution,
						status__in=[
							IdentityVerification.Status.PENDING,
							IdentityVerification.Status.IN_PROGRESS
						],
						credit_application__isnull=True if not credit_application else False
					).first()

				if verification:
					logger.info(f'Reutilizando verificación activa existente: {verification.id} (Status: {verification.status})')
					
					# Si ya está IN_PROGRESS y tiene URL, podemos devolverla directamente
					# Pero es mejor generar una nueva sesión si el usuario volvió a darle a "Iniciar"
					# por si la anterior expiró o falló el redireccionamiento.
					
					# Actualizar campos
					verification.branch = branch
					verification.save()
				else:
					verification = IdentityVerification.objects.create(
						institution=institution,
						user=payload.user,
						credit_application=credit_application,
						branch=branch,
						provider=IdentityVerification.Provider.DIDIT,
						provider_session_id=None,
						verification_url='',
						status=IdentityVerification.Status.PENDING,
						decision=IdentityVerification.Decision.PENDING,
						raw_response={}
					)
					logger.info(f'Creada nueva verificación local: {verification.id}')
				
				# Llamar a Didit para crear sesión
				metadata = payload.metadata or {}
				metadata.update({
					'verification_id': verification.id,
					'user_email': payload.user.email,
					'institution_id': institution.id,
				})
				
				didit_result = self.didit_client.create_verification_session(
					workflow_id=getattr(self.didit_client, 'WORKFLOW_ID', ''),
					webhook_url=payload.webhook_url,
					vendor_data=str(verification.id),
					metadata=metadata,
					redirect_url=payload.return_url or payload.webhook_url
				)
				
				if not didit_result.success:
					# Marcar como error
					verification.mark_error(didit_result.error or 'Error en Didit')
					logger.error(
						f'Error creando sesión Didit: {didit_result.error_code} - {didit_result.error}'
					)
					
					# Registrar auditoría
					AuditService.log_action(
						action='identity_verification',
						resource_type='IdentityVerification',
						resource_id=verification.id,
						description=f'Error iniciando verificación: {didit_result.error}',
						user=request_user,
						institution=institution,
						severity='warning',
						metadata={'error_code': didit_result.error_code}
					)
					
					return StartVerificationResult(
						success=False,
						error=didit_result.error,
						error_code=didit_result.error_code,
						verification_id=verification.id
					)
				
				# Actualizar con datos de Didit
				verification.provider_session_id = didit_result.session_id
				verification.provider_session_token = didit_result.session_token or ''
				verification.verification_url = didit_result.verification_url
				verification.status = IdentityVerification.Status.PENDING
				verification.raw_response = didit_result.raw_response or {}
				verification.save()
				
				logger.info(
					f'Sesión Didit creada: {didit_result.session_id} '
					f'para verificación {verification.id}'
				)
				
				# Registrar auditoría
				AuditService.log_action(
					action='identity_verification',
					resource_type='IdentityVerification',
					resource_id=verification.id,
					description='Verificación de identidad iniciada',
					user=request_user,
					institution=institution,
					severity='info',
					metadata={
						'provider': 'DIDIT',
						'session_id': didit_result.session_id,
						'credit_application_id': credit_application.id if credit_application else None,
					}
				)
				
				# Si hay credit_application, registrar evento
				if credit_application:
					AuditService.log_action(
						action='create',
						resource_type='LoanApplicationTimeline',
						resource_id=credit_application.id,
						description='Verificación de identidad iniciada',
						user=request_user,
						institution=institution,
					)
				
				return StartVerificationResult(
					success=True,
					verification_id=verification.id,
					verification_url=verification.verification_url,
					provider_session_id=verification.provider_session_id
				)
		
		except Exception as e:
			error_msg = f'Error inesperado en start_verification: {str(e)}'
			logger.exception(error_msg)
			return StartVerificationResult(
				success=False,
				error=error_msg,
				error_code='UNEXPECTED_ERROR'
			)
	
	def refresh_verification(
		self,
		payload: RefreshVerificationInput,
		request_user = None
	) -> RefreshVerificationResult:
		"""
		Consulta el estado actual en Didit y actualiza el registro local.
		
		Útil cuando:
		- El webhook no llegó
		- Se quiere forzar una consulta
		- Se necesita saber el estado actual
		
		Args:
			payload: RefreshVerificationInput con verification_id, institution_id
			request_user: Usuario que hizo la solicitud (para auditoría)
		
		Returns:
			RefreshVerificationResult
		"""
		try:
			from api.tenants.models import FinancialInstitution
			
			# Obtener la verificación
			try:
				verification = IdentityVerification.objects.get(
					id=payload.verification_id,
					institution_id=payload.institution_id
				)
			except IdentityVerification.DoesNotExist:
				error_msg = 'Verificación no encontrada'
				logger.warning(f'{error_msg}: {payload.verification_id}')
				return RefreshVerificationResult(
					success=False,
					error=error_msg
				)
			
			# Si ya está completada, no refrescar
			if verification.status in [
				IdentityVerification.Status.APPROVED,
				IdentityVerification.Status.DECLINED,
				IdentityVerification.Status.EXPIRED,
				IdentityVerification.Status.ERROR,
			]:
				logger.info(f'Verificación {verification.id} ya completada, no refrescando')
				return RefreshVerificationResult(
					success=True,
					verification_id=verification.id,
					status=verification.status,
					decision=verification.decision
				)
			
			# Consultar a Didit
			didit_result = self.didit_client.retrieve_verification_session(
				verification.provider_session_id
			)
			
			if not didit_result.success:
				error_msg = f'Error consultando Didit: {didit_result.error}'
				logger.error(error_msg)
				return RefreshVerificationResult(
					success=False,
					error=error_msg,
					verification_id=verification.id
				)
			
			# Procesar resultado
			old_status = verification.status
			old_decision = verification.decision
			
			# Normalizar estados de Didit
			new_status = self.didit_client.normalize_didit_status(didit_result.status or '')
			new_decision = self.didit_client.normalize_didit_decision(didit_result.decision or '')
			
			# Actualizar modelo
			verification.status = new_status
			verification.decision = new_decision
			verification.webhook_received_at = timezone.now()
			
			# Si hay resultado de verificación, guardar datos
			if didit_result.verification_result:
				result = didit_result.verification_result
				if new_status == IdentityVerification.Status.APPROVED:
					verification.mark_approved(result)
				elif new_status == IdentityVerification.Status.DECLINED:
					verification.mark_declined(result.get('reason', ''))
			else:
				verification.save()
			
			logger.info(
				f'Verificación {verification.id} refrescada: '
				f'{old_status} -> {new_status}, decision: {new_decision}'
			)
			
			# Registrar auditoría si cambió
			if old_status != new_status or old_decision != new_decision:
				AuditService.log_action(
					action='update_partial',
					resource_type='IdentityVerification',
					resource_id=verification.id,
					description=f'Estado actualizado: {old_status} -> {new_status}',
					user=request_user,
					institution=verification.institution,
					severity='info',
					metadata={
						'old_status': old_status,
						'new_status': new_status,
						'old_decision': old_decision,
						'new_decision': new_decision,
					}
				)
			
			return RefreshVerificationResult(
				success=True,
				verification_id=verification.id,
				status=new_status,
				decision=new_decision
			)
		
		except Exception as e:
			error_msg = f'Error en refresh_verification: {str(e)}'
			logger.exception(error_msg)
			return RefreshVerificationResult(
				success=False,
				error=error_msg,
				verification_id=payload.verification_id
			)
	
	@staticmethod
	def process_webhook(
		provider: str,
		provider_event_id: str,
		provider_session_id: str,
		payload: Dict[str, Any],
		request_user = None
	) -> bool:
		"""
		Procesa un webhook recibido de Didit.
		
		Pasos:
		1. Crear registro de webhook para auditoría
		2. Validar que no sea duplicado
		3. Buscar la verificación por session_id
		4. Actualizar estado basado en evento
		5. Marcar como procesado
		6. Registrar auditoría
		
		Args:
			provider: Proveedor (e.g., 'DIDIT')
			provider_event_id: ID único del evento
			provider_session_id: ID de sesión en el proveedor
			payload: Payload completo del webhook
			request_user: Usuario del webhook (si aplica)
		
		Returns:
			True si se procesó exitosamente
		"""
		try:
			from api.identity_verification.models import IdentityVerificationWebhook
			
			with transaction.atomic():
				# Crear registro de webhook
				webhook, created = IdentityVerificationWebhook.objects.get_or_create(
					provider=provider,
					provider_event_id=provider_event_id,
					defaults={
						'provider_session_id': provider_session_id,
						'payload': payload,
						'status': IdentityVerificationWebhook.Status.PENDING,
					}
				)
				
				# Si es duplicado, marcar y retornar
				if not created:
					logger.info(f'Webhook duplicado: {provider_event_id}')
					webhook.mark_duplicate()
					return True
				
				# Buscar verificación
				try:
					verification = IdentityVerification.all_objects.get(
						provider_session_id=provider_session_id,
						provider=provider
					)
				except IdentityVerification.DoesNotExist:
					error_msg = f'Verificación no encontrada para session_id: {provider_session_id}'
					logger.warning(error_msg)
					webhook.mark_failed(error_msg)
					return False
				
				# Actualizar estado
				old_status = verification.status
				
				# Procesar payload según proveedor
				if provider == 'DIDIT':
					status = payload.get('status', '').upper()
					decision = payload.get('decision', '').upper()
					result = payload.get('result', {})
					
					# Normalizar
					new_status = DiditClient.normalize_didit_status(status)
					new_decision = DiditClient.normalize_didit_decision(decision)
					
					verification.status = new_status
					verification.decision = new_decision
					verification.webhook_received_at = timezone.now()
					
					# Si hay resultado, guardar datos
					if result:
						if new_status == IdentityVerification.Status.APPROVED:
							verification.mark_approved(result)
						elif new_status == IdentityVerification.Status.DECLINED:
							reason = result.get('reason', result.get('error', 'Rechazado'))
							verification.mark_declined(reason)
						else:
							verification.save()
					else:
						verification.save()
				
				# Marcar webhook como procesado
				webhook.mark_processed(verification)
				
				logger.info(
					f'Webhook procesado: verificación {verification.id} '
					f'{old_status} -> {verification.status}'
				)
				
				# Registrar auditoría
				AuditService.log_action(
					action='identity_verification',
					resource_type='IdentityVerification',
					resource_id=verification.id,
					description=f'Webhook recibido: status={verification.status}, decision={verification.decision}',
					user=request_user,
					institution=verification.institution,
					severity='info',
					metadata={
						'provider': provider,
						'event_id': provider_event_id,
						'old_status': old_status,
						'new_status': verification.status,
					}
				)

				# Actualizar LoanApplication.identity_verification_status y disparar avance automatico
				kyc_app_id = verification.credit_application_id
				logger.info(
					f'[KYC_WEBHOOK] verification_id={verification.id}, '
					f'credit_application_id={kyc_app_id}, '
					f'verification_status={verification.status}'
				)
				if kyc_app_id:
					from api.loans.models import LoanApplication
					from api.loans.services.workflow_service import WorkflowService
					try:
						app = LoanApplication.objects.select_for_update().get(
							id=kyc_app_id
						)
						logger.info(
							f'[KYC_WEBHOOK] app encontrada: id={app.id}, '
							f'status={app.status}, '
							f'institution_id={app.institution_id}, '
							f'identity_verification_status_anterior={app.identity_verification_status}'
						)
						# Mapear estado de verificacion a estado de solicitud
						if verification.status == IdentityVerification.Status.APPROVED:
							app.identity_verification_status = 'APPROVED'
						elif verification.status == IdentityVerification.Status.DECLINED:
							app.identity_verification_status = 'DECLINED'
						elif verification.status == IdentityVerification.Status.ERROR:
							app.identity_verification_status = 'MANUAL_REVIEW'
						elif verification.status in [
							IdentityVerification.Status.PENDING,
							IdentityVerification.Status.IN_PROGRESS
						]:
							app.identity_verification_status = 'PENDING'
						app.save(update_fields=['identity_verification_status'])
						logger.info(
							f'[KYC_WEBHOOK] identity_verification_status actualizado a '
							f'{app.identity_verification_status} para app_id={kyc_app_id}'
						)

						# Disparar avance automatico del workflow solo si KYC fue aprobado
						if verification.status == IdentityVerification.Status.APPROVED:
							logger.info(
								f'[KYC_WEBHOOK] KYC APROBADO. Llamando check_and_advance_if_ready '
								f'para app_id={kyc_app_id}'
							)
							WorkflowService.check_and_advance_if_ready(
								app,
								changed_by=request_user,
								trigger='kyc_completed'
							)
						else:
							logger.info(
								f'[KYC_WEBHOOK] KYC no aprobado (status={verification.status}). '
								f'No se dispara avance automatico para app_id={kyc_app_id}'
							)
					except Exception as e:
						logger.warning(
							f'Error actualizando workflow de solicitud '
							f'{kyc_app_id}: {e}',
							exc_info=True
						)
				else:
					logger.warning(
						f'[KYC_WEBHOOK] verification_id={verification.id} no tiene credit_application asociada'
					)

				return True
		
		except Exception as e:
			error_msg = f'Error procesando webhook: {str(e)}'
			logger.exception(error_msg)
			return False
