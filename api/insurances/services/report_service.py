"""
Servicios de reportes para Gestión de Seguros.
"""
from decimal import Decimal
from datetime import timedelta

from django.db.models import Sum, Count, Q
from django.utils import timezone

from api.insurances.models import CreditInsurance, Insurer, Insurance, CreditInsuranceStatus


class InsuranceReportService:
    """Servicio para generar reportes de seguros."""

    @staticmethod
    def get_active_insurances_summary(institution):
        """
        Resumen de seguros activos para una institución.
        """
        insurances = CreditInsurance.objects.filter(
            institution=institution,
            status__in=[CreditInsuranceStatus.ACTIVE, CreditInsuranceStatus.EXPIRING_SOON]
        )

        total_count = insurances.count()
        active_count = insurances.filter(status=CreditInsuranceStatus.ACTIVE).count()
        expiring_soon_count = insurances.filter(status=CreditInsuranceStatus.EXPIRING_SOON).count()

        total_premium = insurances.aggregate(total=Sum('total_premium'))['total'] or Decimal('0.00')
        total_paid = insurances.aggregate(total=Sum('premium_paid'))['total'] or Decimal('0.00')

        return {
            'total_insurances': total_count,
            'active_insurances': active_count,
            'expiring_soon_insurances': expiring_soon_count,
            'total_premium': float(total_premium),
            'total_paid': float(total_paid),
        }

    @staticmethod
    def get_insurances_expiring_soon(institution, days=30):
        """
        Lista de seguros próximos a vencer.
        """
        today = timezone.now().date()
        end_date_threshold = today + timedelta(days=days)

        return CreditInsurance.objects.filter(
            institution=institution,
            status=CreditInsuranceStatus.ACTIVE,
            end_date__lte=end_date_threshold,
            end_date__gte=today
        ).select_related('insurance', 'insurance__insurer', 'active_credit')

    @staticmethod
    def get_expired_insurances(institution):
        """
        Lista de seguros vencidos.
        """
        return CreditInsurance.objects.filter(
            institution=institution,
            status=CreditInsuranceStatus.EXPIRED
        ).select_related('insurance', 'insurance__insurer', 'active_credit')

    @staticmethod
    def get_insurance_distribution_by_type(institution):
        """
        Distribución de seguros por tipo.
        """
        return CreditInsurance.objects.filter(
            institution=institution,
            status__in=[CreditInsuranceStatus.ACTIVE, CreditInsuranceStatus.EXPIRING_SOON]
        ).values(
            'insurance__insurance_type'
        ).annotate(
            count=Count('id'),
            total_premium=Sum('total_premium')
        ).order_by('-count')

    @staticmethod
    def get_premiums_collected_by_month(institution, year=None):
        """
        Primas cobradas por mes.
        """
        if year is None:
            year = timezone.now().year

        from django.db.models.functions import TruncMonth
        from django.db.models import Sum

        insurances = CreditInsurance.objects.filter(
            institution=institution,
            status__in=[CreditInsuranceStatus.ACTIVE, CreditInsuranceStatus.EXPIRING_SOON, CreditInsuranceStatus.EXPIRED]
        )

        monthly_data = []
        for month in range(1, 13):
            month_start = timezone.datetime(year, month, 1)
            if month == 12:
                month_end = timezone.datetime(year + 1, 1, 1) - timezone.timedelta(days=1)
            else:
                month_end = timezone.datetime(year, month + 1, 1) - timezone.timedelta(days=1)

            month_premiums = insurances.filter(
                start_date__lte=month_end.date(),
                end_date__gte=month_start.date()
            ).aggregate(total=Sum('total_premium'))['total'] or Decimal('0.00')

            monthly_data.append({
                'month': month,
                'year': year,
                'total_premium': float(month_premiums)
            })

        return monthly_data

    @staticmethod
    def get_insurance_by_insurer(institution):
        """
        Resumen de seguros agrupados por aseguradora.
        """
        return Insurer.objects.filter(
            institution=institution,
            is_active=True
        ).annotate(
            insurance_count=Count('insurances'),
            active_credits_count=Count(
                'insurances__credit_insurances',
                filter=Q(insurances__credit_insurances__status__in=[
                    CreditInsuranceStatus.ACTIVE,
                    CreditInsuranceStatus.EXPIRING_SOON
                ])
            ),
            total_premium=Sum('insurances__credit_insurances__total_premium'),
        ).order_by('-insurance_count')

    @staticmethod
    def get_credits_without_insurance(institution):
        """
        Créditos que no tienen seguro obligatorio asociado.
        """
        from api.loans.models_active import ActiveCredit

        active_credits = ActiveCredit.objects.filter(
            institution=institution,
            status__in=['ACTIVE', 'PENDING_PAYMENT', 'IN_ARREARS']
        )

        credits_without_insurance = []
        for credit in active_credits:
            if not credit.insurances.exists():
                credits_without_insurance.append({
                    'credit_id': credit.id,
                    'credit_number': credit.credit_number,
                    'client_name': credit.client.get_full_name() if hasattr(credit.client, 'get_full_name') else str(credit.client),
                    'product_name': credit.product.name if credit.product else None,
                    'disbursement_date': credit.disbursement_date,
                })

        return credits_without_insurance
