"""
Constructor de queries seguro para reportes.

Este servicio construye QuerySets de Django usando ORM,
validando todos los campos, filtros y agrupaciones contra
el catálogo de reportes.
"""
import logging
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta, date
from decimal import Decimal

from django.db.models import (
    Q, QuerySet, Count, Sum, Avg, Max, Min, F, Case, When,
    ExpressionWrapper, FloatField, IntegerField, DecimalField, BooleanField,
    DurationField
)
from django.db.models.functions import (
    TruncDay, TruncWeek, TruncMonth, TruncQuarter, TruncYear, Extract
)
from django.utils import timezone
from django.apps import apps

from .report_catalog import ReportCatalogService

logger = logging.getLogger(__name__)


class ReportQueryBuilder:
    """
    Constructor de queries seguro para reportes.
    
    Construye QuerySets validados usando ORM de Django,
    sin ejecutar SQL directo ni confiar en entrada del usuario.
    
    SEGURIDAD:
    - Todos los campos se validan contra listas blancas del catálogo
    - Solo se usa ORM de Django, nunca SQL directo
    - Filtrado automático por tenant para reportes TENANT
    - Validación de tipos de datos
    """
    
    # Mapeo de datasources a modelos Django
    MODEL_MAP = {
        'LoanApplication': 'loans.LoanApplication',
        'Client': 'clients.Client',
        'CreditProduct': 'products.CreditProduct',
        'LoanApplicationDocumentRequirement': 'loans.LoanApplicationDocumentRequirement',
        'IdentityVerification': 'identity_verification.IdentityVerification',
        'FinancialInstitution': 'tenants.FinancialInstitution',
        'User': 'auth.User',
        'SubscriptionPlan': 'saas.SubscriptionPlan',
        'Subscription': 'saas.Subscription',
        # Nuevos datasources para reportes adicionales
        'Branch': 'branches.Branch',
        'AuditLog': 'audit.AuditLog',
        'SecurityEvent': 'audit.SecurityEvent',
        'FileResource': 'storage.FileResource',
        'TenantRuleSet': 'loans.TenantRuleSet',
        'CreditProductParameter': 'loans.CreditProductParameter',
    }
    
    # Mapeo de columnas a relaciones ForeignKey para optimización
    SELECT_RELATED_MAP = {
        'client_name': 'client__user',
        'client_document': 'client',
        'product_name': 'product',
        'product_code': 'product',
        'product_type': 'product',
        'branch_name': 'branch',
        'branch_city': 'branch',
        'assigned_to_name': 'assigned_to',
        'plan_name': 'subscription__plan',
        'tenant_name': 'institution',
        'tenant_slug': 'institution',
        # Productos crediticios
        'rule_set_name': 'rule_set',
        'rule_set_code': 'rule_set',
        # AuditLog
        'user_email': 'user',
        'user_name': 'user',
        'institution_name': 'institution',
        # SecurityEvent
        'resolved_by_name': 'resolved_by',
        # FileResource
        'uploaded_by_name': 'uploaded_by',
    }
    
    def __init__(self, tenant=None):
        """
        Inicializa el query builder.
        
        Args:
            tenant: Instancia de FinancialInstitution o None para reportes SAAS
        """
        self.tenant = tenant
        self.catalog = ReportCatalogService()
        # Importar aquí para evitar importaciones circulares
        from .product_report_builder import ProductReportBuilder
        self.product_builder = ProductReportBuilder()
    
    def build_query(
        self,
        scope: str,
        category: str,
        report_type: str,
        config: Dict[str, Any]
    ) -> QuerySet:
        """
        Construye un QuerySet seguro para el reporte.
        
        Args:
            scope: TENANT o SAAS
            category: Categoría del reporte
            report_type: Tipo específico de reporte
            config: Configuración del reporte validada
        
        Returns:
            QuerySet configurado
        
        Raises:
            ValueError: Si la configuración es inválida
        """
        # Obtener definición del reporte
        report_def = self.catalog.get_report_definition(scope, category, report_type)
        if not report_def:
            raise ValueError(f"Reporte no encontrado: {scope}.{category}.{report_type}")
        
        # Obtener modelo base
        model = self._get_model(report_def['datasource'])
        
        # Iniciar queryset con filtrado por tenant si aplica
        if scope == 'TENANT':
            if not self.tenant:
                raise ValueError("Tenant requerido para reportes TENANT")
            # Usar manager con filtrado automático por tenant
            queryset = model.objects.all()
        else:
            # Reportes SAAS: usar all_objects sin filtrar por tenant
            queryset = model.all_objects.all() if hasattr(model, 'all_objects') else model.objects.all()
        
        # Aplicar filtros
        if 'filters' in config and config['filters']:
            queryset = self._apply_filters(queryset, config['filters'], report_def)
        
        # Aplicar date_range
        if 'date_range' in config and config['date_range']:
            queryset = self._apply_date_range(queryset, config['date_range'])
        
        # Aplicar anotaciones especiales para productos crediticios
        if report_def['datasource'] == 'CreditProduct':
            queryset = self.product_builder.annotate_product_parameters(queryset)
        
        # Aplicar select_related y prefetch_related para optimización
        queryset = self._optimize_query(queryset, config.get('columns', []), report_def)
        
        return queryset
    
    def build_aggregated_query(
        self,
        queryset: QuerySet,
        config: Dict[str, Any],
        report_def: Dict[str, Any]
    ) -> QuerySet:
        """
        Construye query con agrupaciones y agregaciones.
        
        Args:
            queryset: QuerySet base
            config: Configuración del reporte
            report_def: Definición del reporte del catálogo
        
        Returns:
            QuerySet con agregaciones
        """
        if not config.get('group_by'):
            logger.warning("No se especificaron campos de agrupación (group_by)")
            return queryset
        
        logger.info(f"Construyendo query agregado con group_by: {config['group_by']}")
        
        # Construir annotaciones para campos temporales si se usan
        queryset = self._annotate_temporal_fields(queryset, config['group_by'])
        
        # Construir values() con campos de agrupación
        group_fields = self._build_group_fields(config['group_by'])
        logger.info(f"Campos de agrupación mapeados: {group_fields}")
        
        try:
            queryset = queryset.values(*group_fields)
        except Exception as e:
            logger.error(f"Error al aplicar values() con campos {group_fields}: {e}")
            raise ValueError(f"Error en campos de agrupación: {e}")
        
        # Construir agregaciones
        annotations = self._build_aggregations(config.get('columns', []), report_def)
        logger.info(f"Agregaciones construidas: {list(annotations.keys())}")
        
        if annotations:
            try:
                queryset = queryset.annotate(**annotations)
            except Exception as e:
                logger.error(f"Error al aplicar agregaciones: {e}")
                raise ValueError(f"Error en agregaciones: {e}")
        
        # Aplicar ordenamiento
        if 'sort' in config and config['sort']:
            queryset = self._apply_sorting(queryset, config['sort'])
        
        return queryset
    
    def _get_model(self, datasource: str):
        """
        Obtiene el modelo de Django por nombre.
        
        Args:
            datasource: Nombre del datasource del catálogo
        
        Returns:
            Clase del modelo Django
        
        Raises:
            ValueError: Si el datasource no está soportado
        """
        if datasource not in self.MODEL_MAP:
            raise ValueError(f"Datasource no soportado: {datasource}")
        
        app_label, model_name = self.MODEL_MAP[datasource].split('.')
        return apps.get_model(app_label, model_name)
    
    def _apply_filters(
        self,
        queryset: QuerySet,
        filters: List[Dict],
        report_def: Dict
    ) -> QuerySet:
        """
        Aplica filtros al queryset de forma segura.
        
        Todos los filtros se validan contra el catálogo antes de aplicarse.
        
        Args:
            queryset: QuerySet base
            filters: Lista de filtros a aplicar
            report_def: Definición del reporte
        
        Returns:
            QuerySet filtrado
        """
        q_objects = Q()
        
        for filter_item in filters:
            field = filter_item.get('field')
            operator = filter_item.get('operator')
            value = filter_item.get('value')
            
            # Validar que el filtro existe en el catálogo (lista blanca)
            if field not in report_def['available_filters']:
                continue
            
            # Convertir filtros de rango (_min, _max, _start, _end) al campo base
            actual_field = field
            actual_operator = operator
            
            if field.endswith('_min') or field.endswith('_start'):
                actual_field = field.rsplit('_', 1)[0]
                actual_operator = 'gte'
            elif field.endswith('_max') or field.endswith('_end'):
                actual_field = field.rsplit('_', 1)[0]
                actual_operator = 'lte'
            
            # Construir Q object según operador
            q_obj = self._build_filter_q(actual_field, actual_operator, value)
            if q_obj:
                q_objects &= q_obj
        
        return queryset.filter(q_objects)
    
    def _build_filter_q(self, field: str, operator: str, value: Any) -> Optional[Q]:
        """
        Construye un Q object para un filtro.
        
        Args:
            field: Campo a filtrar
            operator: Operador de comparación
            value: Valor a comparar
        
        Returns:
            Q object o None si el operador no es válido
        """
        from django.utils import timezone
        from datetime import datetime
        
        # Convertir fechas string a timezone-aware si es necesario
        if self._is_date_field(field):
            if isinstance(value, str):
                value = self._parse_date_with_timezone(value)
            elif isinstance(value, list):
                value = [
                    self._parse_date_with_timezone(v) if isinstance(v, str) else v
                    for v in value
                ]
        
        operator_map = {
            'equals': lambda f, v: Q(**{f: v}),
            'not_equals': lambda f, v: ~Q(**{f: v}),
            'in': lambda f, v: Q(**{f'{f}__in': v}),
            'not_in': lambda f, v: ~Q(**{f'{f}__in': v}),
            'gte': lambda f, v: Q(**{f'{f}__gte': v}),
            'lte': lambda f, v: Q(**{f'{f}__lte': v}),
            'gt': lambda f, v: Q(**{f'{f}__gt': v}),
            'lt': lambda f, v: Q(**{f'{f}__lt': v}),
            'between': lambda f, v: Q(**{f'{f}__gte': v[0], f'{f}__lte': v[1]}) if isinstance(v, list) and len(v) == 2 else Q(),
            'contains': lambda f, v: Q(**{f'{f}__icontains': v}),
            'startswith': lambda f, v: Q(**{f'{f}__istartswith': v}),
            'endswith': lambda f, v: Q(**{f'{f}__iendswith': v}),
            'is_null': lambda f, v: Q(**{f'{f}__isnull': True}),
            'is_not_null': lambda f, v: Q(**{f'{f}__isnull': False}),
        }
        
        if operator not in operator_map:
            return None
        
        return operator_map[operator](field, value)
    
    def _is_date_field(self, field: str) -> bool:
        """Verifica si un campo es de tipo fecha."""
        date_fields = [
            'created_at', 'updated_at', 'submitted_at', 'reviewed_at',
            'approved_at', 'rejected_at', 'disbursed_at', 'verified_at',
            'started_at', 'completed_at', 'birth_date', 'employment_start_date'
        ]
        return field in date_fields
    
    def _parse_date_with_timezone(self, date_str: str):
        """
        Convierte string de fecha a datetime con timezone.
        
        Args:
            date_str: Fecha en formato YYYY-MM-DD o ISO
        
        Returns:
            datetime con timezone o el valor original si falla
        """
        from django.utils import timezone
        from datetime import datetime
        
        try:
            # Intentar parsear como fecha simple (YYYY-MM-DD)
            if len(date_str) == 10:  # YYYY-MM-DD
                dt = datetime.strptime(date_str, '%Y-%m-%d')
                # Hacer timezone-aware con la zona horaria actual
                return timezone.make_aware(dt, timezone.get_current_timezone())
            else:
                # Intentar parsear como ISO datetime
                dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                if timezone.is_naive(dt):
                    return timezone.make_aware(dt, timezone.get_current_timezone())
                return dt
        except Exception as e:
            # Si falla, retornar el valor original
            logger.warning(f"No se pudo parsear fecha '{date_str}': {e}")
            return date_str
    
    def _apply_date_range(
        self,
        queryset: QuerySet,
        date_range: Dict
    ) -> QuerySet:
        """
        Aplica rango de fechas al queryset.
        
        Args:
            queryset: QuerySet base
            date_range: Configuración de rango de fechas
        
        Returns:
            QuerySet filtrado por fechas
        """
        start_date = date_range.get('start_date')
        end_date = date_range.get('end_date')
        
        if not start_date or not end_date:
            return queryset
        
        # Convertir strings a date si es necesario
        if isinstance(start_date, str):
            start_date = datetime.fromisoformat(start_date).date()
        if isinstance(end_date, str):
            end_date = datetime.fromisoformat(end_date).date()
        
        # Aplicar filtro de fecha (campo created_at por defecto)
        # TODO: Hacer configurable el campo de fecha según el reporte
        return queryset.filter(
            created_at__date__gte=start_date,
            created_at__date__lte=end_date
        )
    
    def _optimize_query(
        self,
        queryset: QuerySet,
        columns: List[str],
        report_def: Dict
    ) -> QuerySet:
        """
        Optimiza el queryset con select_related y prefetch_related.
        
        Reduce el número de queries SQL usando JOINs para ForeignKeys.
        
        Args:
            queryset: QuerySet base
            columns: Columnas solicitadas
            report_def: Definición del reporte
        
        Returns:
            QuerySet optimizado
        """
        # Mapeo de columnas a relaciones ForeignKey según el datasource
        datasource = report_def.get('datasource')
        
        if datasource == 'LoanApplication':
            select_related_map = {
                # Producto
                'product_name': 'product',
                'product_code': 'product',
                'product_type': 'product',
                # Sucursal
                'branch_name': 'branch',
                'branch_city': 'branch',
                # Cliente
                'client_name': 'client__user',
                'client_document': 'client',
                'client_email': 'client__user',
                'client_phone': 'client',
                # Usuario asignado
                'assigned_to_name': 'assigned_to',
                # Reglas
                'rule_set_snapshot': 'rule_set_snapshot',
                # Usuario que creó/aprobó/rechazó
                'created_by': 'created_by',
                'approved_by': 'approved_by',
                'reviewed_by': 'reviewed_by',
            }
            base_relations = ['product', 'client', 'branch']
        elif datasource == 'CreditProduct':
            select_related_map = {
                # Tipo de producto
                'product_type': 'product_type',
                # Conjunto de reglas
                'rule_set_name': 'rule_set',
                'rule_set_code': 'rule_set',
            }
            base_relations = ['rule_set', 'product_type']
        elif datasource == 'Branch':
            select_related_map = {}
            base_relations = []
            # Branch no tiene ForeignKeys críticos, pero tiene ManyToMany
            # Usar prefetch_related para assigned_users y assigned_loan_applications si es necesario
        elif datasource == 'AuditLog':
            select_related_map = {
                'user_email': 'user',
                'user_name': 'user',
                'institution_name': 'institution',
            }
            base_relations = ['user', 'institution']
        elif datasource == 'SecurityEvent':
            select_related_map = {
                'user_email': 'user',
                'resolved_by_name': 'resolved_by',
            }
            base_relations = ['user', 'resolved_by']
        elif datasource == 'FileResource':
            select_related_map = {
                'institution_name': 'tenant',
                'uploaded_by_name': 'uploaded_by',
            }
            base_relations = ['tenant', 'uploaded_by']
        elif datasource == 'TenantRuleSet':
            select_related_map = {}
            base_relations = []
            # TenantRuleSet tiene reverse relations, usar prefetch si es necesario
        elif datasource == 'CreditProductParameter':
            select_related_map = {
                'rule_set_name': 'rule_set',
            }
            base_relations = ['rule_set']
        elif datasource == 'SubscriptionPlan':
            select_related_map = {}
            base_relations = []
        elif datasource == 'Client':
            select_related_map = {
                # Usuario asociado
                'full_name': 'user',
                'first_name': 'user',
                'last_name': 'user',
                'email': 'user',
                # Usuario que verificó
                'verified_by_name': 'verified_by',
            }
            base_relations = ['user', 'verified_by']
        else:
            select_related_map = {
                # Tenant (para reportes SAAS)
                'tenant_name': 'institution',
                'tenant_slug': 'institution',
                # Plan (para reportes SAAS)
                'plan_name': 'subscription__plan',
            }
            base_relations = []
        
        select_related_fields = set(base_relations)
        
        for column in columns:
            if column in select_related_map:
                select_related_fields.add(select_related_map[column])
        
        if select_related_fields:
            queryset = queryset.select_related(*select_related_fields)
        
        return queryset
    
    def _annotate_temporal_fields(
        self,
        queryset: QuerySet,
        group_by: List[str]
    ) -> QuerySet:
        """
        Anota campos temporales (month, quarter, year, etc.) si se usan en agrupación.
        
        Args:
            queryset: QuerySet base
            group_by: Lista de campos de agrupación
        
        Returns:
            QuerySet con anotaciones temporales
        """
        temporal_fields = {
            'day': TruncDay('created_at'),
            'week': TruncWeek('created_at'),
            'month': TruncMonth('created_at'),
            'quarter': TruncQuarter('created_at'),
            'year': TruncYear('created_at'),
        }
        
        annotations = {}
        for field in group_by:
            if field in temporal_fields:
                annotations[field] = temporal_fields[field]
        
        if annotations:
            queryset = queryset.annotate(**annotations)
        
        return queryset
    
    def _build_group_fields(self, group_by: List[str]) -> List[str]:
        """
        Construye lista de campos para values() en agrupación.
        
        Mapea columnas virtuales a campos reales de la base de datos.
        
        Args:
            group_by: Lista de campos de agrupación
        
        Returns:
            Lista de campos para values()
        """
        # Mapeo de columnas virtuales a campos reales de la base de datos
        field_mapping = {
            # === PRODUCTO ===
            'product_name': 'product__name',
            'product_code': 'product__code',
            'product_type': 'product__product_type__name',
            
            # === SUCURSAL ===
            'branch_name': 'branch__name',
            'branch_city': 'branch__city',
            'branch_address': 'address',
            
            # === CLIENTE ===
            'client_name': 'client__user__first_name',  # Se concatena en annotate
            'client_document': 'client__document_number',
            'client_email': 'client__user__email',
            'client_phone': 'client__mobile_phone',
            'full_name': 'user__first_name',  # Se concatena en annotate
            'first_name': 'user__first_name',
            'last_name': 'user__last_name',
            'email': 'user__email',
            'phone': 'mobile_phone',
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
            'assigned_to_name': 'assigned_to__first_name',  # Se concatena en annotate
            'reviewed_by_name': 'reviewed_by__first_name',  # Se concatena en annotate
            'approved_by_name': 'approved_by__first_name',  # Se concatena en annotate
            'created_by_name': 'created_by__first_name',  # Se concatena en annotate
            'updated_by_name': 'updated_by__first_name',  # Se concatena en annotate
            'verified_by_name': 'verified_by__first_name',  # Se concatena en annotate
            'user_name': 'user__first_name',
            'user_email': 'user__email',
            'resolved_by_name': 'resolved_by__first_name',
            'uploaded_by_name': 'uploaded_by__first_name',
            
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
            'timestamp': 'timestamp',
            'started_at': 'started_at',
            'completed_at': 'completed_at',
            'resolved_at': 'resolved_at',
            
            # === ESTADOS ===
            'kyc_status': 'kyc_status',
            
            # === TENANT ===
            'tenant_name': 'institution__name',
            'tenant_slug': 'institution__slug',
            'institution_type': 'institution_type',
            'institution_name': 'institution__name',
            
            # === PLAN ===
            'plan_name': 'subscription__plan__name',
            'subscription_status': 'subscription_status',
            'payment_status': 'payment_status',
            
            # === DOCUMENTOS ===
            'application_status': 'status',
            'document_status': 'document_status',
            
            # === VERIFICACIÓN ===
            'decision': 'decision',
            'provider': 'provider',
            
            # === PRODUCTOS CREDITICIOS ===
            'rule_set_name': 'rule_set__name',
            'rule_set_code': 'rule_set__code',
            'interest_rate_type': 'selected_parameter__interest_rate_type',
            'display_order': 'display_order',
            'description': 'description',
            'target_audience': 'target_audience',
            'benefits': 'benefits',
            
            # === AUDIT LOG ===
            'action': 'action',
            'action_display': 'action',
            'resource_type': 'resource_type',
            'resource_id': 'resource_id',
            'severity': 'severity',
            'ip_address': 'ip_address',
            'user_agent': 'user_agent',
            
            # === SECURITY EVENT ===
            'event_type': 'event_type',
            'event_type_display': 'event_type',
            'email_attempted': 'email',
            'resolved': 'resolved',
            
            # === FILE RESOURCE ===
            'resource_type': 'resource_type',
            'category': 'category',
            
            # === TENANT RULE SET ===
            'rule_set_description': 'description',
            'is_default': 'is_default',
            
            # === CREDIT PRODUCT PARAMETER ===
            'min_amount': 'min_amount',
            'max_amount': 'max_amount',
            'default_amount': 'default_amount',
            'min_term_months': 'min_term_months',
            'max_term_months': 'max_term_months',
            'default_term_months': 'default_term_months',
            'min_interest_rate': 'min_interest_rate',
            'max_interest_rate': 'max_interest_rate',
            'default_interest_rate': 'default_interest_rate',
            'commission_rate_min': 'commission_rate_min',
            'commission_rate_max': 'commission_rate_max',
            'requires_guarantor': 'requires_guarantor',
            'requires_collateral': 'requires_collateral',
            
            # === SUBSCRIPTION PLAN ===
            'name': 'name',
            'slug': 'slug',
            'price': 'price',
            'billing_cycle': 'billing_cycle',
            'billing_cycle_display': 'billing_cycle',
            'trial_days': 'trial_days',
            'setup_fee': 'setup_fee',
            'max_users': 'max_users',
            'max_branches': 'max_branches',
            'max_products': 'max_products',
            'max_loans_per_month': 'max_loans_per_month',
            'max_storage_gb': 'max_storage_gb',
            'has_ai_scoring': 'has_ai_scoring',
            'has_workflows': 'has_workflows',
            'has_reporting': 'has_reporting',
            'has_mobile_app': 'has_mobile_app',
            'has_api_access': 'has_api_access',
            'has_white_label': 'has_white_label',
            'has_priority_support': 'has_priority_support',
            'has_custom_integrations': 'has_custom_integrations',
            'is_featured': 'is_featured',
            
            # === SUBSCRIPTION (adicionales) ===
            'institution_slug': 'institution__slug',
            'status_display': 'status',
            'payment_status_display': 'payment_status',
            'start_date': 'start_date',
            'end_date': 'end_date',
            'trial_end_date': 'trial_end_date',
            'next_billing_date': 'next_billing_date',
            'current_users': 'current_users',
            'current_branches': 'current_branches',
            'current_products': 'current_products',
            'current_month_loans': 'current_month_loans',
            'current_storage_gb': 'current_storage_gb',
            
            # === CAMPOS TEMPORALES (ya anotados, mantener nombre) ===
            'day': 'day',
            'week': 'week',
            'month': 'month',
            'quarter': 'quarter',
            'year': 'year',
        }
        
        mapped_fields = []
        for field in group_by:
            mapped_field = field_mapping.get(field, field)
            mapped_fields.append(mapped_field)
        
        return mapped_fields
    
    def _build_aggregations(
        self,
        columns: List[str],
        report_def: Dict
    ) -> Dict[str, Any]:
        """
        Construye diccionario de agregaciones.
        
        Mapea columnas virtuales a expresiones Django ORM con soporte completo
        para todos los tipos de reportes del catálogo.
        
        Args:
            columns: Columnas solicitadas
            report_def: Definición del reporte
        
        Returns:
            Diccionario de agregaciones para annotate()
        """
        aggregations = {}
        
        # Mapeo completo de columnas agregadas a expresiones Django ORM
        # Organizado por tipo de reporte para mejor mantenibilidad
        
        # ===== AGREGACIONES GENERALES (Créditos) =====
        agg_map = {
            # Conteos básicos
            'total_applications': Count('id'),
            'total_loans': Count('id'),
            'total_clients': Count('client', distinct=True),
            'total_users': Count('id'),
            'total_active_loans': Count('id', filter=Q(status__in=['APPROVED', 'DISBURSED'])),
            
            # Conteos por estado
            'approved_count': Count('id', filter=Q(status='APPROVED')),
            'rejected_count': Count('id', filter=Q(status='REJECTED')),
            'pending_count': Count('id', filter=Q(status__in=['SUBMITTED', 'IN_REVIEW', 'OBSERVED'])),
            'disbursed_count': Count('id', filter=Q(status='DISBURSED')),
            'draft_count': Count('id', filter=Q(status='DRAFT')),
            'cancelled_count': Count('id', filter=Q(status='CANCELLED')),
            
            # Montos
            'total_requested_amount': Sum('requested_amount'),
            'total_approved_amount': Sum('approved_amount'),
            'avg_requested_amount': Avg('requested_amount'),
            'avg_approved_amount': Avg('approved_amount'),
            'max_approved_amount': Sum('approved_amount'),  # Para reportes de máximo
            'min_approved_amount': Sum('approved_amount'),  # Para reportes de mínimo
            
            # Promedios
            'avg_credit_score': Avg('credit_score'),
            'avg_term_months': Avg('term_months'),
            'avg_interest_rate': Avg('approved_interest_rate'),
            'avg_monthly_payment': Avg('monthly_payment'),
            'avg_monthly_income': Avg('monthly_income'),
            'avg_debt_to_income': Avg('debt_to_income_ratio'),
            
            # Tasas y porcentajes calculados
            'approval_rate': ExpressionWrapper(
                (Count('id', filter=Q(status='APPROVED')) * 100.0) / Count('id'),
                output_field=FloatField()
            ),
            'rejection_rate': ExpressionWrapper(
                (Count('id', filter=Q(status='REJECTED')) * 100.0) / Count('id'),
                output_field=FloatField()
            ),
            'disbursement_rate': ExpressionWrapper(
                (Count('id', filter=Q(status='DISBURSED')) * 100.0) / Count('id'),
                output_field=FloatField()
            ),
            
            # ===== AGREGACIONES PARA CLIENTES =====
            'active_users': Count('id', filter=Q(is_active=True)),
            'inactive_users': Count('id', filter=Q(is_active=False)),
            'verified_clients': Count('id', filter=Q(kyc_status='VERIFIED')),
            'pending_verification': Count('id', filter=Q(kyc_status='PENDING')),
            
            # ===== AGREGACIONES PARA DOCUMENTOS =====
            'total_documents_required': Count('document_checklist'),
            'pending_documents_count': Count('document_checklist', filter=Q(document_checklist__status='PENDING')),
            'uploaded_documents_count': Count('document_checklist', filter=Q(document_checklist__status='UPLOADED')),
            'completion_percentage': ExpressionWrapper(
                (Count('document_checklist', filter=Q(document_checklist__status__in=['UPLOADED', 'VERIFIED'])) * 100.0) / Count('document_checklist'),
                output_field=FloatField()
            ),
            
            # ===== AGREGACIONES PARA VERIFICACIÓN DE IDENTIDAD =====
            'processing_time_minutes': Avg('processing_time_minutes'),
            'approved_verifications': Count('id', filter=Q(decision='APPROVED')),
            'declined_verifications': Count('id', filter=Q(decision='DECLINED')),
            'manual_review_count': Count('id', filter=Q(decision='MANUAL_REVIEW')),
            
            # ===== AGREGACIONES PARA REPORTES SAAS =====
            'user_count': Count('users'),
            'branch_count': Count('branches'),
            'active_loans_count': Count('loan_applications', filter=Q(loan_applications__status__in=['APPROVED', 'DISBURSED'])),
            'admin_count': Count('users', filter=Q(users__role='ADMIN')),
            'manager_count': Count('users', filter=Q(users__role='MANAGER')),
            'analyst_count': Count('users', filter=Q(users__role='ANALYST')),
            'officer_count': Count('users', filter=Q(users__role='OFFICER')),
            'client_count': Count('users', filter=Q(users__role='CLIENT')),
            
            # ===== AGREGACIONES PARA SUSCRIPCIONES =====
            'amount_due': Sum('amount_due'),
            'total_paid': Sum('total_paid'),
            'current_users': Sum('current_users'),
            'current_branches': Sum('current_branches'),
            'days_active': Avg('days_active'),
            
            # ===== AGREGACIONES PARA BRANCH (Sucursales) =====
            'assigned_users_count': Count('assigned_users'),
            'total_clients': Count('assigned_loan_applications__client', distinct=True),
            'active_clients': Count('assigned_loan_applications__client', 
                                   filter=Q(assigned_loan_applications__status__in=['APPROVED', 'DISBURSED']), 
                                   distinct=True),
            'avg_processing_days': Avg(
                ExpressionWrapper(
                    Extract(F('approved_at') - F('created_at'), 'epoch') / 86400.0,
                    output_field=FloatField()
                )
            ),
            
            # ===== AGREGACIONES PARA BRANCH BY CITY =====
            'branch_count': Count('id'),
            'active_branches': Count('id', filter=Q(is_active=True)),
            'inactive_branches': Count('id', filter=Q(is_active=False)),
            'total_users_assigned': Count('assigned_users'),
            
            # ===== AGREGACIONES PARA AUDIT LOG =====
            'total_actions': Count('id'),
            'actions_this_month': Count('id', filter=Q(timestamp__gte=timezone.now() - timedelta(days=30))),
            
            # ===== AGREGACIONES PARA SECURITY EVENT =====
            'total_events': Count('id'),
            'resolved_events': Count('id', filter=Q(resolved=True)),
            'unresolved_events': Count('id', filter=Q(resolved=False)),
            
            # ===== AGREGACIONES PARA FILE RESOURCE =====
            'total_files': Count('id'),
            'total_size_gb': Sum(ExpressionWrapper(F('size') / (1024.0 * 1024.0 * 1024.0), output_field=FloatField())),
            'active_files': Count('id', filter=Q(status='active')),
            'archived_files': Count('id', filter=Q(status='archived')),
            'deleted_files': Count('id', filter=Q(status='deleted')),
            'avg_file_size_mb': Avg(ExpressionWrapper(F('size') / (1024.0 * 1024.0), output_field=FloatField())),
            'oldest_file_date': Min('created_at'),
            'newest_file_date': Max('created_at'),
            
            # ===== AGREGACIONES PARA TENANT RULE SET =====
            'eligibility_rules_count': Count('eligibility_rules'),
            'parameters_count': Count('product_parameters'),
            'thresholds_count': Count('decision_thresholds'),
            
            # ===== AGREGACIONES PARA SUBSCRIPTION =====
            'users_percentage': ExpressionWrapper(
                (F('current_users') * 100.0) / F('plan__max_users'),
                output_field=FloatField()
            ),
            'branches_percentage': ExpressionWrapper(
                (F('current_branches') * 100.0) / F('plan__max_branches'),
                output_field=FloatField()
            ),
            'products_percentage': ExpressionWrapper(
                (F('current_products') * 100.0) / F('plan__max_products'),
                output_field=FloatField()
            ),
            'loans_percentage': ExpressionWrapper(
                (F('current_month_loans') * 100.0) / F('plan__max_loans_per_month'),
                output_field=FloatField()
            ),
            'storage_percentage': ExpressionWrapper(
                (F('current_storage_gb') * 100.0) / F('plan__max_storage_gb'),
                output_field=FloatField()
            ),
            'days_until_renewal': ExpressionWrapper(
                Extract(F('next_billing_date') - timezone.now().date(), 'epoch') / 86400.0,
                output_field=FloatField()
            ),
            'monthly_revenue': Case(
                When(plan__billing_cycle='MONTHLY', then=F('plan__price')),
                When(plan__billing_cycle='QUARTERLY', then=ExpressionWrapper(F('plan__price') / 3.0, output_field=DecimalField())),
                When(plan__billing_cycle='ANNUAL', then=ExpressionWrapper(F('plan__price') / 12.0, output_field=DecimalField())),
                default=F('plan__price'),
                output_field=DecimalField()
            ),
            
            # ===== AGREGACIONES PARA SUBSCRIPTION PLAN =====
            'price_per_month': Case(
                When(billing_cycle='MONTHLY', then=F('price')),
                When(billing_cycle='QUARTERLY', then=ExpressionWrapper(F('price') / 3.0, output_field=DecimalField())),
                When(billing_cycle='ANNUAL', then=ExpressionWrapper(F('price') / 12.0, output_field=DecimalField())),
                default=F('price'),
                output_field=DecimalField()
            ),
            
            # ===== AGREGACIONES PARA ANALYTICS =====
            'conversion_rate': ExpressionWrapper(
                (Count('id', filter=Q(status='DISBURSED')) * 100.0) / Count('id'),
                output_field=FloatField()
            ),
            'drop_off_count': Count('id', filter=Q(status__in=['REJECTED', 'CANCELLED'])),
            'drop_off_rate': ExpressionWrapper(
                (Count('id', filter=Q(status__in=['REJECTED', 'CANCELLED'])) * 100.0) / Count('id'),
                output_field=FloatField()
            ),
            'avg_time_to_next_stage_days': Avg(
                ExpressionWrapper(
                    Extract(F('updated_at') - F('created_at'), 'epoch') / 86400.0,
                    output_field=FloatField()
                )
            ),
        }
        
        # Agregar las agregaciones solicitadas
        for column in columns:
            if column in agg_map:
                aggregations[column] = agg_map[column]
        
        # ===== CAMPOS CALCULADOS ESPECIALES =====
        
        # Campos que requieren anotaciones adicionales
        if 'days_since_submission' in columns:
            aggregations['days_since_submission'] = ExpressionWrapper(
                Extract(timezone.now() - F('submitted_at'), 'epoch') / 86400.0,
                output_field=FloatField()
            )
        
        if 'days_since_disbursement' in columns:
            aggregations['days_since_disbursement'] = ExpressionWrapper(
                Extract(timezone.now() - F('disbursed_at'), 'epoch') / 86400.0,
                output_field=FloatField()
            )
        
        if 'latest_loan_date' in columns:
            aggregations['latest_loan_date'] = Max('approved_at')
        
        if 'last_user_created_at' in columns:
            aggregations['last_user_created_at'] = Max('created_at')
        
        # ===== CAMPOS NO AGREGADOS (campos directos de ForeignKey) =====
        # Estos campos se obtienen directamente del GROUP BY, no necesitan agregación
        non_aggregated_fields = [
            'product_name', 'product_code', 'product_type',
            'branch_name', 'branch_city',
            'client_name', 'client_document', 'client_email', 'client_phone',
            'assigned_to_name',
            'tenant_name', 'tenant_slug',
            'plan_name',
            'application_number',
            'status', 'risk_level', 'employment_status', 'kyc_status',
            'city', 'department', 'decision', 'provider',
            'institution_type', 'is_active', 'subscription_status', 'payment_status',
            'application_status', 'document_status',
            'document_type', 'full_name', 'email', 'mobile_phone',
            'pending_document_types',  # Este requiere lógica especial
        ]
        
        # Para campos no agregados que están en columns pero no en group_by,
        # necesitamos agregarlos como anotaciones usando F()
        # Esto es necesario cuando se solicita un campo que no está en el GROUP BY
        # pero que es único para cada grupo (como product_name cuando agrupamos por product_id)
        
        return aggregations
    
    def _apply_sorting(
        self,
        queryset: QuerySet,
        sort: List[Dict]
    ) -> QuerySet:
        """
        Aplica ordenamiento al queryset.
        
        Mapea campos virtuales a campos reales o agregados.
        
        Args:
            queryset: QuerySet base
            sort: Lista de configuraciones de ordenamiento
        
        Returns:
            QuerySet ordenado
        """
        # Mapeo de campos virtuales a campos reales para ordenamiento
        field_mapping = {
            # === PRODUCTO ===
            'product_name': 'product__name',
            'product_code': 'product__code',
            'product_type': 'product__product_type__name',
            
            # === SUCURSAL ===
            'branch_name': 'branch__name',
            'branch_city': 'branch__city',
            
            # === CLIENTE ===
            'client_name': 'client__user__first_name',
            'client_document': 'client__document_number',
            'client_email': 'client__user__email',
            'client_phone': 'client__mobile_phone',
            'full_name': 'user__first_name',
            'first_name': 'user__first_name',
            'last_name': 'user__last_name',
            'email': 'user__email',
            'phone': 'mobile_phone',
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
            'assigned_to_name': 'assigned_to__first_name',
            'reviewed_by_name': 'reviewed_by__first_name',
            'approved_by_name': 'approved_by__first_name',
            'created_by_name': 'created_by__first_name',
            'updated_by_name': 'updated_by__first_name',
            'verified_by_name': 'verified_by__first_name',
            
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
            
            # === CAMPOS AGREGADOS (mantener nombre, ya están anotados) ===
            'total_applications': 'total_applications',
            'approved_count': 'approved_count',
            'rejected_count': 'rejected_count',
            'pending_count': 'pending_count',
            'total_requested_amount': 'total_requested_amount',
            'total_approved_amount': 'total_approved_amount',
            'avg_requested_amount': 'avg_requested_amount',
            'avg_approved_amount': 'avg_approved_amount',
            'approval_rate': 'approval_rate',
            'disbursement_rate': 'disbursement_rate',
            'total_users': 'total_users',
            'active_users': 'active_users',
            'avg_credit_score': 'avg_credit_score',
            'avg_term_months': 'avg_term_months',
        }
        
        order_by = []
        
        for sort_item in sort:
            field = sort_item.get('field')
            direction = sort_item.get('direction', 'asc')
            
            if not field:
                continue
            
            # Mapear campo virtual a campo real
            mapped_field = field_mapping.get(field, field)
            
            if direction == 'desc':
                order_by.append(f'-{mapped_field}')
            else:
                order_by.append(mapped_field)
        
        if order_by:
            queryset = queryset.order_by(*order_by)
        
        return queryset
