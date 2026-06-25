"""
Modelos para verificación de identidad con Didit
"""
from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import URLValidator
from django.utils import timezone
from decimal import Decimal
from api.core.models import TenantModel

User = get_user_model()


class IdentityVerification(TenantModel):
	"""
	Modelo para registrar verificaciones de identidad de prestatarios.
	
	Asocia un usuario/prestatario con un proveedor externo (Didit) y registra
	el estado y resultado de la verificación.
	
	Relaciones:
	- institution (heredado de TenantModel): Institución financiera propietaria
	- user: Usuario prestatario que se verifica
	- credit_application: Solicitud de crédito asociada (opcional)
	- branch: Sucursal donde se origina la solicitud (opcional)
	
	Estados:
	- PENDING: Sesión creada, usuario aún no inicia
	- IN_PROGRESS: Usuario inició el flujo en Didit
	- APPROVED: Identidad validada exitosamente
	- DECLINED: Identidad rechazada
	- MANUAL_REVIEW: Requiere revisión manual
	- EXPIRED: Sesión expirada
	- ERROR: Error técnico
	"""
	
	class Provider(models.TextChoices):
		DIDIT = 'DIDIT', 'Didit'
	
	class Status(models.TextChoices):
		PENDING = 'PENDING', 'Pendiente'
		IN_PROGRESS = 'IN_PROGRESS', 'En Progreso'
		APPROVED = 'APPROVED', 'Aprobada'
		DECLINED = 'DECLINED', 'Rechazada'
		MANUAL_REVIEW = 'MANUAL_REVIEW', 'Revisión Manual'
		EXPIRED = 'EXPIRED', 'Expirada'
		ERROR = 'ERROR', 'Error'
	
	class Decision(models.TextChoices):
		APPROVED = 'APPROVED', 'Aprobado'
		DECLINED = 'DECLINED', 'Rechazado'
		PENDING = 'PENDING', 'Pendiente'
		MANUAL_REVIEW = 'MANUAL_REVIEW', 'Revisión Manual'
	
	# Identidad de la verificación
	user = models.ForeignKey(
		User,
		on_delete=models.PROTECT,
		related_name='identity_verifications',
		help_text='Usuario prestatario siendo verificado'
	)
	credit_application = models.ForeignKey(
		'loans.LoanApplication',
		on_delete=models.SET_NULL,
		null=True,
		blank=True,
		related_name='identity_verifications',
		help_text='Solicitud de crédito asociada (opcional)'
	)
	branch = models.ForeignKey(
		'branches.Branch',
		on_delete=models.SET_NULL,
		null=True,
		blank=True,
		related_name='identity_verifications',
		help_text='Sucursal donde se originó la solicitud'
	)
	
	# Información del proveedor
	provider = models.CharField(
		max_length=50,
		choices=Provider.choices,
		default=Provider.DIDIT,
		db_index=True,
		help_text='Proveedor de verificación de identidad'
	)
	provider_session_id = models.CharField(
		max_length=255,
		unique=True,
		null=True,
		blank=True,
		db_index=True,
		help_text='ID único de sesión en el proveedor (e.g., Didit session_id)'
	)
	provider_session_token = models.CharField(
		max_length=500,
		null=True,
		blank=True,
		help_text='Token de sesión del proveedor (si aplica y es necesario). SENSIBLE.'
	)
	
	# URL de verificación
	verification_url = models.URLField(
		null=True,
		blank=True,
		help_text='URL del hosting Didit o similar donde el usuario completa la verificación'
	)
	
	# Estado de la verificación
	status = models.CharField(
		max_length=20,
		choices=Status.choices,
		default=Status.PENDING,
		db_index=True,
		help_text='Estado actual de la verificación'
	)
	decision = models.CharField(
		max_length=20,
		choices=Decision.choices,
		default=Decision.PENDING,
		db_index=True,
		help_text='Decisión de aprobación/rechazo'
	)
	
	# Datos extraídos/confirmados
	document_type = models.CharField(
		max_length=50,
		blank=True,
		help_text='Tipo de documento (e.g., PASSPORT, NATIONAL_ID, DRIVER_LICENSE)'
	)
	document_number = models.CharField(
		max_length=50,
		blank=True,
		db_index=True,
		help_text='Número de documento identificado'
	)
	full_name = models.CharField(
		max_length=255,
		blank=True,
		help_text='Nombre completo confirmado en la verificación'
	)
	date_of_birth = models.DateField(
		null=True,
		blank=True,
		help_text='Fecha de nacimiento confirmada'
	)
	country = models.CharField(
		max_length=2,
		blank=True,
		help_text='Código de país ISO 3166-1 alpha-2'
	)
	
	# Resultado y errores
	error_message = models.TextField(
		blank=True,
		help_text='Mensaje de error si la verificación falló o tuvo problemas'
	)
	
	# Respuesta del proveedor (JSON, filtrada de datos sensibles)
	raw_response = models.JSONField(
		default=dict,
		blank=True,
		help_text='Respuesta del proveedor (solo campos no-sensibles y útiles para auditoría)'
	)
	
	# Fechas de control
	started_at = models.DateTimeField(
		auto_now_add=True,
		help_text='Cuando se creó la sesión de verificación'
	)
	completed_at = models.DateTimeField(
		null=True,
		blank=True,
		db_index=True,
		help_text='Cuando se completó/resolvió la verificación'
	)
	expires_at = models.DateTimeField(
		null=True,
		blank=True,
		db_index=True,
		help_text='Cuando expira la sesión (si aplica)'
	)
	webhook_received_at = models.DateTimeField(
		null=True,
		blank=True,
		help_text='Último webhook recibido del proveedor'
	)
	
	class Meta:
		db_table = 'identity_verifications'
		verbose_name = 'Verificación de Identidad'
		verbose_name_plural = 'Verificaciones de Identidad'
		ordering = ['-created_at']
		indexes = [
			models.Index(fields=['institution', 'user']),
			models.Index(fields=['institution', 'status']),
			models.Index(fields=['user', '-created_at']),
			models.Index(fields=['provider_session_id', 'provider']),
			models.Index(fields=['credit_application', 'status']),
		]
		unique_together = [
			# No permitir múltiples verificaciones activas para la misma app de crédito
			# Se validará a nivel de servicio, no de BD para permitir reintentos
		]
	
	def __str__(self) -> str:
		return f'IdentityVerification #{self.id} ({self.user.email}) - {self.get_status_display()}'
	
	@property
	def is_active(self) -> bool:
		"""Determina si la verificación aún está en proceso"""
		return self.status in [self.Status.PENDING, self.Status.IN_PROGRESS]
	
	@property
	def is_expired(self) -> bool:
		"""Determina si la sesión ha expirado"""
		if self.expires_at:
			return timezone.now() > self.expires_at
		return False
	
	@property
	def is_approved(self) -> bool:
		"""Determina si fue aprobada"""
		return self.status == self.Status.APPROVED and self.decision == self.Decision.APPROVED
	
	@property
	def is_declined(self) -> bool:
		"""Determina si fue rechazada"""
		return self.status == self.Status.DECLINED and self.decision == self.Decision.DECLINED
	
	def mark_approved(self, data: dict = None) -> None:
		"""
		Marca la verificación como aprobada y actualiza la solicitud de crédito.
		
		FASE 3 - Transición Automática con Workflow:
		- Logging detallado con prefijo [KYC]
		- Manejo robusto de errores
		- Validación de credit_application
		- Creación de snapshot de rule_set si no existe
		- Transición automática inteligente:
		  * Si está en SUBMITTED, transiciona a KYC y luego a la siguiente etapa de KYC
		  * Si está en otro estado, transiciona a la siguiente etapa configurada
		- Fallbacks cuando falla la transición
		"""
		import logging
		logger = logging.getLogger(__name__)
		
		# 1. Actualizar estado de verificación
		self.status = self.Status.APPROVED
		self.decision = self.Decision.APPROVED
		self.completed_at = timezone.now()
		
		if data:
			# Extraer campos del resultado sin datos sensibles
			self.full_name = data.get('full_name') or self.full_name
			if not self.full_name and (data.get('first_name') or data.get('last_name')):
				self.full_name = f"{data.get('first_name', '')} {data.get('last_name', '')}".strip()
			
			self.document_type = data.get('document_type', self.document_type)
			self.document_number = data.get('document_number', self.document_number)
			self.date_of_birth = data.get('date_of_birth', self.date_of_birth)
			self.country = data.get('country', self.country)
		
		self.save()
		
		logger.info(
			f"[KYC] Verificación {self.id} marcada como APPROVED para usuario {self.user.email}"
		)
		
		# 2. Actualizar solicitud de crédito si existe
		if not self.credit_application:
			logger.warning(
				f"[KYC] IdentityVerification {self.id} no tiene credit_application asociada"
			)
			return
		
		from api.loans.models import LoanApplication
		
		# Actualizar identity_verification_status
		self.credit_application.identity_verification_status = \
			LoanApplication.IdentityVerificationStatus.APPROVED
		self.credit_application.save(
			update_fields=['identity_verification_status', 'updated_at']
		)
		
		logger.info(
			f"[KYC] Verificación {self.id} aprobada para solicitud {self.credit_application.id}. "
			f"Estado actual: {self.credit_application.status}"
		)
		
		# 3. Intentar transición automática al siguiente estado del workflow
		try:
			from api.loans.services.workflow_service import WorkflowService
			
			# Estrategia de transición inteligente:
			# Si la solicitud está en SUBMITTED y el workflow indica que debe ir a KYC,
			# pero el KYC ya está completado, avanzar directamente a la siguiente etapa de KYC
			
			current_status = self.credit_application.status
			
			# Obtener la siguiente etapa desde el estado actual
			next_stage_from_current = self._get_next_stage_from_status(
				self.credit_application, 
				current_status
			)
			
			# Si la siguiente etapa es KYC, transitamos a KYC primero y luego
			# dejamos que el sistema avance automáticamente (check_and_advance_if_ready)
			# en vez de saltar KYC e ir directo a DOCUMENTS.
			if next_stage_from_current == 'KYC':
				logger.info(
					f"[KYC] La siguiente etapa desde {current_status} es KYC. "
					f"Transicionando a KYC (luego el sistema avanzará automáticamente)."
				)
				
				WorkflowService.transition_state(
					loan_application_id=self.credit_application.id,
					to_status='KYC',
					changed_by=None,
					notes='Transición automática después de completar verificación KYC',
					client_message='Tu identidad ha sido verificada exitosamente.',
					requires_client_action=False,
					send_notification=True
				)
				
				# Ahora que estamos en KYC, intentar avanzar automáticamente
				# a la siguiente etapa (DOCUMENTS) usando el mecanismo estándar
				WorkflowService.check_and_advance_if_ready(
					application=self.credit_application,
					changed_by=None,
					trigger='kyc_completed'
				)
				
				logger.info(
					f"[KYC] Transición a KYC completada para solicitud "
					f"{self.credit_application.id}. Auto-advance solicitado."
				)
			
			elif next_stage_from_current:
				logger.info(
					f"[KYC] Transicionando de {current_status} a {next_stage_from_current}"
				)
				
				WorkflowService.transition_state(
					loan_application_id=self.credit_application.id,
					to_status=next_stage_from_current,
					changed_by=None,  # Sistema
					notes=f'Transición automática después de completar verificación KYC',
					client_message='Tu identidad ha sido verificada exitosamente. Continuamos con el proceso.',
					requires_client_action=False,
					send_notification=True
				)
				
				logger.info(
					f"[KYC] Transición automática exitosa: solicitud {self.credit_application.id} "
					f"ahora en estado {next_stage_from_current}"
				)
			else:
				logger.warning(
					f"[KYC] No se pudo determinar siguiente etapa para solicitud {self.credit_application.id}. "
					f"Creando evento en timeline sin transición."
				)
				self._create_identity_verified_timeline_event()
				
		except Exception as e:
			logger.error(
				f"[KYC] Error en transición automática para solicitud {self.credit_application.id}: "
				f"{type(e).__name__}: {str(e)}",
				exc_info=True
			)
			# Fallback: crear evento en timeline sin transición
			self._create_identity_verified_timeline_event()
	
	def _get_next_stage_from_status(self, loan_application, from_status: str):
		"""
		Obtiene la siguiente etapa del workflow desde un estado específico.
		
		FASE 3 - Transición Dinámica:
		- Busca la etapa especificada en el workflow configurado
		- Retorna su next_stage_on_success
		- Múltiples fallbacks para garantizar transición
		
		Args:
			loan_application: LoanApplication instance
			from_status: Código del estado desde el cual buscar la siguiente etapa
			
		Returns:
			str: Código de la siguiente etapa o None
		"""
		import logging
		logger = logging.getLogger(__name__)
		
		# Verificar si hay rule_set_snapshot
		if not loan_application.rule_set_snapshot:
			logger.warning(
				f"[KYC] Solicitud {loan_application.id} no tiene rule_set_snapshot. "
				f"Verificando product.rule_set..."
			)
			
			# Intentar obtener del producto
			try:
				from api.products.models import CreditProduct
				product = CreditProduct.objects.only('id', 'rule_set_id').get(id=loan_application.product_id)
				
				if product.rule_set_id:
					logger.info(
						f"[KYC] Usando rule_set del producto para solicitud {loan_application.id}"
					)
					# Crear snapshot si no existe
					loan_application.rule_set_snapshot_id = product.rule_set_id
					loan_application.save(update_fields=['rule_set_snapshot'])
				else:
					logger.warning(
						f"[KYC] Producto {loan_application.product_id} no tiene rule_set configurado. "
						f"No se puede determinar siguiente etapa."
					)
					return None
			except Exception as e:
				logger.error(f"[KYC] Error obteniendo rule_set del producto: {e}")
				return None
		
		try:
			# Obtener el rule_set
			from api.loans.models_rules import TenantRuleSet
			rule_set_id = loan_application.rule_set_snapshot_id
			rule_set = TenantRuleSet.objects.get(id=rule_set_id)
			
			# Estrategia 1: Buscar etapa específica en el workflow
			stage = rule_set.workflow_stages.filter(stage_code=from_status).first()
			
			if stage and stage.next_stage_on_success:
				logger.info(
					f"[KYC] Siguiente etapa desde {from_status} para solicitud {loan_application.id}: "
					f"{stage.next_stage_on_success}"
				)
				return stage.next_stage_on_success
			
			# Estrategia 2: Buscar la siguiente etapa en orden
			if stage:
				all_stages = rule_set.workflow_stages.order_by('stage_order')
				next_stage = all_stages.filter(stage_order__gt=stage.stage_order).first()
				
				if next_stage:
					logger.info(
						f"[KYC] Siguiente etapa por orden desde {from_status} para solicitud {loan_application.id}: "
						f"{next_stage.stage_code}"
					)
					return next_stage.stage_code
			
			logger.warning(
				f"[KYC] No se pudo determinar siguiente etapa desde {from_status} "
				f"para solicitud {loan_application.id}"
			)
			return None
			
		except Exception as e:
			logger.error(
				f"[KYC] Error obteniendo siguiente etapa del workflow: {type(e).__name__}: {str(e)}",
				exc_info=True
			)
			return None
	
	def _create_identity_verified_timeline_event(self):
		"""
		Crea un evento en timeline cuando se verifica identidad pero no se transiciona.
		
		FASE 2 - Backend Robusto:
		Este método se llama cuando:
		- La solicitud no está en estado SUBMITTED
		- No se pudo determinar la siguiente etapa
		- Falló la transición automática
		
		Garantiza que el usuario vea en su timeline que su identidad fue verificada,
		incluso si el estado principal no cambió.
		"""
		import logging
		logger = logging.getLogger(__name__)
		
		try:
			from api.loans.models import LoanApplicationStatusHistory
			
			LoanApplicationStatusHistory.objects.create(
				institution=self.credit_application.institution,
				application=self.credit_application,
				previous_status=self.credit_application.status,
				new_status=self.credit_application.status,
				title='Identidad verificada',
				description=f'La identidad del cliente fue verificada exitosamente con {self.provider}',
				actor=self.user,
				is_visible_to_borrower=True,
				client_message='Tu identidad ha sido verificada exitosamente.'
			)
			
			logger.info(
				f"[KYC] Evento de timeline creado para solicitud {self.credit_application.id} "
				f"(sin transición de estado)"
			)
			
		except Exception as e:
			logger.error(
				f"[KYC] Error creando evento de timeline para solicitud {self.credit_application.id}: "
				f"{type(e).__name__}: {str(e)}",
				exc_info=True
			)
	
	def mark_declined(self, reason: str = '') -> None:
		"""Marca la verificación como rechazada"""
		self.status = self.Status.DECLINED
		self.decision = self.Decision.DECLINED
		self.completed_at = timezone.now()
		self.error_message = reason or 'Verificación rechazada por el proveedor'
		self.save()
	
	def mark_error(self, error: str) -> None:
		"""Marca la verificación como error"""
		self.status = self.Status.ERROR
		self.error_message = error
		self.save()
	
	def mark_expired(self) -> None:
		"""Marca la verificación como expirada"""
		self.status = self.Status.EXPIRED
		self.error_message = 'Sesión expirada'
		self.completed_at = timezone.now()
		self.save()


