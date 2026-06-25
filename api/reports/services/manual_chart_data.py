"""
Generador de datos para gráficos de reportes manuales.

Autor: Sistema FinCore
Fecha: 2026-05-11
"""

from django.db.models import Count, Sum, Avg, Q
from django.db.models.functions import TruncMonth, TruncDate
from django.utils import timezone
from datetime import timedelta


class ManualChartDataGenerator:
    """
    Genera datos para gráficos según el tipo de reporte.
    """
    
    def __init__(self, queryset, report_type):
        """
        Inicializa el generador.
        
        Args:
            queryset: QuerySet con los datos
            report_type: Tipo de reporte
        """
        self.queryset = queryset
        self.report_type = report_type
    
    def generate(self):
        """
        Genera datos de gráficos según el tipo de reporte.
        
        Returns:
            dict: Datos para gráficos
        """
        generator_map = {
            'clients': self.generate_clients_charts,
            'products': self.generate_products_charts,
            'applications': self.generate_applications_charts,
            'audit': self.generate_audit_charts,
            'users': self.generate_users_charts,
            'branches': self.generate_branches_charts,
        }
        
        generator = generator_map.get(self.report_type)
        if not generator:
            return {}
        
        return generator()
    
    # ============================================================
    # GENERADORES POR TIPO
    # ============================================================
    
    def generate_clients_charts(self):
        """Genera datos de gráficos para clientes."""
        # Por estado
        by_status = [
            {'name': 'Activos', 'value': self.queryset.filter(is_active=True).count()},
            {'name': 'Inactivos', 'value': self.queryset.filter(is_active=False).count()},
        ]
        
        # Por estado KYC
        kyc_statuses = ['PENDING', 'VERIFIED', 'REJECTED', 'EXPIRED']
        by_kyc_status = [
            {'name': status, 'value': self.queryset.filter(kyc_status=status).count()}
            for status in kyc_statuses
        ]
        
        # Por mes
        by_month = list(
            self.queryset.annotate(month=TruncMonth('created_at'))
            .values('month')
            .annotate(count=Count('id'))
            .order_by('month')
        )
        by_month_formatted = [
            {'month': item['month'].strftime('%Y-%m'), 'count': item['count']}
            for item in by_month
        ]
        
        # Por nivel de riesgo
        risk_levels = ['LOW', 'MEDIUM', 'HIGH']
        by_risk_level = [
            {'name': level, 'value': self.queryset.filter(risk_level=level).count()}
            for level in risk_levels
        ]
        
        # Top 10 ciudades
        by_city = list(
            self.queryset.values('city')
            .annotate(value=Count('id'))
            .order_by('-value')[:10]
        )
        by_city_formatted = [
            {'name': item['city'] or 'Sin ciudad', 'value': item['value']}
            for item in by_city
        ]
        
        return {
            'by_status': by_status,
            'by_kyc_status': by_kyc_status,
            'by_month': by_month_formatted,
            'by_risk_level': by_risk_level,
            'by_city': by_city_formatted,
        }
    
    def generate_products_charts(self):
        """Genera datos de gráficos para productos."""
        # Por tipo
        by_type = list(
            self.queryset.values('product_type__name')
            .annotate(value=Count('id'))
            .order_by('-value')
        )
        by_type_formatted = [
            {'name': item['product_type__name'] or 'Sin tipo', 'value': item['value']}
            for item in by_type
        ]
        
        # Por estado
        by_status = [
            {'name': 'Activos', 'value': self.queryset.filter(is_active=True).count()},
            {'name': 'Inactivos', 'value': self.queryset.filter(is_active=False).count()},
        ]
        
        # Por mes
        by_month = list(
            self.queryset.annotate(month=TruncMonth('created_at'))
            .values('month')
            .annotate(count=Count('id'))
            .order_by('month')
        )
        by_month_formatted = [
            {'month': item['month'].strftime('%Y-%m'), 'count': item['count']}
            for item in by_month
        ]
        
        # Comparación de tasas de interés
        interest_rate_comparison = []
        for product in self.queryset.filter(selected_parameter__isnull=False)[:10]:
            if product.selected_parameter:
                # Usar el promedio de min y max
                avg_rate = (float(product.selected_parameter.min_interest_rate) + 
                           float(product.selected_parameter.max_interest_rate)) / 2
                interest_rate_comparison.append({
                    'name': product.name[:20],
                    'min_rate': float(product.selected_parameter.min_interest_rate),
                    'max_rate': float(product.selected_parameter.max_interest_rate),
                    'avg_rate': round(avg_rate, 2)
                })
        
        # Distribución de montos
        amount_distribution = []
        for product in self.queryset.filter(selected_parameter__isnull=False)[:10]:
            if product.selected_parameter:
                amount_distribution.append({
                    'name': product.name[:20],
                    'min_amount': float(product.selected_parameter.min_amount),
                    'max_amount': float(product.selected_parameter.max_amount),
                })
        
        return {
            'by_type': by_type_formatted,
            'by_status': by_status,
            'by_month': by_month_formatted,
            'interest_rate_comparison': interest_rate_comparison,
            'amount_distribution': amount_distribution,
        }
    
    def generate_applications_charts(self):
        """Genera datos de gráficos para solicitudes."""
        # Mapeo de estados a nombres legibles
        status_labels = {
            'DRAFT': 'Borrador',
            'SUBMITTED': 'Enviada',
            'IN_REVIEW': 'En Revisión',
            'APPROVED': 'Aprobada',
            'REJECTED': 'Rechazada',
            'DISBURSED': 'Desembolsada',
            'CANCELLED': 'Cancelada'
        }
        
        # Por estado - solo incluir estados con valores > 0
        statuses = ['DRAFT', 'SUBMITTED', 'IN_REVIEW', 'APPROVED', 'REJECTED', 'DISBURSED', 'CANCELLED']
        by_status = []
        for status in statuses:
            count = self.queryset.filter(status=status).count()
            if count > 0:
                by_status.append({
                    'name': status_labels.get(status, status),
                    'value': count
                })
        
        # Por mes
        by_month = list(
            self.queryset.annotate(month=TruncMonth('created_at'))
            .values('month')
            .annotate(count=Count('id'))
            .order_by('month')
        )
        by_month_formatted = [
            {'month': item['month'].strftime('%Y-%m'), 'count': item['count']}
            for item in by_month
        ]
        
        # Tasa de aprobación por mes
        approval_rate_by_month = []
        for item in by_month:
            month = item['month']
            month_apps = self.queryset.filter(
                created_at__year=month.year,
                created_at__month=month.month
            )
            approved = month_apps.filter(status__in=['APPROVED', 'DISBURSED']).count()
            rejected = month_apps.filter(status='REJECTED').count()
            total = approved + rejected
            rate = (approved / total * 100) if total > 0 else 0
            approval_rate_by_month.append({
                'month': month.strftime('%Y-%m'),
                'approval_rate': round(rate, 2)
            })
        
        # Comparación de montos
        amounts_comparison = [
            {
                'name': 'Solicitado',
                'requested': float(self.queryset.aggregate(Sum('requested_amount'))['requested_amount__sum'] or 0),
                'approved': 0
            },
            {
                'name': 'Aprobado',
                'requested': 0,
                'approved': float(self.queryset.aggregate(Sum('approved_amount'))['approved_amount__sum'] or 0)
            }
        ]
        
        # Por producto
        by_product = list(
            self.queryset.values('product__name')
            .annotate(value=Count('id'))
            .order_by('-value')[:10]
        )
        by_product_formatted = [
            {'name': item['product__name'] or 'Sin producto', 'value': item['value']}
            for item in by_product
        ]
        
        # Por sucursal
        by_branch = list(
            self.queryset.values('branch__name')
            .annotate(value=Count('id'))
            .order_by('-value')[:10]
        )
        by_branch_formatted = [
            {'name': item['branch__name'] or 'Sin sucursal', 'value': item['value']}
            for item in by_branch
        ]
        
        # Por nivel de riesgo
        risk_levels = ['LOW', 'MEDIUM', 'HIGH', 'VERY_HIGH']
        by_risk_level = [
            {'name': level, 'value': self.queryset.filter(risk_level=level).count()}
            for level in risk_levels
        ]
        
        # Tiempo de procesamiento (simplificado)
        processing_time = [
            {'name': '0-7 días', 'value': 0},
            {'name': '8-15 días', 'value': 0},
            {'name': '16-30 días', 'value': 0},
            {'name': '30+ días', 'value': 0},
        ]
        
        return {
            'by_status': by_status,
            'by_month': by_month_formatted,
            'approval_rate_by_month': approval_rate_by_month,
            'amounts_comparison': amounts_comparison,
            'by_product': by_product_formatted,
            'by_branch': by_branch_formatted,
            'by_risk_level': by_risk_level,
            'processing_time': processing_time,
        }
    
    def generate_audit_charts(self):
        """Genera datos de gráficos para auditoría."""
        # Por acción
        by_action = list(
            self.queryset.values('action')
            .annotate(value=Count('id'))
            .order_by('-value')[:10]
        )
        by_action_formatted = [
            {'name': item['action'], 'value': item['value']}
            for item in by_action
        ]
        
        # Por severidad
        severities = ['info', 'warning', 'error', 'critical']
        by_severity = [
            {'name': sev, 'value': self.queryset.filter(severity=sev).count()}
            for sev in severities
        ]
        
        # Top 10 usuarios
        by_user_top10 = list(
            self.queryset.values('user__username', 'user__first_name', 'user__last_name')
            .annotate(value=Count('id'))
            .order_by('-value')[:10]
        )
        by_user_formatted = [
            {
                'name': f"{item['user__first_name']} {item['user__last_name']}" if item['user__first_name'] else item['user__username'],
                'value': item['value']
            }
            for item in by_user_top10
        ]
        
        # Por día (últimos 30 días)
        thirty_days_ago = timezone.now() - timedelta(days=30)
        by_day = list(
            self.queryset.filter(timestamp__gte=thirty_days_ago)
            .annotate(day=TruncDate('timestamp'))
            .values('day')
            .annotate(count=Count('id'))
            .order_by('day')
        )
        by_day_formatted = [
            {'day': item['day'].strftime('%Y-%m-%d'), 'count': item['count']}
            for item in by_day
        ]
        
        # Por recurso
        by_resource = list(
            self.queryset.values('resource_type')
            .annotate(value=Count('id'))
            .order_by('-value')[:10]
        )
        by_resource_formatted = [
            {'name': item['resource_type'] or 'Sin tipo', 'value': item['value']}
            for item in by_resource
        ]
        
        # Por hora del día
        by_hour = [{'name': f'{i}:00', 'value': 0} for i in range(24)]
        
        return {
            'by_action': by_action_formatted,
            'by_severity': by_severity,
            'by_user_top10': by_user_formatted,
            'by_day': by_day_formatted,
            'by_resource': by_resource_formatted,
            'by_hour': by_hour,
        }
    
    def generate_users_charts(self):
        """Genera datos de gráficos para usuarios."""
        # Por rol
        by_role = list(
            self.queryset.values('groups__name')
            .annotate(value=Count('id', distinct=True))
            .order_by('-value')
        )
        by_role_formatted = [
            {'name': item['groups__name'] or 'Sin rol', 'value': item['value']}
            for item in by_role
        ]
        
        # Por estado
        by_status = [
            {'name': 'Activos', 'value': self.queryset.filter(is_active=True).count()},
            {'name': 'Inactivos', 'value': self.queryset.filter(is_active=False).count()},
        ]
        
        # Por mes
        by_month = list(
            self.queryset.annotate(month=TruncMonth('date_joined'))
            .values('month')
            .annotate(count=Count('id'))
            .order_by('month')
        )
        by_month_formatted = [
            {'month': item['month'].strftime('%Y-%m'), 'count': item['count']}
            for item in by_month
        ]
        
        # Actividad (simplificado)
        activity = [
            {'name': 'Muy activos', 'value': 0},
            {'name': 'Activos', 'value': 0},
            {'name': 'Poco activos', 'value': 0},
            {'name': 'Inactivos', 'value': self.queryset.filter(is_active=False).count()},
        ]
        
        return {
            'by_role': by_role_formatted,
            'by_status': by_status,
            'by_month': by_month_formatted,
            'activity': activity,
        }
    
    def generate_branches_charts(self):
        """Genera datos de gráficos para sucursales."""
        # Por ciudad
        by_city = list(
            self.queryset.values('city')
            .annotate(value=Count('id'))
            .order_by('-value')[:10]
        )
        by_city_formatted = [
            {'name': item['city'] or 'Sin ciudad', 'value': item['value']}
            for item in by_city
        ]
        
        # Por estado
        by_status = [
            {'name': 'Activas', 'value': self.queryset.filter(is_active=True).count()},
            {'name': 'Inactivas', 'value': self.queryset.filter(is_active=False).count()},
        ]
        
        # Solicitudes por sucursal
        applications_by_branch = list(
            self.queryset.values('name')
            .annotate(value=Count('loan_applications'))
            .order_by('-value')[:10]
        )
        applications_formatted = [
            {'name': item['name'], 'value': item['value']}
            for item in applications_by_branch
        ]
        
        return {
            'by_city': by_city_formatted,
            'by_status': by_status,
            'applications_by_branch': applications_formatted,
        }
