"""
Vistas para personalización visual white-label del tenant.
"""

from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema, OpenApiParameter

from api.audit.services import AuditService
from api.tenants.models import FinancialInstitution, TenantBranding
from api.tenants.serializers import (
	BrandingFileUploadSerializer,
	TenantBrandingPublicSerializer,
	TenantBrandingSerializer,
	build_default_branding_payload,
)
from api.tenants.services import BrandingService


def _is_tenant_admin(request) -> bool:
	"""Valida que el usuario sea administrador del tenant autenticado."""
	if not request.user.is_authenticated:
		return False

	if not request.tenant:
		return False

	if not hasattr(request.user, 'profile'):
		return False

	# Los SaaS admins pueden gestionar branding de cualquier tenant
	if request.user.profile.is_saas_admin():
		return True

	return request.user.user_roles.filter(
		institution=request.tenant,
		is_active=True,
		role__is_active=True,
	).filter(
		role__name__iexact='Administrador de Institución'
	).exists() or request.user.user_roles.filter(
		institution=request.tenant,
		is_active=True,
		role__is_active=True,
	).filter(
		role__name__icontains='admin'
	).exists()


class TenantBrandingAPIView(APIView):
	"""GET/PUT/PATCH/POST para obtener y actualizar el branding del tenant."""

	permission_classes = [IsAuthenticated]
	parser_classes = [MultiPartParser, FormParser, JSONParser]

	def _resolve_tenant(self, request):
		"""Obtiene el tenant activo desde el middleware o desde la membresía del usuario."""
		if request.tenant:
			return request.tenant

		membership = request.user.institution_memberships.filter(is_active=True).select_related('institution').first()
		if membership:
			request.tenant = membership.institution
			return membership.institution

		return None

	def _validate_access(self, request):
		tenant = self._resolve_tenant(request)
		if not tenant:
			return Response(
				{
					'success': False,
					'message': 'Tenant requerido para personalizar la interfaz.',
				},
				status=status.HTTP_400_BAD_REQUEST,
			)

		if not _is_tenant_admin(request):
			return Response(
				{
					'success': False,
					'message': 'Solo un ADMIN del tenant puede personalizar la interfaz.',
				},
				status=status.HTTP_403_FORBIDDEN,
			)

		return None

	def _get_branding_or_default(self, request):
		"""Obtiene branding desde BD con select_related para optimizar."""
		# Obtener de BD con select_related para optimizar queries
		branding = TenantBranding.objects.filter(
			institution=request.tenant
		).select_related(
			'institution',
			'logo_file',
			'favicon_file',
			'cover_file',
		).first()
		
		if branding:
			return branding
		
		return build_default_branding_payload(request.tenant)

	def _save_branding(self, request, partial: bool = False):
		branding = TenantBranding.objects.filter(institution=request.tenant).first()
		serializer = TenantBrandingSerializer(
			instance=branding,
			data=request.data,
			context={'request': request},
			partial=partial,
		)
		serializer.is_valid(raise_exception=True)

		with transaction.atomic():
			previous_logo = branding.logo if branding and branding.logo else None
			instance = serializer.save(institution=request.tenant)

			if previous_logo and previous_logo != instance.logo:
				previous_logo.delete(save=False)

			AuditService.log_action(
				action='update_partial' if partial else 'update_full',
				resource_type='TenantBranding',
				resource_id=instance.id,
				description=f'Actualización white-label para {request.tenant.name}',
				user=request.user,
				institution=request.tenant,
				request=request,
				metadata={
					'display_name': instance.display_name,
					'primary_color': instance.primary_color,
					'secondary_color': instance.secondary_color,
					'accent_color': instance.accent_color,
				},
			)

		return instance

	@extend_schema(tags=['Tenant Branding'], summary='Obtener branding del tenant')
	def get(self, request):
		access_error = self._validate_access(request)
		if access_error:
			return access_error

		branding = self._get_branding_or_default(request)
		if isinstance(branding, dict):
			return Response(
				{
					'success': True,
					'message': 'Configuración por defecto cargada.',
					'branding': branding,
				},
				status=status.HTTP_200_OK,
			)

		serializer = TenantBrandingSerializer(branding, context={'request': request})
		return Response(
			{
				'success': True,
				'message': 'Configuración de branding cargada.',
				'branding': serializer.data,
			},
			status=status.HTTP_200_OK,
		)

	@extend_schema(tags=['Tenant Branding'], summary='Actualizar branding del tenant')
	def put(self, request):
		access_error = self._validate_access(request)
		if access_error:
			return access_error

		instance = self._save_branding(request, partial=False)
		serializer = TenantBrandingSerializer(instance, context={'request': request})
		return Response(
			{
				'success': True,
				'message': 'Personalización visual guardada correctamente.',
				'branding': serializer.data,
			},
			status=status.HTTP_200_OK,
		)

	@extend_schema(tags=['Tenant Branding'], summary='Actualizar parcialmente branding del tenant')
	def patch(self, request):
		access_error = self._validate_access(request)
		if access_error:
			return access_error

		instance = self._save_branding(request, partial=True)
		serializer = TenantBrandingSerializer(instance, context={'request': request})
		return Response(
			{
				'success': True,
				'message': 'Personalización visual actualizada correctamente.',
				'branding': serializer.data,
			},
			status=status.HTTP_200_OK,
		)

	@extend_schema(tags=['Tenant Branding'], summary='Restaurar branding por defecto')
	def post(self, request):
		access_error = self._validate_access(request)
		if access_error:
			return access_error

		with transaction.atomic():
			branding = TenantBranding.objects.filter(institution=request.tenant).first()
			default_payload = build_default_branding_payload(request.tenant)

			if branding:
				if branding.logo:
					branding.logo.delete(save=False)

				branding.display_name = default_payload['display_name']
				branding.primary_color = default_payload['primary_color']
				branding.secondary_color = default_payload['secondary_color']
				branding.accent_color = default_payload['accent_color']
				branding.background_color = default_payload['background_color']
				branding.text_color = default_payload['text_color']
				branding.is_active = True
				branding.save()
			else:
				branding = TenantBranding.objects.create(
					institution=request.tenant,
					display_name=default_payload['display_name'],
					primary_color=default_payload['primary_color'],
					secondary_color=default_payload['secondary_color'],
					accent_color=default_payload['accent_color'],
					background_color=default_payload['background_color'],
					text_color=default_payload['text_color'],
					is_active=True,
				)

			AuditService.log_action(
				action='system_action',
				resource_type='TenantBranding',
				resource_id=branding.id,
				description=f'Restauración de branding por defecto para {request.tenant.name}',
				user=request.user,
				institution=request.tenant,
				request=request,
				metadata={'reset': True},
			)

		serializer = TenantBrandingSerializer(branding, context={'request': request})
		return Response(
			{
				'success': True,
				'message': 'La personalización visual fue restaurada a los valores por defecto.',
				'branding': serializer.data,
			},
			status=status.HTTP_200_OK,
		)



