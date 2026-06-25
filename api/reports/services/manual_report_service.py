"""
Servicio para reportes manuales con soporte de gráficos y vista previa.

Este servicio extiende la funcionalidad de reportes para incluir:
- Metadatos enriquecidos para formularios dinámicos
- Configuración de gráficos por defecto
- Vista previa con datos y configuración de gráficos
- Generación de reportes con gráficos embebidos
"""
import logging
from typing import Dict, List, Any, Optional
from django.db.models import QuerySet

from .report_catalog import ReportCatalogService
from .report_query_builder import ReportQueryBuilder
from .report_generator_service import ReportGeneratorService

logger = logging.getLogger(__name__)


class ManualReportService:
    """
    Servicio para reportes manuales con soporte completo de UI.
    """
    
    # Configuración de gráficos por tipo de reporte
    CHART_CONFIGS = {
        # === CRÉDITOS ===
        'loans_by_status': {
            'default_chart': 'bar',  # Cambiado de 'donut' a 'bar' para mejor compatibilidad
            'available_charts': ['bar', 'donut', 'pie', 'line'],
            'chart_config': {
                'donut': {
                    'data_key': 'total_applications',
                    'name_key': 'status',
                    'colors': ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899'],
                    'label_format': '{name}: {value} ({percentage}%)'
                },
                'bar': {
                    'x_axis': 'status',
                    'y_axes': [
                        {'key': 'total_applications', 'color': '#3b82f6', 'label': 'Solicitudes'}
                    ]
                },
                'line': {
                    'x_axis': 'month',
                    'y_axes': [
                        {'key': 'total_applications', 'color': '#3b82f6', 'label': 'Solicitudes'}
                    ]
                }
            }
        },
        'loans_by_product': {
            'default_chart': 'bar',
            'available_charts': ['bar', 'horizontal_bar', 'line'],
            'chart_config': {
                'bar': {
                    'x_axis': 'product_name',
                    'y_axes': [
                        {'key': 'total_applications', 'color': '#3b82f6', 'label': 'Solicitudes'},
                        {'key': 'approved_count', 'color': '#10b981', 'label': 'Aprobados'}
                    ]
                },
                'line': {
                    'x_axis': 'product_name',
                    'y_axes': [
                        {'key': 'approval_rate', 'color': '#10b981', 'label': 'Tasa de Aprobación (%)'}
                    ]
                }
            }
        },
        'loans_by_branch': {
            'default_chart': 'bar',
            'available_charts': ['bar', 'horizontal_bar', 'heatmap'],
            'chart_config': {
                'bar': {
                    'x_axis': 'branch_name',
                    'y_axes': [
                        {'key': 'total_applications', 'color': '#3b82f6', 'label': 'Solicitudes'},
                        {'key': 'approval_rate', 'color': '#10b981', 'label': 'Tasa Aprobación (%)'}
                    ]
                }
            }
        },
        'customers_registered': {
            'default_chart': 'line',
            'available_charts': ['line', 'area', 'bar'],
            'chart_config': {
                'line': {
                    'x_axis': 'month',
                    'y_axes': [
                        {'key': 'total_clients', 'color': '#3b82f6', 'label': 'Clientes Registrados'}
                    ]
                },
                'area': {
                    'x_axis': 'month',
                    'y_axes': [
                        {'key': 'total_clients', 'color': '#3b82f6', 'label': 'Clientes Registrados', 'fill': True}
                    ]
                }
            }
        },
        'active_loans': {
            'default_chart': 'table',
            'available_charts': ['table', 'bar'],
            'chart_config': {
                'bar': {
                    'x_axis': 'product_name',
                    'y_axes': [
                        {'key': 'approved_amount', 'color': '#10b981', 'label': 'Monto Aprobado'}
                    ]
                }
            }
        },
        'applications_with_pending_documents': {
            'default_chart': 'table',
            'available_charts': ['table', 'funnel'],
            'chart_config': {
                'funnel': {
                    'stages': [
                        {'key': 'total_documents_required', 'label': 'Total Requeridos'},
                        {'key': 'uploaded_documents_count', 'label': 'Subidos'},
                        {'key': 'completion_percentage', 'label': 'Completados'}
                    ]
                }
            }
        },
        # === SAAS ===
        'tenants_by_subscription_status': {
            'default_chart': 'donut',
            'available_charts': ['donut', 'bar', 'pie'],
            'chart_config': {
                'donut': {
                    'data_key': 'tenant_count',
                    'name_key': 'subscription_status',
                    'colors': ['#10b981', '#f59e0b', '#ef4444', '#8b5cf6']
                }
            }
        },
        'subscriptions_usage_analysis': {
            'default_chart': 'gauge',
            'available_charts': ['gauge', 'bar', 'table'],
            'chart_config': {
                'gauge': {
                    'metrics': [
                        {'key': 'users_percentage', 'label': 'Usuarios', 'max': 100, 'color': '#3b82f6'},
                        {'key': 'branches_percentage', 'label': 'Sucursales', 'max': 100, 'color': '#10b981'},
                        {'key': 'storage_percentage', 'label': 'Almacenamiento', 'max': 100, 'color': '#f59e0b'}
                    ]
                }
            }
        },
        'subscriptions_revenue_analysis': {
            'default_chart': 'line',
            'available_charts': ['line', 'area', 'bar'],
            'chart_config': {
                'line': {
                    'x_axis': 'month',
                    'y_axes': [
                        {'key': 'monthly_revenue', 'color': '#10b981', 'label': 'Revenue Mensual'}
                    ]
                }
            }
        },
        'audit_logs_by_action': {
            'default_chart': 'bar',
            'available_charts': ['bar', 'heatmap', 'timeline'],
            'chart_config': {
                'bar': {
                    'x_axis': 'action',
                    'y_axes': [
                        {'key': 'total_actions', 'color': '#3b82f6', 'label': 'Total Acciones'}
                    ]
                }
            }
        },
        # === REPORTES COMPARTIDOS (TENANT Y SAAS) ===
        'audit': {
            'default_chart': 'bar',
            'available_charts': ['bar', 'line', 'table'],
            'chart_config': {
                'bar': {
                    'x_axis': 'action',
                    'y_axes': [
                        {'key': 'count', 'color': '#3b82f6', 'label': 'Cantidad de Eventos'}
                    ]
                },
                'line': {
                    'x_axis': 'date',
                    'y_axes': [
                        {'key': 'count', 'color': '#3b82f6', 'label': 'Eventos por Día'}
                    ]
                }
            }
        },
        'users': {
            'default_chart': 'bar',
            'available_charts': ['bar', 'donut', 'table'],
            'chart_config': {
                'bar': {
                    'x_axis': 'name',  # Cambiado de 'role' a 'name'
                    'y_axes': [
                        {'key': 'value', 'color': '#3b82f6', 'label': 'Cantidad de Usuarios'}  # Cambiado de 'count' a 'value'
                    ]
                },
                'donut': {
                    'data_key': 'value',  # Cambiado de 'count' a 'value'
                    'name_key': 'name',  # Cambiado de 'role' a 'name'
                    'colors': ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899'],
                    'label_format': '{name}: {value} usuarios'
                }
            }
        },
        'branches': {
            'default_chart': 'bar',
            'available_charts': ['bar', 'table'],
            'chart_config': {
                'bar': {
                    'x_axis': 'name',
                    'y_axes': [
                        {'key': 'applications_count', 'color': '#3b82f6', 'label': 'Solicitudes'}
                    ]
                }
            }
        }
    }
    
    # Configuración de filtros UI por tipo de campo
    FILTER_UI_CONFIG = {
        'choice': {
            'component': 'multiselect',
            'props': {
                'searchable': True,
                'clearable': True
            }
        },
        'integer': {
            'component': 'number_input',
            'props': {
                'min': 0,
                'step': 1
            }
        },
        'decimal': {
            'component': 'number_input',
            'props': {
                'min': 0,
                'step': 0.01,
                'precision': 2
            }
        },
        'date': {
            'component': 'date_picker',
            'props': {
                'format': 'YYYY-MM-DD',
                'clearable': True
            }
        },
        'daterange': {
            'component': 'date_range_picker',
            'props': {
                'format': 'YYYY-MM-DD',
                'shortcuts': ['today', 'yesterday', 'last_7_days', 'last_30_days', 'this_month', 'last_month']
            }
        },
        'boolean': {
            'component': 'toggle',
            'props': {}
        },
        'string': {
            'component': 'text_input',
            'props': {
                'clearable': True
            }
        }
    }
    
    def _infer_ui_component(self, field_name: str, filter_type: str) -> tuple:
        """
        Infiere el componente UI basado en el nombre del campo y tipo.
        
        Args:
            field_name: Nombre del campo
            filter_type: Tipo de dato
        
        Returns:
            Tupla (component, props)
        """
        # Detectar rangos por sufijos
        if field_name.endswith('_min') or field_name.endswith('_max'):
            # Rango numérico (monto, puntaje, etc.)
            if filter_type == 'decimal':
                return ('number_input', {
                    'min': 0,
                    'step': 0.01,
                    'precision': 2
                })
            else:  # integer
                return ('number_input', {
                    'min': 0,
                    'step': 1
                })
        
        if field_name.endswith('_start') or field_name.endswith('_end'):
            # Rango de fechas
            return ('date_picker', {
                'format': 'YYYY-MM-DD',
                'clearable': True
            })
        
        # Detectar relaciones por sufijo _id
        if field_name.endswith('_id'):
            return ('select', {
                'searchable': True,
                'clearable': True
            })
        
        # Usar configuración por defecto según tipo
        config = self.FILTER_UI_CONFIG.get(filter_type, self.FILTER_UI_CONFIG['string'])
        return (config['component'], config['props'])
    
    def __init__(self, user=None, tenant=None):
        """
        Inicializa el servicio.
        
        Args:
            user: Usuario que solicita el reporte
            tenant: Tenant para reportes TENANT
        """
        self.user = user
        self.tenant = tenant
        self.catalog_service = ReportCatalogService()
        self.query_builder = ReportQueryBuilder(tenant=tenant)
    
    def get_enriched_catalog(self, scope: str, user_roles: List[str]) -> Dict[str, Any]:
        """
        Obtiene catálogo enriquecido con configuración de UI y gráficos.
        
        Args:
            scope: TENANT o SAAS
            user_roles: Roles del usuario
        
        Returns:
            Catálogo enriquecido con metadatos de UI
        """
        # Obtener catálogo base
        base_catalog = self.catalog_service.get_available_reports(scope, user_roles)
        
        # Enriquecer con configuración de gráficos y UI
        enriched_catalog = {}
        
        for category, reports in base_catalog.items():
            enriched_reports = []
            
            for report in reports:
                report_type = report['type']
                
                # Agregar configuración de gráficos
                chart_config = self.CHART_CONFIGS.get(report_type, {
                    'default_chart': 'table',
                    'available_charts': ['table'],
                    'chart_config': {}
                })
                
                enriched_report = {
                    **report,
                    'chart_config': chart_config
                }
                
                enriched_reports.append(enriched_report)
            
            enriched_catalog[category] = enriched_reports
        
        return enriched_catalog
    
    def get_report_metadata(self, scope: str, category: str, report_type: str) -> Dict[str, Any]:
        """
        Obtiene metadatos completos de un reporte para construir el formulario.
        
        Args:
            scope: TENANT o SAAS
            category: Categoría del reporte
            report_type: Tipo de reporte
        
        Returns:
            Metadatos enriquecidos con configuración de UI
        """
        # Obtener definición base
        definition = self.catalog_service.get_report_definition(scope, category, report_type)
        
        if not definition:
            raise ValueError(f"Reporte no encontrado: {scope}.{category}.{report_type}")
        
        # Enriquecer filtros con configuración de UI
        enriched_filters = []
        
        for field, filter_config in definition['available_filters'].items():
            filter_type = filter_config.get('type', 'string')
            
            # Inferir componente UI basado en nombre y tipo
            ui_component, ui_props = self._infer_ui_component(field, filter_type)
            
            enriched_filter = {
                'field': field,
                'label': self._generate_label(field),
                'type': filter_type,
                'operators': filter_config.get('operators', ['equals']),
                'required': filter_config.get('required', False),
                'ui_component': ui_component,
                'ui_props': ui_props
            }
            
            # ✅ NO agregar opciones estáticas - dejar que el frontend las cargue dinámicamente
            # Esto permite que los filtros se actualicen automáticamente cuando cambian los datos
            # El frontend detectará automáticamente filtros de relación (_id) y choices
            # y cargará las opciones desde los endpoints correspondientes
            
            # Agregar valor por defecto si existe
            if 'default' in filter_config:
                enriched_filter['default_value'] = filter_config['default']
            
            enriched_filters.append(enriched_filter)
        
        # Enriquecer columnas con metadatos
        enriched_columns = [
            {
                'field': col,
                'label': self._generate_label(col),
                'sortable': col in definition.get('available_sort_fields', []),
                'groupable': col in definition.get('available_groupings', [])
            }
            for col in definition['available_columns']
        ]
        
        # Agregar configuración de gráficos
        chart_config = self.CHART_CONFIGS.get(report_type, {
            'default_chart': 'table',
            'available_charts': ['table'],
            'chart_config': {}
        })
        
        # Configuración por defecto sugerida
        default_config = self._generate_default_config(definition, chart_config)
        
        return {
            'scope': scope,
            'category': category,
            'report_type': report_type,
            'name': definition['name'],
            'description': definition['description'],
            'datasource': definition['datasource'],
            'filters': enriched_filters,
            'columns': enriched_columns,
            'groupings': [
                {'field': g, 'label': self._generate_label(g)}
                for g in definition.get('available_groupings', [])
            ],
            'sort_fields': [
                {'field': s, 'label': self._generate_label(s)}
                for s in definition.get('available_sort_fields', [])
            ],
            'formats': definition.get('formats', ['csv', 'xlsx', 'pdf']),
            'chart_config': chart_config,
            'default_config': default_config
        }
    
    def preview_report_with_chart(
        self,
        scope: str,
        category: str,
        report_type: str,
        config: Dict[str, Any],
        page: int = 1,
        page_size: int = 50
    ) -> Dict[str, Any]:
        """
        Genera vista previa del reporte con datos y configuración de gráfico.
        
        Args:
            scope: TENANT o SAAS
            category: Categoría del reporte
            report_type: Tipo de reporte
            config: Configuración del reporte
            page: Número de página
            page_size: Tamaño de página
        
        Returns:
            Datos de vista previa con configuración de gráfico
        """
        # Obtener definición del reporte
        report_def = self.catalog_service.get_report_definition(scope, category, report_type)
        
        if not report_def:
            raise ValueError(f"Reporte no encontrado: {scope}.{category}.{report_type}")
        
        # Construir query
        queryset = self.query_builder.build_query(scope, category, report_type, config)
        
        # Aplicar agrupaciones si existen
        if config.get('group_by'):
            queryset = self.query_builder.build_aggregated_query(queryset, config, report_def)
        
        # Aplicar ordenamiento
        if config.get('sort'):
            queryset = self.query_builder._apply_sorting(queryset, config['sort'])
        
        # Contar total de registros
        total_count = queryset.count()
        
        # Aplicar paginación
        start = (page - 1) * page_size
        end = start + page_size
        paginated_queryset = queryset[start:end]
        
        # Convertir a lista de diccionarios
        data = list(paginated_queryset.values())
        
        # Obtener configuración de gráfico
        chart_type = config.get('chart_type', self.CHART_CONFIGS.get(report_type, {}).get('default_chart', 'table'))
        chart_config = self._build_chart_config(report_type, chart_type, config)
        
        # Calcular resumen
        summary = self._calculate_summary(data, config)
        
        return {
            'data': data,
            'pagination': {
                'page': page,
                'page_size': page_size,
                'total_count': total_count,
                'total_pages': (total_count + page_size - 1) // page_size,
                'has_next': end < total_count,
                'has_previous': page > 1
            },
            'chart_config': chart_config,
            'summary': summary,
            'columns': config.get('columns', report_def['available_columns'][:10])
        }
    
    def _generate_label(self, field: str) -> str:
        """
        Genera etiqueta legible para un campo.
        
        Args:
            field: Nombre del campo
        
        Returns:
            Etiqueta legible
        """
        # Mapeo de campos comunes a etiquetas en español
        labels = {
            # Estados
            'status': 'Estado',
            'risk_level': 'Nivel de Riesgo',
            'kyc_status': 'Estado KYC',
            'documents_status': 'Estado Documentos',
            'identity_verification_status': 'Estado Verificación',
            'subscription_status': 'Estado Suscripción',
            'payment_status': 'Estado Pago',
            
            # Identificación
            'application_number': 'Número de Solicitud',
            'client_name': 'Nombre Cliente',
            'client_document': 'Documento Cliente',
            'client_email': 'Email Cliente',
            'client_phone': 'Teléfono Cliente',
            'document_number': 'Número Documento',
            'document_type': 'Tipo Documento',
            
            # Producto
            'product_name': 'Producto',
            'product_code': 'Código Producto',
            'product_type': 'Tipo Producto',
            'product_id': 'Producto',
            
            # Sucursal
            'branch_name': 'Sucursal',
            'branch_city': 'Ciudad Sucursal',
            'branch_id': 'Sucursal',
            
            # Montos
            'requested_amount': 'Monto Solicitado',
            'requested_amount_min': 'Monto Solicitado Mínimo',
            'requested_amount_max': 'Monto Solicitado Máximo',
            'approved_amount': 'Monto Aprobado',
            'approved_amount_min': 'Monto Aprobado Mínimo',
            'approved_amount_max': 'Monto Aprobado Máximo',
            'monthly_payment': 'Pago Mensual',
            'monthly_income': 'Ingreso Mensual',
            'monthly_income_min': 'Ingreso Mensual Mínimo',
            'monthly_income_max': 'Ingreso Mensual Máximo',
            
            # Puntajes
            'credit_score': 'Puntaje de Crédito',
            'credit_score_min': 'Puntaje de Crédito Mínimo',
            'credit_score_max': 'Puntaje de Crédito Máximo',
            
            # Términos
            'term_months': 'Plazo (meses)',
            'term_months_min': 'Plazo Mínimo (meses)',
            'term_months_max': 'Plazo Máximo (meses)',
            'approved_term_months': 'Plazo Aprobado (meses)',
            'approved_interest_rate': 'Tasa de Interés',
            
            # Fechas
            'created_at': 'Fecha Creación',
            'created_at_start': 'Fecha Creación Desde',
            'created_at_end': 'Fecha Creación Hasta',
            'submitted_at': 'Fecha Envío',
            'submitted_at_start': 'Fecha Envío Desde',
            'submitted_at_end': 'Fecha Envío Hasta',
            'approved_at': 'Fecha Aprobación',
            'approved_at_start': 'Fecha Aprobación Desde',
            'approved_at_end': 'Fecha Aprobación Hasta',
            'rejected_at': 'Fecha Rechazo',
            'disbursed_at': 'Fecha Desembolso',
            'verified_at': 'Fecha Verificación',
            'verified_at_start': 'Fecha Verificación Desde',
            'verified_at_end': 'Fecha Verificación Hasta',
            'birth_date': 'Fecha de Nacimiento',
            'birth_date_start': 'Fecha de Nacimiento Desde',
            'birth_date_end': 'Fecha de Nacimiento Hasta',
            'started_at': 'Fecha Inicio',
            'started_at_start': 'Fecha Inicio Desde',
            'started_at_end': 'Fecha Inicio Hasta',
            'completed_at': 'Fecha Completado',
            'completed_at_start': 'Fecha Completado Desde',
            'completed_at_end': 'Fecha Completado Hasta',
            'last_login': 'Último Login',
            'last_login_start': 'Último Login Desde',
            'last_login_end': 'Último Login Hasta',
            
            # Asignación
            'assigned_to_id': 'Asignado a',
            'assigned_to_name': 'Asignado a',
            'reviewed_by_name': 'Revisado por',
            'approved_by_name': 'Aprobado por',
            'created_by_name': 'Creado por',
            
            # Empleo
            'employment_type': 'Tipo de Empleo',
            'employment_status': 'Estado de Empleo',
            
            # Cliente
            'client_type': 'Tipo de Cliente',
            'gender': 'Género',
            'city': 'Ciudad',
            'department': 'Departamento',
            'country': 'País',
            
            # Documentos
            'document_status': 'Estado del Documento',
            'document_type_id': 'Tipo de Documento',
            'days_since_submission': 'Días desde Envío',
            'days_since_submission_min': 'Días desde Envío Mínimo',
            'days_since_submission_max': 'Días desde Envío Máximo',
            'completion_percentage': '% Completitud',
            'completion_percentage_min': '% Completitud Mínimo',
            'completion_percentage_max': '% Completitud Máximo',
            
            # Verificación
            'decision': 'Decisión',
            'provider': 'Proveedor',
            'processing_time': 'Tiempo de Procesamiento',
            'processing_time_min': 'Tiempo Procesamiento Mín (min)',
            'processing_time_max': 'Tiempo Procesamiento Máx (min)',
            
            # Auditoría
            'action': 'Acción',
            'user_id': 'Usuario',
            'ip_address': 'Dirección IP',
            'event_type': 'Tipo de Evento',
            'severity': 'Severidad',
            'resource_type': 'Tipo de Recurso',
            'resource_id': 'ID de Recurso',
            
            # Tenants
            'institution_type': 'Tipo de Institución',
            'plan_id': 'Plan',
            'tenant_id': 'Tenant',
            'users_count': 'Cantidad de Usuarios',
            'users_count_min': 'Usuarios Mínimos',
            'users_count_max': 'Usuarios Máximos',
            'branches_count': 'Cantidad de Sucursales',
            'branches_count_min': 'Sucursales Mínimas',
            'branches_count_max': 'Sucursales Máximas',
            
            # Suscripciones
            'billing_cycle': 'Ciclo de Facturación',
            'start_date': 'Fecha de Inicio',
            'start_date_start': 'Fecha Inicio Desde',
            'start_date_end': 'Fecha Inicio Hasta',
            'end_date': 'Fecha de Fin',
            'end_date_start': 'Fecha Fin Desde',
            'end_date_end': 'Fecha Fin Hasta',
            'trial_end_date': 'Fin de Prueba',
            'trial_end_date_start': 'Fin Prueba Desde',
            'trial_end_date_end': 'Fin Prueba Hasta',
            'next_billing_date': 'Próxima Facturación',
            'next_billing_date_start': 'Próxima Facturación Desde',
            'next_billing_date_end': 'Próxima Facturación Hasta',
            
            # Usuarios
            'is_active': 'Activo',
            'is_staff': 'Es Staff',
            'email_verified': 'Email Verificado',
            'role': 'Rol',
            'has_active_loans': 'Tiene Créditos Activos',
            
            # Tasas
            'approval_rate': 'Tasa de Aprobación (%)',
            'approval_rate_min': 'Tasa de Aprobación Mínima (%)',
            'approval_rate_max': 'Tasa de Aprobación Máxima (%)',
            
            # Agregaciones
            'total_applications': 'Total Solicitudes',
            'approved_count': 'Aprobados',
            'rejected_count': 'Rechazados',
            'pending_count': 'Pendientes',
            'total_requested_amount': 'Total Solicitado',
            'total_approved_amount': 'Total Aprobado',
            'avg_requested_amount': 'Promedio Solicitado',
            'avg_approved_amount': 'Promedio Aprobado',
            
            # Temporales
            'month': 'Mes',
            'quarter': 'Trimestre',
            'year': 'Año',
            'day': 'Día',
            'week': 'Semana',
        }
        
        return labels.get(field, field.replace('_', ' ').title())
    
    def _generate_default_config(self, definition: Dict, chart_config: Dict) -> Dict[str, Any]:
        """
        Genera configuración por defecto sugerida para un reporte.
        
        Args:
            definition: Definición del reporte
            chart_config: Configuración de gráficos
        
        Returns:
            Configuración por defecto
        """
        # Seleccionar primeras 5-7 columnas relevantes
        default_columns = definition['available_columns'][:7]
        
        # Seleccionar agrupación por defecto si hay
        default_group_by = []
        if definition.get('available_groupings'):
            # Preferir agrupaciones temporales o por estado
            preferred_groupings = ['month', 'status', 'product_name', 'branch_name']
            for pref in preferred_groupings:
                if pref in definition['available_groupings']:
                    default_group_by = [pref]
                    break
            
            if not default_group_by:
                default_group_by = [definition['available_groupings'][0]]
        
        # Ordenamiento por defecto
        default_sort = []
        if definition.get('available_sort_fields'):
            # Preferir ordenar por fecha o por total
            preferred_sorts = ['created_at', 'total_applications', 'total_approved_amount']
            for pref in preferred_sorts:
                if pref in definition['available_sort_fields']:
                    default_sort = [{'field': pref, 'direction': 'desc'}]
                    break
        
        return {
            'columns': default_columns,
            'group_by': default_group_by,
            'sort': default_sort,
            'filters': [],
            'chart_type': chart_config.get('default_chart', 'table'),
            'format': 'xlsx'
        }
    
    def _build_chart_config(self, report_type: str, chart_type: str, config: Dict) -> Dict[str, Any]:
        """
        Construye configuración específica del gráfico.
        
        Args:
            report_type: Tipo de reporte
            chart_type: Tipo de gráfico
            config: Configuración del reporte
        
        Returns:
            Configuración del gráfico
        """
        # Detectar si hay agrupación temporal
        group_by = config.get('group_by', [])
        temporal_groupings = ['month', 'quarter', 'year', 'week', 'day']
        has_temporal_grouping = any(g in temporal_groupings for g in group_by)
        
        # Si hay agrupación temporal y el tipo de gráfico no es compatible, usar uno compatible
        temporal_incompatible_charts = ['donut', 'pie', 'gauge', 'funnel']
        if has_temporal_grouping and chart_type in temporal_incompatible_charts:
            # Cambiar a gráfico de barras por defecto para series temporales
            logger.warning(
                f"Tipo de gráfico '{chart_type}' no es compatible con agrupación temporal. "
                f"Cambiando a 'bar'"
            )
            chart_type = 'bar'
        
        # Obtener configuración base del gráfico
        base_config = self.CHART_CONFIGS.get(report_type, {}).get('chart_config', {}).get(chart_type, {})
        
        # Si no hay configuración base, crear una por defecto
        if not base_config:
            base_config = self._create_default_chart_config(chart_type, config, group_by)
        
        return {
            'type': chart_type,
            **base_config
        }
    
    def _create_default_chart_config(self, chart_type: str, config: Dict, group_by: List[str]) -> Dict[str, Any]:
        """
        Crea configuración por defecto para un gráfico cuando no existe en el catálogo.
        
        Args:
            chart_type: Tipo de gráfico
            config: Configuración del reporte
            group_by: Campos de agrupación
        
        Returns:
            Configuración del gráfico
        """
        # Determinar el eje X (campo de agrupación)
        x_axis = group_by[0] if group_by else 'name'
        
        # Determinar el eje Y (primera columna numérica o agregación)
        columns = config.get('columns', [])
        y_axis = 'total_applications'  # Por defecto
        
        # Buscar columnas agregadas
        for col in columns:
            if any(keyword in col for keyword in ['total_', 'avg_', 'count', 'sum_']):
                y_axis = col
                break
        
        if chart_type in ['bar', 'horizontal_bar']:
            return {
                'x_axis': x_axis,
                'y_axes': [
                    {'key': y_axis, 'color': '#3b82f6', 'label': self._generate_label(y_axis)}
                ]
            }
        elif chart_type == 'line':
            return {
                'x_axis': x_axis,
                'y_axes': [
                    {'key': y_axis, 'color': '#10b981', 'label': self._generate_label(y_axis)}
                ]
            }
        elif chart_type in ['donut', 'pie']:
            return {
                'data_key': y_axis,
                'name_key': x_axis,
                'colors': ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899']
            }
        else:
            # Configuración genérica
            return {
                'x_axis': x_axis,
                'y_axis': y_axis
            }
    
    def _calculate_summary(self, data: List[Dict], config: Dict) -> Dict[str, Any]:
        """
        Calcula resumen estadístico de los datos.
        
        Args:
            data: Datos del reporte
            config: Configuración del reporte
        
        Returns:
            Resumen estadístico
        """
        if not data:
            return {
                'total_records': 0
            }
        
        summary = {
            'total_records': len(data)
        }
        
        # Calcular sumas y promedios para campos numéricos
        numeric_fields = [
            'total_applications', 'approved_count', 'rejected_count',
            'total_requested_amount', 'total_approved_amount',
            'avg_requested_amount', 'avg_approved_amount',
            'approval_rate'
        ]
        
        for field in numeric_fields:
            if field in data[0]:
                values = [row.get(field, 0) for row in data if row.get(field) is not None]
                if values:
                    if 'total_' in field or '_count' in field:
                        summary[field] = sum(values)
                    elif 'avg_' in field or '_rate' in field:
                        summary[field] = sum(values) / len(values)
        
        return summary
