"""
Servicio de integración con Stripe para pagos online de cuotas.

Maneja:
- Creación de Stripe Checkout Sessions para pagos de cuotas
- Validación de webhooks con verificación de firma
- Procesamiento idempotente de eventos de pago
"""

import logging
import stripe
from django.conf import settings
from django.utils import timezone
from decimal import Decimal

logger = logging.getLogger(__name__)


class StripePaymentService:
    """Servicio para pagos de cuotas vía Stripe Checkout."""

    @classmethod
    def _init_stripe(cls):
        """Inicializa Stripe con la API key."""
        if settings.STRIPE_SECRET_KEY:
            stripe.api_key = settings.STRIPE_SECRET_KEY
            stripe.api_version = settings.STRIPE_API_VERSION

    @classmethod
    def is_configured(cls) -> bool:
        """Verifica si Stripe está configurado."""
        return bool(settings.STRIPE_SECRET_KEY and settings.STRIPE_PUBLISHABLE_KEY)

    @classmethod
    def create_checkout_session(cls, payment, success_url: str, cancel_url: str) -> dict:
        """
        Crea una sesión de Stripe Checkout para pagar una cuota.

        Args:
            payment: Instancia de CreditPayment (PENDING_CONFIRMATION, ONLINE)
            success_url: URL de retorno en éxito
            cancel_url: URL de retorno en cancelación

        Returns:
            Dict con { session_id, url }

        Raises:
            ValueError: Si Stripe no está configurado
        """
        if not cls.is_configured():
            raise ValueError("Stripe no está configurado. Configure STRIPE_SECRET_KEY y STRIPE_PUBLISHABLE_KEY.")

        cls._init_stripe()

        active_credit = payment.active_credit
        installment = payment.allocations.first().installment if payment.allocations.exists() else None

        line_item_name = f"Cuota - {active_credit.credit_number}"
        if installment:
            line_item_name += f" #{installment.installment_number}"

        try:
            session = stripe.checkout.Session.create(
                payment_method_types=['card'],
                line_items=[{
                    'price_data': {
                        'currency': settings.STRIPE_DEFAULT_CURRENCY,
                        'product_data': {
                            'name': line_item_name,
                            'description': f'Pago de cuota crédito {active_credit.credit_number}',
                        },
                        'unit_amount': int(payment.amount * 100),  # Stripe usa centavos
                    },
                    'quantity': 1,
                }],
                mode='payment',
                success_url=success_url,
                cancel_url=cancel_url,
                metadata={
                    'payment_id': str(payment.id),
                    'credit_number': active_credit.credit_number,
                    'installment_number': str(installment.installment_number) if installment else '',
                },
            )

            # Guardar IDs de Stripe en el pago
            payment.provider = 'STRIPE'
            payment.provider_payment_id = session.id
            payment.metadata['stripe_session_url'] = session.url
            payment.metadata['stripe_session_id'] = session.id
            payment.save(update_fields=['provider', 'provider_payment_id', 'metadata', 'updated_at'])

            return {
                'session_id': session.id,
                'url': session.url,
            }

        except stripe.error.StripeError as e:
            logger.error(f"Stripe error creando checkout session: {e}")
            payment.status = 'FAILED'
            payment.notes = f'Error Stripe: {str(e)}'
            payment.save(update_fields=['status', 'notes', 'updated_at'])
            raise ValueError(f"Error de Stripe: {str(e)}")

    @classmethod
    def handle_webhook(cls, payload: bytes, sig_header: str) -> dict:
        """
        Procesa un webhook de Stripe con validación de firma.

        Args:
            payload: Body crudo del request
            sig_header: Header HTTP_STRIPE_SIGNATURE

        Returns:
            Dict con { processed: bool, event_type: str, payment_id: int or None }

        Raises:
            ValueError: Si la firma es inválida
        """
        if not cls.is_configured():
            raise ValueError("Stripe no está configurado.")

        cls._init_stripe()

        # Validar firma del webhook
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
            )
        except ValueError:
            logger.warning("Stripe webhook: payload inválido")
            raise ValueError("Invalid payload")
        except stripe.error.SignatureVerificationError:
            logger.warning("Stripe webhook: firma inválida")
            raise ValueError("Invalid signature")

        event_type = event['type']
        event_data = event['data']['object']
        payment_id = None

        logger.info(f"Stripe webhook recibido: {event_type} (event_id={event['id']})")

        # Manejar checkout.session.completed
        if event_type == 'checkout.session.completed':
            payment_id = cls._handle_checkout_completed(event_data)

        # Manejar otros eventos relevantes
        elif event_type == 'payment_intent.succeeded':
            logger.info(f"PaymentIntent succeeded: {event_data.get('id')}")
        elif event_type == 'payment_intent.payment_failed':
            logger.warning(f"PaymentIntent failed: {event_data.get('id')}")

        return {
            'processed': payment_id is not None,
            'event_type': event_type,
            'payment_id': payment_id,
        }

    @classmethod
    def _handle_checkout_completed(cls, session_data: dict) -> int:
        """
        Procesa un checkout.session.completed.

        Busca el pago por el session_id guardado en provider_payment_id
        y lo confirma vía PaymentApplicationService.
        """
        from api.loans.models_active import CreditPayment
        from api.loans.services.payment_application_service import PaymentApplicationService

        session_id = session_data.get('id')
        payment_intent_id = session_data.get('payment_intent')
        invoice_id = session_data.get('invoice')

        if not session_id:
            logger.error("Stripe session completada sin session_id")
            return None

        # Buscar pago por provider_payment_id (session_id)
        try:
            payment = CreditPayment.objects.get(
                provider='STRIPE',
                provider_payment_id=session_id,
                status='PENDING_CONFIRMATION',
            )
        except CreditPayment.DoesNotExist:
            logger.error(f"No se encontró pago para session_id={session_id}")
            return None
        except CreditPayment.MultipleObjectsReturned:
            logger.error(f"Múltiples pagos para session_id={session_id}")
            return None

        # Guardar el payment_intent_id y extraer método de pago real de Stripe
        if payment_intent_id:
            payment.metadata['payment_intent_id'] = payment_intent_id
            cls._update_payment_method_from_stripe(payment, payment_intent_id)

        # Obtener URLs de la factura de Stripe
        if invoice_id:
            cls._store_invoice_urls(payment, invoice_id)

        payment.save(update_fields=['metadata', 'updated_at'])

        # Confirmar el pago
        try:
            PaymentApplicationService.apply_payment(payment)
            logger.info(f"Pago {payment.id} confirmado vía webhook Stripe session={session_id}")
        except Exception as e:
            logger.error(f"Error confirmando pago {payment.id}: {e}", exc_info=True)
            payment.status = 'MANUAL_REVIEW'
            payment.notes = f'Error confirmando vía webhook: {str(e)}'
            payment.save(update_fields=['status', 'notes', 'updated_at'])

        return payment.id

    @classmethod
    def _store_invoice_urls(cls, payment, invoice_id: str):
        """
        Obtiene las URLs de la factura de Stripe y las guarda en metadata.
        Retorna True si se obtuvieron URLs.
        """
        cls._init_stripe()
        try:
            invoice = stripe.Invoice.retrieve(invoice_id)
            hosted_url = getattr(invoice, 'hosted_invoice_url', None)
            pdf_url = getattr(invoice, 'invoice_pdf', None)
            invoice_number = getattr(invoice, 'number', None)
            if hosted_url:
                payment.metadata['stripe_invoice_url'] = hosted_url
            if pdf_url:
                payment.metadata['stripe_invoice_pdf'] = pdf_url
            if invoice_number:
                payment.metadata['stripe_invoice_number'] = invoice_number
            if hosted_url or pdf_url:
                logger.info(f"Pago {payment.id}: URLs de factura guardadas (invoice={invoice_id})")
            return bool(hosted_url or pdf_url)
        except Exception as e:
            logger.warning(f"No se pudo obtener factura de Stripe "
                          f"invoice={invoice_id}: {e}")
            return False

    @classmethod
    def _store_receipt_url(cls, payment, payment_intent_id: str):
        """
        Obtiene la URL del recibo desde el PaymentIntent para mode=payment.
        Retorna True si se obtuvo la URL.
        """
        cls._init_stripe()
        try:
            pi = stripe.PaymentIntent.retrieve(payment_intent_id)
            latest_charge_id = getattr(pi, 'latest_charge', None)
            if not latest_charge_id:
                return False
            charge = stripe.Charge.retrieve(latest_charge_id)
            receipt_url = getattr(charge, 'receipt_url', None)
            if receipt_url:
                payment.metadata['stripe_invoice_url'] = receipt_url
                payment.metadata['stripe_receipt_url'] = receipt_url
                logger.info(f"Pago {payment.id}: receipt URL guardada desde PaymentIntent={payment_intent_id}")
                return True
        except Exception as e:
            logger.warning(f"No se pudo obtener receipt para "
                          f"payment_intent={payment_intent_id}: {e}")
        return False

    @classmethod
    def ensure_invoice_urls(cls, payment) -> bool:
        """
        Intenta obtener las URLs de factura/recibo de Stripe para un pago.

        Si el pago ya tiene URLs, no hace nada.
        Si es un pago de Stripe con provider_payment_id (session_id),
        busca la factura (subscription mode) o recibo (payment mode).

        Returns:
            True si se obtuvieron (o ya existían) URLs.
        """
        if payment.metadata.get('stripe_invoice_url'):
            return True

        if payment.provider != 'STRIPE' or not payment.provider_payment_id:
            return False

        cls._init_stripe()
        try:
            session = stripe.checkout.Session.retrieve(payment.provider_payment_id)
            invoice_id = getattr(session, 'invoice', None)
            payment_intent_id = getattr(session, 'payment_intent', None)

            result = False

            # 1. Intentar con factura (mode=subscription)
            if invoice_id:
                result = cls._store_invoice_urls(payment, invoice_id)

            # 2. Si no hay factura, intentar con recibo (mode=payment)
            if not result and payment_intent_id:
                result = cls._store_receipt_url(payment, payment_intent_id)

            if result:
                payment.save(update_fields=['metadata', 'updated_at'])

            return result
        except Exception as e:
            logger.warning(f"No se pudo obtener factura/recibo para pago {payment.id}: {e}")

        return False

    @classmethod
    def _update_payment_method_from_stripe(cls, payment, payment_intent_id: str):
        """
        Obtiene el método de pago real usado en Stripe y lo guarda en payment.method.
        """
        cls._init_stripe()
        try:
            pi = stripe.PaymentIntent.retrieve(payment_intent_id)
            payment_method_details = getattr(pi, 'payment_method', None)
            if payment_method_details:
                pm_type = getattr(payment_method_details, 'type', None)
                if pm_type:
                    method = pm_type.upper().replace('-', '_')
                    payment.method = method
                    payment.save(update_fields=['method', 'updated_at'])
                    logger.info(f"Pago {payment.id}: método actualizado a {method} desde Stripe")
        except Exception as e:
            logger.warning(f"No se pudo obtener método de pago de Stripe para "
                          f"payment_intent={payment_intent_id}: {e}")

    @classmethod
    def verify_payment(cls, payment_id: int) -> dict:
        """
        Verifica el estado de un pago consultando directamente la sesión de Stripe.

        Útil cuando los webhooks no están configurados en desarrollo local.
        Si la sesión de Stripe está completa, confirma el pago automáticamente.

        Args:
            payment_id: ID del CreditPayment a verificar

        Returns:
            Dict con { confirmed: bool, status: str, stripe_status: str }
        """
        if not cls.is_configured():
            raise ValueError("Stripe no está configurado.")

        cls._init_stripe()

        from api.loans.models_active import CreditPayment
        from api.loans.services.payment_application_service import PaymentApplicationService

        try:
            payment = CreditPayment.objects.get(
                pk=payment_id,
                provider='STRIPE',
                status='PENDING_CONFIRMATION',
            )
        except CreditPayment.DoesNotExist:
            return {'confirmed': False, 'status': 'NOT_FOUND', 'stripe_status': None}

        session_id = payment.provider_payment_id
        if not session_id:
            return {'confirmed': False, 'status': payment.status, 'stripe_status': None}

        try:
            session = stripe.checkout.Session.retrieve(session_id)
        except stripe.error.StripeError as e:
            logger.error(f"Error verificando sesión Stripe {session_id}: {e}")
            return {'confirmed': False, 'status': payment.status, 'stripe_status': 'error'}

        stripe_status = getattr(session, 'payment_status', None)
        stripe_payment_intent = getattr(session, 'payment_intent', None)

        if stripe_payment_intent:
            payment.metadata['payment_intent_id'] = stripe_payment_intent
            cls._update_payment_method_from_stripe(payment, stripe_payment_intent)

        # Obtener URLs de la factura
        stripe_invoice_id = getattr(session, 'invoice', None)
        if stripe_invoice_id:
            cls._store_invoice_urls(payment, stripe_invoice_id)

        if stripe_status == 'paid':
            try:
                PaymentApplicationService.apply_payment(payment)
                return {'confirmed': True, 'status': 'CONFIRMED', 'stripe_status': stripe_status}
            except Exception as e:
                logger.error(f"Error confirmando pago {payment_id}: {e}", exc_info=True)
                return {'confirmed': False, 'status': payment.status, 'stripe_status': stripe_status}
        elif stripe_status == 'unpaid':
            return {'confirmed': False, 'status': 'PENDING_CONFIRMATION', 'stripe_status': stripe_status}
        else:
            return {'confirmed': False, 'status': payment.status, 'stripe_status': stripe_status}
