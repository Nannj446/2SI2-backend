"""
Data Processor para Reportes Manuales.

Procesa datos de queries y genera resúmenes estadísticos.

Autor: Sistema FinCore
Fecha: 2026-05-11
"""

from django.db.models import Count, Sum, Avg, Q
from django.db.models.functions import TruncMonth
from datetime import datetime, timedelta


class ManualDataProcessor:
    """
    Procesa datos de reportes y genera resúmenes estadísticos.
    """
    
    def __init__(self, queryset, report_type, paginate=True, page=1, page_size=100):
        """
        Inicializa el procesador.
        
        Args:
            queryset: QuerySet con los datos
            report_type: Tipo de reporte
            paginate: Si debe paginar los resultados (True para frontend, False para exportación)
            page: Número de página actual
            page_size: Tamaño de página
        """
        self.queryset = queryset
        self.report_type = report_type
        self.paginate = paginate
        self.page = page
        self.page_size = page_size
    
    def _get_paginated_queryset(self):
        """
        Retorna el queryset paginado si paginate=True, sino retorna todo.
        
        Returns:
            QuerySet: Queryset paginado o completo
        """
        if not self.paginate:
            return self.queryset
        
        # Calcular offset
        start = (self.page - 1) * self.page_size
        end = start + self.page_size
        
        return self.queryset[start:end]
    
    def process(self):
        """
        Procesa los datos según el tipo de reporte.
        
        Returns:
            dict: Datos procesados con resumen y filas
        """
        processor_map = {
            'clients': self.process_clients,
            'products': self.process_products,
            'applications': self.process_applications,
            'audit': self.process_audit,
            'users': self.process_users,
            'branches': self.process_branches,
        }
        
        processor = processor_map.get(self.report_type)
        if not processor:
            raise ValueError(f"Tipo de reporte no soportado: {self.report_type}")
        
        return processor()
    
    # ============================================================
    # PROCESADORES POR TIPO
    # ============================================================
    
    def process_clients(self):
        """Procesa datos de clientes."""
        # Resumen
        total = self.queryset.count()
        active = self.queryset.filter(is_active=True).count()
        inactive = total - active
        verified = self.queryset.filter(kyc_status='VERIFIED').count()
        avg_income = self.queryset.aggregate(Avg('monthly_income'))['monthly_income__avg'] or 0
        
        # Distribución por riesgo
        risk_distribution = list(
            self.queryset.values('risk_level')
            .annotate(count=Count('id'))
            .order_by('risk_level')
        )
        
        summary = {
            'total': total,
            'active': active,
            'inactive': inactive,
            'verified': verified,
            'avg_income': float(avg_income),
            'risk_distribution': risk_distribution,
        }
        
        # Filas (paginadas o todas según configuración)
        rows = []
        paginated_queryset = self._get_paginated_queryset()
        for client in paginated_queryset:
            rows.append({
                'id': client.id,
                'full_name': f"{client.user.first_name} {client.user.last_name}",
                'document_number': client.document_number,
                'email': client.user.email,
                'status': 'Activo' if client.is_active else 'Inactivo',
                'kyc_status': client.kyc_status,
                'risk_level': client.risk_level,
                'monthly_income': float(client.monthly_income) if client.monthly_income else 0,
                'city': client.city or '',
                'created_at': client.created_at.isoformat(),
            })
        
        return {
            'summary': summary,
            'rows': rows,
            'total_count': total,
        }
    
    def process_products(self):
        """Procesa datos de productos."""
        total = self.queryset.count()
        active = self.queryset.filter(is_active=True).count()
        inactive = total - active
        
        # Por tipo
        by_type = list(
            self.queryset.values('product_type__name')
            .annotate(count=Count('id'))
            .order_by('-count')
        )
        
        summary = {
            'total': total,
            'active': active,
            'inactive': inactive,
            'by_type': [
                {'type': item['product_type__name'] or 'Sin tipo', 'count': item['count']}
                for item in by_type
            ],
        }
        
        # Filas (paginadas o todas según configuración)
        rows = []
        paginated_queryset = self._get_paginated_queryset()
        for product in paginated_queryset:
            param = product.selected_parameter
            rows.append({
                'id': product.id,
                'name': product.name,
                'code': product.code,
                'product_type': product.product_type.name if product.product_type else '',
                'status': 'Activo' if product.is_active else 'Inactivo',
                'min_amount': float(param.min_amount) if param else 0,
                'max_amount': float(param.max_amount) if param else 0,
                'min_interest_rate': float(param.min_interest_rate) if param else 0,
                'max_interest_rate': float(param.max_interest_rate) if param else 0,
                'interest_type': param.interest_type if param else '',
                'min_term_months': param.min_term_months if param else 0,
                'max_term_months': param.max_term_months if param else 0,
                'created_at': product.created_at.isoformat(),
            })
        
        return {
            'summary': summary,
            'rows': rows,
            'total_count': total,
        }
    
    def process_applications(self):
        """Procesa datos de solicitudes."""
        total = self.queryset.count()
        
        # Por estado
        by_status = {}
        for status in ['DRAFT', 'SUBMITTED', 'IN_REVIEW', 'APPROVED', 'REJECTED', 'DISBURSED', 'CANCELLED']:
            by_status[status] = self.queryset.filter(status=status).count()
        
        # Tasa de aprobación
        approved = by_status.get('APPROVED', 0) + by_status.get('DISBURSED', 0)
        rejected = by_status.get('REJECTED', 0)
        total_processed = approved + rejected
        approval_rate = (approved / total_processed * 100) if total_processed > 0 else 0
        
        # Montos
        aggregates = self.queryset.aggregate(
            total_requested=Sum('requested_amount'),
            total_approved=Sum('approved_amount')
        )
        
        # Tiempo promedio de procesamiento
        processed_apps = self.queryset.filter(
            status__in=['APPROVED', 'REJECTED'],
            submitted_at__isnull=False,
            reviewed_at__isnull=False
        )
        
        avg_days = 0
        processed_count = processed_apps.count()
        if processed_count > 0:
            # Usar values_list para evitar conflicto entre only() y select_related()
            date_pairs = processed_apps.values_list('submitted_at', 'reviewed_at')
            total_days = sum([
                (reviewed - submitted).days
                for submitted, reviewed in date_pairs
                if submitted and reviewed
            ])
            avg_days = total_days / processed_count if processed_count > 0 else 0
        
        # Por producto
        by_product = list(
            self.queryset.values('product__name')
            .annotate(count=Count('id'))
            .order_by('-count')[:10]
        )
        
        summary = {
            'total': total,
            'by_status': by_status,
            'approval_rate': round(approval_rate, 2),
            'total_requested': float(aggregates['total_requested'] or 0),
            'total_approved': float(aggregates['total_approved'] or 0),
            'avg_processing_days': round(avg_days, 1),
            'by_product': [
                {'product': item['product__name'] or 'Sin producto', 'count': item['count']}
                for item in by_product
            ],
        }
        
        # Filas (paginadas o todas según configuración)
        rows = []
        paginated_queryset = self._get_paginated_queryset()
        for app in paginated_queryset:
            rows.append({
                'id': app.id,
                'application_number': app.application_number,
                'client_name': f"{app.client.user.first_name} {app.client.user.last_name}",
                'client_document': app.client.document_number,
                'product_name': app.product.name if app.product else '',
                'status': app.status,
                'requested_amount': float(app.requested_amount),
                'approved_amount': float(app.approved_amount) if app.approved_amount else None,
                'term_months': app.term_months,
                'risk_level': app.risk_level or '',
                'branch': app.branch.name if app.branch else '',
                'assigned_to': f"{app.assigned_to.first_name} {app.assigned_to.last_name}" if app.assigned_to else '',
                'created_at': app.created_at.isoformat(),
                'submitted_at': app.submitted_at.isoformat() if app.submitted_at else None,
                'approved_at': app.approved_at.isoformat() if app.approved_at else None,
            })
        
        return {
            'summary': summary,
            'rows': rows,
            'total_count': total,
        }
    
    def process_audit(self):
        """Procesa datos de auditoría."""
        total = self.queryset.count()
        
        # Por acción
        by_action = list(
            self.queryset.values('action')
            .annotate(count=Count('id'))
            .order_by('-count')[:10]
        )
        
        # Por severidad
        by_severity = list(
            self.queryset.values('severity')
            .annotate(count=Count('id'))
            .order_by('severity')
        )
        
        # Por usuario
        by_user = list(
            self.queryset.values('user__username', 'user__first_name', 'user__last_name')
            .annotate(count=Count('id'))
            .order_by('-count')[:10]
        )
        
        # Por recurso
        by_resource = list(
            self.queryset.values('resource_type')
            .annotate(count=Count('id'))
            .order_by('-count')[:10]
        )
        
        summary = {
            'total': total,
            'by_action': [
                {'action': item['action'], 'count': item['count']}
                for item in by_action
            ],
            'by_severity': [
                {'severity': item['severity'], 'count': item['count']}
                for item in by_severity
            ],
            'by_user': [
                {
                    'user': f"{item['user__first_name']} {item['user__last_name']}" if item['user__first_name'] else item['user__username'],
                    'count': item['count']
                }
                for item in by_user
            ],
            'by_resource': [
                {'resource_type': item['resource_type'], 'count': item['count']}
                for item in by_resource
            ],
        }
        
        # Filas (paginadas o todas según configuración)
        rows = []
        paginated_queryset = self._get_paginated_queryset()
        for log in paginated_queryset:
            rows.append({
                'id': log.id,
                'user': f"{log.user.first_name} {log.user.last_name}" if log.user else 'Sistema',
                'action': log.action,
                'resource_type': log.resource_type or '',
                'resource_id': log.resource_id,
                'description': log.description or '',
                'severity': log.severity,
                'ip_address': log.ip_address or '',
                'timestamp': log.timestamp.isoformat(),
            })
        
        return {
            'summary': summary,
            'rows': rows,
            'total_count': total,
        }
    
    def process_users(self):
        """Procesa datos de usuarios."""
        import logging
        logger = logging.getLogger(__name__)
        
        total = self.queryset.count()
        logger.info(f'=== PROCESS USERS ===')
        logger.info(f'Total users in queryset: {total}')
        logger.info(f'Paginate: {self.paginate}')
        logger.info(f'Page: {self.page}, Page size: {self.page_size}')
        
        active = self.queryset.filter(is_active=True).count()
        inactive = total - active
        
        logger.info(f'Active: {active}, Inactive: {inactive}')
        
        # Por rol
        by_role = list(
            self.queryset.values('groups__name')
            .annotate(count=Count('id', distinct=True))
            .order_by('-count')
        )
        
        logger.info(f'By role: {by_role}')
        
        summary = {
            'total': total,
            'active': active,
            'inactive': inactive,
            'by_role': [
                {'role': item['groups__name'] or 'Sin rol', 'count': item['count']}
                for item in by_role
            ],
        }
        
        # Filas (paginadas o todas según configuración)
        rows = []
        paginated_queryset = self._get_paginated_queryset()
        
        logger.info(f'Processing {paginated_queryset.count()} users for rows')
        
        for user in paginated_queryset:
            roles = ', '.join([g.name for g in user.groups.all()])
            rows.append({
                'id': user.id,
                'full_name': f"{user.first_name} {user.last_name}",
                'email': user.email,
                'role': roles or 'Sin rol',
                'is_active': user.is_active,
                'date_joined': user.date_joined.isoformat(),
                'last_login': user.last_login.isoformat() if user.last_login else None,
            })
        
        logger.info(f'Generated {len(rows)} rows')
        
        return {
            'summary': summary,
            'rows': rows,
            'total_count': total,
        }
    
    def process_branches(self):
        """Procesa datos de sucursales."""
        total = self.queryset.count()
        active = self.queryset.filter(is_active=True).count()
        inactive = total - active
        
        # Por ciudad
        by_city = list(
            self.queryset.values('city')
            .annotate(count=Count('id'))
            .order_by('-count')[:10]
        )
        
        # Solicitudes por sucursal
        applications_by_branch = list(
            self.queryset.values('name')
            .annotate(count=Count('loan_applications'))
            .order_by('-count')[:10]
        )
        
        summary = {
            'total': total,
            'active': active,
            'inactive': inactive,
            'by_city': [
                {'city': item['city'] or 'Sin ciudad', 'count': item['count']}
                for item in by_city
            ],
            'applications_by_branch': [
                {'branch': item['name'], 'count': item['count']}
                for item in applications_by_branch
            ],
        }
        
        # Filas (paginadas o todas según configuración)
        rows = []
        paginated_queryset = self._get_paginated_queryset()
        for branch in paginated_queryset:
            rows.append({
                'id': branch.id,
                'name': branch.name,
                'city': branch.city or '',
                'address': branch.address or '',
                'is_active': branch.is_active,
                'applications_count': branch.assigned_loan_applications.count() if hasattr(branch, 'assigned_loan_applications') else 0,
                'users_count': branch.assigned_users.count() if hasattr(branch, 'assigned_users') else 0,
                'created_at': branch.created_at.isoformat() if hasattr(branch, 'created_at') else '',
            })
        
        return {
            'summary': summary,
            'rows': rows,
            'total_count': total,
        }