class IdentityVerificationWebhook(models.Model):
	"""
	Modelo para registrar webhooks recibidos del proveedor.
	
	Útil para:
	- Auditar y debuggear eventos
	- Implementar idempotencia (no procesar dos veces el mismo evento)
	- Rastrear qué eventos llegaron y en qué orden
	"""
	
	class Status(models.TextChoices):
		PENDING = 'PENDING', 'Pendiente'
		PROCESSED = 'PROCESSED', 'Procesado'
		FAILED = 'FAILED', 'Fallido'
		DUPLICATE = 'DUPLICATE', 'Duplicado'
	
	# Identidad del evento
	provider = models.CharField(
		max_length=50,
		db_index=True,
		help_text='Proveedor que envió el webhook'
	)
	provider_event_id = models.CharField(
		max_length=255,
		unique=True,
		db_index=True,
		help_text='ID único del evento en el proveedor'
	)
	provider_session_id = models.CharField(
		max_length=255,
		db_index=True,
		help_text='ID de sesión a la que corresponde el evento'
	)
	
	# Payload y control
	payload = models.JSONField(
		help_text='Payload completo del webhook recibido'
	)
	status = models.CharField(
		max_length=20,
		choices=Status.choices,
		default=Status.PENDING,
		help_text='Estado del procesamiento del webhook'
	)
	error_message = models.TextField(
		blank=True,
		help_text='Mensaje de error si el procesamiento falló'
	)
	
	# Verificación asociada (una vez procesada)
	identity_verification = models.ForeignKey(
		IdentityVerification,
		on_delete=models.SET_NULL,
		null=True,
		blank=True,
		related_name='webhooks',
		help_text='Verificación de identidad asociada'
	)
	
	# Fechas
	received_at = models.DateTimeField(
		auto_now_add=True,
		help_text='Cuándo se recibió el webhook'
	)
	processed_at = models.DateTimeField(
		null=True,
		blank=True,
		help_text='Cuándo se procesó'
	)
	
	class Meta:
		db_table = 'identity_verification_webhooks'
		verbose_name = 'Webhook de Verificación de Identidad'
		verbose_name_plural = 'Webhooks de Verificación de Identidad'
		ordering = ['-received_at']
		indexes = [
			models.Index(fields=['provider', 'provider_event_id']),
			models.Index(fields=['provider_session_id', 'status']),
			models.Index(fields=['-received_at']),
		]
	
	def __str__(self) -> str:
		return f'Webhook {self.provider_event_id} - {self.get_status_display()}'
	
	def mark_processed(self, verification: IdentityVerification = None) -> None:
		"""Marca el webhook como procesado"""
		self.status = self.Status.PROCESSED
		self.processed_at = timezone.now()
		if verification:
			self.identity_verification = verification
		self.save()
	
	def mark_failed(self, error: str) -> None:
		"""Marca el webhook como fallido"""
		self.status = self.Status.FAILED
		self.error_message = error
		self.processed_at = timezone.now()
		self.save()
	
	def mark_duplicate(self) -> None:
		"""Marca el webhook como duplicado"""
		self.status = self.Status.DUPLICATE
		self.processed_at = timezone.now()
		self.save()
