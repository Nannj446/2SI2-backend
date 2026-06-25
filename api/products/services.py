"""
Servicios para cálculos y lógica de negocio de productos crediticios.

Los cálculos ahora usan los parámetros del RuleSet activo en lugar de
campos hardcodeados en CreditProduct.
"""

from decimal import Decimal
from typing import Dict, Optional
from api.products.models import CreditProduct
from api.loans.models_rules import CreditProductParameter


class ProductCalculationService:
    """Servicio para cálculos financieros de productos crediticios."""
    
    @staticmethod
    def calculate_monthly_payment(
        amount: Decimal,
        term_months: int,
        interest_rate: Decimal,
        amortization_system: str = 'FRENCH'
    ) -> Decimal:
        """
        Calcula la cuota mensual según el sistema de amortización.
        
        Args:
            amount: Monto del crédito en Bs
            term_months: Plazo en meses
            interest_rate: Tasa de interés anual (%)
            amortization_system: Sistema de amortización (FRENCH, GERMAN, AMERICAN)
            
        Returns:
            Decimal: Cuota mensual
        """
        if term_months <= 0:
            return Decimal('0')
        
        # Tasa mensual
        monthly_rate = interest_rate / Decimal('100') / Decimal('12')
        
        if monthly_rate == 0:
            # Sin interés, solo dividir el monto
            return amount / Decimal(str(term_months))
        
        if amortization_system == 'FRENCH':
            # Sistema Francés: Cuota fija
            # C = P × [i × (1 + i)^n] / [(1 + i)^n – 1]
            factor = (1 + monthly_rate) ** term_months
            monthly_payment = amount * (monthly_rate * factor) / (factor - 1)
            return monthly_payment.quantize(Decimal('0.01'))
        
        elif amortization_system == 'GERMAN':
            # Sistema Alemán: Capital constante
            # Primera cuota (la más alta)
            capital_payment = amount / Decimal(str(term_months))
            interest_payment = amount * monthly_rate
            return (capital_payment + interest_payment).quantize(Decimal('0.01'))
        
        elif amortization_system == 'AMERICAN':
            # Sistema Americano: Solo intereses
            interest_payment = amount * monthly_rate
            return interest_payment.quantize(Decimal('0.01'))
        
        else:
            # Por defecto, usar francés
            factor = (1 + monthly_rate) ** term_months
            monthly_payment = amount * (monthly_rate * factor) / (factor - 1)
            return monthly_payment.quantize(Decimal('0.01'))
    
    @staticmethod
    def calculate_total_cost(
        amount: Decimal,
        term_months: int,
        interest_rate: Decimal,
        commission_rate: Decimal,
        insurance_rate: Decimal,
        amortization_system: str = 'FRENCH'
    ) -> Dict[str, Decimal]:
        """
        Calcula el costo total del crédito.
        
        Args:
            amount: Monto del crédito
            term_months: Plazo en meses
            interest_rate: Tasa de interés anual (%)
            commission_rate: Comisión (%)
            insurance_rate: Seguro mensual (%)
            amortization_system: Sistema de amortización
            
        Returns:
            dict: Desglose de costos
        """
        monthly_payment = ProductCalculationService.calculate_monthly_payment(
            amount, term_months, interest_rate, amortization_system
        )
        
        total_payments = monthly_payment * term_months
        total_interest = total_payments - amount
        commission = amount * (commission_rate / Decimal('100'))
        
        # Seguro de desgravamen aproximado (sobre saldo promedio)
        avg_balance = amount / 2
        insurance_cost = avg_balance * (insurance_rate / Decimal('100')) * term_months
        
        return {
            'monthly_payment': monthly_payment,
            'total_payments': total_payments,
            'total_interest': total_interest,
            'commission': commission,
            'insurance_cost': insurance_cost,
            'total_cost': total_interest + commission + insurance_cost,
        }
    
    @staticmethod
    def calculate_for_product(
        product: CreditProduct,
        amount: Decimal,
        term_months: int,
        interest_rate: Optional[Decimal] = None,
        commission_rate: Optional[Decimal] = None,
        insurance_rate: Optional[Decimal] = None,
        amortization_system: Optional[str] = None
    ) -> Optional[Dict[str, Decimal]]:
        """
        Calcula costos para un producto específico usando sus parámetros activos.
        
        Args:
            product: Producto crediticio
            amount: Monto solicitado
            term_months: Plazo solicitado
            interest_rate: Tasa específica (opcional, usa parámetros si no se provee)
            commission_rate: Comisión específica (opcional)
            insurance_rate: Seguro específico (opcional)
            amortization_system: Sistema específico (opcional)
            
        Returns:
            dict con cálculos o None si no hay parámetros activos
        """
        params = product.get_active_parameters()
        if not params:
            return None
        
        # Usar valores provistos o tomar del rango medio de parámetros
        if interest_rate is None:
            interest_rate = (params.min_interest_rate + params.max_interest_rate) / 2
        
        if commission_rate is None:
            commission_rate = (params.commission_rate_min + params.commission_rate_max) / 2
        
        if insurance_rate is None:
            insurance_rate = (params.insurance_rate_min + params.insurance_rate_max) / 2
        
        if amortization_system is None:
            # Tomar el primer sistema permitido
            first_system = params.allowed_amortization_systems.first()
            amortization_system = first_system.code if first_system else 'FRENCH'
        
        return ProductCalculationService.calculate_total_cost(
            amount=amount,
            term_months=term_months,
            interest_rate=interest_rate,
            commission_rate=commission_rate,
            insurance_rate=insurance_rate,
            amortization_system=amortization_system
        )
    
    @staticmethod
    def validate_product_request(
        product: CreditProduct,
        amount: Decimal,
        term_months: int
    ) -> Dict[str, any]:
        """
        Valida si una solicitud cumple con los parámetros del producto.
        
        Args:
            product: Producto crediticio
            amount: Monto solicitado
            term_months: Plazo solicitado
            
        Returns:
            dict con 'valid' (bool) y 'errors' (list)
        """
        params = product.get_active_parameters()
        if not params:
            return {
                'valid': False,
                'errors': ['No hay parámetros activos configurados para este producto']
            }
        
        errors = []
        
        # Validar monto
        if amount < params.min_amount:
            errors.append(f'El monto mínimo es {params.min_amount} Bs')
        if amount > params.max_amount:
            errors.append(f'El monto máximo es {params.max_amount} Bs')
        
        # Validar plazo
        if term_months < params.min_term_months:
            errors.append(f'El plazo mínimo es {params.min_term_months} meses')
        if term_months > params.max_term_months:
            errors.append(f'El plazo máximo es {params.max_term_months} meses')
        
        return {
            'valid': len(errors) == 0,
            'errors': errors
        }
    
    @staticmethod
    def get_product_ranges(product: CreditProduct) -> Optional[Dict[str, any]]:
        """
        Obtiene los rangos configurados para un producto.
        
        Args:
            product: Producto crediticio
            
        Returns:
            dict con rangos o None si no hay parámetros
        """
        params = product.get_active_parameters()
        if not params:
            return None
        
        return {
            'amount': {
                'min': params.min_amount,
                'max': params.max_amount,
            },
            'term_months': {
                'min': params.min_term_months,
                'max': params.max_term_months,
            },
            'interest_rate': {
                'min': params.min_interest_rate,
                'max': params.max_interest_rate,
                'type': params.interest_type,
            },
            'commission_rate': {
                'min': params.commission_rate_min,
                'max': params.commission_rate_max,
            },
            'insurance_rate': {
                'min': params.insurance_rate_min,
                'max': params.insurance_rate_max,
            },
            'grace_period_months': {
                'min': params.grace_period_months_min,
                'max': params.grace_period_months_max,
            },
            'allows_early_payment': params.allows_early_payment,
            'early_payment_penalty': {
                'min': params.early_payment_penalty_min,
                'max': params.early_payment_penalty_max,
            },
            'requires_guarantor': params.requires_guarantor,
            'requires_collateral': params.requires_collateral,
        }
