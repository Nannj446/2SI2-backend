"""
Servicio de validación de schemas de reportes.

Este servicio valida configuraciones de reportes (ReportConfig)
y intenciones de voz (VoiceIntent) contra el catálogo de reportes.
"""
import logging
from typing import Dict, List, Any, Tuple, Optional
from datetime import datetime, timedelta
from decimal import Decimal

from .report_catalog import ReportCatalogService

logger = logging.getLogger(__name__)


class ReportSchemaService:
    """
    Servicio de validación de schemas de reportes.
    
    Valida configuraciones de reportes y proporciona métodos
    para convertir presets de fechas a rangos concretos.
    """
    
    # Campos requeridos en ReportConfig
    REQUIRED_FIELDS = ['scope', 'category', 'report_type', 'columns', 'format']
    
    # Scopes válidos
    VALID_SCOPES = ['TENANT', 'SAAS']
    
    # Formatos válidos
    VALID_FORMATS = ['csv', 'xlsx', 'pdf']
    
    # Direcciones de ordenamiento válidas
    VALID_SORT_DIRECTIONS = ['asc', 'desc']
    
    # Presets de fecha disponibles
    DATE_PRESETS = [
        'today', 'yesterday', 'last_7_days', 'last_30_days',
        'current_week', 'last_week', 'current_month', 'last_month',
        'current_quarter', 'last_quarter', 'current_year', 'last_year',
        'custom'
    ]
    
    def __init__(self):
        self.catalog = ReportCatalogService()
    
    def validate_report_config(self, config: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """
        Valida una configuración de reporte completa.
        
        Args:
            config: Configuración del reporte
            
        Returns:
            (is_valid, errors)
        """
        errors = []
        
        # Validar campos requeridos
        for field in self.REQUIRED_FIELDS:
            if field not in config or config[field] is None:
                errors.append(f"Campo requerido faltante: {field}")
        
        if errors:
            return False, errors
        
        # Validar scope
        if config['scope'] not in self.VALID_SCOPES:
            errors.append(f"Scope inválido: {config['scope']}. Debe ser TENANT o SAAS")
        
        # Validar categoría y report_type contra catálogo
        report_def = self.catalog.get_report_definition(
            config['scope'],
            config['category'],
            config['report_type']
        )
        
        if not report_def:
            errors.append(
                f"Tipo de reporte no encontrado: {config['scope']}/{config['category']}/{config['report_type']}"
            )
            return False, errors
        
        # Validar columnas (filtrar inválidas en lugar de rechazar)
        invalid_columns = [
            col for col in config['columns']
            if col not in report_def['available_columns']
        ]
        if invalid_columns:
            # Filtrar columnas inválidas automáticamente
            config['columns'] = [
                col for col in config['columns']
                if col in report_def['available_columns']
            ]
            # Solo advertir, no bloquear
            logger.warning(f"Columnas inválidas filtradas: {invalid_columns}")
            
            # Si no quedan columnas válidas, usar las columnas por defecto
            if not config['columns']:
                config['columns'] = report_def['available_columns'][:10]  # Primeras 10 columnas
                logger.info(f"Usando columnas por defecto: {config['columns']}")
        
        # Validar filtros
        valid_filters = []
        for filter_item in config.get('filters', []):
            # Verificar si el filtro es solo para SAAS
            field = filter_item.get('field')
            if field and field in report_def['available_filters']:
                field_def = report_def['available_filters'][field]
                if field_def.get('saas_only') and config['scope'] == 'TENANT':
                    # Filtrar automáticamente filtros saas_only en reportes TENANT
                    logger.warning(f"Filtro '{field}' es solo para SAAS, ignorando en reporte TENANT")
                    continue
            
            filter_errors = self._validate_filter(filter_item, report_def)
            if filter_errors:
                errors.extend(filter_errors)
            else:
                valid_filters.append(filter_item)
        
        # Actualizar filtros con solo los válidos
        config['filters'] = valid_filters
        
        # Validar agrupaciones
        for group_field in config.get('group_by', []):
            if group_field not in report_def['available_groupings']:
                errors.append(f"Agrupación inválida: {group_field}")
        
        # Validar ordenamiento (filtrar inválidos en lugar de rechazar)
        valid_sort = []
        for sort_item in config.get('sort', []):
            if sort_item['field'] not in report_def['available_sort_fields']:
                logger.warning(f"Campo de ordenamiento inválido filtrado: {sort_item['field']}")
                continue
            if sort_item['direction'] not in self.VALID_SORT_DIRECTIONS:
                logger.warning(f"Dirección de ordenamiento inválida: {sort_item['direction']}, usando 'asc'")
                sort_item['direction'] = 'asc'
            valid_sort.append(sort_item)
        
        config['sort'] = valid_sort
        
        # Si no hay ordenamiento válido, usar uno por defecto
        if not config['sort'] and report_def['available_sort_fields']:
            default_sort_field = report_def['available_sort_fields'][0]
            config['sort'] = [{'field': default_sort_field, 'direction': 'asc'}]
            logger.info(f"Usando ordenamiento por defecto: {config['sort']}")
        
        # Validar formato
        if config['format'] not in self.VALID_FORMATS:
            errors.append(f"Formato inválido: {config['format']}")
        
        if config['format'] not in report_def.get('formats', []):
            errors.append(
                f"Formato {config['format']} no soportado para este tipo de reporte"
            )
        
        # Validar date_range si existe
        if 'date_range' in config and config['date_range']:
            date_errors = self._validate_date_range(config['date_range'])
            errors.extend(date_errors)
        
        return len(errors) == 0, errors
    
    def _validate_filter(
        self,
        filter_item: Dict[str, Any],
        report_def: Dict[str, Any]
    ) -> List[str]:
        """
        Valida un filtro individual.
        
        Args:
            filter_item: Filtro a validar
            report_def: Definición del reporte
            
        Returns:
            Lista de errores
        """
        errors = []
        
        field = filter_item.get('field')
        operator = filter_item.get('operator')
        value = filter_item.get('value')
        
        if not field:
            errors.append("Filtro sin campo especificado")
            return errors
        
        if field not in report_def['available_filters']:
            errors.append(f"Campo de filtro inválido: {field}")
            return errors
        
        field_def = report_def['available_filters'][field]
        
        # Validar operador
        if operator not in field_def['operators']:
            errors.append(
                f"Operador '{operator}' no permitido para campo '{field}'. "
                f"Operadores válidos: {field_def['operators']}"
            )
        
        # Validar tipo de valor
        field_type = field_def.get('type')
        if field_type == 'choice' and 'values' in field_def:
            # Validar que el valor esté en las opciones permitidas
            if operator in ['in', 'not_in']:
                if not isinstance(value, list):
                    errors.append(f"Valor para operador '{operator}' debe ser una lista")
                else:
                    invalid_values = [v for v in value if v not in field_def['values']]
                    if invalid_values:
                        errors.append(
                            f"Valores inválidos para campo '{field}': {invalid_values}. "
                            f"Valores válidos: {field_def['values']}"
                        )
            elif operator == 'equals':
                if value not in field_def['values']:
                    errors.append(
                        f"Valor inválido para campo '{field}': {value}. "
                        f"Valores válidos: {field_def['values']}"
                    )
        
        return errors
    
    def _validate_date_range(self, date_range: Dict[str, Any]) -> List[str]:
        """
        Valida el rango de fechas.
        
        Args:
            date_range: Rango de fechas a validar
            
        Returns:
            Lista de errores
        """
        errors = []
        preset = date_range.get('preset')
        
        if preset and preset not in self.DATE_PRESETS:
            errors.append(f"Preset de fecha inválido: {preset}")
        
        if preset == 'custom':
            if not date_range.get('start_date') or not date_range.get('end_date'):
                errors.append("Rango personalizado requiere start_date y end_date")
            else:
                try:
                    start = datetime.fromisoformat(date_range['start_date'])
                    end = datetime.fromisoformat(date_range['end_date'])
                    if start > end:
                        errors.append("start_date debe ser <= end_date")
                except (ValueError, TypeError):
                    errors.append("Formato de fecha inválido (usar YYYY-MM-DD)")
        elif preset and preset != 'custom':
            # Si no es custom, ignorar start_date y end_date si están presentes
            # El backend calculará las fechas basándose en el preset
            pass
        
        return errors
    
    def resolve_date_preset(self, preset: str) -> Tuple[str, str]:
        """
        Convierte un preset de fecha a rango concreto.
        
        Args:
            preset: Preset de fecha
            
        Returns:
            (start_date, end_date) en formato YYYY-MM-DD
        """
        today = datetime.now().date()
        
        if preset == 'today':
            return str(today), str(today)
        
        elif preset == 'yesterday':
            yesterday = today - timedelta(days=1)
            return str(yesterday), str(yesterday)
        
        elif preset == 'last_7_days':
            start = today - timedelta(days=7)
            return str(start), str(today)
        
        elif preset == 'last_30_days':
            start = today - timedelta(days=30)
            return str(start), str(today)
        
        elif preset == 'current_week':
            # Lunes de esta semana
            start = today - timedelta(days=today.weekday())
            return str(start), str(today)
        
        elif preset == 'last_week':
            # Lunes de la semana pasada
            start = today - timedelta(days=today.weekday() + 7)
            end = start + timedelta(days=6)
            return str(start), str(end)
        
        elif preset == 'current_month':
            start = today.replace(day=1)
            return str(start), str(today)
        
        elif preset == 'last_month':
            # Primer día del mes pasado
            first_current = today.replace(day=1)
            last_month_end = first_current - timedelta(days=1)
            last_month_start = last_month_end.replace(day=1)
            return str(last_month_start), str(last_month_end)
        
        elif preset == 'current_quarter':
            # Primer día del trimestre actual
            quarter = (today.month - 1) // 3
            start = today.replace(month=quarter * 3 + 1, day=1)
            return str(start), str(today)
        
        elif preset == 'last_quarter':
            # Trimestre pasado
            current_quarter = (today.month - 1) // 3
            if current_quarter == 0:
                # Si estamos en Q1, el trimestre pasado es Q4 del año anterior
                start = today.replace(year=today.year - 1, month=10, day=1)
                end = today.replace(year=today.year - 1, month=12, day=31)
            else:
                start_month = (current_quarter - 1) * 3 + 1
                start = today.replace(month=start_month, day=1)
                end_month = start_month + 2
                # Último día del mes
                if end_month == 12:
                    end = today.replace(month=12, day=31)
                else:
                    end = today.replace(month=end_month + 1, day=1) - timedelta(days=1)
            return str(start), str(end)
        
        elif preset == 'current_year':
            start = today.replace(month=1, day=1)
            return str(start), str(today)
        
        elif preset == 'last_year':
            start = today.replace(year=today.year - 1, month=1, day=1)
            end = today.replace(year=today.year - 1, month=12, day=31)
            return str(start), str(end)
        
        else:
            # Default: hoy
            return str(today), str(today)
    
    def validate_voice_intent(self, intent: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """
        Valida una intención de voz.
        
        Args:
            intent: Intención parseada por IA
            
        Returns:
            (is_valid, errors)
        """
        errors = []
        
        # Validar confidence
        confidence = intent.get('confidence')
        if confidence is None:
            errors.append("Campo 'confidence' requerido")
        elif not isinstance(confidence, (int, float)) or not (0 <= confidence <= 1):
            errors.append("Campo 'confidence' debe ser un número entre 0 y 1")
        
        # Validar missing_fields
        if 'missing_fields' not in intent:
            errors.append("Campo 'missing_fields' requerido")
        elif not isinstance(intent['missing_fields'], list):
            errors.append("Campo 'missing_fields' debe ser una lista")
        
        # Validar unsupported_terms
        if 'unsupported_terms' not in intent:
            errors.append("Campo 'unsupported_terms' requerido")
        elif not isinstance(intent['unsupported_terms'], list):
            errors.append("Campo 'unsupported_terms' debe ser una lista")
        
        # Si no hay campos faltantes, validar como ReportConfig
        if not intent.get('missing_fields'):
            config_valid, config_errors = self.validate_report_config(intent)
            if not config_valid:
                errors.extend(config_errors)
        
        return len(errors) == 0, errors
    
    def convert_voice_intent_to_config(
        self,
        intent: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Convierte una intención de voz a configuración de reporte.
        
        Args:
            intent: Intención parseada por IA
            
        Returns:
            Configuración de reporte
        """
        config = {
            'scope': intent.get('scope'),
            'category': intent.get('category'),
            'report_type': intent.get('report_type'),
            'date_range': intent.get('date_range'),
            'filters': intent.get('filters', []),
            'columns': intent.get('columns', []),
            'group_by': intent.get('group_by', []),
            'sort': intent.get('sort', []),
            'format': intent.get('format', 'xlsx')
        }
        
        # Resolver preset de fecha si existe
        if config.get('date_range') and config['date_range'].get('preset'):
            preset = config['date_range']['preset']
            if preset != 'custom':
                start, end = self.resolve_date_preset(preset)
                config['date_range']['start_date'] = start
                config['date_range']['end_date'] = end
        
        return config
    
    def get_validation_status(
        self,
        intent: Dict[str, Any]
    ) -> str:
        """
        Determina el estado de validación de una intención.
        
        Args:
            intent: Intención parseada por IA
            
        Returns:
            'VALID', 'NEEDS_REVIEW', o 'INVALID'
        """
        confidence = intent.get('confidence', 0)
        missing_fields = intent.get('missing_fields', [])
        unsupported_terms = intent.get('unsupported_terms', [])
        
        # Si hay términos no soportados, es inválido
        if unsupported_terms:
            return 'INVALID'
        
        # Si hay campos faltantes, necesita revisión
        if missing_fields:
            return 'NEEDS_REVIEW'
        
        # Si la confianza es baja, necesita revisión
        if confidence < 0.7:
            return 'NEEDS_REVIEW'
        
        # Validar la configuración
        is_valid, _ = self.validate_report_config(intent)
        
        if is_valid:
            return 'VALID'
        else:
            return 'NEEDS_REVIEW'
