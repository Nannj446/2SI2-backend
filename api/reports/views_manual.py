"""
ViewSets para Reportes Manuales Independientes.

Autor: Sistema FinCore
Fecha: 2026-05-11
"""

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from api.reports.permissions_manual import (
    HasManualReportPermission,
    CanExportReports,
    check_rate_limit,
    sanitize_filters
)
from api.reports.serializers_manual import (
    ManualReportFilterSerializer,
    ExportRequestSerializer,
    ReportDataSerializer
)
from api.reports.services.manual_query_builder import ManualQueryBuilder
from api.reports.services.manual_data_processor import ManualDataProcessor
from api.reports.services.manual_chart_data import ManualChartDataGenerator
from api.reports.services.manual_export_service import ManualExportService
from api.reports.services.manual_filter_options import ManualFilterOptionsService


class ManualReportViewSet(viewsets.ViewSet):
    """
    ViewSet para reportes manuales.
    
    Endpoints:
    - GET /api/reports/manual/{report_type}/ - Obtener datos del reporte
    - POST /api/reports/manual/export/csv/ - Exportar a CSV
    - POST /api/reports/manual/export/xlsx/ - Exportar a Excel
    - POST /api/reports/manual/export/pdf/ - Exportar a PDF
    """
    
    permission_classes = [IsAuthenticated, HasManualReportPermission]
    
    VALID_REPORT_TYPES = ['clients', 'products', 'applications', 'audit', 'users', 'branches']
    
    def get_serializer_class(self):
        """
        Retorna la clase de serializer apropiada según la acción.
        """
        if self.action == 'list':
            return ManualReportFilterSerializer
        elif self.action in ['export_csv', 'export_xlsx', 'export_pdf']:
            return ExportRequestSerializer
        elif self.action == 'filter_options':
            return None  # No requiere serializer
        elif self.action == 'available':
            return None  # No requiere serializer
        return None
    
    def list(self, request, report_type=None):
        """
        Obtiene los datos de un reporte específico.
        
        Args:
            report_type: Tipo de reporte (clients, products, etc.)
        
        Returns:
            Response: Datos del reporte con resumen, gráficos y filas
        """
        # Validar tipo de reporte
        if report_type not in self.VALID_REPORT_TYPES:
            return Response(
                {'error': f'Tipo de reporte inválido: {report_type}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Obtener scope del request
        scope = request.query_params.get('scope', 'TENANT')
        
        # Logging para diagnóstico
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f'=== MANUAL REPORT REQUEST ===')
        logger.info(f'Report type: {report_type}')
        logger.info(f'Scope: {scope}')
        logger.info(f'User: {request.user.email}')
        logger.info(f'User is_superuser: {request.user.is_superuser}')
        
        # Obtener institución del usuario
        institution = None
        if scope == 'TENANT':
            # Modo TENANT: filtrar por institución
            if hasattr(request.user, 'institution'):
                institution = request.user.institution
                logger.info(f'Institution from user: {institution}')
            elif hasattr(request, 'tenant'):
                institution = request.tenant
                logger.info(f'Institution from request.tenant: {institution}')
            
            # Si no hay institución y no es superusuario, retornar error
            if not institution and not request.user.is_superuser:
                return Response(
                    {'error': 'Usuario no pertenece a ninguna institución'},
                    status=status.HTTP_403_FORBIDDEN
                )
        elif scope == 'SAAS':
            # Modo SAAS: solo permitir reportes específicos
            allowed_saas_reports = ['audit', 'users', 'branches']
            if report_type not in allowed_saas_reports:
                return Response(
                    {'error': f'Reporte {report_type} no disponible en modo SAAS'},
                    status=status.HTTP_403_FORBIDDEN
                )
            # No filtrar por institución (institution = None)
            institution = None
            logger.info(f'SAAS mode: institution set to None')
        
        # Validar y sanitizar filtros
        filter_serializer = ManualReportFilterSerializer(data=request.query_params)
        if not filter_serializer.is_valid():
            return Response(
                {'error': 'Filtros inválidos', 'details': filter_serializer.errors},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        filters = sanitize_filters(filter_serializer.validated_data)
        filters['scope'] = scope  # Agregar scope a los filtros
        
        logger.info(f'Validated filters: {filters}')
        
        try:
            # Construir query
            query_builder = ManualQueryBuilder(institution)
            
            # Obtener método del query builder
            build_method = getattr(query_builder, f'build_{report_type}_query', None)
            if not build_method:
                return Response(
                    {'error': f'Método build_{report_type}_query no encontrado en ManualQueryBuilder'},
                    status=status.HTTP_501_NOT_IMPLEMENTED
                )
            
            queryset = build_method(filters)
            
            # Obtener parámetros de paginación
            page = filters.get('page', 1)
            page_size = filters.get('page_size', 100)
            
            # Procesar datos CON PAGINACIÓN para visualización
            data_processor = ManualDataProcessor(
                queryset, 
                report_type,
                paginate=True,  # Activar paginación para frontend
                page=page,
                page_size=page_size
            )
            processed_data = data_processor.process()
            
            # Generar datos de gráficos
            chart_generator = ManualChartDataGenerator(queryset, report_type)
            chart_data = chart_generator.generate()
            
            # Paginación
            page = filters.get('page', 1)
            page_size = filters.get('page_size', 100)
            total_count = processed_data['total_count']
            total_pages = (total_count + page_size - 1) // page_size
            
            # Construir respuesta
            response_data = {
                'report_type': report_type,
                'scope': scope,
                'filters_applied': filters,
                'summary': processed_data['summary'],
                'chart_data': chart_data,
                'rows': processed_data['rows'],
                'pagination': {
                    'page': page,
                    'page_size': page_size,
                    'total_pages': total_pages,
                    'total_count': total_count,
                }
            }
            
            return Response(response_data, status=status.HTTP_200_OK)
            
        except AttributeError as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f'AttributeError en reporte {report_type}: {str(e)}', exc_info=True)
            return Response(
                {'error': f'Tipo de reporte no implementado: {report_type}', 'details': str(e)},
                status=status.HTTP_501_NOT_IMPLEMENTED
            )
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f'Error al generar reporte: {str(e)}', exc_info=True)
            return Response(
                {'error': f'Error al generar reporte: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['post'], permission_classes=[IsAuthenticated, CanExportReports])
    def export_csv(self, request):
        """Exporta reporte a CSV."""
        return self._export_report(request, 'csv')
    
    @action(detail=False, methods=['post'], permission_classes=[IsAuthenticated, CanExportReports])
    def export_xlsx(self, request):
        """Exporta reporte a Excel."""
        return self._export_report(request, 'xlsx')
    
    @action(detail=False, methods=['post'], permission_classes=[IsAuthenticated, CanExportReports])
    def export_pdf(self, request):
        """Exporta reporte a PDF."""
        return self._export_report(request, 'pdf')
    
    def _export_report(self, request, export_format):
        """
        Método interno para exportar reportes.
        
        Args:
            request: Request object
            export_format: Formato de exportación (csv, xlsx, pdf)
        
        Returns:
            HttpResponse: Archivo descargable
        """
        # Verificar rate limit
        if not check_rate_limit(request.user, action='export', limit=10, window_minutes=60):
            return Response(
                {'error': 'Ha excedido el límite de exportaciones. Intente más tarde.'},
                status=status.HTTP_429_TOO_MANY_REQUESTS
            )
        
        # Obtener scope del request
        scope = request.data.get('filters', {}).get('scope', 'TENANT')
        
        # Obtener institución del usuario
        institution = None
        if scope == 'TENANT':
            if hasattr(request.user, 'institution'):
                institution = request.user.institution
            elif hasattr(request, 'tenant'):
                institution = request.tenant
            
            # Si no hay institución y no es superusuario, retornar error
            if not institution and not request.user.is_superuser:
                return Response(
                    {'error': 'Usuario no pertenece a ninguna institución'},
                    status=status.HTTP_403_FORBIDDEN
                )
        elif scope == 'SAAS':
            # Modo SAAS: solo permitir reportes específicos
            allowed_saas_reports = ['audit', 'users', 'branches']
            report_type = request.data.get('report_type')
            if report_type not in allowed_saas_reports:
                return Response(
                    {'error': f'Reporte {report_type} no disponible en modo SAAS'},
                    status=status.HTTP_403_FORBIDDEN
                )
            institution = None
        
        # Validar request
        serializer = ExportRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {'error': 'Datos inválidos', 'details': serializer.errors},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        report_type = serializer.validated_data['report_type']
        filters = sanitize_filters(serializer.validated_data.get('filters', {}))
        include_chart = serializer.validated_data.get('include_chart', False)
        
        # Agregar scope a los filtros
        filters['scope'] = scope
        
        try:
            # Construir query SIN PAGINACIÓN para exportación
            query_builder = ManualQueryBuilder(institution)
            build_method = getattr(query_builder, f'build_{report_type}_query')
            queryset = build_method(filters)
            
            # NO aplicar paginación - obtener TODOS los registros para exportación
            data_processor = ManualDataProcessor(
                queryset, 
                report_type,
                paginate=False,  # Desactivar paginación para exportación
                page=1,
                page_size=100
            )
            processed_data = data_processor.process()
            
            # Generar datos de gráficos si se solicita
            chart_data = {}
            if include_chart:
                chart_generator = ManualChartDataGenerator(queryset, report_type)
                chart_data = chart_generator.generate()
            
            # Preparar datos completos (TODOS los registros, no paginados)
            export_data = {
                'summary': processed_data['summary'],
                'rows': processed_data['rows'],  # Todas las filas sin límite
                'chart_data': chart_data,
            }
            
            # Exportar
            export_service = ManualExportService(export_data, report_type, filters)
            
            if export_format == 'csv':
                return export_service.export_csv()
            elif export_format == 'xlsx':
                return export_service.export_xlsx()
            elif export_format == 'pdf':
                return export_service.export_pdf(include_chart=include_chart)
            else:
                return Response(
                    {'error': f'Formato no soportado: {export_format}'},
                    status=status.HTTP_400_BAD_REQUEST
                )
                
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f'Error al exportar reporte: {str(e)}', exc_info=True)
            return Response(
                {'error': f'Error al exportar reporte: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'])
    def available(self, request):
        """
        Retorna los tipos de reportes disponibles.
        
        Returns:
            Response: Lista de tipos de reportes
        """
        return Response({
            'report_types': self.VALID_REPORT_TYPES,
            'descriptions': {
                'clients': 'Reporte de clientes y KYC',
                'products': 'Reporte de productos crediticios',
                'applications': 'Reporte de solicitudes de crédito',
                'audit': 'Reporte de auditoría del sistema',
                'users': 'Reporte de usuarios',
                'branches': 'Reporte de sucursales',
            }
        })
    
    @action(
        detail=False, 
        methods=['get'], 
        permission_classes=[IsAuthenticated],
        url_path='filter_options',
        url_name='filter_options'
    )
    def filter_options(self, request):
        """
        Retorna las opciones disponibles para los filtros.
        
        Returns:
            Response: Opciones de filtros (usuarios, productos, clientes, sucursales, etc.)
        """
        import logging
        logger = logging.getLogger(__name__)
        
        logger.info(f'=== FILTER OPTIONS REQUEST ===')
        logger.info(f'User: {request.user}')
        logger.info(f'User authenticated: {request.user.is_authenticated}')
        logger.info(f'User is_superuser: {request.user.is_superuser}')
        logger.info(f'Request method: {request.method}')
        logger.info(f'Request path: {request.path}')
        
        # Obtener institución del usuario
        institution = None
        if hasattr(request.user, 'institution'):
            institution = request.user.institution
            logger.info(f'User institution: {institution}')
        elif hasattr(request, 'tenant'):
            institution = request.tenant
            logger.info(f'Request tenant: {institution}')
        else:
            logger.info('No institution found')
        
        try:
            logger.info('Creating ManualFilterOptionsService...')
            options_service = ManualFilterOptionsService(institution)
            
            logger.info('Getting all options...')
            options = options_service.get_all_options()
            
            logger.info(f'Options retrieved successfully: {len(options)} categories')
            return Response(options, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f'Error al obtener opciones de filtros: {str(e)}', exc_info=True)
            return Response(
                {'error': f'Error al obtener opciones: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
