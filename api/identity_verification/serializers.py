"""
Serializers para verificación de identidad
"""
from rest_framework import serializers
from django.utils import timezone
from api.identity_verification.models import IdentityVerification, IdentityVerificationWebhook
from api.users.serializers import UserSerializer


class IdentityVerificationListSerializer(serializers.ModelSerializer):
	"""Serializer para lista de verificaciones (optimizado)"""
	
	user_email = serializers.CharField(source='user.email', read_only=True)
	user_full_name = serializers.CharField(source='user.get_full_name', read_only=True)
	credit_application_number = serializers.CharField(
		source='credit_application.application_number',
		read_only=True,
		allow_null=True
	)
	
	class Meta:
		model = IdentityVerification
		fields = [
			'id', 'user', 'user_email', 'user_full_name',
			'provider', 'status', 'decision',
			'credit_application', 'credit_application_number',
			'document_type', 'document_number',
			'started_at', 'completed_at', 'created_at'
		]
		read_only_fields = fields


class IdentityVerificationDetailSerializer(serializers.ModelSerializer):
	"""Serializer completo para detalle de verificación"""
	
	user = UserSerializer(read_only=True)
	credit_application_number = serializers.CharField(
		source='credit_application.application_number',
		read_only=True,
		allow_null=True
	)
	branch_name = serializers.CharField(
		source='branch.name',
		read_only=True,
		allow_null=True
	)
	institution_name = serializers.CharField(
		source='institution.name',
		read_only=True
	)
	
	class Meta:
		model = IdentityVerification
		fields = [
			'id',
			'user', 'institution', 'institution_name',
			'credit_application', 'credit_application_number',
			'branch', 'branch_name',
			'provider', 'provider_session_id',
			'status', 'decision',
			'document_type', 'document_number',
			'full_name', 'date_of_birth', 'country',
			'error_message',
			'verification_url',
			'raw_response',
			'started_at', 'completed_at', 'expires_at', 'webhook_received_at',
			'created_at', 'updated_at'
		]
		read_only_fields = fields


class StartIdentityVerificationSerializer(serializers.Serializer):
	"""Serializer para iniciar una verificación"""
	
	credit_application_id = serializers.IntegerField(required=False, allow_null=True)
	branch_id = serializers.IntegerField(required=False, allow_null=True)
	return_url = serializers.CharField(required=False, allow_blank=True, allow_null=True)
	
	def validate_credit_application_id(self, value):
		"""Validar que la credit_application existe"""
		if value is None:
			return value
		
		from api.loans.models import LoanApplication
		try:
			LoanApplication.objects.get(id=value)
		except LoanApplication.DoesNotExist:
			raise serializers.ValidationError('Solicitud de crédito no encontrada')
		
		return value
	
	def validate_branch_id(self, value):
		"""Validar que la branch existe"""
		if value is None:
			return value
		
		from api.branches.models import Branch
		try:
			Branch.objects.get(id=value)
		except Branch.DoesNotExist:
			raise serializers.ValidationError('Sucursal no encontrada')
		
		return value


class IdentityVerificationWebhookSerializer(serializers.ModelSerializer):
	"""Serializer para webhooks (auditoría)"""
	
	class Meta:
		model = IdentityVerificationWebhook
		fields = [
			'id', 'provider', 'provider_event_id', 'provider_session_id',
			'status', 'error_message', 'identity_verification',
			'received_at', 'processed_at'
		]
		read_only_fields = fields


class RefreshIdentityVerificationSerializer(serializers.Serializer):
	"""Serializer para refrescar una verificación"""
	
	# Sin campos requeridos, el ID viene en la URL
	pass


class IdentityVerificationStatusSerializer(serializers.ModelSerializer):
	"""Serializer simplificado para consultar solo el estado"""
	
	class Meta:
		model = IdentityVerification
		fields = [
			'id', 'status', 'decision', 'completed_at', 'error_message'
		]
		read_only_fields = fields
