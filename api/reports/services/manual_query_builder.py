"""
Query Builder para Reportes Manuales Independientes.

Este módulo construye queries optimizados con filtros dinámicos
para cada tipo de reporte.

Autor: Sistema FinCore
Fecha: 2026-05-11
"""

from django.db.models import Q, Count, Sum, Avg, F
from django.db.models.functions import TruncMonth, TruncDate
from django.utils import timezone
from datetime import datetime, timedelta


def make_aware_datetime(date_str, end_of_day=False):
    """
    Convierte un string de fecha a datetime timezone-aware.
    
    Args:
        date_str: String en formato 'YYYY-MM-DD'
        end_of_day: Si True, añade 1 día para incluir todo el día
    
    Returns:
        datetime timezone-aware
    """
    dt = datetime.strptime(date_str, '%Y-%m-%d')
    if end_of_day:
        dt = dt + timedelta(days=1)
    return timezone.make_aware(dt, timezone.get_current_timezone())


class ManualQueryBuilder:
    """
    Construye queries optimizados para reportes manuales.
    
    Cada método construye un query específico para un tipo de reporte,
    aplicando filtros y optimizaciones necesarias.
    """
    
    def __init__(self, institution):
        """
        Inicializa el query builder con la institución del usuario.
        
        Args:
            institution: Instancia de FinancialInstitution
        """
        self.institution = institution
    
    # ============================================================
    # REPORTE DE CLIENTES
    # ============================================================
    
    def build_clients_query(self, filters):
        """
        Construye query para reporte de clientes.
        
        Args:
            filters (dict): Diccionario con filtros aplicados
        
        Returns:
            QuerySet: Query optimizado de clientes
        """
        from api.clients.models import Client
        
        # Query base
        queryset = Client.objects.all()
        
        # Filtrar por institución solo en modo TENANT
        scope = filters.get('scope', 'TENANT')
        if scope == 'TENANT' and self.institution:
            queryset = queryset.filter(institution=self.institution)
        
        # Optimizar con select_related para evitar N+1
        queryset = queryset.select_related(
            'user',
            'institution',
            'verified_by'
        )
        
        # Aplicar filtros
        if filters.get('search'):
            search = filters['search'].strip()
            queryset = queryset.filter(
                Q(user__first_name__icontains=search) |
                Q(user__last_name__icontains=search) |
                Q(document_number__icontains=search) |
                Q(user__email__icontains=search)
            )
        
        if filters.get('status'):
            is_active = filters['status'] == 'active'
            queryset = queryset.filter(is_active=is_active)
        
        if filters.get('kyc_status'):
            queryset = queryset.filter(kyc_status=filters['kyc_status'])
        
        if filters.get('risk_level'):
            queryset = queryset.filter(risk_level=filters['risk_level'])
        
        if filters.get('city'):
            queryset = queryset.filter(city__icontains=filters['city'])
        
        if filters.get('department'):
            queryset = queryset.filter(department__icontains=filters['department'])
        
        if filters.get('employment_status'):
            queryset = queryset.filter(employment_status=filters['employment_status'])
        
        if filters.get('income_min'):
            queryset = queryset.filter(monthly_income__gte=filters['income_min'])
        
        if filters.get('income_max'):
            queryset = queryset.filter(monthly_income__lte=filters['income_max'])
        
        if filters.get('date_from'):
            queryset = queryset.filter(created_at__gte=filters['date_from'])
        
        if filters.get('date_to'):
            date_to = make_aware_datetime(filters['date_to'], end_of_day=True)
            queryset = queryset.filter(created_at__lt=date_to)
        
        # Ordenar por fecha de creación descendente
        return queryset.order_by('-created_at')
    
    # ============================================================
    # REPORTE DE PRODUCTOS CREDITICIOS
    # ============================================================
    
    def build_products_query(self, filters):
        """
        Construye query para reporte de productos crediticios.
        
        Args:
            filters (dict): Filtros aplicados
        
        Returns:
            QuerySet: Query optimizado de productos
        """
        from api.products.models import CreditProduct
        
        # Query base
        queryset = CreditProduct.objects.all()
        
        # Filtrar por institución solo en modo TENANT
        scope = filters.get('scope', 'TENANT')
        if scope == 'TENANT' and self.institution:
            queryset = queryset.filter(institution=self.institution)
        
        # Optimizar
        queryset = queryset.select_related(
            'product_type',
            'rule_set',
            'selected_parameter',
            'institution'
        )
        
        # Aplicar filtros
        if filters.get('search'):
            search = filters['search'].strip()
            queryset = queryset.filter(
                Q(name__icontains=search) |
                Q(code__icontains=search) |
                Q(description__icontains=search)
            )
        
        if filters.get('status'):
            is_active = filters['status'] == 'active'
            queryset = queryset.filter(is_active=is_active)
        
        if filters.get('product_type_id'):
            queryset = queryset.filter(product_type_id=filters['product_type_id'])
        
        # Filtros de montos
        if filters.get('min_amount_from'):
            queryset = queryset.filter(
                selected_parameter__isnull=False,
                selected_parameter__min_amount__gte=filters['min_amount_from']
            )
        
        if filters.get('min_amount_to'):
            queryset = queryset.filter(
                selected_parameter__isnull=False,
                selected_parameter__min_amount__lte=filters['min_amount_to']
            )
        
        if filters.get('max_amount_from'):
            queryset = queryset.filter(
                selected_parameter__isnull=False,
                selected_parameter__max_amount__gte=filters['max_amount_from']
            )
        
        if filters.get('max_amount_to'):
            queryset = queryset.filter(
                selected_parameter__isnull=False,
                selected_parameter__max_amount__lte=filters['max_amount_to']
            )
        
        if filters.get('date_from'):
            queryset = queryset.filter(created_at__gte=filters['date_from'])
        
        if filters.get('date_to'):
            date_to = make_aware_datetime(filters['date_to'], end_of_day=True)
            queryset = queryset.filter(created_at__lt=date_to)
        
        return queryset.order_by('display_order', 'name')
    
    # ============================================================
    # REPORTE DE SOLICITUDES DE CRÉDITO
    # ============================================================
    
    def build_applications_query(self, filters):
        """
        Construye query para reporte de solicitudes de crédito.
        
        Args:
            filters (dict): Filtros aplicados
        
        Returns:
            QuerySet: Query optimizado de solicitudes
        """
        from api.loans.models import LoanApplication
        
        # Query base
        queryset = LoanApplication.objects.all()
        
        # Filtrar por institución solo en modo TENANT
        scope = filters.get('scope', 'TENANT')
        if scope == 'TENANT' and self.institution:
            queryset = queryset.filter(institution=self.institution)
        
        # Optimizar con select_related y prefetch_related
        queryset = queryset.select_related(
            'client',
            'client__user',
            'product',
            'product__product_type',
            'branch',
            'assigned_to',
            'reviewed_by',
            'approved_by',
            'institution'
        )
        
        # Aplicar filtros
        if filters.get('search'):
            search = filters['search'].strip()
            queryset = queryset.filter(
                Q(application_number__icontains=search) |
                Q(client__user__first_name__icontains=search) |
                Q(client__user__last_name__icontains=search) |
                Q(client__document_number__icontains=search)
            )
        
        if filters.get('status'):
            status = filters['status']
            if isinstance(status, list):
                queryset = queryset.filter(status__in=status)
            else:
                queryset = queryset.filter(status=status)
        
        if filters.get('product_id'):
            queryset = queryset.filter(product_id=filters['product_id'])
        
        if filters.get('client_id'):
            queryset = queryset.filter(client_id=filters['client_id'])
        
        if filters.get('branch_id'):
            queryset = queryset.filter(branch_id=filters['branch_id'])
        
        if filters.get('assigned_to_id'):
            queryset = queryset.filter(assigned_to_id=filters['assigned_to_id'])
        
        if filters.get('identity_verification_status'):
            queryset = queryset.filter(
                identity_verification_status=filters['identity_verification_status']
            )
        
        if filters.get('documents_status'):
            queryset = queryset.filter(documents_status=filters['documents_status'])
        
        if filters.get('risk_level'):
            queryset = queryset.filter(risk_level=filters['risk_level'])
        
        # Filtros de fecha de creación
        if filters.get('date_from'):
            queryset = queryset.filter(created_at__gte=filters['date_from'])
        
        if filters.get('date_to'):
            date_to = make_aware_datetime(filters['date_to'], end_of_day=True)
            queryset = queryset.filter(created_at__lt=date_to)
        
        # Filtros de fecha de envío
        if filters.get('submitted_from'):
            queryset = queryset.filter(submitted_at__gte=filters['submitted_from'])
        
        if filters.get('submitted_to'):
            date_to = make_aware_datetime(filters['submitted_to'], end_of_day=True)
            queryset = queryset.filter(submitted_at__lt=date_to)
        
        # Filtros de monto
        if filters.get('amount_min'):
            queryset = queryset.filter(requested_amount__gte=filters['amount_min'])
        
        if filters.get('amount_max'):
            queryset = queryset.filter(requested_amount__lte=filters['amount_max'])
        
        return queryset.order_by('-created_at')
    
    # ============================================================
    # REPORTE DE AUDITORÍA
    # ============================================================
    
    def build_audit_query(self, filters):
        """
        Construye query para reporte de auditoría.
        
        Args:
            filters (dict): Filtros aplicados
        
        Returns:
            QuerySet: Query optimizado de logs de auditoría
        """
        from api.audit.models import AuditLog
        
        # Query base
        queryset = AuditLog.objects.all()
        
        # Filtrar por institución solo en modo TENANT
        scope = filters.get('scope', 'TENANT')
        if scope == 'TENANT' and self.institution:
            queryset = queryset.filter(institution=self.institution)
        
        # Optimizar
        queryset = queryset.select_related('user', 'institution')
        
        # Aplicar filtros
        if filters.get('user_id'):
            queryset = queryset.filter(user_id=filters['user_id'])
        
        if filters.get('action'):
            action = filters['action']
            if isinstance(action, list):
                queryset = queryset.filter(action__in=action)
            else:
                queryset = queryset.filter(action=action)
        
        if filters.get('resource_type'):
            queryset = queryset.filter(resource_type=filters['resource_type'])
        
        if filters.get('resource_id'):
            queryset = queryset.filter(resource_id=filters['resource_id'])
        
        if filters.get('severity'):
            severity = filters['severity']
            if isinstance(severity, list):
                queryset = queryset.filter(severity__in=severity)
            else:
                queryset = queryset.filter(severity=severity)
        
        if filters.get('date_from'):
            queryset = queryset.filter(timestamp__gte=filters['date_from'])
        
        if filters.get('date_to'):
            date_to = make_aware_datetime(filters['date_to'], end_of_day=True)
            queryset = queryset.filter(timestamp__lt=date_to)
        
        if filters.get('ip_address'):
            queryset = queryset.filter(ip_address=filters['ip_address'])
        
        return queryset.order_by('-timestamp')
    
    # ============================================================
    # REPORTE DE USUARIOS
    # ============================================================
    
    def build_users_query(self, filters):
        """
        Construye query para reporte de usuarios.
        
        Args:
            filters (dict): Filtros aplicados
        
        Returns:
            QuerySet: Query optimizado de usuarios
        """
        from django.contrib.auth import get_user_model
        import logging
        logger = logging.getLogger(__name__)
        
        User = get_user_model()
        
        # Query base
        queryset = User.objects.all()
        
        logger.info(f'=== BUILD USERS QUERY ===')
        logger.info(f'Institution: {self.institution}')
        logger.info(f'Filters: {filters}')
        logger.info(f'Total users before filtering: {queryset.count()}')
        
        # Filtrar por institución solo en modo TENANT
        scope = filters.get('scope', 'TENANT')
        logger.info(f'Scope: {scope}')
        
        if scope == 'TENANT' and self.institution:
            queryset = queryset.filter(
                institution_memberships__institution=self.institution,
                institution_memberships__is_active=True
            ).distinct()
            logger.info(f'After TENANT filter: {queryset.count()} users')
        elif scope == 'SAAS':
            # En modo SAAS, no filtrar por institución - traer todos los usuarios
            logger.info(f'SAAS mode: no institution filter applied')
            logger.info(f'Total users in SAAS mode: {queryset.count()}')
        
        # Optimizar
        queryset = queryset.prefetch_related('groups', 'institution_memberships')
        
        # Aplicar filtros
        if filters.get('search'):
            search = filters['search'].strip()
            queryset = queryset.filter(
                Q(first_name__icontains=search) |
                Q(last_name__icontains=search) |
                Q(email__icontains=search) |
                Q(username__icontains=search)
            )
            logger.info(f'After search filter: {queryset.count()} users')
        
        # Solo aplicar filtro is_active si viene explícitamente en los filtros
        # y no es None (evitar que DRF lo interprete como False por defecto)
        if 'is_active' in filters and filters.get('is_active') is not None:
            queryset = queryset.filter(is_active=filters['is_active'])
            logger.info(f'After is_active filter: {queryset.count()} users')
        else:
            logger.info(f'is_active filter not applied (not in filters or is None)')
        
        if filters.get('role'):
            queryset = queryset.filter(groups__name=filters['role'])
            logger.info(f'After role filter: {queryset.count()} users')
        
        if filters.get('date_from'):
            queryset = queryset.filter(date_joined__gte=filters['date_from'])
            logger.info(f'After date_from filter: {queryset.count()} users')
        
        if filters.get('date_to'):
            date_to = make_aware_datetime(filters['date_to'], end_of_day=True)
            queryset = queryset.filter(date_joined__lt=date_to)
            logger.info(f'After date_to filter: {queryset.count()} users')
        
        final_count = queryset.count()
        logger.info(f'Final query count: {final_count} users')
        
        return queryset.order_by('-date_joined')
    
    # ============================================================
    # REPORTE DE SUCURSALES
    # ============================================================
    
    def build_branches_query(self, filters):
        """
        Construye query para reporte de sucursales.
        
        Args:
            filters (dict): Filtros aplicados
        
        Returns:
            QuerySet: Query optimizado de sucursales
        """
        from api.branches.models import Branch
        
        # Query base
        queryset = Branch.objects.all()
        
        # Filtrar por institución solo en modo TENANT
        scope = filters.get('scope', 'TENANT')
        if scope == 'TENANT' and self.institution:
            queryset = queryset.filter(institution=self.institution)
        
        # Optimizar
        queryset = queryset.select_related('institution')
        
        # Anotar con conteo de solicitudes
        queryset = queryset.annotate(
            applications_count=Count('loan_applications')
        )
        
        # Aplicar filtros
        if filters.get('search'):
            search = filters['search'].strip()
            queryset = queryset.filter(
                Q(name__icontains=search) |
                Q(address__icontains=search)
            )
        
        if filters.get('is_active') is not None:
            queryset = queryset.filter(is_active=filters['is_active'])
        
        if filters.get('city'):
            queryset = queryset.filter(city__icontains=filters['city'])
        
        return queryset.order_by('name')