class BrandingFileUploadAPIView(APIView):
	"""POST para subir archivos de branding (logo, favicon, cover)."""
	
	permission_classes = [IsAuthenticated]
	parser_classes = [MultiPartParser, FormParser]
	
	def _resolve_tenant(self, request):
		"""Obtiene el tenant activo desde el middleware o desde la membresía del usuario."""
		if request.tenant:
			return request.tenant
		
		membership = request.user.institution_memberships.filter(is_active=True).select_related('institution').first()
		if membership:
			request.tenant = membership.institution
			return membership.institution
		
		return None
	
	def _validate_access(self, request):
		tenant = self._resolve_tenant(request)
		if not tenant:
			return Response(
				{
					'success': False,
					'message': 'Tenant requerido para subir archivos de branding.',
				},
				status=status.HTTP_400_BAD_REQUEST,
			)
		
		if not _is_tenant_admin(request):
			return Response(
				{
					'success': False,
					'message': 'Solo un ADMIN del tenant puede subir archivos de branding.',
				},
				status=status.HTTP_403_FORBIDDEN,
			)
		
		return None
	
	@extend_schema(
		tags=['Tenant Branding'],
		summary='Subir archivo de branding (logo, favicon, cover)',
		request=BrandingFileUploadSerializer,
	)
	def post(self, request):
		"""Subir archivo de branding."""
		access_error = self._validate_access(request)
		if access_error:
			return access_error
		
		# Validar datos
		serializer = BrandingFileUploadSerializer(data=request.data)
		serializer.is_valid(raise_exception=True)
		
		uploaded_file = serializer.validated_data['file']
		category = serializer.validated_data['category']
		
		# Obtener o crear branding
		branding, created = TenantBranding.objects.get_or_create(
			institution=request.tenant,
			defaults={
				'display_name': request.tenant.name,
				'is_active': True,
			}
		)
		
		# Usar BrandingService para subir archivo
		branding_service = BrandingService()
		
		try:
			with transaction.atomic():
				# Subir archivo según categoría
				if category == 'logo':
					new_file = branding_service.replace_branding_file(
						tenant=request.tenant,
						old_file=branding.logo_file,
						new_uploaded_file=uploaded_file,
						category='logo',
						uploaded_by=request.user,
					)
					branding.logo_file = new_file
				elif category == 'favicon':
					new_file = branding_service.replace_branding_file(
						tenant=request.tenant,
						old_file=branding.favicon_file,
						new_uploaded_file=uploaded_file,
						category='favicon',
						uploaded_by=request.user,
					)
					branding.favicon_file = new_file
				elif category == 'cover':
					new_file = branding_service.replace_branding_file(
						tenant=request.tenant,
						old_file=branding.cover_file,
						new_uploaded_file=uploaded_file,
						category='cover',
						uploaded_by=request.user,
					)
					branding.cover_file = new_file
				
				branding.save()
				
				# Auditoría
				AuditService.log_action(
					action='upload',
					resource_type='TenantBranding',
					resource_id=branding.id,
					description=f'Upload de {category} para {request.tenant.name}',
					user=request.user,
					institution=request.tenant,
					request=request,
					metadata={
						'category': category,
						'file_name': uploaded_file.name,
						'file_size': uploaded_file.size,
					},
				)
		
		except Exception as e:
			return Response(
				{
					'success': False,
					'message': f'Error al subir archivo: {str(e)}',
				},
				status=status.HTTP_500_INTERNAL_SERVER_ERROR,
			)
		
		# Retornar branding actualizado
		response_serializer = TenantBrandingSerializer(branding, context={'request': request})
		return Response(
			{
				'success': True,
				'message': f'{category.capitalize()} subido correctamente.',
				'branding': response_serializer.data,
			},
			status=status.HTTP_200_OK,
		)


