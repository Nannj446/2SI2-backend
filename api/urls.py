from django.urls import include, path

from .views import health_check
from .utils.debug_views import DebugPermissionsView

urlpatterns = [
    path('health/', health_check, name='health-check'),
    path('debug/permissions/', DebugPermissionsView.as_view(), name='debug-permissions'),
    path('', include('api.registration.urls')),
    path('', include('api.authentication.urls')),
    # Parte erick sprint 0
    path('', include('api.roles.urls')),
    # Sprint 3: Gestión de usuarios
    path('users/', include('api.users.urls')),
    # Sprint 6: Panel de administración SaaS
    path('saas/', include('api.saas.urls')),
    # Sistema de backups para tenants
    path('saas/', include('api.backups.urls')),
    # Personalización white-label del tenant
    path('tenant/', include('api.tenants.urls')),
    # Gestión de archivos y storage
    path('storage/', include('api.storage.urls')),
    # Sprint 1: Gestión de clientes/prestatarios
    path('clients/', include('api.clients.urls')),
    # Sprint 2: Gestión de sucursales
    path('branches/', include('api.branches.urls')),
    # Sprint 2: Gestión de productos crediticios
    path('products/', include('api.products.urls')),
    # Sprint 3: Gestión de solicitudes de crédito
    path('loans/', include('api.loans.urls')),
    # Gestión de contratos de crédito
    path('', include('api.contracts.urls')),
    # Garantias y garantes
    path('garantias/', include('api.garantias.urls')),
    # CU-13: Verificación de identidad con Didit
    path('identity-verifications/', include('api.identity_verification.urls')),
    # Auditoría y seguridad (solo SaaS admin)
    path('', include('api.audit.urls')),
    # CU-39: Reportes personalizables con audio
    path('reports/', include('api.reports.urls')),
    # Gestión de integraciones externas
    path('integrations/', include('api.integrations.urls')),
    # Chatbot de asistencia virtual con Groq
    path('chatbot/', include('api.chatbot.urls')),
    # CU-21: Notificaciones Push
    path('notifications/', include('api.notifications.urls')),
    # CU-14: Gestión de Seguros Asociados al Crédito
    path('insurances/', include('api.insurances.urls')),
]

