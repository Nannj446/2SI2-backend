"""
Constructor de configuración de visualizaciones para reportes.

Determina qué tipo de gráfico es más apropiado según:
- Tipo de reporte
- Métricas solicitadas
- Dimensiones de agrupación
- Solicitud explícita del usuario
"""
import logging
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)


class VisualizationConfigBuilder:
    """
    Constructor de configuración de visualizaciones.
    
    Analiza el tipo de reporte y sus características para
    recomendar el gráfico más apropiado.
    """
    
    # Mapeo de tipos de reporte a configuraciones de gráfico recomendadas
    REPORT_CHART_RECOMMENDATIONS = {
        # === CRÉDITOS ===
        'loans_by_status': {
            'chart_type': 'DONUT',
            'title': 'Distribución de Créditos por Estado',
            'label_field': 'status',
            'value_field': 'total_applications',
            'reason': 'Distribución categórica de estados'
        },
        'loans_by_branch': {
            'chart_type': 'HORIZONTAL_BAR',
            'title': 'Créditos por Sucursal',
            'x_field': 'branch_name',
            'y_field': 'total_applications',
            'x_axis': 'Sucursal',
            'y_axis': 'Cantidad de Créditos',
            'reason': 'Comparación entre sucursales'
        },
        'loans_by_product': {
            'chart_type': 'BAR',
            'title': 'Créditos por Producto',
            'x_field': 'product_name',
            'y_field': 'total_applications',
            'x_axis': 'Producto',
            'y_axis': 'Cantidad de Créditos',
            'reason': 'Comparación entre productos'
        },
        'loans_by_date_range': {
            'chart_type': 'LINE',
            'title': 'Evolución de Créditos',
            'x_field': 'month',
            'y_field': 'total_applications',
            'x_axis': 'Período',
            'y_axis': 'Cantidad de Créditos',
            'reason': 'Evolución temporal'
        },
        'active_loans': {
            'chart_type': 'NONE',
            'reason': 'Listado detallado sin agrupación'
        },
        
        # === CLIENTES ===
        'customers_registered': {
            'chart_type': 'LINE',
            'title': 'Clientes Registrados por Período',
            'x_field': 'month',
            'y_field': 'total_clients',
            'x_axis': 'Período',
            'y_axis': 'Cantidad de Clientes',
            'reason': 'Evolución temporal de registros'
        },
        'customers_by_status': {
            'chart_type': 'DONUT',
            'title': 'Distribución de Clientes por Estado',
            'label_field': 'kyc_status',
            'value_field': 'total_clients',
            'reason': 'Distribución de estados KYC'
        },
        'customers_with_active_loans': {
            'chart_type': 'BAR',
            'title': 'Clientes con Créditos Activos',
            'x_field': 'client_name',
            'y_field': 'total_active_loans',
            'x_axis': 'Cliente',
            'y_axis': 'Créditos Activos',
            'reason': 'Comparación cuantitativa'
        },
        
        # === DOCUMENTOS ===
        'applications_with_pending_documents': {
            'chart_type': 'STACKED_BAR',
            'title': 'Documentos por Estado',
            'x_field': 'product_name',
            'series_fields': ['pending_documents_count', 'uploaded_documents_count'],
            'series_labels': ['Pendientes', 'Subidos'],
            'x_axis': 'Producto',
            'y_axis': 'Cantidad de Documentos',
            'reason': 'Estado de documentos por producto'
        },
        
        # === VERIFICACIÓN ===
        'verifications_by_status': {
            'chart_type': 'DONUT',
            'title': 'Verificaciones por Estado',
            'label_field': 'decision',
            'value_field': 'total_verifications',
            'reason': 'Distribución de resultados de verificación'
        },
        
        # === SAAS ===
        'tenants_by_status': {
            'chart_type': 'BAR',
            'title': 'Tenants por Estado',
            'x_field': 'institution_type',
            'y_field': 'total_tenants',
            'x_axis': 'Tipo de Institución',
            'y_axis': 'Cantidad de Tenants',
            'reason': 'Comparación entre tipos de institución'
        },
        'users_by_tenant': {
            'chart_type': 'HORIZONTAL_BAR',
            'title': 'Usuarios por Tenant',
            'x_field': 'tenant_name',
            'y_field': 'user_count',
            'x_axis': 'Tenant',
            'y_axis': 'Cantidad de Usuarios',
            'reason': 'Comparación de usuarios entre tenants'
        },
        'subscriptions_by_status': {
            'chart_type': 'DONUT',
            'title': 'Suscripciones por Estado',
            'label_field': 'subscription_status',
            'value_field': 'total_subscriptions',
            'reason': 'Distribución de estados de suscripción'
        },
    }
    
    def build_visualization_config(
        self,
        report_type: str,
        config: Dict[str, Any],
        user_request: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Construye configuración de visualización para un reporte.
        
        Args:
            report_type: Tipo de reporte
            config: Configuración del reporte
            user_request: Solicitud explícita del usuario (de Groq)
        
        Returns:
            Configuración de visualización o None si no aplica
        """
        # Si el usuario solicitó explícitamente no tener gráfico
        if user_request and user_request.get('chart_type') == 'NONE':
            return None
        
        # Si el usuario solicitó un tipo específico de gráfico
        if user_request and user_request.get('chart_type'):
            return self._build_from_user_request(user_request, config)
        
        # Obtener recomendación por defecto
        recommendation = self.REPORT_CHART_RECOMMENDATIONS.get(report_type)
        
        if not recommendation:
            logger.info(f"No hay recomendación de gráfico para {report_type}")
            return None
        
        # Si la recomendación es NONE, no generar gráfico
        if recommendation.get('chart_type') == 'NONE':
            return None
        
        # Validar que el reporte tenga agrupación (necesaria para gráficos)
        if not config.get('group_by') and recommendation['chart_type'] != 'LINE':
            logger.info(f"Reporte {report_type} no tiene agrupación, omitiendo gráfico")
            return None
        
        # Construir configuración completa
        viz_config = {
            'requested': False,
            'recommended': True,
            'chart_type': recommendation['chart_type'],
            'title': recommendation.get('title', 'Gráfico'),
            'reason': recommendation.get('reason', 'Visualización recomendada')
        }
        
        # Agregar campos específicos según tipo de gráfico
        chart_type = recommendation['chart_type']
        
        if chart_type in ['BAR', 'HORIZONTAL_BAR', 'LINE']:
            viz_config.update({
                'x_field': recommendation.get('x_field'),
                'y_field': recommendation.get('y_field'),
                'x_axis': recommendation.get('x_axis', 'Categoría'),
                'y_axis': recommendation.get('y_axis', 'Valor')
            })
        
        elif chart_type in ['PIE', 'DONUT']:
            viz_config.update({
                'label_field': recommendation.get('label_field'),
                'value_field': recommendation.get('value_field')
            })
        
        elif chart_type == 'STACKED_BAR':
            viz_config.update({
                'x_field': recommendation.get('x_field'),
                'series_fields': recommendation.get('series_fields', []),
                'series_labels': recommendation.get('series_labels', []),
                'x_axis': recommendation.get('x_axis', 'Categoría'),
                'y_axis': recommendation.get('y_axis', 'Valor')
            })
        
        return viz_config
    
    def _build_from_user_request(
        self,
        user_request: Dict[str, Any],
        config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Construye configuración desde solicitud explícita del usuario.
        
        Args:
            user_request: Solicitud del usuario (de Groq)
            config: Configuración del reporte
        
        Returns:
            Configuración de visualización
        """
        chart_type = user_request.get('chart_type', 'BAR')
        
        viz_config = {
            'requested': True,
            'recommended': True,
            'chart_type': chart_type,
            'title': user_request.get('title', 'Gráfico'),
            'reason': 'Solicitado explícitamente por el usuario'
        }
        
        # Intentar inferir campos desde la configuración del reporte
        group_by = config.get('group_by', [])
        columns = config.get('columns', [])
        
        # Identificar campo de agrupación (eje X)
        x_field = group_by[0] if group_by else None
        
        # Identificar campo de valor (eje Y) - buscar métricas agregadas
        y_field = None
        for col in columns:
            if any(keyword in col for keyword in ['total_', 'avg_', 'count', 'rate']):
                y_field = col
                break
        
        # Agregar campos según tipo de gráfico
        if chart_type in ['BAR', 'HORIZONTAL_BAR', 'LINE']:
            viz_config.update({
                'x_field': user_request.get('x_field', x_field),
                'y_field': user_request.get('y_field', y_field),
                'x_axis': user_request.get('x_axis', 'Categoría'),
                'y_axis': user_request.get('y_axis', 'Valor')
            })
        
        elif chart_type in ['PIE', 'DONUT']:
            viz_config.update({
                'label_field': user_request.get('label_field', x_field),
                'value_field': user_request.get('value_field', y_field)
            })
        
        return viz_config
    
    def should_generate_chart(
        self,
        report_type: str,
        config: Dict[str, Any],
        data: List[Dict[str, Any]]
    ) -> bool:
        """
        Determina si se debe generar un gráfico.
        
        Args:
            report_type: Tipo de reporte
            config: Configuración del reporte
            data: Datos del reporte
        
        Returns:
            True si se debe generar gráfico
        """
        # No generar si no hay datos
        if not data:
            return False
        
        # No generar si hay muy pocos datos (menos de 2 puntos)
        if len(data) < 2:
            return False
        
        # No generar si hay demasiados datos sin agrupación
        if len(data) > 100 and not config.get('group_by'):
            return False
        
        # Verificar si el tipo de reporte tiene recomendación
        recommendation = self.REPORT_CHART_RECOMMENDATIONS.get(report_type)
        if not recommendation:
            return False
        
        if recommendation.get('chart_type') == 'NONE':
            return False
        
        return True
