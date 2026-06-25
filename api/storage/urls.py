"""
URLs para gestión de archivos.
"""

from django.urls import path
from api.storage.views import (
    FileUploadAPIView,
    FileListAPIView,
    FileDetailAPIView,
    FileDownloadAPIView,
)

app_name = 'storage'

urlpatterns = [
    # Upload genérico
    path('files/upload/', FileUploadAPIView.as_view(), name='file-upload'),
    
    # Listado de archivos
    path('files/', FileListAPIView.as_view(), name='file-list'),
    
    # Detalle de archivo
    path('files/<uuid:file_id>/', FileDetailAPIView.as_view(), name='file-detail'),
    
    # Descarga de archivo
    path('files/<uuid:file_id>/download/', FileDownloadAPIView.as_view(), name='file-download'),
]
