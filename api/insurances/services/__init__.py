"""
Servicios de negocio para Gestión de Seguros.
"""
from decimal import Decimal
from typing import Optional

from django.db import transaction
from django.utils import timezone

from api.insurances.models import (
    Insurance, InsuranceCoverage, ProductInsurance,
    CreditInsurance, Insurer, CreditInsuranceStatus,
    CoverageType, PremiumType
)


class InsuranceService:
    """Servicio para gestión de catálogo de seguros."""

    @staticmethod
    def create_insurer(institution, data):
        """Crear una nueva aseguradora."""
        return Insurer.objects.create(
            institution=institution,
            **data
        )

    @staticmethod
    def update_insurer(insurer, data):
        """Actualizar aseguradora."""
        for attr, value in data.items():
            setattr(insurer, attr, value)
        insurer.save()
        return insurer

    @staticmethod
    def create_insurance(institution, data):
        """Crear un nuevo seguro."""
        coverages_data = data.pop('coverages', [])
        insurance = Insurance.objects.create(
            institution=institution,
            **data
        )
        for coverage_data in coverages_data:
            InsuranceCoverage.objects.create(
                insurance=insurance,
                institution=institution,
                **coverage_data
            )
        return insurance

    @staticmethod
    def update_insurance(insurance, data):
        """Actualizar seguro."""
        coverages_data = data.pop('coverages', None)
        for attr, value in data.items():
            setattr(insurance, attr, value)
        insurance.save()
        if coverages_data is not None:
            insurance.coverages.all().delete()
            for coverage_data in coverages_data:
                InsuranceCoverage.objects.create(
                    insurance=insurance,
                    institution=insurance.institution,
                    **coverage_data
                )
        return insurance

    @staticmethod
    def associate_insurance_to_product(product, insurance_id, data):
        """Asociar un seguro a un producto crediticio."""
        insurance = Insurance.objects.get(id=insurance_id, institution=product.institution)
        return ProductInsurance.objects.create(
            product=product,
            insurance=insurance,
            institution=product.institution,
            **data
        )

    @staticmethod
    def get_product_insurances(product):
        """Obtener todos los seguros asociados a un producto."""
        return ProductInsurance.objects.filter(
            product=product,
            insurance__is_active=True
        ).select_related('insurance', 'insurance__insurer')

    @staticmethod
    def get_mandatory_insurances(product):
        """Obtener seguros obligatorios de un producto."""
        return ProductInsurance.objects.filter(
            product=product,
            is_required=True,
            insurance__is_active=True
        ).select_related('insurance')


class InsuranceCalculationService:
    """Servicio para cálculo de primas de seguros."""

    @staticmethod
    def calculate_premium(
        insurance: Insurance,
        loan_amount: Decimal,
        loan_term_months: int,
        balance: Optional[Decimal] = None
    ) -> dict:
        """
        Calcular prima de seguro según el tipo.

        Args:
            insurance: Seguro a calcular
            loan_amount: Monto total del crédito
            loan_term_months: Plazo en meses
            balance: Saldo insoluto (para tipo BALANCE)

        Returns:
            Dict con detalles del cálculo
        """
        result = {
            'insurance_id': insurance.id,
            'insurance_name': insurance.name,
            'premium_type': insurance.premium_type,
            'base_premium': insurance.base_premium,
            'calculated_premium': Decimal('0.00'),
        }

        if insurance.premium_type == PremiumType.BALANCE:
            effective_balance = balance if balance is not None else loan_amount
            premium_rate = insurance.base_premium / Decimal('100')
            result['calculated_premium'] = effective_balance * premium_rate
            result['premium_mode'] = 'balance'
            result['monthly_premium'] = result['calculated_premium']

        elif insurance.premium_type == PremiumType.MONTHLY:
            premium_rate = insurance.base_premium / Decimal('100')
            result['calculated_premium'] = loan_amount * premium_rate
            result['premium_mode'] = 'monthly_included'
            result['monthly_premium'] = result['calculated_premium']

        elif insurance.premium_type == PremiumType.LUMP_SUM:
            premium_rate = insurance.base_premium / Decimal('100')
            result['calculated_premium'] = loan_amount * premium_rate
            result['premium_mode'] = 'lump_sum'
            result['lump_sum_premium'] = result['calculated_premium']

        elif insurance.premium_type == PremiumType.ANNUAL:
            premium_rate = insurance.base_premium / Decimal('100')
            annual_premium = loan_amount * premium_rate
            monthly_premium = annual_premium / Decimal('12')
            result['calculated_premium'] = annual_premium
            result['premium_mode'] = 'annual'
            result['annual_premium'] = annual_premium
            result['monthly_premium'] = monthly_premium

        return result

    @staticmethod
    def calculate_total_premiums(product, loan_amount, loan_term_months, balance=None):
        """
        Calcular total de primas para todos los seguros de un producto.

        Returns:
            Dict con totales y detalle por seguro
        """
        product_insurances = ProductInsurance.objects.filter(
            product=product,
            insurance__is_active=True
        ).select_related('insurance')

        details = []
        total_monthly = Decimal('0.00')
        total_lump_sum = Decimal('0.00')
        total_annual = Decimal('0.00')

        for pi in product_insurances:
            insurance = pi.insurance
            custom_premium = pi.custom_premium or insurance.base_premium

            temp_insurance = insurance
            temp_insurance.base_premium = custom_premium

            calc = InsuranceCalculationService.calculate_premium(
                temp_insurance,
                loan_amount,
                loan_term_months,
                balance
            )

            calc['is_required'] = pi.is_required
            details.append(calc)

            if calc.get('monthly_premium'):
                total_monthly += calc['monthly_premium']
            if calc.get('lump_sum_premium'):
                total_lump_sum += calc['lump_sum_premium']
            if calc.get('annual_premium'):
                total_annual += calc['annual_premium']

        return {
            'details': details,
            'totals': {
                'monthly': total_monthly,
                'lump_sum': total_lump_sum,
                'annual': total_annual
            }
        }

    @staticmethod
    def validate_premium_percentage(monthly_premium, installment_amount, max_percentage=30):
        """
        Validar que la prima no exceda un porcentaje de la cuota.

        Args:
            monthly_premium: Prima mensual calculada
            installment_amount: Monto de la cuota
            max_percentage: Porcentaje máximo (default 30%)

        Returns:
            Tuple (is_valid, error_message)
        """
        if installment_amount > 0:
            percentage = (monthly_premium / installment_amount) * 100
            if percentage > max_percentage:
                return False, f"La prima no puede exceder {max_percentage}% de la cuota"
        return True, None


