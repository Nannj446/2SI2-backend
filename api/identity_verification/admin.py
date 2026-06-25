"""
Configuración Django Admin para verificación de identidad
"""
from django.contrib import admin
from api.identity_verification.models import IdentityVerification, IdentityVerificationWebhook


@admin.register(IdentityVerification)
class IdentityVerificationAdmin(admin.ModelAdmin):
	"""Admin para IdentityVerification"""
	
	list_display = [
		'id', 'user', 'provider', 'status', 'decision',
		'document_number', 'started_at', 'completed_at'
	]
	list_filter = ['status', 'decision', 'provider', 'created_at']
	search_fields = ['user__email', 'user__first_name', 'document_number']
	readonly_fields = [
		'id', 'provider_session_id', 'started_at', 'created_at', 'updated_at',
		'raw_response'
	]
	
	fieldsets = (
		('Identidad', {
			'fields': ('user', 'institution', 'credit_application', 'branch')
		}),
		('Proveedor', {
			'fields': ('provider', 'provider_session_id', 'provider_session_token', 'verification_url')
		}),
		('Estado', {
			'fields': ('status', 'decision', 'error_message')
		}),
		('Datos Verificados', {
			'fields': (
				'full_name', 'document_type', 'document_number',
				'date_of_birth', 'country'
			)
		}),
		('Fechas', {
			'fields': ('started_at', 'completed_at', 'expires_at', 'webhook_received_at', 'created_at', 'updated_at'),
			'classes': ('collapse',)
		}),
		('Respuesta Cruda', {
			'fields': ('raw_response',),
			'classes': ('collapse',)
		}),
	)


@admin.register(IdentityVerificationWebhook)
class IdentityVerificationWebhookAdmin(admin.ModelAdmin):
	"""Admin para webhooks"""
	
	list_display = [
		'id', 'provider', 'status', 'received_at', 'processed_at'
	]
	list_filter = ['status', 'provider', 'received_at']
	search_fields = ['provider_event_id', 'provider_session_id']
	readonly_fields = ['id', 'received_at', 'processed_at', 'payload']
	
	fieldsets = (
		('Evento', {
			'fields': ('provider', 'provider_event_id', 'provider_session_id')
		}),
		('Estado', {
			'fields': ('status', 'error_message', 'identity_verification')
		}),
		('Fechas', {
			'fields': ('received_at', 'processed_at')
		}),
		('Payload', {
			'fields': ('payload',),
			'classes': ('collapse',)
		}),
	)
