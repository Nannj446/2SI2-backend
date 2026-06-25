"""
URLs para el sistema de auditoría.
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from api.audit.views import AuditLogViewSet, SecurityEventViewSet

router = DefaultRouter()
router.register(r'logs', AuditLogViewSet, basename='audit-logs')
router.register(r'security-events', SecurityEventViewSet, basename='security-events')

urlpatterns = [
    path('audit/', include(router.urls)),
]
