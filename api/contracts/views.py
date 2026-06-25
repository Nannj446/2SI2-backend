"""
Vistas para el módulo de contratos
"""

import logging
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import ValidationError
from django.shortcuts import get_object_or_404
from django.http import HttpResponse
from django.db.models import Q, Count, Prefetch

from api.contracts.models import (
    Contract,
    ContractTemplate,
    ContractSignature,
    ContractAmortizationSchedule,
    ContractDocument
)
from api.contracts.serializers import (
    ContractSerializer,
    ContractListSerializer,
    ContractCreateSerializer,
    ContractSignSerializer,
    ContractTemplateSerializer,
    ContractTemplateListSerializer,
    ContractSignatureSerializer,
    ContractAmortizationScheduleSerializer,
    ContractDocumentSerializer,
)
from api.contracts.permissions import (
    CanViewContract,
    CanGenerateContract,
    CanManageContractTemplates,
    CanSignContract,
    CanCancelContract,
    CanPublishContract,
    CanDownloadContractPDF,
)
from api.contracts.services import (
    ContractGeneratorService,
    PDFGeneratorService,
    SignatureService,
    AmortizationService,
)
from api.loans.models import LoanApplication

logger = logging.getLogger(__name__)


def _get_request_tenant(request):
    tenant = getattr(request, 'tenant', None)
    if tenant:
        return tenant

    user = getattr(request, 'user', None)
    if not user or not user.is_authenticated:
        return None
    
    # Intentar obtener desde user.institution (si existe)
    if hasattr(user, 'institution'):
        return user.institution

    # Intentar obtener desde user.institution_memberships (si existe)
    if hasattr(user, 'institution_memberships'):
        membership = user.institution_memberships.filter(is_active=True).first()
        if membership:
            return membership.institution
    
    # Obtener desde UserRole (sistema actual)
    from api.roles.models import UserRole
    user_role = UserRole.objects.filter(
        user=user,
        is_active=True
    ).select_related('institution').first()
    
    if user_role:
        return user_role.institution

    return None


