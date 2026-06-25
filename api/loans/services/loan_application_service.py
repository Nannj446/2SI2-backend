"""
Servicio para gestión de solicitudes de crédito.

Maneja la lógica de negocio para:
- Creación y envío de solicitudes
- Revisión y evaluación
- Aprobación y rechazo
- Desembolso
- Cálculo de score y ratios
"""

from django.db import transaction
from django.utils import timezone
from api.loans.models import LoanApplication


class LoanApplicationService:
    """
    Servicio para gestión de solicitudes de crédito.
    """
    
    @staticmethod
    @transaction.atomic
    def submit_application(application):
        """
        Envía una solicitud de crédito para revisión.
        
        Args:
            application: LoanApplication
        
        Returns:
            LoanApplication: Solicitud actualizada
        """
        if application.status != LoanApplication.Status.DRAFT:
            raise ValueError("Solo se pueden enviar solicitudes en estado DRAFT")
        
        application.status = LoanApplication.Status.SUBMITTED
        application.submitted_at = timezone.now()
        application.save(update_fields=['status', 'submitted_at'])
        
        return application
    
    @staticmethod
    @transaction.atomic
    def start_review(application, reviewer):
        """
        Inicia la revisión de una solicitud.
        
        Args:
            application: LoanApplication
            reviewer: Usuario que revisa
        
        Returns:
            LoanApplication: Solicitud actualizada
        """
        if application.status != LoanApplication.Status.SUBMITTED:
            raise ValueError("Solo se pueden revisar solicitudes en estado SUBMITTED")
        
        application.status = LoanApplication.Status.UNDER_REVIEW
        application.reviewed_by = reviewer
        application.reviewed_at = timezone.now()
        application.save(update_fields=['status', 'reviewed_by', 'reviewed_at'])
        
        return application
    
    @staticmethod
    @transaction.atomic
    def update_evaluation(application, **evaluation_data):
        """
        Actualiza la evaluación de una solicitud.
        
        Args:
            application: LoanApplication
            **evaluation_data: Datos de evaluación
        
        Returns:
            LoanApplication: Solicitud actualizada
        """
        for key, value in evaluation_data.items():
            if hasattr(application, key):
                setattr(application, key, value)
        
        application.save()
        return application
    
    @staticmethod
    def calculate_score(application):
        """
        Calcula el score crediticio de una solicitud.
        
        Args:
            application: LoanApplication
        
        Returns:
            float: Score calculado
        """
        # TODO: Implementar lógica de cálculo de score
        # Por ahora retornar un valor por defecto
        return 0.0
    
    @staticmethod
    def determine_risk_level(score):
        """
        Determina el nivel de riesgo basado en el score.
        
        Args:
            score: Score crediticio
        
        Returns:
            str: Nivel de riesgo
        """
        if score >= 80:
            return 'LOW'
        elif score >= 60:
            return 'MEDIUM'
        else:
            return 'HIGH'
    
    @staticmethod
    def calculate_debt_to_income_ratio(application):
        """
        Calcula el ratio deuda/ingreso.
        
        Args:
            application: LoanApplication
        
        Returns:
            float: Ratio calculado
        """
        if not application.monthly_income or application.monthly_income == 0:
            return 0.0
        
        # TODO: Calcular deudas totales del cliente
        total_debt = 0.0
        
        return (total_debt / application.monthly_income) * 100
    
    @staticmethod
    def validate_approved_terms(application, approved_amount, approved_term_months, approved_interest_rate):
        """
        Valida que los términos aprobados estén dentro de los límites del producto.
        
        Args:
            application: LoanApplication
            approved_amount: Decimal - Monto aprobado
            approved_term_months: int - Plazo aprobado en meses
            approved_interest_rate: Decimal - Tasa de interés aprobada
        
        Raises:
            ValidationError: Si algún valor está fuera de rango
        
        Returns:
            bool: True si todas las validaciones pasan
        """
        from rest_framework.exceptions import ValidationError
        from decimal import Decimal
        
        product = application.product
        errors = {}
        
        # Convertir a Decimal si es necesario
        if approved_amount is not None:
            approved_amount = Decimal(str(approved_amount))
        if approved_interest_rate is not None:
            approved_interest_rate = Decimal(str(approved_interest_rate))
        
        # Validar monto
        if approved_amount is not None:
            min_amount = Decimal(str(product.min_amount))
            max_amount = Decimal(str(product.max_amount))
            
            if approved_amount < min_amount:
                errors['approved_amount'] = f'El monto mínimo permitido es {min_amount}'
            elif approved_amount > max_amount:
                errors['approved_amount'] = f'El monto máximo permitido es {max_amount}'
        
        # Validar plazo
        if approved_term_months is not None:
            if approved_term_months < product.min_term_months:
                errors['approved_term_months'] = f'El plazo mínimo permitido es {product.min_term_months} meses'
            elif approved_term_months > product.max_term_months:
                errors['approved_term_months'] = f'El plazo máximo permitido es {product.max_term_months} meses'
        
        # Validar tasa de interés
        if approved_interest_rate is not None:
            if approved_interest_rate < 0:
                errors['approved_interest_rate'] = 'La tasa de interés debe ser positiva'
            elif approved_interest_rate > 100:
                errors['approved_interest_rate'] = 'La tasa de interés no puede exceder 100%'
        
        if errors:
            raise ValidationError(errors)
        
        return True
    
    @staticmethod
    @transaction.atomic
    def approve_application(application, approver, **approval_data):
        """
        Aprueba una solicitud de crédito.
        
        Args:
            application: LoanApplication
            approver: Usuario que aprueba
            **approval_data: Datos de aprobación
        
        Returns:
            LoanApplication: Solicitud actualizada
        """
        if application.status not in [LoanApplication.Status.UNDER_REVIEW, LoanApplication.Status.SUBMITTED]:
            raise ValueError("Solo se pueden aprobar solicitudes en revisión")
        
        # Validar términos aprobados si se proporcionan
        approved_amount = approval_data.get('approved_amount')
        approved_term_months = approval_data.get('approved_term_months')
        approved_interest_rate = approval_data.get('approved_interest_rate')
        
        if any([approved_amount, approved_term_months, approved_interest_rate]):
            # Usar valores solicitados como default si no se proporcionan
            from decimal import Decimal
            
            if approved_amount is None:
                approved_amount = application.requested_amount
            if approved_term_months is None:
                approved_term_months = application.term_months
            if approved_interest_rate is None:
                approved_interest_rate = Decimal(str(application.product.interest_rate))
            
            # Validar límites
            LoanApplicationService.validate_approved_terms(
                application,
                approved_amount,
                approved_term_months,
                approved_interest_rate
            )
        
        application.status = LoanApplication.Status.APPROVED
        application.approved_by = approver
        application.approved_at = timezone.now()
        
        # Actualizar datos de aprobación
        for key, value in approval_data.items():
            if hasattr(application, key):
                setattr(application, key, value)
        
        application.save()
        return application
    
    @staticmethod
    @transaction.atomic
    def reject_application(application, reviewer, rejection_reason=''):
        """
        Rechaza una solicitud de crédito.
        
        Args:
            application: LoanApplication
            reviewer: Usuario que rechaza
            rejection_reason: Razón del rechazo
        
        Returns:
            LoanApplication: Solicitud actualizada
        """
        if application.status not in [LoanApplication.Status.UNDER_REVIEW, LoanApplication.Status.SUBMITTED]:
            raise ValueError("Solo se pueden rechazar solicitudes en revisión")
        
        application.status = LoanApplication.Status.REJECTED
        application.reviewed_by = reviewer
        application.reviewed_at = timezone.now()
        application.rejection_reason = rejection_reason
        application.save(update_fields=['status', 'reviewed_by', 'reviewed_at', 'rejection_reason'])
        
        return application
    
    @staticmethod
    @transaction.atomic
    def disburse_application(application, **disbursement_data):
        """
        Desembolsa una solicitud aprobada.
        
        Args:
            application: LoanApplication
            **disbursement_data: Datos de desembolso
        
        Returns:
            LoanApplication: Solicitud actualizada
        """
        if application.status != LoanApplication.Status.APPROVED:
            raise ValueError("Solo se pueden desembolsar solicitudes aprobadas")
        
        application.status = LoanApplication.Status.DISBURSED
        application.disbursed_at = timezone.now()
        
        # Actualizar datos de desembolso
        for key, value in disbursement_data.items():
            if hasattr(application, key):
                setattr(application, key, value)
        
        application.save()
        return application
