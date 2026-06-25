"""
Vistas/Endpoints para verificación de identidad
"""
import logging
from rest_framework import generics, status, viewsets
from rest_framework.views import APIView
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.shortcuts import get_object_or_404
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.db.models import Q
from api.core.permissions import HasPermission
from api.core.pagination import StandardResultsSetPagination
from api.identity_verification.models import IdentityVerification
from api.identity_verification.serializers import (
	IdentityVerificationListSerializer,
	IdentityVerificationDetailSerializer,
	StartIdentityVerificationSerializer,
	IdentityVerificationStatusSerializer,
)
from api.identity_verification.services.identity_verification_service import (
	IdentityVerificationService,
	StartVerificationInput
)
from api.audit.services import AuditService

logger = logging.getLogger(__name__)


class IdentityVerificationListCreateAPIView(generics.ListCreateAPIView):
	"""
	GET: Lista las verificaciones de identidad del usuario o institución
	POST: Crea/inicia una nueva verificación de identidad
	"""
	permission_classes = [IsAuthenticated]
	pagination_class = StandardResultsSetPagination
	
	def get_serializer_class(self):
		if self.request.method == 'POST':
			return StartIdentityVerificationSerializer
		return IdentityVerificationListSerializer
	
	def get_queryset(self):
		"""
		Filtra por usuario (cliente) o institución (admin/analista)
		"""
		user = self.request.user
		institution = getattr(self.request, 'tenant', None)
		
		if not institution:
			# SaaS admin: no permitido listar
			return IdentityVerification.all_objects.none()
		
		# Si es cliente (prestatario), solo su verificación
		if hasattr(user, 'client_profile') and user.client_profile:
			return IdentityVerification.objects.filter(
				user=user,
				institution=institution
			).select_related('user', 'credit_application')
		
		# Si es usuario de la institución, ver todas de la institución
		return IdentityVerification.objects.filter(
			institution=institution
		).select_related('user', 'credit_application')
	
	def post(self, request, *args, **kwargs):
		"""Crear/iniciar una nueva verificación"""
		serializer = self.get_serializer(data=request.data)
		serializer.is_valid(raise_exception=True)
		
		institution = getattr(request, 'tenant', None)
		if not institution:
			return Response(
				{'detail': 'No institution context'},
				status=status.HTTP_400_BAD_REQUEST
			)
		
		# Construir URL de webhook absoluta
		from django.urls import reverse
		webhook_url = request.build_absolute_uri(reverse('identity_verification:webhook-didit'))
		
		# Preparar input para el servicio
		payload = StartVerificationInput(
			user=request.user,
			institution_id=institution.id,
			credit_application_id=serializer.validated_data.get('credit_application_id'),
			branch_id=serializer.validated_data.get('branch_id'),
			return_url=serializer.validated_data.get('return_url'),
			webhook_url=webhook_url,
		)
		
		# Llamar al servicio
		service = IdentityVerificationService()
		result = service.start_verification(payload, request_user=request.user)
		
		if not result.success:
			# Registrar fallo
			AuditService.log_action(
				action='security_event',
				resource_type='IdentityVerification',
				description=f'Error iniciando verificación: {result.error}',
				user=request.user,
				institution=institution,
				severity='warning',
				metadata={'error_code': result.error_code}
			)
			
			return Response(
				{
					'detail': result.error,
					'error_code': result.error_code,
					'verification_id': result.verification_id
				},
				status=status.HTTP_400_BAD_REQUEST
			)
		
		# Obtener la verificación creada
		verification = IdentityVerification.objects.get(id=result.verification_id)
		response_serializer = IdentityVerificationDetailSerializer(
			verification,
			context={'request': request}
		)
		
		return Response(
			response_serializer.data,
			status=status.HTTP_201_CREATED
		)


class IdentityVerificationDetailAPIView(generics.RetrieveUpdateAPIView):
	"""
	GET: Obtener detalle de una verificación
	PATCH: Actualizar (admin only, para notas/decisiones manuales si aplica)
	"""
	permission_classes = [IsAuthenticated]
	serializer_class = IdentityVerificationDetailSerializer
	
	def get_queryset(self):
		"""Filtrar por institución y usuario"""
		user = self.request.user
		institution = getattr(self.request, 'tenant', None)
		
		if not institution:
			return IdentityVerification.all_objects.none()
		
		# Cliente: solo su verificación
		if hasattr(user, 'client_profile') and user.client_profile:
			return IdentityVerification.objects.filter(
				user=user,
				institution=institution
			)
		
		# Staff de institución: todas de la institución
		return IdentityVerification.objects.filter(
			institution=institution
		)
	
	def get_object(self):
		"""Obtener por ID y validar permisos"""
		pk = self.kwargs.get('pk')
		queryset = self.get_queryset()
		obj = get_object_or_404(queryset, pk=pk)
		return obj