class CreditInsuranceService:
    """Servicio para gestión de seguros asociados a créditos."""

    @staticmethod
    @transaction.atomic
    def register_insurance(credit, data):
        """
        Registrar un nuevo seguro para un crédito.

        Args:
            credit: Crédito activo
            data: Datos del seguro

        Returns:
            CreditInsurance creado
        """
        insurance_id = data.get('insurance')
        insurance = Insurance.objects.get(id=insurance_id, institution=credit.institution)

        return CreditInsurance.objects.create(
            active_credit=credit,
            insurance=insurance,
            institution=credit.institution,
            status=CreditInsuranceStatus.ACTIVE,
            **data
        )

    @staticmethod
    @transaction.atomic
    def update_insurance_status(credit_insurance, new_status, reason=None):
        """
        Actualizar estado de una póliza de seguro.

        Args:
            credit_insurance: Póliza de seguro
            new_status: Nuevo estado
            reason: Razón del cambio (para auditoría)
        """
        old_status = credit_insurance.status
        credit_insurance.status = new_status
        credit_insurance.save()

        return credit_insurance

    @staticmethod
    def check_and_update_expired_insurances():
        """
        Verificar y actualizar seguros vencidos.
        Se debe ejecutar como tarea programada.

        Returns:
            Lista de pólizas actualizadas
        """
        today = timezone.now().date()
        updated = []

        expiring_insurances = CreditInsurance.objects.filter(
            status=CreditInsuranceStatus.ACTIVE,
            end_date__lte=today + timezone.timedelta(days=30),
            end_date__gt=today
        )
        for insurance in expiring_insurances:
            insurance.status = CreditInsuranceStatus.EXPIRING_SOON
            insurance.save()
            updated.append(insurance)

        expired_insurances = CreditInsurance.objects.filter(
            status__in=[CreditInsuranceStatus.ACTIVE, CreditInsuranceStatus.EXPIRING_SOON],
            end_date__lt=today
        )
        for insurance in expired_insurances:
            insurance.status = CreditInsuranceStatus.EXPIRED
            insurance.save()
            updated.append(insurance)

        return updated

    @staticmethod
    def get_credit_insurances(credit):
        """Obtener todos los seguros de un crédito."""
        return CreditInsurance.objects.filter(
            active_credit=credit
        ).select_related('insurance', 'insurance__insurer')

    @staticmethod
    def get_active_insurances(credit):
        """Obtener seguros activos de un crédito."""
        return CreditInsurance.objects.filter(
            active_credit=credit,
            status__in=[
                CreditInsuranceStatus.ACTIVE,
                CreditInsuranceStatus.EXPIRING_SOON
            ]
        ).select_related('insurance', 'insurance__insurer')

    @staticmethod
    def get_insurance_by_policy_number(institution, policy_number):
        """Buscar seguro por número de póliza."""
        return CreditInsurance.objects.get(
            institution=institution,
            policy_number=policy_number
        )
