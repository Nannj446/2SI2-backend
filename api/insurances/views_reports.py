"""
Views para Reportes de Seguros.
"""
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema

from .services.report_service import InsuranceReportService


def get_tenant_filter(self):
    """Obtiene el filtro de tenant según el tipo de usuario."""
    if hasattr(self, 'request') and hasattr(self.request, 'tenant'):
        if self.request.tenant is not None:
            return self.request.tenant.id
    return None


class InsuranceSummaryReportView(APIView):
    """
    Resumen general de seguros de la institución.
    """
    permission_classes = []  # Se maneja en el serializer/permission

    @extend_schema(
        responses={200: {
            'type': 'object',
            'properties': {
                'total_insurances': {'type': 'integer'},
                'active_insurances': {'type': 'integer'},
                'expiring_soon_insurances': {'type': 'integer'},
                'total_premium': {'type': 'number'},
                'total_paid': {'type': 'number'},
            }
        }},
        description='Resumen de seguros activos de la institución'
    )
    def get(self, request):
        tenant_id = get_tenant_filter(self)
        if tenant_id is None:
            return Response(
                {'error': 'No se pudo identificar la institución'},
                status=status.HTTP_400_BAD_REQUEST
            )

        from api.tenants.models import FinancialInstitution
        institution = FinancialInstitution.objects.get(id=tenant_id)

        data = InsuranceReportService.get_active_insurances_summary(institution)
        return Response(data)


class InsuranceExpiringSoonReportView(APIView):
    """
    Reporte de seguros próximos a vencer.
    """
    permission_classes = []

    @extend_schema(
        parameters=[{
            'name': 'days',
            'in': 'query',
            'schema': {'type': 'integer', 'default': 30}
        }],
        description='Lista de seguros próximos a vencer'
    )
    def get(self, request):
        tenant_id = get_tenant_filter(self)
        if tenant_id is None:
            return Response(
                {'error': 'No se pudo identificar la institución'},
                status=status.HTTP_400_BAD_REQUEST
            )

        from api.tenants.models import FinancialInstitution
        institution = FinancialInstitution.objects.get(id=tenant_id)

        days = int(request.query_params.get('days', 30))
        insurances = InsuranceReportService.get_insurances_expiring_soon(institution, days)

        data = []
        for insurance in insurances:
            data.append({
                'id': insurance.id,
                'policy_number': insurance.policy_number,
                'insurance_name': insurance.insurance.name,
                'insurance_type': insurance.insurance.insurance_type,
                'insurer_name': insurance.insurance.insurer.name,
                'credit_number': insurance.active_credit.credit_number,
                'start_date': insurance.start_date,
                'end_date': insurance.end_date,
                'days_until_expiry': insurance.days_until_expiry,
                'total_premium': float(insurance.total_premium),
            })

        return Response(data)


class InsuranceExpiredReportView(APIView):
    """
    Reporte de seguros vencidos.
    """
    permission_classes = []

    def get(self, request):
        tenant_id = get_tenant_filter(self)
        if tenant_id is None:
            return Response(
                {'error': 'No se pudo identificar la institución'},
                status=status.HTTP_400_BAD_REQUEST
            )

        from api.tenants.models import FinancialInstitution
        institution = FinancialInstitution.objects.get(id=tenant_id)

        insurances = InsuranceReportService.get_expired_insurances(institution)

        data = []
        for insurance in insurances:
            data.append({
                'id': insurance.id,
                'policy_number': insurance.policy_number,
                'insurance_name': insurance.insurance.name,
                'insurance_type': insurance.insurance.insurance_type,
                'insurer_name': insurance.insurance.insurer.name,
                'credit_number': insurance.active_credit.credit_number,
                'start_date': insurance.start_date,
                'end_date': insurance.end_date,
                'days_overdue': -insurance.days_until_expiry if insurance.days_until_expiry < 0 else 0,
                'total_premium': float(insurance.total_premium),
            })

        return Response(data)


class InsuranceDistributionByTypeView(APIView):
    """
    Distribución de seguros por tipo.
    """
    permission_classes = []

    def get(self, request):
        tenant_id = get_tenant_filter(self)
        if tenant_id is None:
            return Response(
                {'error': 'No se pudo identificar la institución'},
                status=status.HTTP_400_BAD_REQUEST
            )

        from api.tenants.models import FinancialInstitution
        institution = FinancialInstitution.objects.get(id=tenant_id)

        distribution = InsuranceReportService.get_insurance_distribution_by_type(institution)

        return Response(list(distribution))


class InsurancePremiumsByMonthView(APIView):
    """
    Primas cobradas por mes.
    """
    permission_classes = []

    @extend_schema(
        parameters=[{
            'name': 'year',
            'in': 'query',
            'schema': {'type': 'integer'}
        }],
        description='Primas cobradas por mes en un año'
    )
    def get(self, request):
        tenant_id = get_tenant_filter(self)
        if tenant_id is None:
            return Response(
                {'error': 'No se pudo identificar la institución'},
                status=status.HTTP_400_BAD_REQUEST
            )

        from api.tenants.models import FinancialInstitution
        institution = FinancialInstitution.objects.get(id=tenant_id)

        year = request.query_params.get('year')
        year = int(year) if year else None

        data = InsuranceReportService.get_premiums_collected_by_month(institution, year)

        return Response(data)


class InsuranceByInsurerView(APIView):
    """
    Resumen de seguros agrupados por aseguradora.
    """
    permission_classes = []

    def get(self, request):
        tenant_id = get_tenant_filter(self)
        if tenant_id is None:
            return Response(
                {'error': 'No se pudo identificar la institución'},
                status=status.HTTP_400_BAD_REQUEST
            )

        from api.tenants.models import FinancialInstitution
        institution = FinancialInstitution.objects.get(id=tenant_id)

        insurers = InsuranceReportService.get_insurance_by_insurer(institution)

        data = []
        for insurer in insurers:
            data.append({
                'id': insurer.id,
                'name': insurer.name,
                'code': insurer.code,
                'insurance_count': insurer.insurance_count,
                'active_credits_count': insurer.active_credits_count or 0,
                'total_premium': float(insurer.total_premium or 0),
            })

        return Response(data)


class CreditsWithoutInsuranceView(APIView):
    """
    Créditos sin seguro obligatorio.
    """
    permission_classes = []

    def get(self, request):
        tenant_id = get_tenant_filter(self)
        if tenant_id is None:
            return Response(
                {'error': 'No se pudo identificar la institución'},
                status=status.HTTP_400_BAD_REQUEST
            )

        from api.tenants.models import FinancialInstitution
        institution = FinancialInstitution.objects.get(id=tenant_id)

        credits = InsuranceReportService.get_credits_without_insurance(institution)

        return Response(credits)