class BrandingFileDeleteAPIView(APIView):
	"""DELETE para eliminar archivos de branding (logo, favicon, cover)."""
	
	permission_classes = [IsAuthenticated]
	
	def _resolve_tenant(self, request):
		"""Obtiene el tenant activo desde el middleware o desde la membresía del usuario."""
		if request.tenant:
			return request.tenant
		
		membership = request.user.institution_memberships.filter(is_active=True).select_related('institution').first()
		if membership:
			request.tenant = membership.institution
			return membership.institution
		
		return None
	
	def _validate_access(self, request):
		tenant = self._resolve_tenant(request)
		if not tenant:
			return Response(
				{
					'success': False,
					'message': 'Tenant requerido para eliminar archivos de branding.',
				},
				status=status.HTTP_400_BAD_REQUEST,
			)
		
		if not _is_tenant_admin(request):
			return Response(
				{
					'success': False,
					'message': 'Solo un ADMIN del tenant puede eliminar archivos de branding.',
				},
				status=status.HTTP_403_FORBIDDEN,
			)
		
		return None
	
	@extend_schema(
		tags=['Tenant Branding'],
		summary='Eliminar archivo de branding',
		parameters=[
			OpenApiParameter(
				name='category',
				description='Tipo de archivo a eliminar: logo, favicon o cover',
				required=True,
				type=str,
			),
		],
	)
	def delete(self, request):
		"""Eliminar archivo de branding."""
		access_error = self._validate_access(request)
		if access_error:
			return access_error
		
		category = request.query_params.get('category')
		
		# Validar que se envió el parámetro category
		if not category:
			return Response(
				{
					'success': False,
					'message': 'El parámetro "category" es requerido. Debe ser: logo, favicon o cover.',
					'error': 'missing_category_parameter',
				},
				status=status.HTTP_400_BAD_REQUEST,
			)
		
		# Validar que la categoría es válida
		if category not in ['logo', 'favicon', 'cover']:
			return Response(
				{
					'success': False,
					'message': f'Categoría inválida: "{category}". Debe ser: logo, favicon o cover.',
					'error': 'invalid_category',
					'received': category,
				},
				status=status.HTTP_400_BAD_REQUEST,
			)
		
		# Obtener branding
		try:
			branding = TenantBranding.objects.get(institution=request.tenant)
		except TenantBranding.DoesNotExist:
			return Response(
				{
					'success': False,
					'message': 'No existe configuración de branding para este tenant.',
				},
				status=status.HTTP_404_NOT_FOUND,
			)
		
		# Obtener archivo según categoría
		file_to_delete = None
		if category == 'logo':
			file_to_delete = branding.logo_file
		elif category == 'favicon':
			file_to_delete = branding.favicon_file
		elif category == 'cover':
			file_to_delete = branding.cover_file
		
		if not file_to_delete:
			return Response(
				{
					'success': False,
					'message': f'No existe {category} para eliminar.',
				},
				status=status.HTTP_404_NOT_FOUND,
			)
		
		# Eliminar archivo
		branding_service = BrandingService()
		
		try:
			with transaction.atomic():
				branding_service.delete_branding_file(file_to_delete)
				
				# Actualizar referencia en branding
				if category == 'logo':
					branding.logo_file = None
				elif category == 'favicon':
					branding.favicon_file = None
				elif category == 'cover':
					branding.cover_file = None
				
				branding.save()
				
				# Auditoría
				AuditService.log_action(
					action='delete',
					resource_type='TenantBranding',
					resource_id=branding.id,
					description=f'Eliminación de {category} para {request.tenant.name}',
					user=request.user,
					institution=request.tenant,
					request=request,
					metadata={'category': category},
				)
		
		except Exception as e:
			return Response(
				{
					'success': False,
					'message': f'Error al eliminar archivo: {str(e)}',
				},
				status=status.HTTP_500_INTERNAL_SERVER_ERROR,
			)
		
		return Response(
			{
				'success': True,
				'message': f'{category.capitalize()} eliminado correctamente.',
			},
			status=status.HTTP_200_OK,
		)


