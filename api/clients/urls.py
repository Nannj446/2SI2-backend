"""
URLs para gestión de clientes.
"""

from django.urls import path
from api.clients.views import (
    ClientListCreateAPIView,
    ClientDetailAPIView,
    ClientDocumentsAPIView,
)

app_name = 'clients'

urlpatterns = [
    # Gestión de clientes
    path('', ClientListCreateAPIView.as_view(), name='client-list-create'),
    path('<int:client_id>/', ClientDetailAPIView.as_view(), name='client-detail'),
    path('<int:client_id>/documents/', ClientDocumentsAPIView.as_view(), name='client-documents'),
]
