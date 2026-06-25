"""
Vistas para gestión genérica de archivos.
"""

from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiExample
from drf_spectacular.types import OpenApiTypes

from api.audit.services import AuditService
from api.storage.models import FileResource
from api.storage.serializers import (
    FileResourceSerializer,
    FileUploadSerializer,
    FileListSerializer,
)
from api.storage.services import StorageService
from api.storage.constants import (
    get_validation_rules,
    is_valid_category,
    get_categories_for_resource_type,
)


class FileUploadAPIView(APIView):
    """
    POST para subir archivos genéricos.
    Soporta múltiples tipos de recursos y categorías.
    """
    
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]
    
    @extend_schema(
        tags=['Storage'],
        summary='Subir archivo genérico',
        description='Sube un archivo al storage con validaciones según el tipo y categoría',
        request=FileUploadSerializer,
        responses={
            200: FileResourceSerializer,
            400: OpenApiTypes.OBJECT,
            403: OpenApiTypes.OBJECT,
        },
        examples=[
            OpenApiExample(
                'Subir documento de cliente',
                value={
                    'file': '(binary)',
                    'resource_type': 'customer_document',
                    'category': 'identity_front',
                    'related_object_type': 'customer',
                    'related_object_id': 123,
                    'description': 'Identificación oficial del cliente',
                },
            ),
        ],
    )
    def post(self, request):
        """Subir archivo genérico."""
        # Validar datos
        serializer = FileUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        uploaded_file = serializer.validated_data['file']
        resource_type = serializer.validated_data['resource_type']
        category = serializer.validated_data.get('category', 'general')
        related_object_type = serializer.validated_data.get('related_object_type')
        related_object_id = serializer.validated_data.get('related_object_id')
        description = serializer.validated_data.get('description', '')
        
        # Validar que la categoría sea válida para el tipo de recurso
        if not is_valid_category(resource_type, category):
            return Response(
                {
                    'success': False,
                    'message': f'Categoría "{category}" no válida para tipo "{resource_type}"',
                    'available_categories': get_categories_for_resource_type(resource_type),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        
        # Obtener reglas de validación
        try:
            validation_rules = get_validation_rules(category)
        except ValueError as e:
            return Response(
                {
                    'success': False,
                    'message': str(e),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        
        # Usar StorageService para subir
        storage_service = StorageService()
        
        try:
            with transaction.atomic():
                # Subir archivo
                file_resource = storage_service.upload_file(
                    file=uploaded_file,
                    tenant=request.tenant,
                    resource_type=resource_type,
                    category=category,
                    uploaded_by=request.user,
                    related_object_type=related_object_type,
                    related_object_id=related_object_id,
                    description=description,
                    allowed_types=validation_rules['allowed_types'],
                    max_size=validation_rules['max_size'],
                )
                
                # Auditoría
                AuditService.log_action(
                    action='upload',
                    resource_type='FileResource',
                    resource_id=file_resource.id,
                    description=f'Upload de {category} ({resource_type})',
                    user=request.user,
                    institution=request.tenant,
                    request=request,
                    metadata={
                        'resource_type': resource_type,
                        'category': category,
                        'file_name': uploaded_file.name,
                        'file_size': uploaded_file.size,
                        'mime_type': file_resource.mime_type,
                        'related_object_type': related_object_type,
                        'related_object_id': related_object_id,
                    },
                )
        
        except Exception as e:
            return Response(
                {
                    'success': False,
                    'message': f'Error al subir archivo: {str(e)}',
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        
        # Retornar archivo subido
        response_serializer = FileResourceSerializer(file_resource, context={'request': request})
        return Response(
            {
                'success': True,
                'message': 'Archivo subido correctamente',
                'file': response_serializer.data,
            },
            status=status.HTTP_201_CREATED,
        )


class FileListAPIView(APIView):
    """
    GET para listar archivos del tenant.
    Soporta filtros por tipo, categoría y objeto relacionado.
    """
    
    permission_classes = [IsAuthenticated]
    
    @extend_schema(
        tags=['Storage'],
        summary='Listar archivos del tenant',
        description='Lista todos los archivos del tenant con filtros opcionales',
        parameters=[
            OpenApiParameter(
                name='resource_type',
                description='Filtrar por tipo de recurso',
                required=False,
                type=str,
            ),
            OpenApiParameter(
                name='category',
                description='Filtrar por categoría',
                required=False,
                type=str,
            ),
            OpenApiParameter(
                name='related_object_type',
                description='Filtrar por tipo de objeto relacionado',
                required=False,
                type=str,
            ),
            OpenApiParameter(
                name='related_object_id',
                description='Filtrar por ID de objeto relacionado',
                required=False,
                type=int,
            ),
            OpenApiParameter(
                name='status',
                description='Filtrar por estado (active, replaced, deleted)',
                required=False,
                type=str,
            ),
        ],
        responses={
            200: FileListSerializer(many=True),
        },
    )
    def get(self, request):
        """Listar archivos del tenant."""
        # Obtener queryset base
        queryset = FileResource.objects.filter(
            tenant=request.tenant
        ).select_related(
            'uploaded_by',
            'replaced_by',
        ).order_by('-created_at')
        
        # Aplicar filtros
        resource_type = request.query_params.get('resource_type')
        if resource_type:
            queryset = queryset.filter(resource_type=resource_type)
        
        category = request.query_params.get('category')
        if category:
            queryset = queryset.filter(category=category)
        
        related_object_type = request.query_params.get('related_object_type')
        if related_object_type:
            queryset = queryset.filter(related_object_type=related_object_type)
        
        related_object_id = request.query_params.get('related_object_id')
        if related_object_id:
            queryset = queryset.filter(related_object_id=related_object_id)
        
        file_status = request.query_params.get('status')
        if file_status:
            queryset = queryset.filter(status=file_status)
        
        # Serializar
        serializer = FileListSerializer(queryset, many=True, context={'request': request})
        
        return Response(
            {
                'success': True,
                'count': queryset.count(),
                'files': serializer.data,
            },
            status=status.HTTP_200_OK,
        )


class FileDetailAPIView(APIView):
    """
    GET/DELETE para gestionar un archivo específico.
    """
    
    permission_classes = [IsAuthenticated]
    
    def _get_file_resource(self, file_id, tenant):
        """Helper para obtener FileResource validando tenant."""
        return get_object_or_404(
            FileResource,
            id=file_id,
            tenant=tenant,
        )
    
    @extend_schema(
        tags=['Storage'],
        summary='Obtener detalles de un archivo',
        description='Obtiene la metadata completa de un archivo',
        responses={
            200: FileResourceSerializer,
            404: OpenApiTypes.OBJECT,
        },
    )
    def get(self, request, file_id):
        """Obtener detalles de un archivo."""
        file_resource = self._get_file_resource(file_id, request.tenant)
        
        serializer = FileResourceSerializer(file_resource, context={'request': request})
        
        return Response(
            {
                'success': True,
                'file': serializer.data,
            },
            status=status.HTTP_200_OK,
        )
    
    @extend_schema(
        tags=['Storage'],
        summary='Eliminar un archivo',
        description='Marca un archivo como eliminado y lo borra del storage',
        responses={
            200: OpenApiTypes.OBJECT,
            404: OpenApiTypes.OBJECT,
            403: OpenApiTypes.OBJECT,
        },
    )
    def delete(self, request, file_id):
        """Eliminar un archivo."""
        file_resource = self._get_file_resource(file_id, request.tenant)
        
        # Verificar que el archivo no esté siendo usado
        if file_resource.is_referenced():
            return Response(
                {
                    'success': False,
                    'message': 'No se puede eliminar un archivo que está siendo usado',
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        
        # Usar StorageService para eliminar
        storage_service = StorageService()
        
        try:
            with transaction.atomic():
                # Eliminar del storage
                storage_service.delete_file(file_resource.storage_path)
                
                # Marcar como eliminado
                file_resource.mark_as_deleted(deleted_by=request.user)
                
                # Auditoría
                AuditService.log_action(
                    action='delete',
                    resource_type='FileResource',
                    resource_id=file_resource.id,
                    description=f'Eliminación de archivo {file_resource.file_name}',
                    user=request.user,
                    institution=request.tenant,
                    request=request,
                    metadata={
                        'resource_type': file_resource.resource_type,
                        'category': file_resource.category,
                        'file_name': file_resource.file_name,
                    },
                )
        
        except Exception as e:
            return Response(
                {
                    'success': False,
                    'message': f'Error al eliminar archivo: {str(e)}',
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        
        return Response(
            {
                'success': True,
                'message': 'Archivo eliminado correctamente',
            },
            status=status.HTTP_200_OK,
        )


class FileDownloadAPIView(APIView):
    """
    GET para obtener URL de descarga de un archivo.
    """
    
    permission_classes = [IsAuthenticated]
    
    @extend_schema(
        tags=['Storage'],
        summary='Obtener URL de descarga',
        description='Genera una URL firmada para descargar el archivo',
        parameters=[
            OpenApiParameter(
                name='expires_in',
                description='Tiempo de expiración en segundos (default: 3600)',
                required=False,
                type=int,
            ),
        ],
        responses={
            200: OpenApiTypes.OBJECT,
            404: OpenApiTypes.OBJECT,
        },
    )
    def get(self, request, file_id):
        """Obtener URL de descarga."""
        file_resource = get_object_or_404(
            FileResource,
            id=file_id,
            tenant=request.tenant,
        )
        
        # Obtener tiempo de expiración
        expires_in = int(request.query_params.get('expires_in', 3600))
        
        # Generar URL firmada
        storage_service = StorageService()
        
        try:
            download_url = storage_service.get_signed_url(
                file_path=file_resource.storage_path,
                expires_in=expires_in,
            )
            
            # Auditoría (opcional, puede generar muchos logs)
            # AuditService.log_action(...)
            
            return Response(
                {
                    'success': True,
                    'download_url': download_url,
                    'expires_in': expires_in,
                    'file_name': file_resource.file_name,
                },
                status=status.HTTP_200_OK,
            )
        
        except Exception as e:
            return Response(
                {
                    'success': False,
                    'message': f'Error al generar URL de descarga: {str(e)}',
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
