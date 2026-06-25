"""
ViewSets para el módulo de reportes.
"""
import logging
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.pagination import PageNumberPagination
from django.shortcuts import get_object_or_404

logger = logging.getLogger(__name__)


class ReportPagination(PageNumberPagination):
    """Paginación para reportes."""
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100

from api.reports.models import ReportTemplate, GeneratedReport, VoiceReportRequest
from api.reports.serializers import (
    ReportTemplateSerializer,
    ReportTemplateListSerializer,
    GeneratedReportSerializer,
    GeneratedReportListSerializer,
    VoiceReportRequestSerializer,
    ReportPreviewRequestSerializer,
    ReportGenerationRequestSerializer,
    VoiceReportInterpretRequestSerializer,
    VoiceReportInterpretResponseSerializer,
    ReportCatalogSerializer,
    ReportDefinitionSerializer
)
from api.reports.services import (
    ReportCatalogService,
    ReportGeneratorService,
    VoiceReportService,
    ManualReportService,
    GroqAPIError
)
from api.reports.permissions import (
    CanViewReportCatalog,
    CanGenerateReports,
    CanManageTemplates,
    CanAccessSaaSReports
)
from api.reports.throttling import (
    ReportCatalogThrottle,
    ReportGenerationThrottle,
    ReportPreviewThrottle,
    ReportDownloadThrottle,
    VoiceInterpretationThrottle
)