class TenantBrandingPublicAPIView(APIView):
	"""GET público para obtener branding por slug (sin autenticación)."""
	
	permission_classes = [AllowAny]
	
	@extend_schema(
		tags=['Tenant Branding'],
		summary='Obtener branding público por slug',
		parameters=[
			OpenApiParameter(
				name='slug',
				description='Slug del tenant',
				required=True,
				type=str,
				location=OpenApiParameter.PATH,
			),
		],
	)
	def get(self, request, slug: str):
		"""Obtener branding público por slug con queries optimizadas."""
		# Buscar tenant por slug
		tenant = get_object_or_404(FinancialInstitution, slug=slug, is_active=True)
		
		# Buscar branding con select_related para optimizar queries
		branding = TenantBranding.objects.filter(
			institution__slug=slug,
			is_active=True,
		).select_related(
			'institution',
			'logo_file',
			'favicon_file',
			'cover_file',
		).first()
		
		if not branding:
			# Retornar configuración por defecto
			default_payload = build_default_branding_payload(tenant)
			return Response(
				{
					'success': True,
					'message': 'Configuración por defecto cargada.',
					'branding': default_payload,
				},
				status=status.HTTP_200_OK,
			)
		
		# Serializar branding
		serializer = TenantBrandingPublicSerializer(branding)
		return Response(
			{
				'success': True,
				'message': 'Branding cargado correctamente.',
				'branding': serializer.data,
			},
			status=status.HTTP_200_OK,
		)
