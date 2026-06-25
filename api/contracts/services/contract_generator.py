"""
Servicio para generación de contratos

Este servicio maneja la lógica de negocio para generar contratos
a partir de solicitudes aprobadas.
"""

import logging
from decimal import Decimal
from datetime import timedelta
from django.utils import timezone
from django.db import transaction
from api.contracts.models import Contract, ContractTemplate
from api.loans.models import LoanApplication

logger = logging.getLogger(__name__)


class ContractGeneratorService:
    """
    Servicio para generar contratos de crédito.
    """
    
    @staticmethod
    def generate_contract(
        loan_application: LoanApplication,
        template: ContractTemplate = None,
        contract_date=None,
        start_date=None,
        special_clauses=None,
        notes='',
        generated_by=None
    ) -> Contract:
        """
        Genera un contrato a partir de una solicitud aprobada.
        
        Args:
            loan_application: Solicitud de crédito aprobada
            template: Plantilla a usar (si es None, usa la plantilla por defecto)
            contract_date: Fecha del contrato (si es None, usa la fecha actual)
            start_date: Fecha de inicio del crédito (si es None, usa fecha actual + 5 días)
            special_clauses: Cláusulas especiales adicionales
            notes: Notas internas
            generated_by: Usuario que genera el contrato
        
        Returns:
            Contract: Contrato generado
        
        Raises:
            ValueError: Si la solicitud no está aprobada o ya tiene contrato
        """
        
        # Validaciones
        if loan_application.status != LoanApplication.Status.APPROVED:
            raise ValueError(
                f"La solicitud debe estar en estado APPROVED. "
                f"Estado actual: {loan_application.status}"
            )
        
        if hasattr(loan_application, 'contract'):
            raise ValueError(
                f"La solicitud {loan_application.application_number} "
                f"ya tiene un contrato generado."
            )
        
        # Seleccionar plantilla
        if template is None:
            template = ContractGeneratorService._get_default_template(
                loan_application.institution,
                loan_application.product
            )
        
        # Validar que la plantilla pertenezca al mismo tenant
        if template.institution != loan_application.institution:
            raise ValueError("La plantilla no pertenece a la misma institución.")
        
        # Preparar fechas
        if contract_date is None:
            contract_date = timezone.now().date()
        
        if start_date is None:
            start_date = contract_date + timedelta(days=5)
        
        # Calcular fechas importantes
        end_date = ContractGeneratorService._calculate_end_date(
            start_date,
            loan_application.approved_term_months
        )
        first_payment_date = ContractGeneratorService._calculate_first_payment_date(
            start_date
        )
        
        # Calcular monto total
        total_amount = ContractGeneratorService._calculate_total_amount(
            loan_application.approved_amount,
            loan_application.approved_interest_rate,
            loan_application.approved_term_months,
            loan_application.monthly_payment
        )
        
        # Preparar términos y condiciones
        terms_and_conditions = template.terms_and_conditions
        
        # Preparar cláusulas especiales
        if special_clauses is None:
            special_clauses = {}
        
        # Crear el contrato
        with transaction.atomic():
            contract = Contract.objects.create(
                institution=loan_application.institution,
                loan_application=loan_application,
                template=template,
                status=Contract.Status.DRAFT,
                principal_amount=loan_application.approved_amount,
                interest_rate=loan_application.approved_interest_rate,
                term_months=loan_application.approved_term_months,
                monthly_payment=loan_application.monthly_payment,
                total_amount=total_amount,
                contract_date=contract_date,
                start_date=start_date,
                end_date=end_date,
                first_payment_date=first_payment_date,
                terms_and_conditions=terms_and_conditions,
                special_clauses=special_clauses,
                notes=notes,
                generated_by=generated_by,
                version=1
            )
            
            logger.info(
                f"Contrato generado: {contract.contract_number} "
                f"para solicitud {loan_application.application_number}"
            )
            
            # Marcar la solicitud como con contrato generado
            loan_application.contract_generated = True
            loan_application.save(update_fields=['contract_generated', 'updated_at'])
        
        return contract
    
    @staticmethod
    def _get_default_template(institution, product):
        """
        Obtiene la plantilla por defecto para un producto o institución.
        
        Prioridad:
        1. Plantilla específica del producto (activa)
        2. Plantilla por defecto de la institución (activa)
        3. Error si no hay plantilla disponible
        """
        # Buscar plantilla específica del producto
        template = ContractTemplate.objects.filter(
            institution=institution,
            product=product,
            is_active=True
        ).first()
        
        if template:
            return template
        
        # Buscar plantilla por defecto
        template = ContractTemplate.objects.filter(
            institution=institution,
            is_default=True,
            is_active=True
        ).first()
        
        if template:
            return template
        
        # No hay plantilla disponible
        raise ValueError(
            f"No hay plantilla de contrato disponible para la institución "
            f"{institution.name} y el producto {product.name}. "
            f"Por favor, configure una plantilla antes de generar contratos."
        )
    
    @staticmethod
    def _calculate_end_date(start_date, term_months):
        """
        Calcula la fecha de finalización del crédito.
        
        Args:
            start_date: Fecha de inicio
            term_months: Plazo en meses
        
        Returns:
            date: Fecha de finalización
        """
        from dateutil.relativedelta import relativedelta
        return start_date + relativedelta(months=term_months)
    
    @staticmethod
    def _calculate_first_payment_date(start_date):
        """
        Calcula la fecha del primer pago.
        Por defecto, es 30 días después de la fecha de inicio.
        
        Args:
            start_date: Fecha de inicio del crédito
        
        Returns:
            date: Fecha del primer pago
        """
        return start_date + timedelta(days=30)
    
    @staticmethod
    def _calculate_total_amount(principal, interest_rate, term_months, monthly_payment):
        """
        Calcula el monto total a pagar (capital + intereses).
        
        Args:
            principal: Monto principal
            interest_rate: Tasa de interés anual
            term_months: Plazo en meses
            monthly_payment: Cuota mensual
        
        Returns:
            Decimal: Monto total a pagar
        """
        # Método simple: cuota mensual * número de cuotas
        total = Decimal(str(monthly_payment)) * term_months
        return total.quantize(Decimal('0.01'))
    
    @staticmethod
    def regenerate_contract(contract: Contract, regenerated_by=None) -> Contract:
        """
        Regenera un contrato existente (incrementa versión).
        
        Útil cuando se necesita actualizar el contrato con nuevos datos
        o corregir errores.
        
        Args:
            contract: Contrato a regenerar
            regenerated_by: Usuario que regenera el contrato
        
        Returns:
            Contract: Contrato actualizado
        
        Raises:
            ValueError: Si el contrato no puede ser regenerado
        """
        # Solo se pueden regenerar contratos en DRAFT
        if contract.status != Contract.Status.DRAFT:
            raise ValueError(
                f"Solo se pueden regenerar contratos en estado DRAFT. "
                f"Estado actual: {contract.status}"
            )
        
        with transaction.atomic():
            # Incrementar versión
            contract.version += 1
            contract.generated_by = regenerated_by
            contract.save(update_fields=['version', 'generated_by', 'updated_at'])
            
            logger.info(
                f"Contrato regenerado: {contract.contract_number} "
                f"(versión {contract.version})"
            )
        
        return contract
    
    @staticmethod
    def publish_contract(contract: Contract, published_by=None) -> Contract:
        """
        Publica un contrato (cambia estado a PENDING_SIGNATURE).
        
        Args:
            contract: Contrato a publicar
            published_by: Usuario que publica el contrato
        
        Returns:
            Contract: Contrato publicado
        
        Raises:
            ValueError: Si el contrato no puede ser publicado
        """
        # Solo se pueden publicar contratos en DRAFT
        if contract.status != Contract.Status.DRAFT:
            raise ValueError(
                f"Solo se pueden publicar contratos en estado DRAFT. "
                f"Estado actual: {contract.status}"
            )
        
        # Validar que tenga PDF generado (opcional en desarrollo)
        # if not contract.pdf_file:
        #     raise ValueError(
        #         "El contrato debe tener un PDF generado antes de ser publicado."
        #     )
        
        with transaction.atomic():
            contract.status = Contract.Status.PENDING_SIGNATURE
            contract.published_by = published_by
            contract.published_at = timezone.now()
            contract.save(update_fields=[
                'status',
                'published_by',
                'published_at',
                'updated_at'
            ])
            
            logger.info(
                f"Contrato publicado: {contract.contract_number} "
                f"por {published_by}"
            )
        
        return contract
    
    @staticmethod
    def cancel_contract(
        contract: Contract,
        cancellation_reason: str,
        cancelled_by=None
    ) -> Contract:
        """
        Cancela un contrato.
        
        Args:
            contract: Contrato a cancelar
            cancellation_reason: Motivo de la cancelación
            cancelled_by: Usuario que cancela el contrato
        
        Returns:
            Contract: Contrato cancelado
        
        Raises:
            ValueError: Si el contrato no puede ser cancelado
        """
        if not contract.can_be_cancelled():
            raise ValueError(
                f"El contrato en estado {contract.status} no puede ser cancelado."
            )
        
        if not cancellation_reason or not cancellation_reason.strip():
            raise ValueError("Debe especificar un motivo de cancelación.")
        
        with transaction.atomic():
            contract.status = Contract.Status.CANCELLED
            contract.cancellation_reason = cancellation_reason
            contract.cancelled_by = cancelled_by
            contract.cancelled_at = timezone.now()
            contract.save(update_fields=[
                'status',
                'cancellation_reason',
                'cancelled_by',
                'cancelled_at',
                'updated_at'
            ])
            
            logger.info(
                f"Contrato cancelado: {contract.contract_number} "
                f"por {cancelled_by}. Motivo: {cancellation_reason}"
            )
        
        return contract
    
    @staticmethod
    def get_contract_variables(contract: Contract) -> dict:
        """
        Obtiene las variables disponibles para reemplazar en la plantilla.
        
        Args:
            contract: Contrato
        
        Returns:
            dict: Diccionario con las variables y sus valores
        """
        application = contract.loan_application
        client = application.client
        product = application.product
        institution = contract.institution
        
        variables = {
            # Institución
            'institution_name': institution.name,
            'institution_address': getattr(institution, 'address', ''),
            'institution_nit': getattr(institution, 'nit', ''),
            'institution_phone': getattr(institution, 'phone', ''),
            'institution_email': getattr(institution, 'email', ''),
            
            # Cliente/Prestatario
            'borrower_name': client.get_full_name(),
            'borrower_document': client.document_number,
            'borrower_address': client.address or '',
            'borrower_email': client.email or '',
            'borrower_phone': client.phone or '',
            
            # Contrato
            'contract_number': contract.contract_number,
            'contract_date': contract.contract_date.strftime('%d/%m/%Y'),
            'start_date': contract.start_date.strftime('%d/%m/%Y'),
            'end_date': contract.end_date.strftime('%d/%m/%Y'),
            
            # Términos financieros
            'principal_amount': f"Bs. {contract.principal_amount:,.2f}",
            'principal_amount_raw': str(contract.principal_amount),
            'interest_rate': f"{contract.interest_rate}%",
            'interest_rate_raw': str(contract.interest_rate),
            'term_months': str(contract.term_months),
            'monthly_payment': f"Bs. {contract.monthly_payment:,.2f}",
            'monthly_payment_raw': str(contract.monthly_payment),
            'total_amount': f"Bs. {contract.total_amount:,.2f}",
            'total_amount_raw': str(contract.total_amount),
            
            # Fechas de pago
            'first_payment_date': contract.first_payment_date.strftime('%d/%m/%Y'),
            'last_payment_date': contract.end_date.strftime('%d/%m/%Y'),
            
            # Producto
            'product_name': product.name,
            'product_description': product.description or '',
        }
        
        return variables
