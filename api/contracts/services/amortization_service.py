"""
Servicio para cálculo y gestión de tablas de amortización

Este servicio maneja la lógica de negocio para generar y gestionar
las tablas de amortización de los contratos.
"""

import logging
from decimal import Decimal, ROUND_HALF_UP
from datetime import timedelta
from dateutil.relativedelta import relativedelta
from django.db import transaction
from api.contracts.models import Contract, ContractAmortizationSchedule

logger = logging.getLogger(__name__)


class AmortizationService:
    """
    Servicio para generar y gestionar tablas de amortización.
    """
    
    @staticmethod
    def generate_amortization_schedule(contract: Contract) -> list:
        """
        Genera la tabla de amortización para un contrato.
        
        Utiliza el sistema francés (cuota fija) para calcular la amortización.
        
        Args:
            contract: Contrato para el cual generar la tabla
        
        Returns:
            list: Lista de objetos ContractAmortizationSchedule creados
        """
        # Validar que el contrato no tenga ya una tabla de amortización
        if contract.amortization_schedule.exists():
            logger.warning(
                f"El contrato {contract.contract_number} ya tiene una tabla "
                f"de amortización. Se eliminará la existente."
            )
            contract.amortization_schedule.all().delete()
        
        # Obtener datos del contrato
        principal = Decimal(str(contract.principal_amount))
        annual_rate = Decimal(str(contract.interest_rate)) / Decimal('100')
        monthly_rate = annual_rate / Decimal('12')
        term_months = contract.term_months
        monthly_payment = Decimal(str(contract.monthly_payment))
        
        # Fecha de inicio de pagos
        current_date = contract.first_payment_date
        
        # Saldo pendiente inicial
        remaining_balance = principal
        
        # Lista para almacenar las cuotas
        schedule_items = []
        
        with transaction.atomic():
            for payment_number in range(1, term_months + 1):
                # Calcular interés de la cuota
                interest_amount = (remaining_balance * monthly_rate).quantize(
                    Decimal('0.01'),
                    rounding=ROUND_HALF_UP
                )
                
                # Calcular capital de la cuota
                principal_amount = monthly_payment - interest_amount
                
                # Ajuste para la última cuota (por redondeos)
                if payment_number == term_months:
                    principal_amount = remaining_balance
                    total_payment = principal_amount + interest_amount
                else:
                    total_payment = monthly_payment
                
                # Calcular nuevo saldo
                new_balance = remaining_balance - principal_amount
                
                # Asegurar que el saldo no sea negativo
                if new_balance < Decimal('0'):
                    new_balance = Decimal('0')
                
                # Crear registro de cuota
                schedule_item = ContractAmortizationSchedule.objects.create(
                    institution=contract.institution,
                    contract=contract,
                    payment_number=payment_number,
                    due_date=current_date,
                    principal_amount=principal_amount.quantize(
                        Decimal('0.01'),
                        rounding=ROUND_HALF_UP
                    ),
                    interest_amount=interest_amount,
                    total_payment=total_payment.quantize(
                        Decimal('0.01'),
                        rounding=ROUND_HALF_UP
                    ),
                    remaining_balance=new_balance.quantize(
                        Decimal('0.01'),
                        rounding=ROUND_HALF_UP
                    ),
                    is_paid=False,
                    paid_amount=Decimal('0')
                )
                
                schedule_items.append(schedule_item)
                
                # Actualizar saldo pendiente
                remaining_balance = new_balance
                
                # Avanzar a la siguiente fecha de pago (1 mes)
                current_date = current_date + relativedelta(months=1)
            
            logger.info(
                f"Tabla de amortización generada para contrato "
                f"{contract.contract_number}: {len(schedule_items)} cuotas"
            )
        
        return schedule_items
    
    @staticmethod
    def mark_payment_as_paid(
        schedule_item: ContractAmortizationSchedule,
        paid_amount: Decimal,
        payment_reference: str = '',
        notes: str = ''
    ) -> ContractAmortizationSchedule:
        """
        Marca una cuota como pagada.
        
        Args:
            schedule_item: Cuota a marcar como pagada
            paid_amount: Monto pagado
            payment_reference: Referencia del pago
            notes: Notas adicionales
        
        Returns:
            ContractAmortizationSchedule: Cuota actualizada
        
        Raises:
            ValueError: Si la cuota ya está pagada o el monto es inválido
        """
        from django.utils import timezone
        
        if schedule_item.is_paid:
            raise ValueError(
                f"La cuota #{schedule_item.payment_number} ya está marcada como pagada."
            )
        
        if paid_amount <= Decimal('0'):
            raise ValueError("El monto pagado debe ser mayor a cero.")
        
        with transaction.atomic():
            schedule_item.is_paid = True
            schedule_item.paid_at = timezone.now()
            schedule_item.paid_amount = paid_amount
            schedule_item.payment_reference = payment_reference
            schedule_item.notes = notes
            schedule_item.save(update_fields=[
                'is_paid',
                'paid_at',
                'paid_amount',
                'payment_reference',
                'notes',
                'updated_at'
            ])
            
            logger.info(
                f"Cuota #{schedule_item.payment_number} del contrato "
                f"{schedule_item.contract.contract_number} marcada como pagada. "
                f"Monto: {paid_amount}"
            )
        
        return schedule_item
    
    @staticmethod
    def get_next_payment_due(contract: Contract):
        """
        Obtiene la siguiente cuota pendiente de pago.
        
        Args:
            contract: Contrato
        
        Returns:
            ContractAmortizationSchedule o None: Siguiente cuota pendiente
        """
        return contract.amortization_schedule.filter(
            is_paid=False
        ).order_by('payment_number').first()
    
    @staticmethod
    def get_overdue_payments(contract: Contract):
        """
        Obtiene las cuotas vencidas (no pagadas y con fecha pasada).
        
        Args:
            contract: Contrato
        
        Returns:
            QuerySet: Cuotas vencidas
        """
        from django.utils import timezone
        
        return contract.amortization_schedule.filter(
            is_paid=False,
            due_date__lt=timezone.now().date()
        ).order_by('payment_number')
    
    @staticmethod
    def get_payment_summary(contract: Contract) -> dict:
        """
        Obtiene un resumen del estado de pagos del contrato.
        
        Args:
            contract: Contrato
        
        Returns:
            dict: Resumen con estadísticas de pagos
        """
        from django.utils import timezone
        from django.db.models import Sum, Count, Q
        
        schedule = contract.amortization_schedule.all()
        
        total_payments = schedule.count()
        paid_payments = schedule.filter(is_paid=True).count()
        pending_payments = total_payments - paid_payments
        
        overdue_payments = schedule.filter(
            is_paid=False,
            due_date__lt=timezone.now().date()
        ).count()
        
        total_paid = schedule.filter(is_paid=True).aggregate(
            total=Sum('paid_amount')
        )['total'] or Decimal('0')
        
        total_pending = schedule.filter(is_paid=False).aggregate(
            total=Sum('total_payment')
        )['total'] or Decimal('0')
        
        next_payment = AmortizationService.get_next_payment_due(contract)
        
        return {
            'total_payments': total_payments,
            'paid_payments': paid_payments,
            'pending_payments': pending_payments,
            'overdue_payments': overdue_payments,
            'total_paid': total_paid,
            'total_pending': total_pending,
            'next_payment_number': next_payment.payment_number if next_payment else None,
            'next_payment_date': next_payment.due_date if next_payment else None,
            'next_payment_amount': next_payment.total_payment if next_payment else None,
            'completion_percentage': (paid_payments / total_payments * 100) if total_payments > 0 else 0,
        }
    
    @staticmethod
    def calculate_early_payoff_amount(contract: Contract) -> dict:
        """
        Calcula el monto necesario para liquidar anticipadamente el contrato.
        
        Args:
            contract: Contrato
        
        Returns:
            dict: Información sobre el pago anticipado
        """
        from django.utils import timezone
        
        # Obtener cuotas pendientes
        pending_schedule = contract.amortization_schedule.filter(
            is_paid=False
        ).order_by('payment_number')
        
        if not pending_schedule.exists():
            return {
                'payoff_amount': Decimal('0'),
                'remaining_principal': Decimal('0'),
                'remaining_interest': Decimal('0'),
                'pending_payments': 0,
                'savings': Decimal('0'),
            }
        
        # Sumar capital e intereses pendientes
        remaining_principal = pending_schedule.aggregate(
            total=Sum('principal_amount')
        )['total'] or Decimal('0')
        
        remaining_interest = pending_schedule.aggregate(
            total=Sum('interest_amount')
        )['total'] or Decimal('0')
        
        # Monto total pendiente
        total_pending = remaining_principal + remaining_interest
        
        # Para pago anticipado, típicamente se cobra solo el capital
        # (esto puede variar según políticas de la institución)
        payoff_amount = remaining_principal
        
        # Ahorro en intereses
        savings = remaining_interest
        
        return {
            'payoff_amount': payoff_amount,
            'remaining_principal': remaining_principal,
            'remaining_interest': remaining_interest,
            'pending_payments': pending_schedule.count(),
            'savings': savings,
            'calculation_date': timezone.now().date(),
        }
    
    @staticmethod
    def regenerate_amortization_schedule(contract: Contract) -> list:
        """
        Regenera la tabla de amortización de un contrato.
        
        Útil cuando se modifican los términos del contrato.
        ADVERTENCIA: Elimina la tabla existente.
        
        Args:
            contract: Contrato
        
        Returns:
            list: Nueva tabla de amortización
        
        Raises:
            ValueError: Si el contrato tiene pagos registrados
        """
        # Verificar que no haya pagos registrados
        if contract.amortization_schedule.filter(is_paid=True).exists():
            raise ValueError(
                "No se puede regenerar la tabla de amortización porque "
                "ya hay pagos registrados."
            )
        
        # Eliminar tabla existente
        contract.amortization_schedule.all().delete()
        
        # Generar nueva tabla
        return AmortizationService.generate_amortization_schedule(contract)
