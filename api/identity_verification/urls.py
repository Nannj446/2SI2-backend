"""
URLs para verificación de identidad
"""
from django.urls import path
from . import views

app_name = 'identity_verification'

urlpatterns = [
	# Listar/Crear verificaciones
	path(
		'',
		views.IdentityVerificationListCreateAPIView.as_view(),
		name='verification-list-create'
	),
	
	# Obtener mi última verificación
	path(
		'me/',
		views.IdentityVerificationMyAPIView.as_view(),
		name='verification-me'
	),
	
	# Detalle de una verificación
	path(
		'<int:pk>/',
		views.IdentityVerificationDetailAPIView.as_view(),
		name='verification-detail'
	),
	
	# Refrescar estado de una verificación
	path(
		'<int:pk>/refresh/',
		views.IdentityVerificationRefreshAPIView.as_view(),
		name='verification-refresh'
	),
	
	# Webhook de Didit
	path(
		'webhook/didit/',
		views.IdentityVerificationWebhookAPIView.as_view(),
		name='webhook-didit'
	),
]
