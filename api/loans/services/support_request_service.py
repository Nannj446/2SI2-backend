"""
Servicio de gestión de solicitudes de apoyo de pago.

Permite al cliente solicitar:
- Período de gracia
- Reestructuración del crédito

El banco revisa desde web y puede aprobar, rechazar o solicitar más información.
La aplicación real (GracePeriodService/RestructuringService) solo ocurre al aprobar.
"""

import logging
from django.db import transaction
from django.utils import timezone

from api.audit.models import AuditLog

logger = logging.getLogger(__name__)


class SupportRequestService:
    """Servicio para gestión de CreditSupportRequest."""

    @classmethod
    def create_request(cls, active_credit, client, data: dict, user=None) -> 'CreditSupportRequest':
        """
        Crea una solicitud de apoyo de pago desde mobile.

        Args:
            active_credit: Instancia de ActiveCredit
            client: Instancia de Client (prestatario)
            data: Dict con campos del formulario mobile
            user: Usuario autenticado (cliente)

        Returns:
            CreditSupportRequest creado

        Raises:
            ValueError si el crédito está cancelado o ya existe solicitud pendiente
        """
        from api.loans.models_active import CreditSupportRequest, ActiveCredit

        if active_credit.status == ActiveCredit.Status.CANCELLED:
            raise ValueError("No se puede solicitar apoyo para un crédito cancelado.")

        request_type = data['request_type']

        # No permitir duplicar solicitud pendiente del mismo tipo
        existing = CreditSupportRequest.objects.filter(
            active_credit=active_credit,
            request_type=request_type,
            status__in=[CreditSupportRequest.RequestStatus.PENDING,
                        CreditSupportRequest.RequestStatus.UNDER_REVIEW],
        ).first()

        if existing:
            raise ValueError(
                f"Ya existe una solicitud de {existing.get_request_type_display()} "
                f"pendiente de revisión."
            )

        support_request = CreditSupportRequest.objects.create(
            institution=active_credit.institution,
            active_credit=active_credit,
            client=client,
            request_type=request_type,
            reason_category=data.get('reason_category', 'other'),
            description=data['description'],
            requested_months=data.get('requested_months'),
            contact_phone=data.get('contact_phone', ''),
            status=CreditSupportRequest.RequestStatus.PENDING,
        )

        cls._audit(
            user=user,
            action='create',
            resource_type='CreditSupportRequest',
            resource_id=support_request.id,
            institution=active_credit.institution,
            description=f'Solicitud de apoyo creada: {support_request.get_request_type_display()} '
                       f'para {active_credit.credit_number}',
            metadata={
                'request_type': request_type,
                'credit_number': active_credit.credit_number,
                'client_id': client.id,
            }
        )

        logger.info(
            f"Solicitud de apoyo #{support_request.id} creada: "
            f"{request_type} para {active_credit.credit_number}"
        )

        return support_request

    @classmethod
    def start_review(cls, support_request, user=None):
        """Marca la solicitud como 'en revisión'."""
        from api.loans.models_active import CreditSupportRequest

        if support_request.status != CreditSupportRequest.RequestStatus.PENDING:
            raise ValueError(f"La solicitud no está pendiente (estado: {support_request.get_status_display()})")

        support_request.status = CreditSupportRequest.RequestStatus.UNDER_REVIEW
        support_request.reviewed_by = user
        support_request.reviewed_at = timezone.now()
        support_request.save(update_fields=['status', 'reviewed_by', 'reviewed_at', 'updated_at'])

        cls._audit(
            user=user, action='update_full',
            resource_type='CreditSupportRequest', resource_id=support_request.id,
            institution=support_request.institution,
            description=f'Revisión iniciada para solicitud #{support_request.id}',
        )

    @classmethod
    def approve(cls, support_request, bank_response='', user=None) -> dict:
        """
        Aprueba la solicitud y aplica la gracia o reestructuración real.

        Returns:
            Dict con resultado de la operación
        """
        from api.loans.models_active import CreditSupportRequest, ActiveCredit

        if support_request.status != CreditSupportRequest.RequestStatus.UNDER_REVIEW:
            raise ValueError("La solicitud debe estar en revisión para aprobarse.")

        active_credit = support_request.active_credit

        with transaction.atomic():
            active_credit = ActiveCredit.objects.select_for_update().get(pk=active_credit.pk)

            result = {
                'action': support_request.request_type,
                'credit_number': active_credit.credit_number,
            }

            if support_request.request_type == CreditSupportRequest.RequestType.GRACE_PERIOD:
                from api.loans.services.grace_period_service import GracePeriodService

                # Determinar tipo de gracia y fechas
                grace_type = 'INTEREST_ONLY'
                start_date = timezone.now().date()
                from datetime import timedelta
                months = support_request.requested_months or 1
                end_date = start_date + timedelta(days=months * 30)

                grace = GracePeriodService.apply_grace_period(
                    active_credit=active_credit,
                    grace_type=grace_type,
                    start_date=start_date,
                    end_date=end_date,
                    reason=f"Solicitud de cliente aprobada. {support_request.description[:200]}",
                    user=user,
                )
                result['grace_period_id'] = grace.id
                result['grace_type'] = grace_type
                result['start_date'] = start_date.isoformat()
                result['end_date'] = end_date.isoformat()

            elif support_request.request_type == CreditSupportRequest.RequestType.RESTRUCTURING:
                from api.loans.services.restructuring_service import RestructuringService

                new_terms = {
                    'reason': f"Solicitud de cliente aprobada. {support_request.description[:200]}",
                }
                if support_request.requested_months:
                    new_terms['new_term_periods'] = support_request.requested_months

                restructuring = RestructuringService.apply_restructuring(
                    active_credit=active_credit,
                    new_terms=new_terms,
                    reason=new_terms['reason'],
                    user=user,
                )
                result['restructuring_id'] = restructuring.id

            # Actualizar solicitud
            support_request.status = CreditSupportRequest.RequestStatus.APPROVED
            support_request.bank_response = bank_response
            support_request.reviewed_by = user
            support_request.reviewed_at = timezone.now()
            support_request.approved_terms_snapshot = result
            support_request.save()

            cls._audit(
                user=user, action='update_full',
                resource_type='CreditSupportRequest', resource_id=support_request.id,
                institution=support_request.institution,
                description=f'Solicitud #{support_request.id} APROBADA: {support_request.get_request_type_display()}',
                metadata=result,
                severity='warning',
            )

        return result

    @classmethod
    def reject(cls, support_request, reason='', user=None):
        """Rechaza la solicitud con un motivo."""
        from api.loans.models_active import CreditSupportRequest

        if support_request.status not in [CreditSupportRequest.RequestStatus.PENDING,
                                           CreditSupportRequest.RequestStatus.UNDER_REVIEW]:
            raise ValueError("Solo se pueden rechazar solicitudes pendientes o en revisión.")

        support_request.status = CreditSupportRequest.RequestStatus.REJECTED
        support_request.bank_response = reason
        support_request.reviewed_by = user
        support_request.reviewed_at = timezone.now()
        support_request.save()

        cls._audit(
            user=user, action='update_full',
            resource_type='CreditSupportRequest', resource_id=support_request.id,
            institution=support_request.institution,
            description=f'Solicitud #{support_request.id} RECHAZADA: {reason}',
            severity='warning',
        )

    @classmethod
    def request_more_info(cls, support_request, requested_info='', user=None):
        """Solicita más información al cliente."""
        from api.loans.models_active import CreditSupportRequest

        if support_request.status not in [CreditSupportRequest.RequestStatus.PENDING,
                                           CreditSupportRequest.RequestStatus.UNDER_REVIEW]:
            raise ValueError("Solo se puede pedir info de solicitudes pendientes o en revisión.")

        support_request.status = CreditSupportRequest.RequestStatus.UNDER_REVIEW
        support_request.requires_more_info = True
        support_request.requested_info = requested_info
        support_request.reviewed_by = user
        support_request.reviewed_at = timezone.now()
        support_request.save()

        cls._audit(
            user=user, action='update_full',
            resource_type='CreditSupportRequest', resource_id=support_request.id,
            institution=support_request.institution,
            description=f'Info adicional solicitada para solicitud #{support_request.id}',
        )

    @classmethod
    def cancel(cls, support_request, user=None):
        """El cliente cancela su propia solicitud."""
        from api.loans.models_active import CreditSupportRequest

        if support_request.status not in [CreditSupportRequest.RequestStatus.PENDING,
                                           CreditSupportRequest.RequestStatus.UNDER_REVIEW]:
            raise ValueError("Solo se pueden cancelar solicitudes pendientes o en revisión.")

        support_request.status = CreditSupportRequest.RequestStatus.CANCELLED
        support_request.save()

        cls._audit(
            user=user, action='delete',
            resource_type='CreditSupportRequest', resource_id=support_request.id,
            institution=support_request.institution,
            description=f'Solicitud #{support_request.id} cancelada por el cliente',
        )

    @classmethod
    def _audit(cls, user=None, action='', resource_type='', resource_id=None,
               institution=None, description='', metadata=None, severity='info'):
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
            logger.error(f"Error en auditoría de solicitud: {e}", exc_info=True)
