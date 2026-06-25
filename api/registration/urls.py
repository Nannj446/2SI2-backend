from django.urls import path

from .views import RegisterUserAPIView
from .views_client import PublicInstitutionsListView, ClientRegisterView

urlpatterns = [
    # Registro de instituciones (administradores)
    path('auth/register/', RegisterUserAPIView.as_view(), name='auth-register'),
    
    # Registro de clientes
    path('institutions/', PublicInstitutionsListView.as_view(), name='public-institutions'),
    path('clients/register/', ClientRegisterView.as_view(), name='client-register'),
]
