"""
Servicio de reestructuración de créditos activos.

Permite modificar condiciones de un crédito activo:
- Nuevo plazo
- Nueva tasa de interés
- Nueva frecuencia de pago
- Nuevo sistema de amortización

NUNCA se borran cuotas históricas. Las cuotas pagadas se preservan,
las pendientes se marcan REPROGRAMMED y se genera nuevo cronograma.
"""

import logging
from decimal import Decimal
from django.db import transaction
from api.audit.models import AuditLog

logger = logging.getLogger(__name__)


class RestructuringService:
    """
    Servicio para simulación y aplicación de reestructuraciones.
    """

    @classmethod
    def preview_restructuring(cls, active_credit, new_terms: dict) -> dict:
        """
        Genera una vista previa del nuevo cronograma sin aplicar cambios.

        Args:
            active_credit: Instancia de ActiveCredit
            new_terms: Dict con los nuevos términos:
                - new_term_periods: int
                - new_interest_rate: Decimal
                - new_payment_frequency_id: int
                - new_amortization_system_id: int
                - new_first_payment_date: date

        Returns:
            Dict con:
                - current_summary: Resumen de condiciones actuales
                - new_summary: Resumen de condiciones propuestas
                - preview_schedule: Lista de cuotas simuladas
                - comparison: Comparación lado a lado
        """
        from api.loans.services.amortization_calculation_service import AmortizationCalculationService
        from api.loans.models_catalogs import PaymentFrequency, AmortizationSystem

        # Resolver catálogos
        freq = active_credit.payment_frequency
        amsys = active_credit.amortization_system
        payments_per_year = active_credit.payment_frequency.payments_per_year

        if new_terms.get('new_payment_frequency_id'):
            freq = PaymentFrequency.objects.get(pk=new_terms['new_payment_frequency_id'])
            payments_per_year = freq.payments_per_year

        if new_terms.get('new_amortization_system_id'):
            amsys = AmortizationSystem.objects.get(pk=new_terms['new_amortization_system_id'])

        term = new_terms.get('new_term_periods') or active_credit.term_periods
        rate = new_terms.get('new_interest_rate') or active_credit.annual_interest_rate

        # Obtener saldo actual
        remaining_balance = active_credit.current_balance

        # Calcular nuevo cronograma
        preview = AmortizationCalculationService.preview_schedule(
            principal=remaining_balance,
            annual_rate=rate,
            term_periods=term,
            amortization_code=amsys.code,
            payments_per_year=payments_per_year,
        )

        # Resumen actual
        current_summary = {
            'balance': str(active_credit.current_balance),
            'term_periods': active_credit.term_periods,
            'interest_rate': str(active_credit.annual_interest_rate),
            'payment_frequency': active_credit.payment_frequency.name,
            'amortization_system': active_credit.amortization_system.name,
        }

        new_summary = {
            'balance': str(remaining_balance),
            'term_periods': term,
            'interest_rate': str(rate),
            'payment_frequency': freq.name,
            'amortization_system': amsys.name,
        }

        return {
            'current_summary': current_summary,
            'new_summary': new_summary,
            'preview_schedule': preview,
            'comparison': cls._compare_terms(current_summary, new_summary),
        }

    @classmethod
    def apply_restructuring(cls, active_credit, new_terms: dict, reason: str, user=None) -> 'CreditRestructuring':
        """
        Aplica una reestructuración al crédito activo.

        Pasos:
        1. Snapshot de condiciones originales
        2. Marcar cuotas pendientes como REPROGRAMMED
        3. Ajustar términos del ActiveCredit
        4. Generar nuevo cronograma
        5. Crear registro de reestructuración
        6. Actualizar estado
        7. Auditoría

        Args:
            active_credit: Instancia de ActiveCredit
            new_terms: Dict con nuevos términos
            reason: Motivo de la reestructuración
            user: Usuario que aplica

        Returns:
            CreditRestructuring creado
        """
        from api.loans.models_active import CreditRestructuring, ActiveCredit
        from api.loans.services.amortization_calculation_service import AmortizationCalculationService
        from api.loans.models_catalogs import PaymentFrequency, AmortizationSystem

        if active_credit.status == ActiveCredit.Status.CANCELLED:
            raise ValueError("No se puede reestructurar un crédito cancelado.")

        with transaction.atomic():
            # Bloquear el crédito
            active_credit = ActiveCredit.objects.select_for_update().get(pk=active_credit.pk)

            # 1. Snapshot de condiciones originales
            original_terms = {
                'term_periods': active_credit.term_periods,
                'interest_rate': str(active_credit.annual_interest_rate),
                'payment_frequency': active_credit.payment_frequency.code if active_credit.payment_frequency else None,
                'payment_frequency_id': active_credit.payment_frequency_id,
                'amortization_system': active_credit.amortization_system.code if active_credit.amortization_system else None,
                'amortization_system_id': active_credit.amortization_system_id,
                'first_payment_date': active_credit.first_payment_date.isoformat(),
                'maturity_date': active_credit.maturity_date.isoformat(),
            }

            # 2. Snapshot del cronograma actual (serializado como strings para JSON)
            previous_schedule = list(
                active_credit.installments.order_by('installment_number').values(
                    'installment_number', 'due_date', 'opening_balance',
                    'principal_amount', 'interest_amount', 'total_amount',
                    'paid_amount', 'closing_balance', 'status',
                )
            )
            # Convertir date/decimal a strings para JSON serialization
            for entry in previous_schedule:
                if 'due_date' in entry and entry['due_date']:
                    entry['due_date'] = entry['due_date'].isoformat()
                for key in ('opening_balance', 'principal_amount', 'interest_amount',
                           'total_amount', 'paid_amount', 'closing_balance'):
                    if key in entry and entry[key] is not None:
                        entry[key] = str(entry[key])

            # 3. Marcar cuotas pendientes como REPROGRAMMED
            pending_installments = active_credit.installments.filter(
                status__in=['PENDING', 'PARTIAL', 'OVERDUE', 'IN_GRACE'],
            )
            # Guardar la primera cuota no pagada para referencia
            first_reprogrammed = pending_installments.order_by('installment_number').first()
            pending_installments.update(status='REPROGRAMMED')

            # 4. Aplicar nuevos términos
            if new_terms.get('new_term_periods'):
                active_credit.term_periods = new_terms['new_term_periods']
            if new_terms.get('new_interest_rate') is not None:
                active_credit.annual_interest_rate = new_terms['new_interest_rate']
            if new_terms.get('new_payment_frequency_id'):
                freq = PaymentFrequency.objects.get(pk=new_terms['new_payment_frequency_id'])
                active_credit.payment_frequency = freq
            if new_terms.get('new_amortization_system_id'):
                amsys = AmortizationSystem.objects.get(pk=new_terms['new_amortization_system_id'])
                active_credit.amortization_system = amsys
            if new_terms.get('new_first_payment_date'):
                active_credit.first_payment_date = new_terms['new_first_payment_date']

            active_credit.save()

            # 5. Generar nuevo cronograma desde la primera cuota no pagada
            start_installment_number = first_reprogrammed.installment_number if first_reprogrammed else 1
            AmortizationCalculationService.recalculate_schedule(
                active_credit,
                from_installment_number=start_installment_number
            )

            # Actualizar maturity_date y next_due_date
            last_installment = active_credit.installments.order_by('-installment_number').first()
            next_pending = active_credit.installments.filter(
                status__in=['PENDING', 'PARTIAL', 'OVERDUE', 'IN_GRACE']
            ).order_by('installment_number').first()

            if last_installment:
                active_credit.maturity_date = last_installment.due_date
            if next_pending:
                active_credit.next_due_date = next_pending.due_date
            active_credit.save()

            # 6. Crear registro de reestructuración
            restructuring = CreditRestructuring.objects.create(
                institution=active_credit.institution,
                active_credit=active_credit,
                original_terms=original_terms,
                new_term_periods=new_terms.get('new_term_periods'),
                new_interest_rate=new_terms.get('new_interest_rate'),
                new_payment_frequency_id=new_terms.get('new_payment_frequency_id'),
                new_amortization_system_id=new_terms.get('new_amortization_system_id'),
                new_first_payment_date=new_terms.get('new_first_payment_date'),
                reason=reason,
                applied_by=user,
                previous_schedule_snapshot=previous_schedule,
                is_active=True,
            )

            # 7. Actualizar estado
            from api.loans.services.credit_status_service import CreditStatusService
            CreditStatusService.refresh_status(active_credit)

            # 8. Auditoría
            cls._audit(
                user=user,
                action='update_full',
                resource_type='CreditRestructuring',
                resource_id=restructuring.id,
                institution=active_credit.institution,
                description=f'Crédito reestructurado: {active_credit.credit_number}. '
                           f'Motivo: {reason}',
                metadata={
                    'credit_number': active_credit.credit_number,
                    'original_terms': original_terms,
                    'new_terms': {
                        'term_periods': new_terms.get('new_term_periods'),
                        'interest_rate': str(new_terms.get('new_interest_rate', '')),
                        'payment_frequency_id': new_terms.get('new_payment_frequency_id'),
                        'amortization_system_id': new_terms.get('new_amortization_system_id'),
                    },
                    'reason': reason,
                }
            )

            logger.info(
                f"Reestructuración aplicada a {active_credit.credit_number}"
            )

        return restructuring

    @staticmethod
    def _compare_terms(current: dict, new: dict) -> list:
        """
        Compara condiciones actuales vs nuevas lado a lado.

        Returns:
            Lista de dicts con diferencias
        """
        comparisons = []
        keys = ['term_periods', 'interest_rate', 'payment_frequency', 'amortization_system', 'balance']

        labels = {
            'term_periods': 'Plazo (cuotas)',
            'interest_rate': 'Tasa de interés (%)',
            'payment_frequency': 'Frecuencia de pago',
            'amortization_system': 'Sistema de amortización',
            'balance': 'Saldo a reestructurar',
        }

        for key in keys:
            comparisons.append({
                'field': key,
                'label': labels.get(key, key),
                'current': current.get(key, 'N/A'),
                'proposed': new.get(key, 'N/A'),
                'changed': str(current.get(key)) != str(new.get(key)),
            })

        return comparisons

    @staticmethod
    def _audit(user=None, action='', resource_type='', resource_id=None,
               institution=None, description='', metadata=None):
        """Registra evento de auditoría."""
        try:
            AuditLog.objects.create(
                user=user,
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                institution=institution,
                description=description,
                severity='warning',
                metadata=metadata or {},
            )
        except Exception as e:
            logger.error(f"Error en auditoría de reestructuración: {e}", exc_info=True)
