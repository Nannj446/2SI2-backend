"""
Servicio de generación de reportes.

Orquesta el proceso completo de generación:
- Validación de configuración
- Construcción de query
- Ejecución y paginación
- Exportación a archivo
- Almacenamiento en storage
- Registro en base de datos
"""
import time
import logging
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
from decimal import Decimal
from uuid import uuid4

from django.db import transaction
from django.core.paginator import Paginator

from api.reports.models import GeneratedReport, ReportTemplate
from api.storage.models import FileResource
from api.storage.services import StorageService

from .report_catalog import ReportCatalogService
from .report_schema import ReportSchemaService
from .report_query_builder import ReportQueryBuilder
from .export_service import ExportService
from .chart_generator_service import ChartGeneratorService
from .visualization_config_builder import VisualizationConfigBuilder

logger = logging.getLogger(__name__)


class ReportGeneratorService:
    """
    Servicio de generación de reportes.
    
    Maneja el ciclo completo de generación de reportes:
    validación, query, exportación y almacenamiento.
    """
    
    def __init__(self, user, tenant=None):
        """
        Inicializa el servicio.
        
        Args:
            user: Usuario que solicita el reporte
            tenant: Tenant para reportes TENANT, None para SAAS
        """
        self.user = user
        self.tenant = tenant
        self.catalog = ReportCatalogService()
        self.validator = ReportSchemaService()
        self.query_builder = ReportQueryBuilder(tenant)
        self.export_service = ExportService()
        self.chart_service = ChartGeneratorService()
        self.viz_builder = VisualizationConfigBuilder()
        self.storage_service = StorageService()
    
    @transaction.atomic
    def generate_report(
        self,
        config: Dict[str, Any],
        generation_source: str = 'MANUAL',
        voice_request_id: Optional[int] = None
    ) -> GeneratedReport:
        """
        Genera un reporte completo.
        
        Args:
            config: Configuración del reporte validada
            generation_source: MANUAL o AUDIO
            voice_request_id: ID de VoiceReportRequest si aplica
        
        Returns:
            Instancia de GeneratedReport
        
        Raises:
            ValueError: Si la configuración es inválida
        """
        start_time = time.time()
        
        logger.info(f"Iniciando generación de reporte: {config.get('report_type')}")
        logger.info(f"Configuración: {config}")
        
        # 1. Validar configuración
        is_valid, errors = self.validator.validate_report_config(config)
        if not is_valid:
            logger.error(f"Configuración inválida: {errors}")
            raise ValueError(f"Configuración inválida: {errors}")
        
        # 2. Crear registro de reporte
        report = self._create_report_record(config, generation_source, voice_request_id)
        logger.info(f"Reporte creado con ID: {report.id}")
        
        try:
            # 3. Marcar como procesando
            report.mark_as_processing()
            
            # 4. Construir y ejecutar query
            logger.info("Construyendo query base...")
            queryset = self.query_builder.build_query(
                config['scope'],
                config['category'],
                config['report_type'],
                config
            )
            
            # 5. Aplicar agrupaciones si existen
            report_def = self.catalog.get_report_definition(
                config['scope'],
                config['category'],
                config['report_type']
            )
            
            if config.get('group_by'):
                logger.info(f"Aplicando agrupaciones: {config['group_by']}")
                queryset = self.query_builder.build_aggregated_query(
                    queryset,
                    config,
                    report_def
                )
            
            # 6. Obtener datos (convertir QuerySet a lista de diccionarios)
            logger.info("Ejecutando query y convirtiendo a diccionarios...")
            try:
                data = self._queryset_to_dicts(queryset, config.get('columns', []))
                row_count = len(data)
                logger.info(f"Query ejecutado exitosamente. Filas obtenidas: {row_count}")
            except Exception as e:
                logger.error(f"Error al ejecutar query: {e}")
                logger.error(f"Query SQL: {queryset.query if hasattr(queryset, 'query') else 'N/A'}")
                raise
            
            # 7. Generar gráfico si aplica (solo para PDF)
            chart_image = None
            viz_config = None
            
            if config['format'] == 'pdf':
                logger.info("Formato PDF detectado, evaluando generación de gráfico...")
                
                # Construir configuración de visualización
                user_viz_request = config.get('visualization')
                viz_config = self.viz_builder.build_visualization_config(
                    report_type=config['report_type'],
                    config=config,
                    user_request=user_viz_request
                )
                
                # Generar gráfico si se recomienda y hay datos suficientes
                if viz_config and self.viz_builder.should_generate_chart(
                    config['report_type'],
                    config,
                    data
                ):
                    try:
                        logger.info(f"Generando gráfico tipo {viz_config['chart_type']}...")
                        chart_image = self.chart_service.generate_chart(
                            chart_type=viz_config['chart_type'],
                            data=data,
                            config=viz_config
                        )
                        logger.info(f"Gráfico generado exitosamente. Tamaño: {len(chart_image)} bytes")
                    except Exception as e:
                        logger.warning(f"Error al generar gráfico: {e}. Continuando sin gráfico.")
                        chart_image = None
                        viz_config = None
                else:
                    logger.info("No se generará gráfico para este reporte")
            
            # 8. Exportar a archivo
            logger.info(f"Exportando a formato {config['format']}...")
            
            # Obtener configuración del gráfico si existe
            chart_config = None
            if config.get('chart_type'):
                # Usar el servicio manual para obtener la configuración del gráfico
                from .manual_report_service import ManualReportService
                manual_service = ManualReportService(user=self.user, tenant=self.tenant)
                chart_config = manual_service._build_chart_config(
                    config['report_type'],
                    config['chart_type'],
                    config
                )
            
            # Preparar metadatos para el reporte
            report_metadata = {
                'report_type': config['report_type'],
                'user_name': f"{self.user.first_name} {self.user.last_name}".strip() or self.user.username,
                'tenant_name': self.tenant.name if self.tenant else None,
                'filters': config.get('filters', {}),
                'chart_config': chart_config,  # Pasar configuración del gráfico
                'visualization': viz_config
            }
            
            file_content = self.export_service.export(
                data,
                config['columns'],
                config['format'],
                report_metadata
            )
            
            # 9. Guardar en storage
            logger.info("Guardando archivo en storage...")
            file_resource = self._save_to_storage(
                file_content,
                config,
                report
            )
            
            # 10. Calcular tiempo de procesamiento
            processing_time = int(time.time() - start_time)
            logger.info(f"Reporte generado exitosamente en {processing_time}s")
            
            # 11. Marcar como completado
            report.mark_as_completed(file_resource, row_count, processing_time)
            
            return report
        
        except Exception as e:
            # Marcar como fallido
            logger.error(f"Error generando reporte: {e}", exc_info=True)
            report.mark_as_failed(str(e))
            raise
    
    def preview_report(
        self,
        config: Dict[str, Any],
        page: int = 1,
        page_size: int = 50
    ) -> Dict[str, Any]:
        """
        Genera vista previa paginada del reporte.
        
        Args:
            config: Configuración del reporte
            page: Número de página
            page_size: Tamaño de página
        
        Returns:
            Diccionario con datos paginados y metadata
        """
        # 1. Validar configuración
        is_valid, errors = self.validator.validate_report_config(config)
        if not is_valid:
            raise ValueError(f"Configuración inválida: {errors}")
        
        # 2. Construir query
        queryset = self.query_builder.build_query(
            config['scope'],
            config['category'],
            config['report_type'],
            config
        )
        
        # 3. Aplicar agrupaciones si existen
        report_def = self.catalog.get_report_definition(
            config['scope'],
            config['category'],
            config['report_type']
        )
        
        if config.get('group_by'):
            queryset = self.query_builder.build_aggregated_query(
                queryset,
                config,
                report_def
            )
        
        # 4. Paginar
        paginator = Paginator(queryset, page_size)
        page_obj = paginator.get_page(page)
        
        # 5. Convertir a diccionarios (pasar el queryset de la página, no el objeto Page)
        data = self._queryset_to_dicts(page_obj.object_list, config.get('columns', []))
        
        return {
            'preview_rows': data,
            'total_rows': paginator.count,
            'columns': config.get('columns', []),
            'estimated_file_size_mb': round(paginator.count * 0.001, 2)  # Estimación simple
        }
    
    def _create_report_record(
        self,
        config: Dict[str, Any],
        generation_source: str,
        voice_request_id: Optional[int]
    ) -> GeneratedReport:
        """Crea registro de reporte en base de datos."""
        return GeneratedReport.objects.create(
            institution=self.tenant,
            scope=config['scope'],
            category=config['category'],
            report_type=config['report_type'],
            requested_by=self.user,
            config_json=config,
            generation_source=generation_source,
            voice_request_id=voice_request_id,
            file_format=config['format'],
            status='PENDING'
        )
    
    def _save_to_storage(
        self,
        file_content: bytes,
        config: Dict[str, Any],
        report: GeneratedReport
    ) -> FileResource:
        """
        Guarda archivo en storage y crea FileResource.
        
        Args:
            file_content: Contenido del archivo en bytes
            config: Configuración del reporte
            report: Instancia de GeneratedReport
        
        Returns:
            Instancia de FileResource creada
        """
        # Generar nombre de archivo
        filename = self._generate_filename(config, report)
        
        # Determinar extensión y MIME type
        format_ext = config['format']
        mime_types = {
            'csv': 'text/csv',
            'xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            'pdf': 'application/pdf'
        }
        mime_type = mime_types.get(format_ext, 'application/octet-stream')
        
        # Construir ruta en storage
        if self.tenant:
            tenant_id = str(self.tenant.id)
        else:
            tenant_id = 'saas'
        
        file_path = self.storage_service.build_storage_path(
            tenant_id=tenant_id,
            resource_type='report',
            category=config['category'].lower(),
            file_extension=format_ext,
            entity_id=str(report.id)
        )
        
        # Subir a storage
        self.storage_service.upload_to_storage(
            file_path=file_path,
            file_content=file_content,
            content_type=mime_type
        )
        
        # Calcular checksum
        checksum = StorageService.calculate_checksum(file_content)
        
        # Crear FileResource
        file_resource = FileResource.objects.create(
            tenant=self.tenant,
            resource_type='REPORT',
            entity_type='generated_report',
            entity_id=report.id,
            original_name=filename,
            stored_name=file_path.split('/')[-1],
            file_path=file_path,
            bucket=self.storage_service.bucket,
            mime_type=mime_type,
            extension=format_ext,
            size=len(file_content),
            category=config['category'].lower(),
            visibility='PRIVATE',
            uploaded_by=self.user,
            status='ACTIVE',
            checksum=checksum,
            metadata={
                'report_type': config['report_type'],
                'scope': config['scope'],
                'generation_source': report.generation_source
            }
        )
        
        return file_resource
    
    def _generate_filename(
        self,
        config: Dict[str, Any],
        report: GeneratedReport
    ) -> str:
        """Genera nombre de archivo para el reporte."""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        report_type = config['report_type']
        format_ext = config['format']
        
        # Sanitizar report_type para nombre de archivo
        safe_report_type = report_type.replace('_', '-')
        
        return f"reporte_{safe_report_type}_{timestamp}.{format_ext}"
    
    def _queryset_to_dicts(
        self,
        queryset,
        columns: List[str]
    ) -> List[Dict[str, Any]]:
        """
        Convierte QuerySet a lista de diccionarios.
        
        Maneja tanto queries agregados (diccionarios) como queries normales (instancias de modelo).
        Asegura que TODOS los campos solicitados sean incluidos.
        
        Args:
            queryset: QuerySet de Django
            columns: Columnas a incluir (nombres del catálogo)
        
        Returns:
            Lista de diccionarios con datos serializados
        """
        # Mapeo completo de campos virtuales a campos reales de BD
        column_to_field_map = {
            # === PRODUCTO ===
            'product_name': 'product__name',
            'product_code': 'product__code',
            'product_type': 'product__product_type__name',
            
            # === SUCURSAL ===
            'branch_name': 'branch__name',
            'branch_city': 'branch__city',
            
            # === CLIENTE ===
            'client_name': 'client__user__first_name',  # Necesita concatenación
            'client_document': 'client__document_number',
            'client_email': 'client__user__email',
            'client_phone': 'client__mobile_phone',
            'full_name': 'user__first_name',  # Volverá a concatenación manual
            'first_name': 'user__first_name',
            'last_name': 'user__last_name',
            'email': 'user__email',  # Campo directo
            'phone': 'mobile_phone',
            'mobile_phone': 'mobile_phone',
            'document_number': 'document_number',
            'document_type': 'document_type',
            'document_extension': 'document_extension',
            'birth_date': 'birth_date',
            'gender': 'gender',
            'client_type': 'client_type',
            'address': 'address',
            'city': 'city',
            'department': 'department',
            'country': 'country',
            'postal_code': 'postal_code',
            
            # === INFORMACIÓN LABORAL ===
            'employment_status': 'employment_status',
            'employment_type': 'employment_type',
            'employer_name': 'employer_name',
            'employer_nit': 'employer_nit',
            'job_title': 'job_title',
            'employment_start_date': 'employment_start_date',
            'monthly_income': 'monthly_income',
            'additional_income': 'additional_income',
            'debt_to_income_ratio': 'debt_to_income_ratio',
            
            # === USUARIOS ===
            'assigned_to_name': 'assigned_to__first_name',  # Necesita concatenación
            'reviewed_by_name': 'reviewed_by__first_name',  # Necesita concatenación
            'approved_by_name': 'approved_by__first_name',  # Necesita concatenación
            'created_by_name': 'created_by__first_name',  # Necesita concatenación
            'updated_by_name': 'updated_by__first_name',  # Necesita concatenación
            'verified_by_name': 'verified_by__first_name',  # Volverá a concatenación manual
            
            # === SOLICITUD ===
            'application_number': 'application_number',
            'status': 'status',
            'risk_level': 'risk_level',
            'credit_score': 'credit_score',
            'purpose': 'purpose',
            'notes': 'notes',
            'observation_reason': 'observation_reason',
            'rejection_reason': 'rejection_reason',
            'identity_verification_status': 'identity_verification_status',
            'documents_status': 'documents_status',
            'requested_amount': 'requested_amount',
            'approved_amount': 'approved_amount',
            'term_months': 'term_months',
            'approved_term_months': 'approved_term_months',
            'approved_interest_rate': 'approved_interest_rate',
            'monthly_payment': 'monthly_payment',
            'is_active': 'is_active',
            
            # === FECHAS ===
            'created_at': 'created_at',
            'submitted_at': 'submitted_at',
            'reviewed_at': 'reviewed_at',
            'approved_at': 'approved_at',
            'rejected_at': 'rejected_at',
            'disbursed_at': 'disbursed_at',
            'updated_at': 'updated_at',
            'verified_at': 'verified_at',
            
            # === ESTADOS ===
            'kyc_status': 'kyc_status',
            
            # === TENANT ===
            'tenant_name': 'institution__name',
            'tenant_slug': 'institution__slug',
            'institution_type': 'institution_type',
            
            # === PLAN ===
            'plan_name': 'subscription__plan__name',
            'subscription_status': 'subscription_status',
            'payment_status': 'payment_status',
            
            # === PRODUCTOS CREDITICIOS ===
            # Información básica
            'product_code': 'code',
            'product_type': 'product_type__name',
            'description': 'description',
            'is_active': 'is_active',
            'display_order': 'display_order',
            
            # Parámetros de montos (campos anotados)
            'min_amount': 'min_amount',
            'max_amount': 'max_amount',
            'default_amount': 'default_amount',
            
            # Parámetros de plazos (campos anotados)
            'min_term_months': 'min_term_months',
            'max_term_months': 'max_term_months',
            'default_term_months': 'default_term_months',
            
            # Tasas de interés (campos anotados)
            'min_interest_rate': 'min_interest_rate',
            'max_interest_rate': 'max_interest_rate',
            'default_interest_rate': 'default_interest_rate',
            'interest_rate_type': 'interest_rate_type_value',
            
            # Comisiones y cargos (campos anotados)
            'origination_fee_percentage': 'origination_fee_percentage',
            'origination_fee_fixed': 'origination_fee_fixed',
            'late_payment_fee_percentage': 'late_payment_fee_percentage',
            'late_payment_fee_fixed': 'late_payment_fee_fixed',
            'prepayment_penalty_percentage': 'prepayment_penalty_percentage',
            
            # Información de marketing
            'target_audience': 'target_audience',
            'benefits': 'benefits',
            
            # Conjunto de reglas (campos anotados)
            'rule_set_name': 'rule_set_name_value',
            'rule_set_code': 'rule_set_code_value',
        }
        
        # Campos que necesitan concatenación de nombres
        concatenation_fields = {
            'client_name': ('client__user__first_name', 'client__user__last_name'),
            'full_name': ('user__first_name', 'user__last_name'),  # Restaurado
            'assigned_to_name': ('assigned_to__first_name', 'assigned_to__last_name'),
            'reviewed_by_name': ('reviewed_by__first_name', 'reviewed_by__last_name'),
            'approved_by_name': ('approved_by__first_name', 'approved_by__last_name'),
            'created_by_name': ('created_by__first_name', 'created_by__last_name'),
            'updated_by_name': ('updated_by__first_name', 'updated_by__last_name'),
            'verified_by_name': ('verified_by__first_name', 'verified_by__last_name'),  # Restaurado
        }
        
        result = []
        
        # Si el queryset ya tiene values() aplicado (es un diccionario), usarlo directamente
        # Si no, necesitamos convertir las instancias de modelo
        first_item = queryset.first()
        is_dict_query = isinstance(first_item, dict)
        
        # Si no es un query con values(), aplicarlo ahora con los campos necesarios
        if not is_dict_query and columns:
            # Construir lista de campos de BD a seleccionar
            fields_to_select = []
            for col in columns:
                if col in concatenation_fields:
                    # Agregar ambos campos para concatenación
                    fields_to_select.extend(concatenation_fields[col])
                elif col in column_to_field_map:
                    fields_to_select.append(column_to_field_map[col])
                else:
                    # Campo directo
                    fields_to_select.append(col)
            
            # Eliminar duplicados
            fields_to_select = list(set(fields_to_select))
            
            # Aplicar values() con los campos necesarios
            try:
                queryset = queryset.values(*fields_to_select)
                is_dict_query = True
            except Exception as e:
                logger.warning(f"No se pudo aplicar values() con campos {fields_to_select}: {e}")
                # Continuar con el enfoque de instancias de modelo
        
        for item in queryset:
            row = {}
            
            for col in columns:
                value = None
                
                if is_dict_query:
                    # Item es un diccionario
                    if col in concatenation_fields:
                        # Concatenar nombres
                        first_field, last_field = concatenation_fields[col]
                        first_name = item.get(first_field, '')
                        last_name = item.get(last_field, '')
                        value = f"{first_name} {last_name}".strip() if first_name or last_name else None
                    elif col in item:
                        # Campo directo en el diccionario
                        value = item[col]
                    elif col in column_to_field_map and column_to_field_map[col] in item:
                        # Campo mapeado en el diccionario
                        value = item[column_to_field_map[col]]
                else:
                    # Item es una instancia de modelo
                    if col in concatenation_fields:
                        # Concatenar nombres navegando por relaciones
                        first_field, last_field = concatenation_fields[col]
                        first_name = self._get_nested_attr(item, first_field)
                        last_name = self._get_nested_attr(item, last_field)
                        value = f"{first_name} {last_name}".strip() if first_name or last_name else None
                    elif hasattr(item, col):
                        # Atributo directo
                        value = getattr(item, col)
                    elif col in column_to_field_map:
                        # Navegar por relaciones
                        value = self._get_nested_attr(item, column_to_field_map[col])
                
                row[col] = self._serialize_value(value)
            
            result.append(row)
        
        return result
    
    def _get_nested_attr(self, obj, attr_path: str):
        """
        Obtiene un atributo navegando por relaciones.
        
        Args:
            obj: Objeto base
            attr_path: Ruta del atributo (ej: 'client__user__email')
        
        Returns:
            Valor del atributo o None
        """
        parts = attr_path.split('__')
        value = obj
        
        for part in parts:
            if value is None:
                return None
            try:
                value = getattr(value, part, None)
            except (AttributeError, TypeError):
                return None
        
        return value
    
    def _serialize_value(self, value: Any) -> Any:
        """
        Serializa un valor para JSON/exportación.
        
        Args:
            value: Valor a serializar
        
        Returns:
            Valor serializado
        """
        if isinstance(value, (datetime, )):
            return value.isoformat()
        if isinstance(value, Decimal):
            return float(value)
        if isinstance(value, uuid4().__class__):
            return str(value)
        return value
