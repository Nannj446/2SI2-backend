"""
URLs para personalización visual white-label del tenant.
"""

from django.urls import path

from .views import (
	BrandingFileDeleteAPIView,
	BrandingFileUploadAPIView,
	TenantBrandingAPIView,
	TenantBrandingPublicAPIView,
)

app_name = 'tenants'

urlpatterns = [
	# Endpoints autenticados (admin del tenant)
	path('branding/', TenantBrandingAPIView.as_view(), name='tenant-branding'),
	path('branding/reset/', TenantBrandingAPIView.as_view(), name='tenant-branding-reset'),
	path('branding/upload/', BrandingFileUploadAPIView.as_view(), name='tenant-branding-upload'),
	path('branding/delete/', BrandingFileDeleteAPIView.as_view(), name='tenant-branding-delete'),
	
	# Endpoint público (sin autenticación)
	path('branding/public/<str:slug>/', TenantBrandingPublicAPIView.as_view(), name='tenant-branding-public'),
]
