"""
Servicio de actualización de estados de créditos activos.

Reglas de negocio para determinar el estado:
- Saldo = 0 → CANCELLED
- Reestructuración activa → RESTRUCTURED
- Período de gracia activo → IN_GRACE_PERIOD
- Cuota vencida sin pago → IN_ARREARS
- Ninguna de las anteriores → ACTIVE
"""

import logging
from decimal import Decimal
from django.utils import timezone

logger = logging.getLogger(__name__)


class CreditStatusService:
    """
    Servicio para el cálculo y actualización automática de estados.
    """

    @classmethod
    def refresh_status(cls, active_credit) -> str:
        """
        Refresca el estado de un crédito activo.

        Reglas de decisión (en orden de prioridad):
        1. Saldo insoluto = 0 → CANCELLED (prevalece sobre todo)
        2. Reestructuración activa → RESTRUCTURED
        3. Período de gracia activo vigente → IN_GRACE_PERIOD
        4. Cuotas vencidas → IN_ARREARS
        5. Por defecto → ACTIVE

        Args:
            active_credit: Instancia de ActiveCredit

        Returns:
            str: Nuevo estado
        """
        from api.loans.models_active import ActiveCredit, CreditStatusHistory

        old_status = active_credit.status
        new_status = cls._determine_status(active_credit)

        if new_status != old_status:
            active_credit.status = new_status
            active_credit.save(update_fields=['status', 'updated_at'])

            CreditStatusHistory.objects.create(
                institution=active_credit.institution,
                active_credit=active_credit,
                previous_status=old_status,
                new_status=new_status,
                reason='Actualización automática',
                metadata={'trigger': 'credit_status_service'},
            )

            logger.info(
                f"[StatusRefresh] {active_credit.credit_number}: "
                f"{old_status} → {new_status}"
            )

        # Siempre actualizar días en mora
        cls._update_days_in_arrears(active_credit)

        return new_status

    @classmethod
    def refresh_all_active_credits(cls, institution=None) -> int:
        """
        Refresca el estado de todos los créditos activos.

        Args:
            institution: Opcional, filtrar por FinancialInstitution

        Returns:
            int: Cantidad de créditos cuyo estado cambió
        """
        from api.loans.models_active import ActiveCredit

        queryset = ActiveCredit.objects.select_related(
            'payment_frequency', 'amortization_system', 'currency'
        ).exclude(status=ActiveCredit.Status.CANCELLED)

        if institution:
            queryset = queryset.filter(institution=institution)

        updated_count = 0
        for credit in queryset.iterator(chunk_size=100):
            old = credit.status
            new = cls.refresh_status(credit)
            if new != old:
                updated_count += 1

        logger.info(f"[MassRefresh] {updated_count} créditos actualizados")

        return updated_count

    @classmethod
    def _determine_status(cls, active_credit) -> str:
        """
        Determina el estado correcto según reglas de negocio.

        Orden de evaluación:
        1. CANCELLED (saldo = 0)
        2. RESTRUCTURED (si tiene restructuraciones activas)
        3. IN_GRACE_PERIOD (período de gracia vigente)
        4. IN_ARREARS (cuotas vencidas)
        5. ACTIVE (por defecto)
        """
        from api.loans.models_active import ActiveCredit

        today = timezone.now().date()

        # 1. Saldo cero → cancelado
        if active_credit.current_balance <= Decimal('0'):
            return ActiveCredit.Status.CANCELLED

        # 2. Reestructuración activa
        if active_credit.restructurings.filter(is_active=True).exists():
            return ActiveCredit.Status.RESTRUCTURED

        # 3. Período de gracia activo y vigente
        active_grace = active_credit.grace_periods.filter(
            is_active=True,
            start_date__lte=today,
            end_date__gte=today,
        ).exists()
        if active_grace:
            return ActiveCredit.Status.IN_GRACE_PERIOD

        # 4. Cuotas vencidas
        has_overdue = active_credit.installments.filter(
            status__in=['PENDING', 'PARTIAL', 'OVERDUE'],
            due_date__lt=today,
        ).exists()

        if has_overdue:
            return ActiveCredit.Status.IN_ARREARS

        # 5. Por defecto
        return ActiveCredit.Status.ACTIVE

    @classmethod
    def _update_days_in_arrears(cls, active_credit):
        """
        Calcula y actualiza los días en mora del crédito.

        Busca la cuota vencida más antigua y calcula la diferencia.
        """
        today = timezone.now().date()

        oldest_overdue = active_credit.installments.filter(
            status__in=['PENDING', 'PARTIAL', 'OVERDUE'],
            due_date__lt=today,
        ).order_by('due_date').first()

        if oldest_overdue:
            days = max((today - oldest_overdue.due_date).days, 0)
            if days != active_credit.days_in_arrears:
                active_credit.days_in_arrears = days
                active_credit.save(update_fields=['days_in_arrears', 'updated_at'])
        elif active_credit.days_in_arrears != 0:
            active_credit.days_in_arrears = 0
            active_credit.save(update_fields=['days_in_arrears', 'updated_at'])