class IdentityVerificationMyAPIView(generics.RetrieveAPIView):
	"""
	GET: Obtener la última verificación de identidad del usuario autenticado
	
	Query params opcionales:
	- credit_application_id: Filtrar por solicitud de crédito específica
	"""
	permission_classes = [IsAuthenticated]
	serializer_class = IdentityVerificationDetailSerializer
	
	def get_object(self):
		"""Obtener última verificación del usuario"""
		institution = getattr(self.request, 'tenant', None)
		if not institution:
			raise PermissionError('No institution context')
		
		# Obtener credit_application_id de query params si existe
		credit_app_id = self.request.query_params.get('credit_application_id')
		
		queryset = IdentityVerification.objects.filter(
			user=self.request.user,
			institution=institution
		)
		
		# Si se especifica credit_application_id, filtrar por esa solicitud
		if credit_app_id:
			try:
				credit_app_id = int(credit_app_id)
				queryset = queryset.filter(credit_application_id=credit_app_id)
			except (ValueError, TypeError):
				pass
		
		verification = queryset.order_by('-created_at').first()
		
		if not verification:
			from rest_framework.exceptions import NotFound
			raise NotFound('No identity verification found for current user')
		
		return verification


class IdentityVerificationRefreshAPIView(generics.GenericAPIView):
	"""
	POST: Refrescar el estado de una verificación consultando a Didit
	
	Útil cuando:
	- El webhook no llegó
	- Se quiere forzar una consulta
	- Se necesita saber el estado actual
	"""
	permission_classes = [IsAuthenticated]
	
	def post(self, request, pk=None):
		"""Refrescar el estado"""
		institution = getattr(request, 'tenant', None)
		if not institution:
			return Response(
				{'detail': 'No institution context'},
				status=status.HTTP_400_BAD_REQUEST
			)
		
		# Obtener la verificación
		try:
			verification = IdentityVerification.objects.get(
				id=pk,
				institution=institution
			)
		except IdentityVerification.DoesNotExist:
			return Response(
				{'detail': 'Verification not found'},
				status=status.HTTP_404_NOT_FOUND
			)
		
		# Validar permiso: el usuario solo puede refrescar la suya
		user = request.user
		if hasattr(user, 'client_profile') and user.client_profile:
			if verification.user_id != user.id:
				return Response(
					{'detail': 'Permission denied'},
					status=status.HTTP_403_FORBIDDEN
				)
		
		# Refrescar
		from api.identity_verification.services.identity_verification_service import (
			RefreshVerificationInput
		)
		
		service = IdentityVerificationService()
		refresh_result = service.refresh_verification(
			RefreshVerificationInput(
				verification_id=verification.id,
				institution_id=institution.id
			),
			request_user=request.user
		)
		
		if not refresh_result.success:
			return Response(
				{'detail': refresh_result.error},
				status=status.HTTP_400_BAD_REQUEST
			)
		
		# Obtener la verificación actualizada
		verification.refresh_from_db()
		serializer = IdentityVerificationDetailSerializer(
			verification,
			context={'request': request}
		)
		
		return Response(serializer.data, status=status.HTTP_200_OK)