class ContractViewSet(viewsets.ModelViewSet):
    """
    ViewSet para gestión de contratos.
    
    Endpoints:
    - GET /contracts/ - Listar contratos
    - POST /contracts/ - Crear contrato (desde solicitud aprobada)
    - GET /contracts/{id}/ - Ver detalle de contrato
    - PATCH /contracts/{id}/ - Actualizar contrato
    - DELETE /contracts/{id}/ - Eliminar contrato (solo DRAFT)
    
    Acciones personalizadas:
    - POST /contracts/generate-from-application/ - Generar contrato desde solicitud
    - POST /contracts/{id}/publish/ - Publicar contrato
    - POST /contracts/{id}/sign/ - Firmar contrato
    - GET /contracts/{id}/pdf/ - Descargar PDF
    - GET /contracts/{id}/preview/ - Vista previa HTML
    - POST /contracts/{id}/cancel/ - Cancelar contrato
    - GET /contracts/{id}/signature-status/ - Estado de firmas
    - GET /contracts/{id}/payment-summary/ - Resumen de pagos
    """
    
    queryset = Contract.objects.all()
    permission_classes = [IsAuthenticated]
    
    def get_serializer_class(self):
        if self.action == 'list':
            return ContractListSerializer
        elif self.action == 'generate_from_application':
            return ContractCreateSerializer
        elif self.action == 'sign':
            return ContractSignSerializer
        return ContractSerializer
    
    def get_queryset(self):
        """
        Filtra contratos por tenant.
        """
        tenant = _get_request_tenant(self.request)
        
        if not tenant:
            return Contract.objects.none()
        
        queryset = Contract.objects.filter(
            institution=tenant
        ).select_related(
            'loan_application',
            'loan_application__client',
            'loan_application__product',
            'template',
            'pdf_file',
            'generated_by',
            'published_by',
        ).prefetch_related(
            'signatures',
            'amortization_schedule',
        )

        return queryset
    
    def get_permissions(self):
        """Permisos según la acción"""
        if self.action == 'create' or self.action == 'generate_from_application':
            return [IsAuthenticated(), CanGenerateContract()]
        elif self.action == 'publish':
            return [IsAuthenticated(), CanPublishContract()]
        elif self.action == 'sign':
            return [IsAuthenticated(), CanSignContract()]
        elif self.action == 'cancel':
            return [IsAuthenticated(), CanCancelContract()]
        elif self.action in ['retrieve', 'list']:
            return [IsAuthenticated(), CanViewContract()]
        elif self.action == 'pdf':
            return [IsAuthenticated(), CanDownloadContractPDF()]
        return [IsAuthenticated()]
    
    @action(detail=False, methods=['post'], url_path='generate-from-application')
    def generate_from_application(self, request):
        """
        Genera un contrato a partir de una solicitud aprobada.
        
        POST /api/contracts/generate-from-application/
        {
            "loan_application_id": 123,
            "template_id": 1,  // opcional
            "contract_date": "2026-05-30",  // opcional
            "start_date": "2026-06-05",  // opcional
            "special_clauses": {},  // opcional
            "notes": ""  // opcional
        }
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        try:
            tenant = _get_request_tenant(request)
            if not tenant:
                return Response(
                    {'error': 'Usuario sin institución asignada'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Obtener solicitud
            loan_application = LoanApplication.objects.get(
                id=serializer.validated_data['loan_application_id'],
                institution=tenant
            )
            
            # Obtener plantilla (si se especificó)
            template = None
            if serializer.validated_data.get('template_id'):
                template = ContractTemplate.objects.get(
                    id=serializer.validated_data['template_id'],
                    institution=tenant
                )
            
            # Generar contrato
            contract = ContractGeneratorService.generate_contract(
                loan_application=loan_application,
                template=template,
                contract_date=serializer.validated_data.get('contract_date'),
                start_date=serializer.validated_data.get('start_date'),
                special_clauses=serializer.validated_data.get('special_clauses'),
                notes=serializer.validated_data.get('notes', ''),
                generated_by=request.user
            )
            
            # Generar tabla de amortización
            AmortizationService.generate_amortization_schedule(contract)
            
            # Generar PDF (opcional - puede fallar en Windows sin GTK+)
            try:
                PDFGeneratorService.generate_and_save_contract_pdf(contract)
            except Exception as pdf_error:
                logger.warning(f"No se pudo generar PDF automáticamente: {pdf_error}")
                # El contrato se crea sin PDF, se puede generar después
            
            # Serializar respuesta
            response_serializer = ContractSerializer(
                contract,
                context={'request': request}
            )
            
            return Response(
                response_serializer.data,
                status=status.HTTP_201_CREATED
            )
            
        except LoanApplication.DoesNotExist:
            return Response(
                {'error': 'Solicitud no encontrada'},
                status=status.HTTP_404_NOT_FOUND
            )
        except ContractTemplate.DoesNotExist:
            return Response(
                {'error': 'Plantilla no encontrada'},
                status=status.HTTP_404_NOT_FOUND
            )
        except ValueError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"Error generando contrato: {str(e)}", exc_info=True)
            return Response(
                {'error': 'Error generando contrato'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'])
    def publish(self, request, pk=None):
        """
        Publica un contrato (cambia de DRAFT a PENDING_SIGNATURE).
        
        POST /api/contracts/{id}/publish/
        """
        contract = self.get_object()
        
        try:
            ContractGeneratorService.publish_contract(
                contract=contract,
                published_by=request.user
            )
            
            serializer = self.get_serializer(contract)
            return Response(serializer.data)
            
        except ValueError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['post'])
    def sign(self, request, pk=None):
        """
        Firma un contrato.
        
        POST /api/contracts/{id}/sign/
        {
            "signature_method": "DIGITAL",
            "signature_data": "hash_or_signature_data",
            "device_info": {},
            "geolocation": {},
            "verification_method": "2FA"
        }
        """
        contract = self.get_object()
        serializer = self.get_serializer(data=request.data)
        
        if not serializer.is_valid():
            logger.error(f"Error de validación al firmar contrato {contract.id}: {serializer.errors}")
            return Response(
                {'error': 'Datos de firma inválidos', 'details': serializer.errors},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            # Obtener IP del request
            ip_address = self._get_client_ip(request)
            
            # Log para debugging
            logger.info(
                f"Intento de firma de contrato {contract.id} por usuario {request.user.email} (ID: {request.user.id})"
            )
            
            # Determinar tipo de firmante
            # 1. Verificar si es el prestatario
            if hasattr(contract.loan_application.client, 'user'):
                client_user = contract.loan_application.client.user
                logger.info(
                    f"Cliente del contrato: {client_user.email} (ID: {client_user.id}), "
                    f"Usuario que firma: {request.user.email} (ID: {request.user.id})"
                )
                if client_user == request.user:
                    signature = SignatureService.sign_contract_as_borrower(
                        contract=contract,
                        user=request.user,
                        signature_data=serializer.validated_data['signature_data'],
                        ip_address=ip_address,
                        signature_method=serializer.validated_data.get(
                            'signature_method',
                            ContractSignature.SignatureMethod.DIGITAL
                        ),
                        device_info=serializer.validated_data.get('device_info'),
                        geolocation=serializer.validated_data.get('geolocation'),
                        verification_method=serializer.validated_data.get('verification_method', '')
                    )
                    
                    return Response({
                        'message': 'Contrato firmado exitosamente',
                        'signature': ContractSignatureSerializer(signature).data,
                        'contract_status': contract.status
                    })
            
            # 2. Verificar si es un garante
            guarantor_email = getattr(request.user, 'email', None)
            guarantor = None
            if guarantor_email:
                guarantor = contract.loan_application.guarantors.filter(
                    email__iexact=guarantor_email,
                    status='APPROVED'
                ).first()
            
            if guarantor:
                signature = SignatureService.sign_contract_as_guarantor(
                    contract=contract,
                    guarantor=guarantor,
                    signature_data=serializer.validated_data['signature_data'],
                    ip_address=ip_address,
                    signature_method=serializer.validated_data.get(
                        'signature_method',
                        ContractSignature.SignatureMethod.DIGITAL
                    ),
                    device_info=serializer.validated_data.get('device_info'),
                    geolocation=serializer.validated_data.get('geolocation'),
                    verification_method=serializer.validated_data.get('verification_method', '')
                )
                
                return Response({
                    'message': 'Contrato firmado exitosamente',
                    'signature': ContractSignatureSerializer(signature).data,
                    'contract_status': contract.status
                })
            
            # 3. Verificar si es staff/empleado de la institución (firma como institución)
            # Solo permitir si el usuario tiene permisos de staff
            if request.user.is_staff or hasattr(request.user, 'institution_memberships'):
                # Verificar que pertenezca a la institución del contrato
                user_institution = None
                if hasattr(request.user, 'institution'):
                    user_institution = request.user.institution
                elif hasattr(request.user, 'institution_memberships'):
                    membership = request.user.institution_memberships.filter(is_active=True).first()
                    if membership:
                        user_institution = membership.institution
                
                if user_institution == contract.institution:
                    signature = SignatureService.sign_contract_as_institution(
                        contract=contract,
                        user=request.user,
                        signature_data=serializer.validated_data['signature_data'],
                        ip_address=ip_address,
                        signature_method=serializer.validated_data.get(
                            'signature_method',
                            ContractSignature.SignatureMethod.DIGITAL
                        ),
                        device_info=serializer.validated_data.get('device_info')
                    )
                    
                    return Response({
                        'message': 'Contrato firmado exitosamente como representante de la institución',
                        'signature': ContractSignatureSerializer(signature).data,
                        'contract_status': contract.status
                    })
            
            # Si no es ninguno de los anteriores, no tiene permiso para firmar
            logger.warning(
                f"Usuario {request.user.email} intentó firmar contrato {contract.id} "
                f"sin ser prestatario, garante ni staff de la institución"
            )
            return Response(
                {
                    'error': 'No tiene permiso para firmar este contrato',
                    'detail': 'Debe ser el prestatario, un garante aprobado o un representante de la institución'
                },
                status=status.HTTP_403_FORBIDDEN
            )
            
        except ValueError as e:
            logger.error(f"Error de negocio al firmar contrato {contract.id}: {str(e)}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.exception(f"Error inesperado al firmar contrato {contract.id}: {str(e)}")
            return Response(
                {'error': f'Error al procesar la firma: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['get'])
    def pdf(self, request, pk=None):
        """
        Descarga el PDF del contrato.
        
        GET /api/contracts/{id}/pdf/
        """
        contract = self.get_object()
        
        if not contract.pdf_file:
            return Response(
                {'error': 'El contrato no tiene PDF generado'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        try:
            # Obtener archivo
            file_path = contract.pdf_file.file.path
            
            with open(file_path, 'rb') as pdf_file:
                response = HttpResponse(
                    pdf_file.read(),
                    content_type='application/pdf'
                )
                response['Content-Disposition'] = (
                    f'attachment; filename="contrato_{contract.contract_number}.pdf"'
                )
                return response
                
        except Exception as e:
            logger.error(f"Error descargando PDF: {str(e)}", exc_info=True)
            return Response(
                {'error': 'Error descargando PDF'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['get'])
    def preview(self, request, pk=None):
        """
        Vista previa HTML del contrato.
        
        GET /api/contracts/{id}/preview/
        """
        contract = self.get_object()
        
        try:
            html_content = PDFGeneratorService.preview_contract_html(contract)
            return HttpResponse(html_content, content_type='text/html')
        except Exception as e:
            logger.error(f"Error generando preview: {str(e)}", exc_info=True)
            return Response(
                {'error': 'Error generando vista previa'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """
        Cancela un contrato.
        
        POST /api/contracts/{id}/cancel/
        {
            "cancellation_reason": "Motivo de cancelación"
        }
        """
        contract = self.get_object()
        
        cancellation_reason = request.data.get('cancellation_reason', '')
        
        try:
            ContractGeneratorService.cancel_contract(
                contract=contract,
                cancellation_reason=cancellation_reason,
                cancelled_by=request.user
            )
            
            serializer = self.get_serializer(contract)
            return Response(serializer.data)
            
        except ValueError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['get'], url_path='signature-status')
    def signature_status(self, request, pk=None):
        """
        Obtiene el estado de firmas del contrato.
        
        GET /api/contracts/{id}/signature-status/
        """
        contract = self.get_object()
        signature_status = SignatureService.get_signature_status(contract)
        return Response(signature_status)
    
    @action(detail=True, methods=['get'], url_path='payment-summary')
    def payment_summary(self, request, pk=None):
        """
        Obtiene el resumen de pagos del contrato.
        
        GET /api/contracts/{id}/payment-summary/
        """
        contract = self.get_object()
        payment_summary = AmortizationService.get_payment_summary(contract)
        return Response(payment_summary)
    
    def _get_client_ip(self, request):
        """Obtiene la IP del cliente desde el request"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip


class ContractTemplateViewSet(viewsets.ModelViewSet):
    """
    ViewSet para gestión de plantillas de contratos.
    
    Endpoints:
    - GET /contract-templates/ - Listar plantillas
    - POST /contract-templates/ - Crear plantilla
    - GET /contract-templates/{id}/ - Ver detalle de plantilla
    - PATCH /contract-templates/{id}/ - Actualizar plantilla
    - DELETE /contract-templates/{id}/ - Eliminar plantilla
    
    Acciones personalizadas:
    - GET /contract-templates/{id}/preview/ - Vista previa de plantilla
    """
    
    queryset = ContractTemplate.objects.all()
    permission_classes = [IsAuthenticated, CanManageContractTemplates]
    
    def get_serializer_class(self):
        if self.action == 'list':
            return ContractTemplateListSerializer
        return ContractTemplateSerializer
    
    def get_queryset(self):
        """Filtra plantillas por tenant"""
        user = self.request.user
        tenant = _get_request_tenant(self.request)
        
        if not tenant:
            return ContractTemplate.objects.none()
        
        return ContractTemplate.objects.filter(
            institution=tenant
        ).select_related('product').annotate(
            contracts_count=Count('contracts')
        )
    
    def perform_create(self, serializer):
        """Asigna la institución al crear"""
        tenant = _get_request_tenant(self.request)
        if not tenant:
            raise ValidationError('Usuario sin institución asignada.')

        serializer.save(institution=tenant)
    
    @action(detail=True, methods=['get'])
    def preview(self, request, pk=None):
        """
        Vista previa HTML de la plantilla con datos de ejemplo.
        
        GET /api/contract-templates/{id}/preview/
        """
        template = self.get_object()
        
        try:
            html_content = PDFGeneratorService.preview_template_html(template)
            return HttpResponse(html_content, content_type='text/html')
        except Exception as e:
            logger.error(f"Error generando preview: {str(e)}", exc_info=True)
            return Response(
                {'error': 'Error generando vista previa'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class ContractAmortizationScheduleViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet para consulta de tablas de amortización.
    Solo lectura.
    """
    
    queryset = ContractAmortizationSchedule.objects.all()
    serializer_class = ContractAmortizationScheduleSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Filtra por contrato y tenant"""
        user = self.request.user
        tenant = _get_request_tenant(self.request)
        
        if not tenant:
            return ContractAmortizationSchedule.objects.none()
        
        queryset = ContractAmortizationSchedule.objects.filter(
            institution=tenant
        ).select_related('contract')
        
        # Filtrar por contrato si se especifica
        contract_id = self.request.query_params.get('contract_id')
        if contract_id:
            queryset = queryset.filter(contract_id=contract_id)
        
        return queryset.order_by('contract', 'payment_number')
