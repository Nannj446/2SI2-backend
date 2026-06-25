"""
Servicio de gestión de períodos de gracia.

Tipos de gracia:
- FULL_GRACE: No se cobra capital ni interés durante la gracia
- INTEREST_ONLY: Solo se pagan intereses
- PARTIAL_PAYMENT: Pago reducido
"""

import logging
from datetime import timedelta
from django.db import transaction
from django.utils import timezone

from api.audit.models import AuditLog

logger = logging.getLogger(__name__)


class GracePeriodService:
    """
    Servicio para aplicar y gestionar períodos de gracia.
    """

    @classmethod
    def apply_grace_period(cls, active_credit, grace_type, start_date, end_date,
                           reason, user=None) -> 'CreditGracePeriod':
        """
        Aplica un período de gracia al crédito activo.

        Args:
            active_credit: Instancia de ActiveCredit
            grace_type: Tipo de gracia (FULL_GRACE, INTEREST_ONLY, PARTIAL_PAYMENT)
            start_date: Fecha de inicio
            end_date: Fecha de fin
            reason: Motivo de la gracia
            user: Usuario que aplica

        Returns:
            CreditGracePeriod creado
        """
        from api.loans.models_active import CreditGracePeriod, ActiveCredit

        # Validar que no haya otra gracia activa
        active_gracia = active_credit.grace_periods.filter(is_active=True).first()
        if active_gracia:
            raise ValueError(
                f"El crédito ya tiene un período de gracia activo "
                f"({active_gracia.start_date} a {active_gracia.end_date})"
            )

        if start_date >= end_date:
            raise ValueError("La fecha de inicio debe ser anterior a la fecha de fin")

        with transaction.atomic():
            # Bloquear el crédito
            active_credit = ActiveCredit.objects.select_for_update().get(pk=active_credit.pk)

            # Marcar cuotas dentro del rango como IN_GRACE
            grace_installments = active_credit.installments.filter(
                due_date__gte=start_date,
                due_date__lte=end_date,
                status__in=['PENDING', 'PARTIAL', 'OVERDUE'],
            ).select_for_update()

            for installment in grace_installments:
                installment.status = 'IN_GRACE'
                installment.save(update_fields=['status', 'updated_at'])

            # Si es FULL_GRACE, desplazar fechas de cuotas posteriores
            if grace_type == 'FULL_GRACE':
                grace_duration = (end_date - start_date).days
                later_installments = active_credit.installments.filter(
                    due_date__gt=end_date,
                ).order_by('installment_number')

                for installment in later_installments:
                    installment.due_date = installment.due_date + timedelta(days=grace_duration)
                    installment.original_due_date = installment.due_date - timedelta(days=grace_duration)
                    installment.save(update_fields=['due_date', 'original_due_date', 'updated_at'])

                # Actualizar maturity_date
                last_installment = active_credit.installments.order_by('-installment_number').first()
                if last_installment:
                    active_credit.maturity_date = last_installment.due_date
                    active_credit.save(update_fields=['maturity_date', 'updated_at'])

            # Crear registro de gracia
            grace_period = CreditGracePeriod.objects.create(
                institution=active_credit.institution,
                active_credit=active_credit,
                grace_type=grace_type,
                start_date=start_date,
                end_date=end_date,
                reason=reason,
                applied_by=user,
                is_active=True,
                metadata={
                    'installments_affected': grace_installments.count(),
                }
            )

            # Actualizar estado
            from api.loans.services.credit_status_service import CreditStatusService
            CreditStatusService.refresh_status(active_credit)

            # Auditoría
            cls._audit(
                user=user,
                action='create',
                resource_type='CreditGracePeriod',
                resource_id=grace_period.id,
                institution=active_credit.institution,
                description=f'Período de gracia aplicado: {grace_type} '
                           f'({start_date} a {end_date})',
                metadata={
                    'grace_type': grace_type,
                    'start_date': start_date.isoformat(),
                    'end_date': end_date.isoformat(),
                    'reason': reason,
                }
            )

            logger.info(
                f"Gracia aplicada a {active_credit.credit_number}: "
                f"{grace_type} ({start_date} → {end_date})"
            )

        return grace_period

    @classmethod
    def end_grace_period(cls, grace_period, user=None) -> None:
        """
        Finaliza un período de gracia activo.

        Args:
            grace_period: Instancia de CreditGracePeriod
            user: Usuario que finaliza
        """
        if not grace_period.is_active:
            raise ValueError("El período de gracia ya está inactivo.")

        with transaction.atomic():
            grace_period.is_active = False
            grace_period.save(update_fields=['is_active', 'updated_at'])

            # Restaurar estado de cuotas afectadas
            grace_period.active_credit.installments.filter(
                status='IN_GRACE',
                due_date__lte=grace_period.end_date,
            ).update(status='PENDING')

            # Refrescar estado
            from api.loans.services.credit_status_service import CreditStatusService
            CreditStatusService.refresh_status(grace_period.active_credit)

            logger.info(f"Período de gracia {grace_period.id} finalizado")

    @classmethod
    def _audit(cls, user=None, action='', resource_type='', resource_id=None,
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
                severity='info',
                metadata=metadata or {},
            )
        except Exception as e:
            logger.error(f"Error en auditoría de gracia: {e}", exc_info=True)
