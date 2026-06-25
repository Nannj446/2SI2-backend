"""
Servicio de gestión de créditos activos.

Maneja la activación de créditos desde contratos desembolsados,
generación de resúmenes financieros, y actualización de estados.
"""

import logging
from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from datetime import date

from api.audit.models import AuditLog

logger = logging.getLogger(__name__)


class ActiveCreditService:
    """
    Servicio para la gestión del ciclo de vida de créditos activos.
    """

    @classmethod
    def activate_from_contract(cls, contract, user=None) -> 'ActiveCredit':
        """
        Activa un crédito desde un contrato desembolsado.

        Crea el ActiveCredit a partir del Contract y LoanApplication asociados,
        copia la información financiera y genera el cronograma de cuotas.

        Args:
            contract: Instancia de Contract (debe tener loan_application DISBURSED)
            user: Usuario que realiza la activación (para auditoría)

        Returns:
            ActiveCredit creado

        Raises:
            ValueError: Si el contrato ya tiene un ActiveCredit o no cumple condiciones
        """
        from api.loans.models_active import ActiveCredit
        from api.loans.services.amortization_calculation_service import AmortizationCalculationService

        loan_app = contract.loan_application

        # Validar que no exista ya un crédito activo
        if hasattr(loan_app, 'active_credit') and loan_app.active_credit is not None:
            raise ValueError(f"La solicitud {loan_app.application_number} ya tiene un crédito activo.")

        if hasattr(contract, 'active_credit') and contract.active_credit is not None:
            raise ValueError(f"El contrato {contract.contract_number} ya tiene un crédito activo.")

        if loan_app.status != 'DISBURSED':
            raise ValueError(
                f"La solicitud debe estar en estado DISBURSED. Estado actual: {loan_app.status}"
            )

        # Determinar sistema de amortización y frecuencia desde el producto o parámetros
        from api.loans.services.amortization_calculation_service import AmortizationCalculationService

        # Usar el producto de la solicitud para determinar los catálogos
        product = loan_app.product

        # Buscar parámetros del producto para obtener amortización/frecuencia configuradas
        amortization_system = None
        payment_frequency = None

        from api.loans.models_catalogs import AmortizationSystem, PaymentFrequency, Currency

        # Intentar obtener desde CreditProductParameter
        try:
            param = product.parameters.filter(
                institution=contract.institution,
            ).first()
            if param and hasattr(param, 'allowed_amortization_systems'):
                systems = param.allowed_amortization_systems.filter(is_active=True)
                if systems.exists():
                    amortization_system = systems.first()
            if param and hasattr(param, 'allowed_payment_frequencies'):
                freqs = param.allowed_payment_frequencies.filter(is_active=True)
                if freqs.exists():
                    payment_frequency = freqs.first()
        except Exception:
            pass

        # Fallback a defaults
        if not amortization_system:
            amortization_system = AmortizationSystem.objects.filter(
                institution=contract.institution, is_active=True
            ).first()
        if not payment_frequency:
            payment_frequency = PaymentFrequency.objects.filter(
                institution=contract.institution, is_active=True
            ).first()

        # Determinar moneda
        currency = Currency.objects.filter(
            institution=contract.institution, is_active=True
        ).first()

        if not amortization_system or not payment_frequency or not currency:
            raise ValueError("Faltan catálogos configurados (amortización, frecuencia o moneda).")

        # Determinar término: usar approved_term_months del loan_app o term_months del contract
        term_periods = loan_app.approved_term_months or contract.term_months

        # Generar credit_number
        credit_number = cls._generate_credit_number(contract.institution)

        with transaction.atomic():
            active_credit = ActiveCredit.objects.create(
                institution=contract.institution,
                loan_application=loan_app,
                contract=contract,
                client=loan_app.client,
                product=product,
                credit_number=credit_number,
                approved_amount=contract.principal_amount,
                currency=currency,
                annual_interest_rate=contract.interest_rate,
                term_periods=term_periods,
                payment_frequency=payment_frequency,
                amortization_system=amortization_system,
                disbursement_date=loan_app.disbursed_at.date() if loan_app.disbursed_at else date.today(),
                first_payment_date=contract.first_payment_date,
                maturity_date=contract.end_date,
                current_balance=contract.principal_amount,
                status='ACTIVE',
            )

            # Generar cronograma de cuotas
            AmortizationCalculationService.generate_schedule(active_credit)

            # Actualizar next_due_date y maturity_date desde las cuotas
            first_installment = active_credit.installments.order_by('installment_number').first()
            last_installment = active_credit.installments.order_by('-installment_number').first()
            if first_installment:
                active_credit.next_due_date = first_installment.due_date
            if last_installment:
                active_credit.maturity_date = last_installment.due_date
            active_credit.save(update_fields=['next_due_date', 'maturity_date'])

            # Registrar en auditoría
            cls._audit(
                user=user,
                action='create',
                resource_type='ActiveCredit',
                resource_id=active_credit.id,
                institution=active_credit.institution,
                description=f'Crédito activo creado: {credit_number} desde contrato {contract.contract_number}',
                metadata={
                    'credit_number': credit_number,
                    'contract_number': contract.contract_number,
                    'approved_amount': str(active_credit.approved_amount),
                    'amortization_system': amortization_system.code,
                    'payment_frequency': payment_frequency.code,
                }
            )

            # Registrar cambio de estado inicial
            from api.loans.models_active import CreditStatusHistory
            CreditStatusHistory.objects.create(
                institution=active_credit.institution,
                active_credit=active_credit,
                previous_status='',
                new_status='ACTIVE',
                changed_by=user,
                reason='Crédito activado desde contrato',
            )

            logger.info(f"Crédito activo creado: {credit_number}")

        return active_credit

    @classmethod
    def get_summary(cls, active_credit) -> dict:
        """
        Obtiene un resumen financiero del crédito activo.

        Args:
            active_credit: Instancia de ActiveCredit

        Returns:
            Dict con resumen financiero
        """
        installments = active_credit.installments.all()

        total_installments = installments.exclude(
            status__in=['REPROGRAMMED', 'CANCELLED']
        ).count()
        paid_installments = installments.filter(status='PAID').count()
        pending_installments = installments.filter(
            status__in=['PENDING', 'PARTIAL', 'OVERDUE', 'IN_GRACE']
        ).count()
        overdue_installments = installments.filter(
            status__in=['PENDING', 'PARTIAL', 'OVERDUE'],
            due_date__lt=timezone.now().date()
        ).count()

        # Progreso
        progress_percentage = (paid_installments / total_installments * 100) if total_installments > 0 else 0

        # Próxima cuota
        next_installment = installments.filter(
            status__in=['PENDING', 'PARTIAL', 'OVERDUE', 'IN_GRACE']
        ).order_by('installment_number').first()

        # Calcular montos pendientes totales
        from django.db.models import Sum
        total_pending_amount = installments.filter(
            status__in=['PENDING', 'PARTIAL', 'OVERDUE', 'IN_GRACE']
        ).aggregate(
            total_pending=Sum('total_amount'),
            total_paid=Sum('paid_amount'),
        )

        return {
            'credit_number': active_credit.credit_number,
            'status': active_credit.status,
            'status_display': active_credit.get_status_display(),
            'approved_amount': str(active_credit.approved_amount),
            'current_balance': str(active_credit.current_balance),
            'total_paid': str(active_credit.total_paid),
            'principal_paid': str(active_credit.principal_paid),
            'interest_paid': str(active_credit.interest_paid),
            'fees_paid': str(active_credit.fees_paid),
            'penalty_paid': str(active_credit.penalty_paid),
            'annual_interest_rate': str(active_credit.annual_interest_rate),
            'term_periods': active_credit.term_periods,
            'payment_frequency': active_credit.payment_frequency.name if active_credit.payment_frequency else None,
            'amortization_system': active_credit.amortization_system.name if active_credit.amortization_system else None,
            'currency': active_credit.currency.code if active_credit.currency else None,
            'disbursement_date': active_credit.disbursement_date.isoformat() if active_credit.disbursement_date else None,
            'first_payment_date': active_credit.first_payment_date.isoformat() if active_credit.first_payment_date else None,
            'maturity_date': active_credit.maturity_date.isoformat() if active_credit.maturity_date else None,
            'next_due_date': active_credit.next_due_date.isoformat() if active_credit.next_due_date else None,
            'days_in_arrears': active_credit.days_in_arrears,
            'total_installments': total_installments,
            'paid_installments': paid_installments,
            'pending_installments': pending_installments,
            'overdue_installments': overdue_installments,
            'progress_percentage': round(progress_percentage, 1),
            'next_installment': {
                'number': next_installment.installment_number,
                'due_date': next_installment.due_date.isoformat(),
                'total_amount': str(next_installment.total_amount),
                'paid_amount': str(next_installment.paid_amount),
                'status': next_installment.status,
            } if next_installment else None,
            'total_pending_amount': str(total_pending_amount.get('total_pending') or Decimal('0')),
            'client_name': str(active_credit.client) if active_credit.client else None,
            'product_name': active_credit.product.name if active_credit.product else None,
        }

    @classmethod
    def refresh_status(cls, active_credit) -> str:
        """
        Refresca el estado del crédito activo basado en reglas de negocio.

        Args:
            active_credit: Instancia de ActiveCredit

        Returns:
            Nuevo estado (str)
        """
        from api.loans.models_active import ActiveCredit

        old_status = active_credit.status
        new_status = old_status

        # Regla: saldo cero = cancelado
        if active_credit.current_balance <= Decimal('0'):
            new_status = ActiveCredit.Status.CANCELLED

        # Regla: reestructurado (si no está cancelado)
        elif active_credit.restructurings.filter(is_active=True).exists():
            new_status = ActiveCredit.Status.RESTRUCTURED

        # Regla: período de gracia activo
        elif active_credit.grace_periods.filter(
            is_active=True,
            start_date__lte=timezone.now().date(),
            end_date__gte=timezone.now().date(),
        ).exists():
            new_status = ActiveCredit.Status.IN_GRACE_PERIOD

        else:
            # Regla: cuota vencida → en mora
            has_overdue = active_credit.installments.filter(
                status__in=['PENDING', 'PARTIAL', 'OVERDUE'],
                due_date__lt=timezone.now().date(),
            ).exists()

            if has_overdue:
                new_status = ActiveCredit.Status.IN_ARREARS
            else:
                new_status = ActiveCredit.Status.ACTIVE

        # Solo actualizar si cambió
        if new_status != old_status:
            active_credit.status = new_status
            active_credit.save(update_fields=['status', 'updated_at'])

            # Registrar cambio de estado
            from api.loans.models_active import CreditStatusHistory
            CreditStatusHistory.objects.create(
                institution=active_credit.institution,
                active_credit=active_credit,
                previous_status=old_status,
                new_status=new_status,
                reason='Actualización automática de estado',
                metadata={'trigger': 'refresh_status'},
            )

            cls._audit(
                action='subscription_change',
                resource_type='ActiveCredit',
                resource_id=active_credit.id,
                institution=active_credit.institution,
                description=f'Estado cambiado: {old_status} → {new_status}',
                metadata={'previous_status': old_status, 'new_status': new_status},
            )

            logger.info(
                f"Estado de {active_credit.credit_number}: {old_status} → {new_status}"
            )

        # Actualizar days_in_arrears
        cls._update_days_in_arrears(active_credit)

        return new_status

    @classmethod
    def refresh_all_active_credits(cls, institution=None) -> int:
        """
        Refresca el estado de todos los créditos activos.

        Args:
            institution: Opcional, filtrar por institución

        Returns:
            Número de créditos actualizados
        """
        from api.loans.models_active import ActiveCredit

        queryset = ActiveCredit.objects.exclude(status=ActiveCredit.Status.CANCELLED)
        if institution:
            queryset = queryset.filter(institution=institution)

        updated = 0
        for active_credit in queryset.iterator():
            old_status = active_credit.status
            new_status = cls.refresh_status(active_credit)
            if new_status != old_status:
                updated += 1

        logger.info(f"Refresco de estados completado: {updated} créditos actualizados")
        return updated

    @classmethod
    def _update_days_in_arrears(cls, active_credit):
        """
        Actualiza el contador de días en mora del crédito activo.

        Busca la cuota vencida más antigua y calcula los días transcurridos.
        """
        from datetime import date as dt_date

        oldest_overdue = active_credit.installments.filter(
            status__in=['PENDING', 'PARTIAL', 'OVERDUE'],
            due_date__lt=timezone.now().date(),
        ).order_by('due_date').first()

        if oldest_overdue:
            days = (timezone.now().date() - oldest_overdue.due_date).days
            active_credit.days_in_arrears = max(days, 0)
        else:
            active_credit.days_in_arrears = 0

        active_credit.save(update_fields=['days_in_arrears', 'updated_at'])

    @classmethod
    def _generate_credit_number(cls, institution) -> str:
        """
        Genera un número único de crédito activo.

        Formato: {INST_SLUG}-CRED-{SEQ}

        Args:
            institution: Instancia de FinancialInstitution

        Returns:
            Número de crédito único
        """
        from api.loans.models_active import ActiveCredit
        from django.db.models import Count

        prefix = institution.slug[:4].upper() if hasattr(institution, 'slug') else 'INST'
        last_count = ActiveCredit.all_objects.filter(
            institution=institution
        ).count()
        seq = str(last_count + 1).zfill(6)

        return f"{prefix}-CRED-{seq}"

    @staticmethod
    def _audit(user=None, action='', resource_type='', resource_id=None,
               institution=None, description='', metadata=None, severity='info'):
        """
        Registra un evento de auditoría.

        Args:
            user: Usuario que realizó la acción
            action: Tipo de acción
            resource_type: Tipo de recurso
            resource_id: ID del recurso
            institution: Institución
            description: Descripción
            metadata: Datos adicionales
            severity: Nivel de severidad
        """
        try:
            AuditLog.objects.create(
                user=user,
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                institution=institution,
                description=description,
                severity=severity,
                metadata=metadata or {},
            )
        except Exception as e:
            logger.error(f"Error registrando auditoría: {e}", exc_info=True)
