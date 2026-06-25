"""
Views para gestión de clientes.
"""

from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Q
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiExample
from drf_spectacular.types import OpenApiTypes

from api.clients.models import Client, ClientDocument
from api.clients.serializers import (
    ClientSerializer,
    CreateClientSerializer,
    UpdateClientSerializer,
    ClientListSerializer,
    ClientDocumentSerializer,
)
from api.clients.services import (
    ClientManagementService,
    CreateClientInput,
    UpdateClientInput,
)
from api.core.permissions import require_permission
from api.core.pagination import StandardResultsSetPagination


class ClientListCreateAPIView(APIView):
    """
    Vista para listar y crear clientes.
    
    GET /api/clients/ - Lista todos los clientes de la institución
    POST /api/clients/ - Crea un nuevo cliente
    """
    permission_classes = [IsAuthenticated, require_permission('clients.view')]
    
    @extend_schema(
        tags=['Clientes'],
        summary='Listar clientes',
        description='Obtiene la lista de clientes de la institución financiera con filtros opcionales y paginación',
        parameters=[
            OpenApiParameter(
                name='page',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description='Número de página (default: 1)',
                required=False,
            ),
            OpenApiParameter(
                name='page_size',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description='Tamaño de página (default: 20, max: 100)',
                required=False,
            ),
            OpenApiParameter(
                name='is_active',
                type=OpenApiTypes.BOOL,
                location=OpenApiParameter.QUERY,
                description='Filtrar por estado activo/inactivo',
                required=False,
            ),
            OpenApiParameter(
                name='kyc_status',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description='Filtrar por estado KYC (PENDING, VERIFIED, REJECTED)',
                required=False,
                enum=['PENDING', 'VERIFIED', 'REJECTED', 'EXPIRED'],
            ),
            OpenApiParameter(
                name='search',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description='Buscar por nombre, apellido, CI o email',
                required=False,
            ),
        ],
        responses={
            200: ClientListSerializer(many=True),
            401: OpenApiTypes.OBJECT,
            403: OpenApiTypes.OBJECT,
        },
    )
    def get(self, request):
        """Lista clientes con filtros opcionales y paginación."""
        institution_id = request.user_institution_id
        
        # Parámetros de filtro
        is_active = request.query_params.get('is_active')
        kyc_status = request.query_params.get('kyc_status')
        search = request.query_params.get('search')
        
        # Construir queryset con optimización de consultas
        queryset = Client.objects.filter(
            institution_id=institution_id
        ).select_related('user', 'user__profile')
        
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == 'true')
        
        if kyc_status:
            queryset = queryset.filter(kyc_status=kyc_status)
        
        if search:
            queryset = queryset.filter(
                Q(user__first_name__icontains=search) |
                Q(user__last_name__icontains=search) |
                Q(document_number__icontains=search) |
                Q(user__email__icontains=search)
            )
        
        queryset = queryset.order_by('-created_at')
        
        # Aplicar paginación
        paginator = StandardResultsSetPagination()
        paginated_queryset = paginator.paginate_queryset(queryset, request)
        
        # Serializar
        serializer = ClientListSerializer(paginated_queryset, many=True)
        
        # Retornar respuesta paginada
        return paginator.get_paginated_response(serializer.data)
    
    @extend_schema(
        tags=['Clientes'],
        summary='Crear cliente',
        description='Crea un nuevo cliente/prestatario en el sistema',
        request=CreateClientSerializer,
        responses={
            201: ClientSerializer,
            400: OpenApiTypes.OBJECT,
            401: OpenApiTypes.OBJECT,
            403: OpenApiTypes.OBJECT,
        },
        examples=[
            OpenApiExample(
                'Ejemplo de cliente',
                value={
                    'client_type': 'NATURAL',
                    'first_name': 'Juan',
                    'last_name': 'Pérez',
                    'document_type': 'CI',
                    'document_number': '12345678',
                    'document_extension': 'LP',
                    'birth_date': '1990-01-15',
                    'email': 'juan.perez@example.com',
                    'phone': '70123456',
                    'address': 'Calle Ejemplo 123',
                    'city': 'La Paz',
                    'department': 'La Paz',
                    'employment_status': 'EMPLOYED',
                    'employer_name': 'Empresa XYZ',
                    'monthly_income': 5000.00,
                },
                request_only=True,
            ),
        ],
    )
    def post(self, request):
        """Crea un nuevo cliente."""
        # Verificar permiso de creación ANTES de validar datos
        if not (hasattr(request.user, 'profile') and 
                (request.user.profile.is_saas_admin() or 
                 request.user.profile.has_permission('clients.create', request.tenant))):
            return Response({
                'success': False,
                'message': 'No tiene permiso para crear clientes'
            }, status=status.HTTP_403_FORBIDDEN)
        
        serializer = CreateClientSerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response({
                'success': False,
                'message': 'Datos inválidos',
                'errors': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Crear input para el servicio
        input_data = CreateClientInput(
            client_type=serializer.validated_data['client_type'],
            first_name=serializer.validated_data['first_name'],
            last_name=serializer.validated_data['last_name'],
            document_type=serializer.validated_data['document_type'],
            document_number=serializer.validated_data['document_number'],
            document_extension=serializer.validated_data.get('document_extension'),
            birth_date=serializer.validated_data['birth_date'],
            gender=serializer.validated_data.get('gender'),
            email=serializer.validated_data.get('email'),
            phone=serializer.validated_data['phone'],
            mobile_phone=serializer.validated_data.get('mobile_phone'),
            address=serializer.validated_data['address'],
            city=serializer.validated_data['city'],
            department=serializer.validated_data['department'],
            country=serializer.validated_data.get('country', 'Bolivia'),
            postal_code=serializer.validated_data.get('postal_code'),
            employment_status=serializer.validated_data['employment_status'],
            employer_name=serializer.validated_data.get('employer_name'),
            employer_nit=serializer.validated_data.get('employer_nit'),
            job_title=serializer.validated_data.get('job_title'),
            employment_start_date=serializer.validated_data.get('employment_start_date'),
            monthly_income=serializer.validated_data['monthly_income'],
            additional_income=serializer.validated_data.get('additional_income', 0),
            notes=serializer.validated_data.get('notes'),
        )
        
        # Llamar al servicio
        service = ClientManagementService()
        result = service.create_client(
            institution_id=request.user_institution_id,
            input_data=input_data,
            created_by=request.user
        )
        
        if not result.success:
            return Response({
                'success': False,
                'message': result.message,
                'errors': result.errors
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Serializar el cliente creado
        client_serializer = ClientSerializer(result.client)
        
        return Response({
            'success': True,
            'message': result.message,
            'client': client_serializer.data
        }, status=status.HTTP_201_CREATED)


class ClientDetailAPIView(APIView):
    """
    Vista para operaciones sobre un cliente específico.
    
    GET /api/clients/{id}/ - Obtiene detalle del cliente
    PATCH /api/clients/{id}/ - Actualiza el cliente
    DELETE /api/clients/{id}/ - Desactiva el cliente
    """
    permission_classes = [IsAuthenticated, require_permission('clients.view')]
    
    def get(self, request, client_id):
        """Obtiene el detalle de un cliente."""
        try:
            client = Client.objects.select_related(
                'user', 'user__profile', 'verified_by'
            ).get(
                id=client_id,
                institution_id=request.user_institution_id
            )
            serializer = ClientSerializer(client)
            
            return Response({
                'success': True,
                'client': serializer.data
            })
            
        except Client.DoesNotExist:
            return Response({
                'success': False,
                'message': 'Cliente no encontrado'
            }, status=status.HTTP_404_NOT_FOUND)
    
    def patch(self, request, client_id):
        """Actualiza un cliente."""
        # Verificar permiso de edición
        if not (hasattr(request.user, 'profile') and 
                (request.user.profile.is_saas_admin() or 
                 request.user.profile.has_permission('clients.edit', request.tenant))):
            return Response({
                'success': False,
                'message': 'No tiene permiso para editar clientes'
            }, status=status.HTTP_403_FORBIDDEN)
        
        try:
            client = Client.objects.select_related('user', 'user__profile').get(
                id=client_id,
                institution_id=request.user_institution_id
            )
        except Client.DoesNotExist:
            return Response({
                'success': False,
                'message': 'Cliente no encontrado'
            }, status=status.HTTP_404_NOT_FOUND)
        
        serializer = UpdateClientSerializer(client, data=request.data, partial=True)
        
        if not serializer.is_valid():
            return Response({
                'success': False,
                'message': 'Datos inválidos',
                'errors': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)
        
        serializer.save()
        
        # Retornar cliente actualizado
        client_serializer = ClientSerializer(client)
        
        return Response({
            'success': True,
            'message': 'Cliente actualizado exitosamente',
            'client': client_serializer.data
        })
    
    def delete(self, request, client_id):
        """Desactiva un cliente (soft delete)."""
        # Verificar permiso de eliminación
        if not (hasattr(request.user, 'profile') and 
                (request.user.profile.is_saas_admin() or 
                 request.user.profile.has_permission('clients.delete', request.tenant))):
            return Response({
                'success': False,
                'message': 'No tiene permiso para eliminar clientes'
            }, status=status.HTTP_403_FORBIDDEN)
        
        service = ClientManagementService()
        result = service.deactivate_client(
            client_id=client_id,
            institution_id=request.user_institution_id,
            reason=request.data.get('reason')
        )
        
        if not result.success:
            return Response({
                'success': False,
                'message': result.message
            }, status=status.HTTP_404_NOT_FOUND if 'no encontrado' in result.message.lower() else status.HTTP_400_BAD_REQUEST)
        
        return Response({
            'success': True,
            'message': result.message
        })


class ClientDocumentsAPIView(APIView):
    """
    Vista para gestión de documentos de un cliente.
    
    GET /api/clients/{id}/documents/ - Lista documentos del cliente
    POST /api/clients/{id}/documents/ - Sube un documento
    """
    permission_classes = [IsAuthenticated, require_permission('clients.view')]
    
    def get(self, request, client_id):
        """Lista documentos de un cliente."""
        try:
            client = Client.objects.select_related('user').get(
                id=client_id,
                institution_id=request.user_institution_id
            )
        except Client.DoesNotExist:
            return Response({
                'success': False,
                'message': 'Cliente no encontrado'
            }, status=status.HTTP_404_NOT_FOUND)
        
        documents = ClientDocument.objects.filter(client=client).order_by('-created_at')
        serializer = ClientDocumentSerializer(documents, many=True)
        
        return Response({
            'success': True,
            'count': documents.count(),
            'documents': serializer.data
        })
    
    def post(self, request, client_id):
        """Sube un documento para el cliente."""
        # Verificar permiso de edición
        if not (hasattr(request.user, 'profile') and 
                (request.user.profile.is_saas_admin() or 
                 request.user.profile.has_permission('clients.edit', request.tenant))):
            return Response({
                'success': False,
                'message': 'No tiene permiso para subir documentos'
            }, status=status.HTTP_403_FORBIDDEN)
        
        try:
            client = Client.objects.select_related('user').get(
                id=client_id,
                institution_id=request.user_institution_id
            )
        except Client.DoesNotExist:
            return Response({
                'success': False,
                'message': 'Cliente no encontrado'
            }, status=status.HTTP_404_NOT_FOUND)
        
        serializer = ClientDocumentSerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response({
                'success': False,
                'message': 'Datos inválidos',
                'errors': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Guardar el documento
        document = serializer.save(
            client=client,
            institution_id=request.user_institution_id,
            uploaded_by=request.user
        )
        
        # Actualizar tamaño y tipo MIME
        if document.file:
            document.file_size = document.file.size
            document.mime_type = request.FILES.get('file').content_type if 'file' in request.FILES else None
            document.save()
        
        return Response({
            'success': True,
            'message': 'Documento subido exitosamente',
            'document': ClientDocumentSerializer(document).data
        }, status=status.HTTP_201_CREATED)