class ReportCatalogViewSet(viewsets.ViewSet):
    """
    ViewSet para catálogo de reportes disponibles.
    
    Endpoints:
    - GET /api/reports/catalog/ - Lista reportes disponibles (enriquecido con UI config)
    - GET /api/reports/catalog/{report_type}/ - Metadatos completos de un reporte
    - GET /api/reports/catalog/definition/{scope}/{category}/{report_type}/ - Definición base (legacy)
    """
    
    permission_classes = [IsAuthenticated, CanViewReportCatalog]
    throttle_classes = [ReportCatalogThrottle]
    
    def list(self, request):
        """
        Lista reportes disponibles según scope y roles del usuario.
        Retorna catálogo enriquecido con configuración de UI y gráficos.
        
        Query params:
        - scope: TENANT o SAAS (opcional, detecta automáticamente)
        
        Response:
        {
            "scope": "TENANT",
            "categories": {
                "CREDITS": [
                    {
                        "type": "loans_by_status",
                        "name": "Créditos por Estado",
                        "description": "...",
                        "chart_config": {
                            "default_chart": "donut",
                            "available_charts": ["donut", "bar", "pie"],
                            "chart_config": {...}
                        }
                    }
                ]
            }
        }
        """
        # Determinar scope
        if request.user.is_superuser or (hasattr(request.user, 'profile') and request.user.profile.is_saas_admin()):
            scope = request.query_params.get('scope', 'SAAS')
        else:
            scope = 'TENANT'
        
        # Validar acceso a scope SAAS
        if scope == 'SAAS' and not request.user.is_superuser:
            if not (hasattr(request.user, 'profile') and request.user.profile.is_saas_admin()):
                return Response(
                    {'error': 'No tiene acceso a reportes SAAS'},
                    status=status.HTTP_403_FORBIDDEN
                )
        
        # Obtener roles del usuario (simplificado por ahora)
        user_roles = ['admin', 'manager', 'analyst']
        
        # Obtener catálogo enriquecido
        manual_service = ManualReportService(
            user=request.user,
            tenant=getattr(request, 'tenant', None)
        )
        
        enriched_catalog = manual_service.get_enriched_catalog(scope, user_roles)
        
        return Response({
            'scope': scope,
            'categories': enriched_catalog
        })
    
    @action(detail=False, methods=['get'], url_path='(?P<report_type>[^/.]+)')
    def metadata(self, request, report_type=None):
        """
        Obtiene metadatos completos de un reporte para construir el formulario.
        
        URL: /api/reports/catalog/{report_type}/
        Query params:
        - scope: TENANT o SAAS (opcional, detecta automáticamente)
        
        Response:
        {
            "scope": "TENANT",
            "category": "CREDITS",
            "report_type": "loans_by_status",
            "name": "Créditos por Estado",
            "description": "...",
            "filters": [
                {
                    "field": "status",
                    "label": "Estado",
                    "type": "choice",
                    "operators": ["in", "not_in"],
                    "options": [...],
                    "ui_component": "multiselect",
                    "ui_props": {...}
                }
            ],
            "columns": [...],
            "groupings": [...],
            "sort_fields": [...],
            "formats": ["csv", "xlsx", "pdf"],
            "chart_config": {...},
            "default_config": {...}
        }
        """
        # Determinar scope
        if request.user.is_superuser or (hasattr(request.user, 'profile') and request.user.profile.is_saas_admin()):
            scope = request.query_params.get('scope', 'TENANT')
        else:
            scope = 'TENANT'
        
        # Validar acceso a scope SAAS
        if scope == 'SAAS' and not request.user.is_superuser:
            if not (hasattr(request.user, 'profile') and request.user.profile.is_saas_admin()):
                return Response(
                    {'error': 'No tiene acceso a reportes SAAS'},
                    status=status.HTTP_403_FORBIDDEN
                )
        
        # Buscar el reporte en el catálogo para obtener category
        catalog_service = ReportCatalogService()
        user_roles = ['admin', 'manager', 'analyst']
        available_reports = catalog_service.get_available_reports(scope, user_roles)
        
        category = None
        for cat, reports in available_reports.items():
            for report in reports:
                if report['type'] == report_type:
                    category = cat
                    break
            if category:
                break
        
        if not category:
            return Response(
                {'error': 'Reporte no encontrado'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Obtener metadatos enriquecidos
        manual_service = ManualReportService(
            user=request.user,
            tenant=getattr(request, 'tenant', None)
        )
        
        try:
            metadata = manual_service.get_report_metadata(scope, category, report_type)
            return Response(metadata)
        except ValueError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_404_NOT_FOUND
            )
    
    @action(detail=False, methods=['get'], url_path='definition/(?P<scope>[^/.]+)/(?P<category>[^/.]+)/(?P<report_type>[^/.]+)')
    def definition(self, request, scope=None, category=None, report_type=None):
        """
        Obtiene definición completa de un reporte específico (legacy endpoint).
        
        URL: /api/reports/catalog/definition/{scope}/{category}/{report_type}/
        """
        # Validar acceso a scope SAAS
        if scope == 'SAAS' and not request.user.is_superuser:
            if not (hasattr(request.user, 'profile') and request.user.profile.is_saas_admin()):
                return Response(
                    {'error': 'No tiene acceso a reportes SAAS'},
                    status=status.HTTP_403_FORBIDDEN
                )
        
        # Obtener definición
        catalog_service = ReportCatalogService()
        definition = catalog_service.get_report_definition(scope, category, report_type)
        
        if not definition:
            return Response(
                {'error': 'Reporte no encontrado'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        serializer = ReportDefinitionSerializer(definition)
        return Response(serializer.data)


class ReportTemplateViewSet(viewsets.ModelViewSet):
    """
    ViewSet para plantillas de reportes.
    
    Endpoints:
    - GET /api/reports/templates/ - Lista plantillas
    - POST /api/reports/templates/ - Crea plantilla
    - GET /api/reports/templates/{id}/ - Detalle de plantilla
    - PATCH /api/reports/templates/{id}/ - Actualiza plantilla
    - DELETE /api/reports/templates/{id}/ - Elimina plantilla
    - POST /api/reports/templates/{id}/use/ - Usa plantilla para generar reporte
    """
    
    permission_classes = [IsAuthenticated, CanManageTemplates]
    
    def get_queryset(self):
        """Filtra plantillas según scope y tenant."""
        user = self.request.user
        
        if user.is_superuser or (hasattr(user, 'profile') and user.profile.is_saas_admin()):
            # Admin SaaS ve todas las plantillas
            scope = self.request.query_params.get('scope')
            if scope == 'SAAS':
                return ReportTemplate.objects.filter(scope='SAAS')
            elif scope == 'TENANT':
                return ReportTemplate.objects.filter(scope='TENANT')
            else:
                return ReportTemplate.objects.all()
        else:
            # Usuario de tenant solo ve sus plantillas
            tenant = getattr(self.request, 'tenant', None)
            if tenant:
                return ReportTemplate.objects.filter(
                    scope='TENANT',
                    institution=tenant,
                    is_active=True
                )
            return ReportTemplate.objects.none()
    
    def get_serializer_class(self):
        """Retorna serializer según acción."""
        if self.action == 'list':
            return ReportTemplateListSerializer
        return ReportTemplateSerializer
    
    def perform_create(self, serializer):
        """Crea plantilla asignando tenant según scope."""
        scope = serializer.validated_data['scope']
        
        if scope == 'TENANT':
            serializer.save(
                created_by=self.request.user,
                institution=getattr(self.request, 'tenant', None)
            )
        else:
            serializer.save(
                created_by=self.request.user,
                institution=None
            )
    
    @action(detail=True, methods=['post'])
    def use(self, request, pk=None):
        """
        Usa plantilla para generar reporte.
        
        POST /api/reports/templates/{id}/use/
        """
        template = self.get_object()
        
        # Generar reporte usando configuración de la plantilla
        generator = ReportGeneratorService(
            user=request.user,
            tenant=getattr(request, 'tenant', None)
        )
        
        try:
            report = generator.generate_report(
                config=template.config_json,
                generation_source='MANUAL'
            )
            
            serializer = GeneratedReportSerializer(report)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )


class ReportGenerationViewSet(viewsets.ViewSet):
    """
    ViewSet para generación de reportes.
    
    Endpoints:
    - POST /api/reports/generate/preview/ - Vista previa de reporte
    - POST /api/reports/generate/ - Genera reporte
    """
    
    permission_classes = [IsAuthenticated, CanGenerateReports]
    
    def get_throttles(self):
        """Retorna throttles según la acción."""
        if self.action == 'preview':
            return [ReportPreviewThrottle()]
        return [ReportGenerationThrottle()]
    
    @action(detail=False, methods=['post'])
    def preview(self, request):
        """
        Genera vista previa paginada del reporte con configuración de gráficos.
        
        POST /api/reports/generate/preview/
        Body: {
            "scope": "TENANT",
            "category": "CREDITS",
            "report_type": "loans_by_status",
            "config": {
                "filters": [...],
                "columns": [...],
                "group_by": [...],
                "sort": [...],
                "chart_type": "donut"
            },
            "page": 1,
            "page_size": 50
        }
        
        Response:
        {
            "data": [...],
            "pagination": {
                "page": 1,
                "page_size": 50,
                "total_count": 150,
                "total_pages": 3,
                "has_next": true,
                "has_previous": false
            },
            "chart_config": {
                "type": "donut",
                "data_key": "total_applications",
                "name_key": "status",
                "colors": [...]
            },
            "summary": {
                "total_records": 150,
                "total_applications": 1250,
                "approval_rate": 67.5
            },
            "columns": [...]
        }
        """
        # Extraer parámetros
        scope = request.data.get('scope', 'TENANT')
        category = request.data.get('category')
        report_type = request.data.get('report_type')
        config = request.data.get('config', {})
        page = request.data.get('page', 1)
        page_size = request.data.get('page_size', 50)
        
        # Validaciones básicas
        if not category or not report_type:
            return Response(
                {'error': 'category y report_type son requeridos'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Validar acceso a scope
        if scope == 'SAAS' and not request.user.is_superuser:
            if not (hasattr(request.user, 'profile') and request.user.profile.is_saas_admin()):
                return Response(
                    {'error': 'No tiene acceso a reportes SAAS'},
                    status=status.HTTP_403_FORBIDDEN
                )
        
        # Generar vista previa con servicio manual
        manual_service = ManualReportService(
            user=request.user,
            tenant=getattr(request, 'tenant', None) if scope == 'TENANT' else None
        )
        
        try:
            preview_data = manual_service.preview_report_with_chart(
                scope=scope,
                category=category,
                report_type=report_type,
                config=config,
                page=page,
                page_size=page_size
            )
            return Response(preview_data)
        
        except ValueError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"Error en preview: {str(e)}", exc_info=True)
            return Response(
                {'error': f'Error al generar vista previa: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def create(self, request):
        """
        Genera reporte completo.
        
        POST /api/reports/generate/
        Body: {
            "config": {...},
            "save_as_template": false,
            "template_name": "",
            "template_description": ""
        }
        """
        import logging
        logger = logging.getLogger(__name__)
        
        logger.info(f"Datos recibidos para generación de reporte: {request.data}")
        
        serializer = ReportGenerationRequestSerializer(data=request.data)
        if not serializer.is_valid():
            logger.error(f"Errores de validación: {serializer.errors}")
            return Response(
                {'error': 'Datos inválidos', 'details': serializer.errors},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        serializer.is_valid(raise_exception=True)
        
        config = serializer.validated_data['config']
        save_as_template = serializer.validated_data.get('save_as_template', False)
        
        # Validar acceso a scope
        if config['scope'] == 'SAAS' and not request.user.is_superuser:
            if not (hasattr(request.user, 'profile') and request.user.profile.is_saas_admin()):
                return Response(
                    {'error': 'No tiene acceso a reportes SAAS'},
                    status=status.HTTP_403_FORBIDDEN
                )
        
        # Guardar como plantilla si se solicita
        if save_as_template:
            template = ReportTemplate.objects.create(
                institution=getattr(request, 'tenant', None) if config['scope'] == 'TENANT' else None,
                scope=config['scope'],
                category=config['category'],
                report_type=config['report_type'],
                name=serializer.validated_data['template_name'],
                description=serializer.validated_data.get('template_description', ''),
                config_json=config,
                created_by=request.user
            )
        
        # Generar reporte
        generator = ReportGeneratorService(
            user=request.user,
            tenant=getattr(request, 'tenant', None) if config['scope'] == 'TENANT' else None
        )
        
        try:
            report = generator.generate_report(
                config=config,
                generation_source='MANUAL'
            )
            
            serializer = GeneratedReportSerializer(report)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )


class GeneratedReportViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet para reportes generados (solo lectura).
    
    Endpoints:
    - GET /api/reports/generated/ - Lista reportes generados
    - GET /api/reports/generated/{id}/ - Detalle de reporte
    - GET /api/reports/generated/{id}/download/ - Descarga reporte
    """
    
    permission_classes = [IsAuthenticated]
    pagination_class = ReportPagination
    
    def get_queryset(self):
        """Filtra reportes según scope y tenant."""
        user = self.request.user
        
        logger.info(f"Usuario solicitando reportes: {user.id} - {user.username}")
        
        if user.is_superuser or (hasattr(user, 'profile') and user.profile.is_saas_admin()):
            # Admin SaaS ve todos los reportes
            scope = self.request.query_params.get('scope')
            if scope:
                queryset = GeneratedReport.objects.filter(scope=scope)
            else:
                queryset = GeneratedReport.objects.all()
        else:
            # Usuario de tenant solo ve sus reportes
            queryset = GeneratedReport.objects.filter(
                requested_by=user
            )
        
        logger.info(f"Reportes encontrados: {queryset.count()}")
        for report in queryset[:5]:  # Log primeros 5
            logger.info(f"  - Reporte {report.id}: {report.report_type} - {report.status} - requested_by={report.requested_by_id}")
        
        return queryset
    
    def list(self, request, *args, **kwargs):
        """Override list para agregar logging de la respuesta."""
        response = super().list(request, *args, **kwargs)
        logger.info(f"Respuesta serializada: {response.data}")
        return response
    
    def get_serializer_class(self):
        """Retorna serializer según acción."""
        if self.action == 'list':
            return GeneratedReportListSerializer
        return GeneratedReportSerializer
    
    @action(detail=True, methods=['get'])
    def download(self, request, pk=None):
        """
        Descarga archivo del reporte.
        
        GET /api/reports/generated/{id}/download/
        
        Retorna URL firmada para descargar el archivo.
        """
        # Aplicar throttling específico para descargas
        throttle = ReportDownloadThrottle()
        if not throttle.allow_request(request, self):
            self.throttled(request, throttle.wait())
        
        report = self.get_object()
        
        # Validar que el reporte esté completado
        if report.status != 'COMPLETED':
            return Response(
                {'error': 'Reporte no completado'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Validar que tenga archivo
        if not report.file_resource:
            return Response(
                {'error': 'Archivo no disponible'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Generar URL firmada
        download_url = report.file_resource.get_signed_url(expires_in=3600)
        
        if not download_url:
            return Response(
                {'error': 'No se pudo generar URL de descarga'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
        return Response({
            'download_url': download_url,
            'expires_in': 3600,
            'filename': report.file_resource.original_name,
            'file_size_bytes': report.file_resource.size
        })


class VoiceReportViewSet(viewsets.ViewSet):
    """
    ViewSet para reportes por voz.
    
    Endpoints:
    - POST /api/reports/voice/interpret/ - Interpreta audio y devuelve configuración
    - GET /api/reports/voice/history/ - Lista historial de solicitudes de voz
    - GET /api/reports/voice/history/{id}/ - Detalle de solicitud de voz
    """
    
    permission_classes = [IsAuthenticated, CanGenerateReports]
    throttle_classes = [VoiceInterpretationThrottle]
    
    def get_queryset(self):
        """Obtiene queryset filtrado por tenant y usuario."""
        user = self.request.user
        queryset = VoiceReportRequest.objects.all()
        
        # Filtrar por tenant si es usuario TENANT
        if hasattr(user, 'institution') and user.institution:
            queryset = queryset.filter(institution=user.institution)
        
        # Usuarios no-admin solo ven sus propias solicitudes
        if not user.is_staff and not user.is_superuser:
            if not (hasattr(user, 'profile') and user.profile.is_saas_admin()):
                queryset = queryset.filter(requested_by=user)
        
        return queryset.select_related(
            'institution',
            'requested_by',
            'audio_file_resource'
        ).order_by('-created_at')
    
    @action(detail=False, methods=['post'])
    def interpret(self, request):
        """
        Interpreta audio y devuelve configuración propuesta.
        
        POST /api/reports/voice/interpret/
        Body (multipart/form-data):
        - audio_file: archivo de audio
        - scope: TENANT o SAAS
        
        Response: {
            "voice_request_id": 123,
            "transcription": "...",
            "proposed_config": {...},
            "validation_status": "VALID | NEEDS_REVIEW | INVALID",
            "missing_fields": [],
            "unsupported_terms": [],
            "interpretation_notes": "...",
            "confidence": 0.95
        }
        """
        serializer = VoiceReportInterpretRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        audio_file = serializer.validated_data['audio_file']
        scope = serializer.validated_data['scope']
        
        # Validar acceso a scope SAAS
        if scope == 'SAAS' and not request.user.is_superuser:
            if not (hasattr(request.user, 'profile') and request.user.profile.is_saas_admin()):
                return Response(
                    {'error': 'No tiene acceso a reportes SAAS'},
                    status=status.HTTP_403_FORBIDDEN
                )
        
        # Procesar audio con servicio de voz
        voice_service = VoiceReportService(
            user=request.user,
            tenant=getattr(request, 'tenant', None) if scope == 'TENANT' else None
        )
        
        try:
            voice_request, proposed_config = voice_service.process_voice_request(
                audio_file=audio_file,
                scope=scope
            )
            
            response_data = {
                'voice_request_id': voice_request.id,
                'transcription': voice_request.transcription,
                'language': voice_request.transcription_language,
                'proposed_config': proposed_config,
                'validation_status': voice_request.validation_status,
                'missing_fields': voice_request.missing_fields_json or [],
                'unsupported_terms': voice_request.unsupported_terms_json or [],
                'interpretation_notes': voice_request.parsed_intent_json.get('interpretation_notes', '') if voice_request.parsed_intent_json else '',
                'confidence': voice_request.parsed_intent_json.get('confidence', 0.0) if voice_request.parsed_intent_json else 0.0
            }
            
            response_serializer = VoiceReportInterpretResponseSerializer(response_data)
            return Response(response_serializer.data, status=status.HTTP_200_OK)
        
        except ValueError as e:
            # Error de validación de audio
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        except GroqAPIError as e:
            # Error de API de Groq
            return Response(
                {'error': f'Error de servicio de IA: {str(e)}'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )
        
        except Exception as e:
            # Error inesperado
            return Response(
                {'error': f'Error al procesar audio: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'])
    def history(self, request):
        """
        Lista historial de solicitudes de voz del usuario.
        
        GET /api/reports/voice/history/
        
        Query params:
        - scope: Filtrar por TENANT o SAAS
        - validation_status: Filtrar por VALID, NEEDS_REVIEW, INVALID
        - page: Número de página
        - page_size: Tamaño de página (default: 20)
        
        Response:
        {
            "count": 100,
            "next": "url",
            "previous": "url",
            "results": [...]
        }
        """
        queryset = self.get_queryset()
        
        # Filtros opcionales
        scope = request.query_params.get('scope')
        if scope:
            queryset = queryset.filter(scope=scope)
        
        validation_status = request.query_params.get('validation_status')
        if validation_status:
            queryset = queryset.filter(validation_status=validation_status)
        
        # Paginación
        from rest_framework.pagination import PageNumberPagination
        
        paginator = PageNumberPagination()
        paginator.page_size = int(request.query_params.get('page_size', 20))
        page = paginator.paginate_queryset(queryset, request)
        
        if page is not None:
            serializer = VoiceReportRequestSerializer(page, many=True)
            return paginator.get_paginated_response(serializer.data)
        
        serializer = VoiceReportRequestSerializer(queryset, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'], url_path='history/(?P<request_id>[^/.]+)')
    def history_detail(self, request, request_id=None):
        """
        Obtiene detalle de una solicitud de voz.
        
        GET /api/reports/voice/history/{id}/
        
        Response:
        {
            "id": "uuid",
            "scope": "TENANT",
            "transcription": "...",
            "validation_status": "VALID",
            "parsed_intent_json": {...},
            "audio_file_resource": {...},
            "processing_time_seconds": 5,
            "created_at": "2026-05-10T10:00:00Z"
        }
        """
        try:
            voice_request = self.get_queryset().get(pk=request_id)
        except VoiceReportRequest.DoesNotExist:
            return Response(
                {'error': 'Solicitud de voz no encontrada'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        serializer = VoiceReportRequestSerializer(voice_request)
        return Response(serializer.data)
