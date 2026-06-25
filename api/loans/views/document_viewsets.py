"""
ViewSets para CU-12: Gestión Documental.

Proporciona endpoints REST para:
- Clientes: cargar documentos de sus solicitudes
- Staff: revisar y aprobar/rechazar documentos
"""

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser
from api.loans.models_documents import LoanApplicationDocumentRequirement
from api.loans.serializers.document_serializers import (
    LoanApplicationDocumentRequirementSerializer,
    DocumentUploadSerializer,
    DocumentReviewSerializer
)
from api.loans.services.document_service import DocumentService
from api.loans.permissions import CanReviewDocuments, IsDocumentOwner


class ClientDocumentViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet para que clientes gestionen sus documentos.
    
    Endpoints:
    - GET /api/loans/my-documents/ - Listar mis documentos
    - GET /api/loans/my-documents/{id}/ - Detalle de documento
    - POST /api/loans/my-documents/{id}/upload/ - Cargar documento
    """
    
    serializer_class = LoanApplicationDocumentRequirementSerializer
    permission_classes = [IsAuthenticated, IsDocumentOwner]
    parser_classes = [MultiPartParser, FormParser]
    
    def get_queryset(self):
        import logging
        logger = logging.getLogger(__name__)
        
        # Solo documentos de solicitudes del cliente
        # Verificar si el usuario tiene un cliente asociado
        client = None
        if hasattr(self.request.user, 'client_profile'):
            client = self.request.user.client_profile
        elif hasattr(self.request.user, 'client'):
            client = self.request.user.client
            
        if not client:
            logger.warning(f"[DOCUMENTS] Usuario {self.request.user.id} no tiene cliente asociado")
            return LoanApplicationDocumentRequirement.objects.none()
        
        queryset = LoanApplicationDocumentRequirement.objects.filter(
            institution=self.request.tenant,
            loan_application__client=client
        ).select_related(
            'product_document_requirement',
            'file_resource',
            'loan_application'
        )
        
        # Filtrar por solicitud específica si se pasa el query param
        loan_app_id = self.request.query_params.get('loan_application')
        if loan_app_id:
            queryset = queryset.filter(loan_application_id=loan_app_id)
            count = queryset.count()
            logger.info(
                f"[DOCUMENTS] Solicitud {loan_app_id}: {count} documentos encontrados "
                f"(Usuario: {self.request.user.id}, Cliente: {client.id})"
            )
            
            # Verificar si existen ProductDocumentRequirement para el producto
            from api.loans.models import LoanApplication
            try:
                app = LoanApplication.objects.get(id=loan_app_id)
                from api.products.models import ProductDocumentRequirement
                prod_docs = ProductDocumentRequirement.objects.filter(
                    product=app.product,
                    institution=self.request.tenant
                ).count()
                logger.info(
                    f"[DOCUMENTS] Producto {app.product.name} (ID: {app.product_id}) "
                    f"tiene {prod_docs} documentos configurados"
                )
            except Exception as e:
                logger.error(f"[DOCUMENTS] Error verificando producto: {e}")
        
        return queryset

    
    @action(detail=True, methods=['post'])
    def upload(self, request, pk=None):
        """
        Carga un documento.
        
        POST /api/loans/my-documents/{id}/upload/
        Body (multipart/form-data):
        - file: archivo
        - notes: notas (opcional)
        """
        import logging
        logger = logging.getLogger(__name__)
        
        doc_req = self.get_object()
        app_id = doc_req.loan_application_id
        
        logger.info(
            f"[UPLOAD] ===== INICIO upload action ====="
        )
        logger.info(
            f"[UPLOAD] Usuario {request.user.id} subiendo documento {doc_req.id} "
            f"para solicitud {app_id} (estado: {doc_req.loan_application.status})"
        )
        
        if not request.FILES.get('file'):
            logger.warning(f"[UPLOAD] No se recibió archivo en la petición")
            return Response(
                {'error': 'El campo "file" es requerido'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        file = request.FILES.get('file')
        logger.info(f"[UPLOAD] Archivo recibido: {file.name}, tamaño: {file.size} bytes")
        
        serializer = DocumentUploadSerializer(data={
            'document_requirement_id': doc_req.id,
            'file': file
        })
        
        if not serializer.is_valid():
            logger.error(f"[UPLOAD] Errores de validación: {serializer.errors}")
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            logger.info(f"[UPLOAD] Llamando DocumentService.upload_document para doc_req={doc_req.id}, app={app_id}")
            updated_doc = DocumentService.upload_document(
                document_requirement_id=doc_req.id,
                file=serializer.validated_data['file'],
                uploaded_by=request.user,
                notes=request.data.get('notes', '')
            )
            
            logger.info(f"[UPLOAD] Documento {doc_req.id} subido exitosamente para app={app_id}")
            result_serializer = self.get_serializer(updated_doc)
            logger.info(f"[UPLOAD] ===== FIN upload action (OK) =====")
            return Response(result_serializer.data)
        
        except ValueError as e:
            logger.error(f"[UPLOAD] ValueError: {str(e)}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.exception(f"[UPLOAD] Error inesperado al cargar documento")
            return Response(
                {'error': f'Error al cargar el documento: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class StaffDocumentViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet para que staff revise documentos.
    
    Endpoints:
    - GET /api/loans/staff/documents/ - Listar documentos para revisar
    - GET /api/loans/staff/documents/{id}/ - Detalle
    - POST /api/loans/staff/documents/{id}/review/ - Revisar documento
    
    Query params:
    - status: Filtrar por estado (PENDING, UPLOADED, UNDER_REVIEW, APPROVED, REJECTED)
    """
    
    serializer_class = LoanApplicationDocumentRequirementSerializer
    permission_classes = [IsAuthenticated, CanReviewDocuments]
    
    def get_queryset(self):
        queryset = LoanApplicationDocumentRequirement.objects.filter(
            institution=self.request.tenant
        ).select_related(
            'product_document_requirement',
            'file_resource',
            'loan_application',
            'loan_application__client'
        )

        
        # Filtrar por solicitud específica
        loan_app_id = self.request.query_params.get('loan_application')
        if loan_app_id:
            queryset = queryset.filter(loan_application_id=loan_app_id)
        
        # Filtrar por estado
        status_filter = self.request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        else:
            # Por defecto, mostrar solo los que requieren revisión
            queryset = queryset.filter(
                status__in=['UPLOADED', 'UNDER_REVIEW']
            )
        
        return queryset.order_by('-uploaded_at')
    
    @action(detail=True, methods=['post'])
    def review(self, request, pk=None):
        """
        Revisa un documento.
        
        POST /api/loans/staff/documents/{id}/review/
        Body:
        - action: APPROVED | REJECTED | REQUESTED_REUPLOAD
        - comments: comentarios
        """
        doc_req = self.get_object()
        
        serializer = DocumentReviewSerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            reviewed_doc = DocumentService.review_document(
                document_requirement_id=doc_req.id,
                action=serializer.validated_data['action'],
                reviewed_by=request.user,
                comments=serializer.validated_data.get('comments', '')
            )
            
            result_serializer = self.get_serializer(reviewed_doc)
            return Response(result_serializer.data)
        
        except ValueError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            return Response(
                {'error': f'Error al revisar el documento: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
