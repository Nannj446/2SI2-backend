"""
URLs para notificaciones push.
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    PushTokenViewSet,
    NotificationViewSet,
    NotificationTemplateViewSet,
    SendNotificationView,
    SendMoraAlertView,
    RegisterTokenView,
    UnregisterTokenView,
)

router = DefaultRouter()
router.register(r'tokens', PushTokenViewSet, basename='push-tokens')
router.register(r'', NotificationViewSet, basename='notifications')
router.register(r'templates', NotificationTemplateViewSet, basename='notification-templates')

urlpatterns = [
    # Rutas explícitas ANTES del router para evitar conflicto con (?P<pk>[^/.]+)/
    path('send/', SendNotificationView.as_view(), name='send-notification'),
    path('send/mora/', SendMoraAlertView.as_view(), name='send-mora-alert'),
    path('register-token/', RegisterTokenView.as_view(), name='register-token'),
    path('unregister-token/', UnregisterTokenView.as_view(), name='unregister-token'),
    # Router va al final
    path('', include(router.urls)),
]
