"""
Servicio de consulta a buró de crédito (SP3-93).

Provee interfaz abstracta para múltiples proveedores de buró.
"""

import logging
import time
from django.utils import timezone
from decimal import Decimal
from typing import Optional

from api.loans.models_scoring import CreditBureauQuery

logger = logging.getLogger(__name__)


class CreditBureauError(Exception):
    """Error en consulta a buró de crédito."""
    pass


class BaseBureauProvider:
    """Clase base para proveedores de buró."""

    provider_code: str = ''

    def query(self, application) -> dict:
        raise NotImplementedError


class SimulatedBureauProvider(BaseBureauProvider):
    """
    Proveedor simulado para desarrollo/testing.

    Retorna datos ficticios pero realistas basados en los datos
    de la solicitud.
    """

    provider_code = 'SIMULATED'

    def query(self, application) -> dict:
        monthly_income = float(application.monthly_income or 0)
        amount = float(application.requested_amount)

        # Score inversamente proporcional al monto vs ingreso
        income_ratio = min(amount / max(monthly_income, 1), 10)
        base_score = max(300, min(800, int(800 - (income_ratio * 50))))

        # Deuda total simulada
        debt_total = monthly_income * Decimal(str(round(0.3 + (income_ratio * 0.05), 2)))

        # Categoría CIC basada en score
        if base_score >= 700:
            cic = 'A'
        elif base_score >= 600:
            cic = 'B'
        elif base_score >= 450:
            cic = 'C'
        else:
            cic = 'D'

        return {
            'score': base_score,
            'debt_total': debt_total,
            'has_defaults': base_score < 400,
            'default_details': {} if base_score >= 400 else {
                'days_overdue': 120,
                'amount_defaulted': debt_total * Decimal('0.3'),
                'entities': ['Banco Simulado S.A.']
            },
            'cic_category': cic,
            'raw_response': {
                'provider': 'SIMULATED',
                'query_id': f'SIM-{application.id}-{int(time.time())}',
                'timestamp': timezone.now().isoformat()
            }
        }


class CreditBureauService:
    """
    Servicio principal de consulta a buró.

    Maneja la selección de proveedor, registro de consultas y caché.
    """

    PROVIDER_MAP = {
        'SIMULATED': SimulatedBureauProvider,
    }

    @classmethod
    def get_provider(cls, provider_code: str = 'SIMULATED') -> BaseBureauProvider:
        """
        Obtiene una instancia del proveedor de buró.

        Args:
            provider_code: Código del proveedor

        Returns:
            BaseBureauProvider: Instancia del proveedor
        """
        provider_class = cls.PROVIDER_MAP.get(provider_code)
        if not provider_class:
            raise CreditBureauError(f"Proveedor no soportado: {provider_code}")
        return provider_class()

    @classmethod
    def query_bureau(cls, application, provider_code: str = 'SIMULATED') -> CreditBureauQuery:
        """
        Ejecuta consulta a buró y registra el resultado.

        Args:
            application: LoanApplication instance
            provider_code: Código del proveedor

        Returns:
            CreditBureauQuery: Registro de la consulta
        """
        provider = cls.get_provider(provider_code)

        bureau_query = CreditBureauQuery.objects.create(
            institution=application.institution,
            application=application,
            provider=provider_code,
            status=CreditBureauQuery.QueryStatus.PENDING,
            query_data={
                'client_id': application.client_id,
                'document_number': application.client.document_number,
                'full_name': application.client.get_full_name(),
                'amount': str(application.requested_amount),
                'term_months': application.term_months,
            }
        )

        start_time = time.time()

        try:
            result = provider.query(application)

            bureau_query.status = CreditBureauQuery.QueryStatus.SUCCESS
            bureau_query.score_external = result.get('score')
            bureau_query.debt_total = result.get('debt_total')
            bureau_query.has_defaults = result.get('has_defaults')
            bureau_query.default_details = result.get('default_details', {})
            bureau_query.cic_category = result.get('cic_category')
            bureau_query.response_data = result.get('raw_response', {})
            bureau_query.queried_at = timezone.now()
            bureau_query.response_time_ms = int((time.time() - start_time) * 1000)
            bureau_query.save()

            logger.info(
                f"[BUREAU] Consulta exitosa: {application.application_number} "
                f"via {provider_code}, score={result.get('score')}"
            )

        except Exception as e:
            bureau_query.status = CreditBureauQuery.QueryStatus.FAILED
            bureau_query.error_message = str(e)
            bureau_query.response_time_ms = int((time.time() - start_time) * 1000)
            bureau_query.save()

            logger.error(f"[BUREAU] Error consultando {provider_code}: {str(e)}")
            raise CreditBureauError(f"Error consultando buró: {str(e)}")

        return bureau_query
