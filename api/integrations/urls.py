"""
URLs para gestión de integraciones externas
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import ExternalIntegrationViewSet, IntegrationLogViewSet

app_name = 'integrations'

# Router principal
router = DefaultRouter()
router.register(r'integrations', ExternalIntegrationViewSet, basename='integration')
router.register(r'logs', IntegrationLogViewSet, basename='integration-log')

urlpatterns = [
    path('', include(router.urls)),
]
