"""
Servicio de aplicación de pagos a créditos activos.

Implementa el algoritmo FIFO único para ambos canales (presencial y online).
Distribuye el monto del pago: penalidad → interés → seguro → comisión → capital.
"""

import logging
from decimal import Decimal, ROUND_HALF_UP
from django.db import transaction
from django.utils import timezone

from api.audit.models import AuditLog

logger = logging.getLogger(__name__)


class PaymentApplicationService:
    """
    Servicio central para aplicar pagos a créditos activos.

    Este es el ÚNICO punto de entrada para aplicar pagos,
    tanto presenciales como online.
    """

    @classmethod
    def apply_payment(cls, payment) -> 'CreditPayment':
        """
        Aplica un pago confirmado al crédito activo.

        Algoritmo FIFO:
        1. Obtener cuotas pendientes/vencidas ordenadas por installment_number
        2. Para cada cuota, distribuir: penalidad → interés → seguro → comisión → capital
        3. Actualizar paid_amount, status, closing_balance de cada cuota
        4. Actualizar saldos del active_credit (total_paid, principal_paid, etc.)
        5. Marcar payment como CONFIRMED
        6. Refrescar estado del crédito
        7. Registrar auditoría

        Args:
            payment: Instancia de CreditPayment en estado PENDING_CONFIRMATION

        Returns:
            CreditPayment confirmado

        Raises:
            ValueError: Si el pago no está en PENDING_CONFIRMATION o ya fue procesado
        """
        from api.loans.models_active import (
            CreditPayment, CreditPaymentAllocation, CreditInstallment,
        )

        if payment.status != CreditPayment.Status.PENDING_CONFIRMATION:
            raise ValueError(
                f"El pago debe estar en PENDING_CONFIRMATION. Estado actual: {payment.status}"
            )

        active_credit = payment.active_credit
        remaining = payment.amount

        if remaining <= Decimal('0'):
            raise ValueError("El monto del pago debe ser mayor a cero.")

        with transaction.atomic():
            # Bloquear el active_credit para evitar race conditions
            from api.loans.models_active import ActiveCredit
            active_credit = ActiveCredit.objects.select_for_update().get(pk=active_credit.pk)

            # Obtener cuotas pendientes ordenadas por número
            pending_installments = active_credit.installments.filter(
                status__in=['PENDING', 'PARTIAL', 'OVERDUE', 'IN_GRACE']
            ).order_by('installment_number').select_for_update()

            total_principal = Decimal('0')
            total_interest = Decimal('0')
            total_insurance = Decimal('0')
            total_fee = Decimal('0')
            total_penalty = Decimal('0')

            for installment in pending_installments:
                if remaining <= Decimal('0'):
                    break

                alloc_penalty = Decimal('0')
                alloc_interest = Decimal('0')
                alloc_insurance = Decimal('0')
                alloc_fee = Decimal('0')
                alloc_principal = Decimal('0')

                # 1. Penalidad primero
                if remaining > Decimal('0') and installment.penalty_amount > Decimal('0'):
                    alloc_penalty = min(remaining, installment.penalty_amount)
                    remaining -= alloc_penalty
                    total_penalty += alloc_penalty

                # 2. Interés
                if remaining > Decimal('0') and installment.interest_amount > Decimal('0'):
                    alloc_interest = min(remaining, installment.interest_amount)
                    remaining -= alloc_interest
                    total_interest += alloc_interest

                # 3. Seguro
                if remaining > Decimal('0') and installment.insurance_amount > Decimal('0'):
                    alloc_insurance = min(remaining, installment.insurance_amount)
                    remaining -= alloc_insurance
                    total_insurance += alloc_insurance

                # 4. Comisión
                if remaining > Decimal('0') and installment.fee_amount > Decimal('0'):
                    alloc_fee = min(remaining, installment.fee_amount)
                    remaining -= alloc_fee
                    total_fee += alloc_fee

                # 5. Capital
                if remaining > Decimal('0') and installment.principal_amount > Decimal('0'):
                    alloc_principal = min(remaining, installment.principal_amount)
                    remaining -= alloc_principal
                    total_principal += alloc_principal

                total_applied = (alloc_principal + alloc_interest + alloc_insurance +
                                alloc_fee + alloc_penalty)

                if total_applied <= Decimal('0'):
                    continue

                # Crear allocation
                CreditPaymentAllocation.objects.create(
                    institution=active_credit.institution,
                    payment=payment,
                    installment=installment,
                    amount_applied=total_applied,
                    principal_covered=alloc_principal,
                    interest_covered=alloc_interest,
                    insurance_covered=alloc_insurance,
                    fee_covered=alloc_fee,
                    penalty_covered=alloc_penalty,
                )

                # Actualizar cuota
                installment.paid_amount += total_applied
                installment.penalty_amount -= alloc_penalty
                if installment.penalty_amount < Decimal('0'):
                    installment.penalty_amount = Decimal('0')

                # Determinar nuevo estado de la cuota
                if installment.paid_amount >= (installment.total_amount + installment.penalty_amount):
                    installment.status = CreditInstallment.Status.PAID
                    installment.paid_at = timezone.now()
                elif installment.paid_amount > Decimal('0'):
                    installment.status = CreditInstallment.Status.PARTIAL

                # Actualizar closing_balance
                installment.closing_balance = max(
                    installment.opening_balance - alloc_principal,
                    Decimal('0')
                )
                installment.days_overdue = 0

                installment.save()

            # Actualizar saldos del active_credit
            active_credit.total_paid += payment.amount
            active_credit.principal_paid += total_principal
            active_credit.interest_paid += total_interest
            active_credit.fees_paid += total_fee
            active_credit.penalty_paid += total_penalty
            active_credit.current_balance -= total_principal

            if active_credit.current_balance < Decimal('0'):
                active_credit.current_balance = Decimal('0')

            # Actualizar próxima fecha de pago
            next_pending = active_credit.installments.filter(
                status__in=['PENDING', 'PARTIAL', 'OVERDUE', 'IN_GRACE']
            ).order_by('installment_number').first()

            if next_pending:
                active_credit.next_due_date = next_pending.due_date
            else:
                active_credit.next_due_date = None

            active_credit.save()

            # Confirmar pago
            payment.status = CreditPayment.Status.CONFIRMED
            payment.confirmed_at = timezone.now()
            payment.save()

            # Refrescar estado del crédito
            from api.loans.services.active_credit_service import ActiveCreditService
            ActiveCreditService.refresh_status(active_credit)

            # Auditoría
            cls._audit_payment(
                payment=payment,
                description=f'Pago aplicado: {payment.amount} {payment.currency.code} - '
                           f'Principal: {total_principal}, Interés: {total_interest}',
                metadata={
                    'payment_id': payment.id,
                    'channel': payment.channel,
                    'amount': str(payment.amount),
                    'principal_covered': str(total_principal),
                    'interest_covered': str(total_interest),
                    'insurance_covered': str(total_insurance),
                    'fee_covered': str(total_fee),
                    'penalty_covered': str(total_penalty),
                }
            )

            logger.info(
                f"Pago {payment.id} aplicado a {active_credit.credit_number}: "
                f"{payment.amount} ({payment.get_channel_display()})"
            )

        return payment

    @classmethod
    def reverse_payment(cls, payment, user=None, reason='') -> 'CreditPayment':
        """
        Revierte un pago previamente confirmado.

        Args:
            payment: Instancia de CreditPayment confirmado
            user: Usuario que revierte
            reason: Motivo de la reversión

        Returns:
            CreditPayment con estado REVERSED
        """
        from api.loans.models_active import CreditPayment

        if payment.status != CreditPayment.Status.CONFIRMED:
            raise ValueError(f"Solo pagos CONFIRMED pueden ser revertidos. Estado: {payment.status}")

        active_credit = payment.active_credit

        with transaction.atomic():
            # Bloquear registros
            from api.loans.models_active import ActiveCredit
            active_credit = ActiveCredit.objects.select_for_update().get(pk=active_credit.pk)

            # CALCULAR TOTALES ANTES de borrar allocations
            rev_principal = sum(
                a.principal_covered for a in payment.allocations.all()
            ).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP) if payment.allocations.exists() else Decimal('0')
            rev_interest = sum(
                a.interest_covered for a in payment.allocations.all()
            ).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP) if payment.allocations.exists() else Decimal('0')
            rev_insurance = sum(
                a.insurance_covered for a in payment.allocations.all()
            ).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP) if payment.allocations.exists() else Decimal('0')
            rev_fee = sum(
                a.fee_covered for a in payment.allocations.all()
            ).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP) if payment.allocations.exists() else Decimal('0')
            rev_penalty = sum(
                a.penalty_covered for a in payment.allocations.all()
            ).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP) if payment.allocations.exists() else Decimal('0')

            # Deshacer allocations
            for alloc in payment.allocations.all():
                installment = alloc.installment
                installment.paid_amount -= alloc.amount_applied
                installment.penalty_amount += alloc.penalty_covered

                if installment.paid_amount <= Decimal('0'):
                    installment.paid_amount = Decimal('0')
                    installment.status = 'PENDING'
                    installment.paid_at = None
                elif installment.paid_amount < installment.total_amount:
                    installment.status = 'PARTIAL'

                installment.closing_balance += alloc.principal_covered
                installment.save()

            # Eliminar allocations (después de restaurar cuotas)
            payment.allocations.all().delete()

            # Revertir saldos con los totales pre-calculados
            active_credit.total_paid -= payment.amount
            active_credit.principal_paid -= rev_principal
            active_credit.interest_paid -= rev_interest
            active_credit.fees_paid -= rev_fee
            active_credit.penalty_paid -= rev_penalty
            active_credit.current_balance += rev_principal
            active_credit.save()

            # Marcar pago como REVERSED
            payment.status = CreditPayment.Status.REVERSED
            payment.save()

            # Refrescar estado
            from api.loans.services.active_credit_service import ActiveCreditService
            ActiveCreditService.refresh_status(active_credit)

            # Auditoría
            cls._audit_payment(
                payment=payment,
                action='update_full',
                description=f'Pago revertido: {payment.amount} - Motivo: {reason}',
                metadata={
                    'payment_id': payment.id,
                    'reversal_reason': reason,
                    'reversed_by': user.id if user else None,
                }
            )

        return payment

    @staticmethod
    def _audit_payment(payment, action='create', description='', metadata=None):
        """Registra auditoría de pago."""
        try:
            AuditLog.objects.create(
                user=payment.registered_by,
                action=action,
                resource_type='CreditPayment',
                resource_id=payment.id,
                institution=payment.active_credit.institution,
                description=description,
                severity='info',
                metadata=metadata or {},
            )
        except Exception as e:
            logger.error(f"Error registrando auditoría de pago: {e}", exc_info=True)
