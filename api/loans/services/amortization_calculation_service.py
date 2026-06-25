"""
Servicio de cálculo de amortización para créditos activos.

Soporta tres sistemas:
- Francés (cuota fija)
- Alemán (capital fijo)
- Americano (solo intereses, capital al final)

Y múltiples frecuencias de pago: mensual, quincenal, semanal.
"""

import logging
from decimal import Decimal, ROUND_HALF_UP
from datetime import timedelta, date
from typing import List, Dict, Optional
from django.db import transaction

logger = logging.getLogger(__name__)


class AmortizationCalculationService:
    """
    Servicio de cálculo de tablas de amortización.

    Fórmulas base:
      Sistema Francés: PMT = P * (i*(1+i)^n) / ((1+i)^n - 1)
      Sistema Alemán: Capital fijo = P / n, interés decreciente
      Sistema Americano: Interés fijo = P*i, capital al final
    """

    @staticmethod
    def calculate_french(
        principal: Decimal,
        annual_rate: Decimal,
        term_periods: int,
        payments_per_year: int,
        insurance_rate: Decimal = Decimal('0'),
        fee_amount: Decimal = Decimal('0'),
    ) -> List[Dict]:
        """
        Calcula tabla de amortización por sistema francés (cuota fija).

        Args:
            principal: Monto del préstamo
            annual_rate: Tasa de interés anual en porcentaje (ej: 18.5)
            term_periods: Número total de cuotas
            payments_per_year: Pagos por año (12=Mensual, 24=Quincenal, 52=Semanal)
            insurance_rate: Tasa de seguro anual en porcentaje
            fee_amount: Comisión fija por cuota

        Returns:
            Lista de dicts con el cronograma de cuotas
        """
        if principal <= Decimal('0') or term_periods <= 0:
            raise ValueError("Principal debe ser > 0 y term_periods >= 1")

        periodic_rate = (annual_rate / Decimal('100')) / Decimal(str(payments_per_year))
        periodic_insurance_rate = (insurance_rate / Decimal('100')) / Decimal(str(payments_per_year))

        # Fórmula de cuota fija (PMT)
        if periodic_rate > Decimal('0'):
            factor = (Decimal('1') + periodic_rate) ** term_periods
            installment_amount = principal * (periodic_rate * factor) / (factor - Decimal('1'))
        else:
            installment_amount = principal / Decimal(str(term_periods))

        installment_amount = installment_amount.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

        schedule = []
        balance = principal

        for period in range(1, term_periods + 1):
            is_last = (period == term_periods)

            interest = (balance * periodic_rate).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            insurance = (balance * periodic_insurance_rate).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

            if is_last:
                # Última cuota: capital es el saldo pendiente exacto
                principal_amt = balance
                total = (principal_amt + interest + insurance + fee_amount).quantize(
                    Decimal('0.01'), rounding=ROUND_HALF_UP
                )
            else:
                principal_amt = (installment_amount - interest - insurance - fee_amount).quantize(
                    Decimal('0.01'), rounding=ROUND_HALF_UP
                )
                if principal_amt < Decimal('0'):
                    principal_amt = Decimal('0')
                total = installment_amount + insurance + fee_amount

            balance = (balance - principal_amt).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            if balance < Decimal('0'):
                balance = Decimal('0')

            schedule.append({
                'period': period,
                'opening_balance': (balance + principal_amt).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP),
                'principal_amount': principal_amt,
                'interest_amount': interest,
                'insurance_amount': insurance,
                'fee_amount': fee_amount,
                'penalty_amount': Decimal('0'),
                'total_amount': total,
                'closing_balance': balance,
            })

            if balance <= Decimal('0') and not is_last:
                break

        return schedule

    @staticmethod
    def calculate_german(
        principal: Decimal,
        annual_rate: Decimal,
        term_periods: int,
        payments_per_year: int,
        insurance_rate: Decimal = Decimal('0'),
        fee_amount: Decimal = Decimal('0'),
    ) -> List[Dict]:
        """
        Calcula tabla de amortización por sistema alemán (capital fijo).

        El capital amortizado en cada cuota es constante = principal / n.
        Los intereses se calculan sobre el saldo pendiente, decreciendo.
        """
        if principal <= Decimal('0') or term_periods <= 0:
            raise ValueError("Principal debe ser > 0 y term_periods >= 1")

        periodic_rate = (annual_rate / Decimal('100')) / Decimal(str(payments_per_year))
        periodic_insurance_rate = (insurance_rate / Decimal('100')) / Decimal(str(payments_per_year))

        fixed_principal = (principal / Decimal(str(term_periods))).quantize(
            Decimal('0.01'), rounding=ROUND_HALF_UP
        )

        schedule = []
        balance = principal

        for period in range(1, term_periods + 1):
            is_last = (period == term_periods)

            interest = (balance * periodic_rate).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            insurance = (balance * periodic_insurance_rate).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

            if is_last:
                principal_amt = balance
            else:
                principal_amt = fixed_principal

            total = (principal_amt + interest + insurance + fee_amount).quantize(
                Decimal('0.01'), rounding=ROUND_HALF_UP
            )

            balance = (balance - principal_amt).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            if balance < Decimal('0'):
                balance = Decimal('0')

            schedule.append({
                'period': period,
                'opening_balance': (balance + principal_amt).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP),
                'principal_amount': principal_amt,
                'interest_amount': interest,
                'insurance_amount': insurance,
                'fee_amount': fee_amount,
                'penalty_amount': Decimal('0'),
                'total_amount': total,
                'closing_balance': balance,
            })

            if balance <= Decimal('0') and not is_last:
                break

        return schedule

    @staticmethod
    def calculate_american(
        principal: Decimal,
        annual_rate: Decimal,
        term_periods: int,
        payments_per_year: int,
        insurance_rate: Decimal = Decimal('0'),
        fee_amount: Decimal = Decimal('0'),
    ) -> List[Dict]:
        """
        Calcula tabla de amortización por sistema americano (solo intereses).

        Durante n-1 períodos se pagan SOLO intereses + seguro + comisión.
        El capital total se paga en la última cuota.
        """
        if principal <= Decimal('0') or term_periods <= 1:
            raise ValueError("Principal debe ser > 0 y term_periods >= 2")

        periodic_rate = (annual_rate / Decimal('100')) / Decimal(str(payments_per_year))
        periodic_insurance_rate = (insurance_rate / Decimal('100')) / Decimal(str(payments_per_year))

        fixed_interest = (principal * periodic_rate).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        fixed_insurance = (principal * periodic_insurance_rate).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

        schedule = []
        balance = principal

        for period in range(1, term_periods + 1):
            is_last = (period == term_periods)

            if is_last:
                principal_amt = balance
                interest = fixed_interest
                insurance = fixed_insurance
            else:
                principal_amt = Decimal('0')
                interest = fixed_interest
                insurance = fixed_insurance

            total = (principal_amt + interest + insurance + fee_amount).quantize(
                Decimal('0.01'), rounding=ROUND_HALF_UP
            )

            balance = (balance - principal_amt).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            if balance < Decimal('0'):
                balance = Decimal('0')

            schedule.append({
                'period': period,
                'opening_balance': (balance + principal_amt).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP),
                'principal_amount': principal_amt,
                'interest_amount': interest,
                'insurance_amount': insurance,
                'fee_amount': fee_amount,
                'penalty_amount': Decimal('0'),
                'total_amount': total,
                'closing_balance': balance,
            })

        return schedule

    @classmethod
    def generate_schedule(cls, active_credit) -> List:
        """
        Genera y persiste la tabla de amortización para un crédito activo.

        Determina el sistema de amortización y la frecuencia desde el modelo,
        calcula las cuotas y las guarda como CreditInstallment.

        Args:
            active_credit: Instancia de ActiveCredit

        Returns:
            Lista de CreditInstallment creados
        """
        from api.loans.models_active import CreditInstallment
        from api.insurances.models import PremiumType

        system_code = active_credit.amortization_system.code.upper()
        payments_per_year = active_credit.payment_frequency.payments_per_year
        days_between = active_credit.payment_frequency.days_between_payments

        insurance_rate = Decimal('0')
        for credit_insurance in active_credit.insurances.filter(status='ACTIVE').select_related('insurance'):
            insurance = credit_insurance.insurance
            if insurance.premium_type == PremiumType.BALANCE:
                insurance_rate += insurance.base_premium

        if system_code == 'FRENCH':
            schedule_data = cls.calculate_french(
                principal=active_credit.approved_amount,
                annual_rate=active_credit.annual_interest_rate,
                term_periods=active_credit.term_periods,
                payments_per_year=payments_per_year,
                insurance_rate=insurance_rate,
            )
        elif system_code == 'GERMAN':
            schedule_data = cls.calculate_german(
                principal=active_credit.approved_amount,
                annual_rate=active_credit.annual_interest_rate,
                term_periods=active_credit.term_periods,
                payments_per_year=payments_per_year,
                insurance_rate=insurance_rate,
            )
        elif system_code == 'AMERICAN':
            schedule_data = cls.calculate_american(
                principal=active_credit.approved_amount,
                annual_rate=active_credit.annual_interest_rate,
                term_periods=active_credit.term_periods,
                payments_per_year=payments_per_year,
                insurance_rate=insurance_rate,
            )
        else:
            raise ValueError(f"Sistema de amortización no soportado: {system_code}")

        installments = []
        with transaction.atomic():
            for item in schedule_data:
                installment = CreditInstallment.objects.create(
                    institution=active_credit.institution,
                    active_credit=active_credit,
                    installment_number=item['period'],
                    due_date=cls._calculate_payment_date(
                        active_credit.first_payment_date,
                        item['period'] - 1,
                        days_between,
                    ),
                    opening_balance=item['opening_balance'],
                    principal_amount=item['principal_amount'],
                    interest_amount=item['interest_amount'],
                    insurance_amount=item['insurance_amount'],
                    fee_amount=item['fee_amount'],
                    penalty_amount=item['penalty_amount'],
                    total_amount=item['total_amount'],
                    closing_balance=item['closing_balance'],
                    status='PENDING',
                )
                installments.append(installment)

        logger.info(
            f"Cronograma generado para {active_credit.credit_number}: "
            f"{len(installments)} cuotas (sistema {system_code})"
        )
        return installments

    @classmethod
    def recalculate_schedule(cls, active_credit, from_installment_number: int = 1) -> List:
        """
        Recalcula el cronograma desde una cuota específica.

        Solo afecta cuotas no pagadas (PENDING, PARTIAL, OVERDUE, IN_GRACE).
        Las cuotas PAID o REPROGRAMMED no se modifican.

        Args:
            active_credit: Instancia de ActiveCredit
            from_installment_number: Número de cuota desde donde recalcular

        Returns:
            Lista de nuevas CreditInstallment (cuotas no pagadas)
        """
        from api.loans.models_active import CreditInstallment
        from api.insurances.models import PremiumType

        # Eliminar cuotas no pagadas desde from_installment_number.
        # Las REPROGRAMMED se preservan y se actualizan en vez de crear nuevas
        # (porque pueden tener payment allocations vinculadas vía FK PROTECT).
        # Las PAID no se tocan.
        active_credit.installments.filter(
            installment_number__gte=from_installment_number,
        ).exclude(
            status__in=['PAID', 'REPROGRAMMED'],
        ).delete()

        # Si hay REPROGRAMMED en este rango, actualizarlas; si no, crear nuevas.
        existing_reprogrammed = {
            i.installment_number: i
            for i in active_credit.installments.filter(
                installment_number__gte=from_installment_number,
                status='REPROGRAMMED',
            )
        }

        # Calcular nuevo cronograma con saldo actual
        remaining_balance = active_credit.current_balance
        remaining_periods = active_credit.term_periods - from_installment_number + 1

        if remaining_periods <= 0 or remaining_balance <= Decimal('0'):
            return []

        system_code = active_credit.amortization_system.code.upper()
        payments_per_year = active_credit.payment_frequency.payments_per_year
        days_between = active_credit.payment_frequency.days_between_payments

        insurance_rate = Decimal('0')
        for credit_insurance in active_credit.insurances.filter(status='ACTIVE').select_related('insurance'):
            insurance = credit_insurance.insurance
            if insurance.premium_type == PremiumType.BALANCE:
                insurance_rate += insurance.base_premium

        if system_code == 'FRENCH':
            schedule_data = cls.calculate_french(
                principal=remaining_balance,
                annual_rate=active_credit.annual_interest_rate,
                term_periods=remaining_periods,
                payments_per_year=payments_per_year,
                insurance_rate=insurance_rate,
            )
        elif system_code == 'GERMAN':
            schedule_data = cls.calculate_german(
                principal=remaining_balance,
                annual_rate=active_credit.annual_interest_rate,
                term_periods=remaining_periods,
                payments_per_year=payments_per_year,
                insurance_rate=insurance_rate,
            )
        elif system_code == 'AMERICAN':
            schedule_data = cls.calculate_american(
                principal=remaining_balance,
                annual_rate=active_credit.annual_interest_rate,
                term_periods=remaining_periods,
                payments_per_year=payments_per_year,
                insurance_rate=insurance_rate,
            )
        else:
            raise ValueError(f"Sistema de amortización no soportado: {system_code}")

        # Obtener última cuota anterior para referencia de fecha
        last_paid_installment = active_credit.installments.filter(
            installment_number__lt=from_installment_number,
        ).order_by('-installment_number').first()

        if last_paid_installment and last_paid_installment.paid_at:
            base_date = last_paid_installment.paid_at.date()
        else:
            base_date = active_credit.first_payment_date

        new_installments = []
        with transaction.atomic():
            for idx, item in enumerate(schedule_data):
                inst_number = from_installment_number + idx

                if inst_number in existing_reprogrammed:
                    # Actualizar cuota REPROGRAMMED existente
                    installment = existing_reprogrammed[inst_number]
                    installment.due_date = cls._calculate_payment_date(
                        base_date,
                        from_installment_number - 1 + idx + 1,
                        days_between,
                    )
                    installment.opening_balance = item['opening_balance']
                    installment.principal_amount = item['principal_amount']
                    installment.interest_amount = item['interest_amount']
                    installment.insurance_amount = item['insurance_amount']
                    installment.fee_amount = item['fee_amount']
                    installment.penalty_amount = item['penalty_amount']
                    installment.total_amount = item['total_amount']
                    installment.closing_balance = item['closing_balance']
                    installment.status = 'PENDING'
                    installment.paid_amount = Decimal('0')
                    installment.days_overdue = 0
                    installment.original_due_date = None
                    installment.paid_at = None
                    installment.metadata = {}
                    installment.save(update_fields=[
                        'due_date', 'opening_balance', 'principal_amount',
                        'interest_amount', 'insurance_amount', 'fee_amount',
                        'penalty_amount', 'total_amount', 'closing_balance',
                        'status', 'paid_amount', 'days_overdue',
                        'original_due_date', 'paid_at', 'metadata',
                        'updated_at',
                    ])
                else:
                    installment = CreditInstallment.objects.create(
                        institution=active_credit.institution,
                        active_credit=active_credit,
                        installment_number=inst_number,
                        due_date=cls._calculate_payment_date(
                            base_date,
                            from_installment_number - 1 + idx + 1,
                            days_between,
                        ),
                        opening_balance=item['opening_balance'],
                        principal_amount=item['principal_amount'],
                        interest_amount=item['interest_amount'],
                        insurance_amount=item['insurance_amount'],
                        fee_amount=item['fee_amount'],
                        penalty_amount=item['penalty_amount'],
                        total_amount=item['total_amount'],
                        closing_balance=item['closing_balance'],
                        status='PENDING',
                    )
                new_installments.append(installment)

            # Cancelar cuotas REPROGRAMMED que queden fuera del nuevo cronograma
            # (cuando el nuevo plazo es menor que el anterior)
            remaining_reprogrammed = active_credit.installments.filter(
                installment_number__gte=from_installment_number,
                status='REPROGRAMMED',
            )
            if remaining_reprogrammed.exists():
                remaining_reprogrammed.update(
                    status='CANCELLED',
                    metadata={'cancelled_reason': 'replaced_by_restructuring'}
                )

        return new_installments

    @staticmethod
    def _calculate_payment_date(
        first_date: date,
        periods_offset: int,
        days_between: int,
    ) -> date:
        """
        Calcula la fecha de vencimiento de una cuota.

        Args:
            first_date: Fecha base (primera cuota o fecha de referencia)
            periods_offset: Número de períodos a avanzar
            days_between: Días entre pagos

        Returns:
            Fecha calculada
        """
        return first_date + timedelta(days=days_between * periods_offset)

    @classmethod
    def preview_schedule(cls,
        principal: Decimal,
        annual_rate: Decimal,
        term_periods: int,
        amortization_code: str,
        payments_per_year: int,
        insurance_rate: Decimal = Decimal('0'),
        fee_amount: Decimal = Decimal('0'),
    ) -> List[Dict]:
        """
        Genera una vista previa del cronograma sin persistir.
        Útil para simulación de reestructuración.

        Args:
            principal: Monto del préstamo
            annual_rate: Tasa de interés anual (%)
            term_periods: Número de cuotas
            amortization_code: FRENCH, GERMAN, AMERICAN
            payments_per_year: Pagos por año
            insurance_rate: Tasa de seguro anual (%)
            fee_amount: Comisión fija por cuota

        Returns:
            Lista de dicts del cronograma
        """
        system_code = amortization_code.upper()
        if system_code == 'FRENCH':
            return cls.calculate_french(principal, annual_rate, term_periods, payments_per_year, insurance_rate, fee_amount)
        elif system_code == 'GERMAN':
            return cls.calculate_german(principal, annual_rate, term_periods, payments_per_year, insurance_rate, fee_amount)
        elif system_code == 'AMERICAN':
            return cls.calculate_american(principal, annual_rate, term_periods, payments_per_year, insurance_rate, fee_amount)
        else:
            raise ValueError(f"Sistema de amortización no soportado: {system_code}")