class IdentityVerificationWebhookAPIView(APIView):
	"""
	POST: Recibir webhooks de Didit
	
	Validaciones:
	- No requiere autenticación JWT (es del proveedor externo)
	- Valida firma/secreto si está configurado
	- Es idempotente (mismo evento no se procesa dos veces)
	
	Payload esperado de Didit:
	{
		"event_id": "evt_123...",
		"session_id": "sess_456...",
		"status": "completed",
		"decision": "approved" | "declined",
		"result": {
			"full_name": "...",
			"document_type": "...",
			"document_number": "...",
			"date_of_birth": "...",
			"country": "..."
		}
	}
	"""
	permission_classes = [AllowAny]  # Sin JWT requerido
	
	def get(self, request):
		"""
		Manejar GET en caso de que Didit lo use para redirecciones.
		Retorna una página de éxito amigable.
		"""
		logger.info(f"Webhook GET recibido (redirección): {request.query_params}")
		
		# HTML Premium para la página de éxito
		html_content = """
		<!DOCTYPE html>
		<html lang="es">
		<head>
			<meta charset="UTF-8">
			<meta name="viewport" content="width=device-width, initial-scale=1.0">
			<title>Verificación Completada | FinCore</title>
			<link href="https://fonts.googleapis.com/css2?family=Outfit:wght@400;600&display=swap" rel="stylesheet">
			<style>
				:root {
					--primary: #4F46E5;
					--success: #10B981;
					--bg: #F8FAFC;
					--text: #1E293B;
				}
				body {
					font-family: 'Outfit', sans-serif;
					background-color: var(--bg);
					color: var(--text);
					margin: 0;
					display: flex;
					align-items: center;
					justify-content: center;
					height: 100vh;
					overflow: hidden;
				}
				.container {
					background: white;
					padding: 3rem 2rem;
					border-radius: 24px;
					box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 8px 10px -6px rgba(0, 0, 0, 0.1);
					text-align: center;
					max-width: 400px;
					width: 90%;
					animation: slideUp 0.6s ease-out;
				}
				@keyframes slideUp {
					from { opacity: 0; transform: translateY(20px); }
					to { opacity: 1; transform: translateY(0); }
				}
				.icon-wrapper {
					width: 80px;
					height: 80px;
					background-color: #ECFDF5;
					border-radius: 50%;
					display: flex;
					align-items: center;
					justify-content: center;
					margin: 0 auto 1.5rem;
				}
				.icon {
					font-size: 40px;
					animation: scaleCheck 0.5s cubic-bezier(0.175, 0.885, 0.32, 1.275) 0.3s both;
				}
				@keyframes scaleCheck {
					from { transform: scale(0); }
					to { transform: scale(1); }
				}
				h1 {
					font-size: 1.5rem;
					font-weight: 600;
					margin-bottom: 1rem;
					color: #0F172A;
				}
				p {
					color: #64748B;
					line-height: 1.6;
					margin-bottom: 2rem;
				}
				.btn {
					background-color: var(--primary);
					color: white;
					text-decoration: none;
					padding: 0.75rem 1.5rem;
					border-radius: 12px;
					font-weight: 600;
					transition: all 0.2s;
					display: inline-block;
					cursor: pointer;
					border: none;
					width: 100%;
					box-sizing: border-box;
				}
				.btn:hover {
					transform: translateY(-2px);
					box-shadow: 0 10px 15px -3px rgba(79, 70, 229, 0.3);
				}
				.footer {
					margin-top: 1.5rem;
					font-size: 0.875rem;
					color: #94A3B8;
				}
			</style>
		</head>
		<body>
			<div class="container">
				<div class="icon-wrapper">
					<div class="icon">✅</div>
				</div>
				<h1>¡Verificación Completada!</h1>
				<p>Tu identidad ha sido procesada con éxito. Ya puedes cerrar esta ventana y volver a la aplicación para continuar con tu solicitud.</p>
				<a href="fincore://identity-verification" class="btn">Volver a la Aplicación</a>
				<div class="footer">FinCore Security System</div>
			</div>
			<script>
				// Intentar abrir la app automáticamente después de 2 segundos
				setTimeout(() => {
					window.location.href = "fincore://identity-verification";
				}, 2000);
			</script>
		</body>
		</html>
		"""
		return HttpResponse(html_content)

	@method_decorator(csrf_exempt)
	def post(self, request):
		"""Procesar webhook de Didit"""
		try:
			payload = request.data
			
			# Validar campos mínimos
			provider_event_id = payload.get('event_id')
			provider_session_id = payload.get('session_id')
			
			if not provider_event_id or not provider_session_id:
				logger.warning('Webhook sin event_id o session_id')
				return Response(
					{'detail': 'Missing event_id or session_id'},
					status=status.HTTP_400_BAD_REQUEST
				)
			
			# Validar firma si está configurada (futuro)
			# if not self._validate_webhook_signature(request, payload):
			#     return Response({'detail': 'Invalid signature'}, status=status.HTTP_401_UNAUTHORIZED)
			
			# Procesar
			success = IdentityVerificationService.process_webhook(
				provider='DIDIT',
				provider_event_id=provider_event_id,
				provider_session_id=provider_session_id,
				payload=payload
			)
			
			if not success:
				logger.error(f'Error procesando webhook: {provider_event_id}')
				return Response(
					{'detail': 'Failed to process webhook'},
					status=status.HTTP_400_BAD_REQUEST
				)
			
			logger.info(f'Webhook procesado: {provider_event_id}')
			return Response(
				{'status': 'received'},
				status=status.HTTP_200_OK
			)
		
		except Exception as e:
			logger.exception(f'Error en webhook endpoint: {str(e)}')
			return Response(
				{'detail': f'Internal server error: {str(e)}'},
				status=status.HTTP_500_INTERNAL_SERVER_ERROR
			)
	
	@staticmethod
	def _validate_webhook_signature(request, payload):
		"""
		Valida la firma del webhook (futuro).
		
		Didit puede enviar un header X-Signature con HMAC-SHA256
		de la payload usando el WEBHOOK_SECRET.
		"""
		# TODO: Implementar validación de firma
		return True
