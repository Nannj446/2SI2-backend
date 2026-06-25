import json
import logging
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Optional

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class EmailInput:
    """Input para envío de email."""

    to_email: str
    subject: str
    template_name: str
    context: dict
    from_email: Optional[str] = None
    from_name: Optional[str] = None


@dataclass(frozen=True)
class EmailResult:
    """Resultado del envío de email."""

    success: bool
    message: str
    email_sent_to: str


class EmailService:
    """Servicio para envío de emails usando SMTP o API HTTPS de Brevo."""

    def execute(self, payload: EmailInput) -> EmailResult:
        """
        Envía un email usando una plantilla HTML.

        Args:
            payload: EmailInput con los datos del email

        Returns:
            EmailResult con el resultado del envío
        """
        try:
            delivery_method = getattr(settings, 'EMAIL_DELIVERY_METHOD', 'smtp').strip().lower()

            if delivery_method not in {'smtp', 'brevo_api', 'smtp_with_brevo_fallback'}:
                logger.warning('EMAIL_DELIVERY_METHOD inválido (%s). Usando smtp.', delivery_method)
                delivery_method = 'smtp'

            # Determinar remitente
            from_email = payload.from_email or settings.DEFAULT_FROM_EMAIL
            from_name = payload.from_name or settings.DEFAULT_FROM_NAME

            if from_email == 'noreply@ejemplo.com':
                logger.warning(
                    'Email no enviado: DEFAULT_FROM_EMAIL mantiene valor de ejemplo',
                    extra={'to_email': payload.to_email},
                )
                return EmailResult(
                    success=False,
                    message='DEFAULT_FROM_EMAIL no está configurado para producción.',
                    email_sent_to=payload.to_email,
                )

            # Renderizar template HTML
            template_context = {'frontend_url': settings.FRONTEND_URL}
            template_context.update(payload.context or {})
            html_content = render_to_string(payload.template_name, template_context)

            if delivery_method == 'brevo_api':
                return self._send_via_brevo_api(
                    payload=payload,
                    from_email=from_email,
                    from_name=from_name,
                    html_content=html_content,
                )

            # SMTP path (smtp | smtp_with_brevo_fallback)
            if not settings.EMAIL_HOST_USER or not settings.EMAIL_HOST_PASSWORD:
                if delivery_method == 'smtp_with_brevo_fallback' and getattr(settings, 'BREVO_API_KEY', None):
                    logger.warning(
                        'Credenciales SMTP no configuradas. Usando fallback Brevo API.',
                        extra={'to_email': payload.to_email},
                    )
                    return self._send_via_brevo_api(
                        payload=payload,
                        from_email=from_email,
                        from_name=from_name,
                        html_content=html_content,
                    )

                logger.warning(
                    'Email no enviado: faltan credenciales SMTP',
                    extra={'to_email': payload.to_email},
                )
                return EmailResult(
                    success=False,
                    message='Configuración SMTP incompleta: faltan credenciales de email.',
                    email_sent_to=payload.to_email,
                )

            from_address = f'{from_name} <{from_email}>'

            # Crear email
            email = EmailMultiAlternatives(
                subject=payload.subject,
                body='',  # Texto plano vacío, usaremos HTML
                from_email=from_address,
                to=[payload.to_email],
            )

            # Adjuntar contenido HTML
            email.attach_alternative(html_content, 'text/html')

            # Enviar por SMTP
            try:
                email.send(fail_silently=False)
            except Exception as smtp_error:
                if delivery_method == 'smtp_with_brevo_fallback' and getattr(settings, 'BREVO_API_KEY', None):
                    logger.warning(
                        'Fallo SMTP (%s). Reintentando vía Brevo API.',
                        smtp_error.__class__.__name__,
                        extra={'to_email': payload.to_email},
                    )
                    api_result = self._send_via_brevo_api(
                        payload=payload,
                        from_email=from_email,
                        from_name=from_name,
                        html_content=html_content,
                    )
                    if api_result.success:
                        return api_result

                raise

            return EmailResult(
                success=True,
                message='Email enviado exitosamente.',
                email_sent_to=payload.to_email,
            )

        except Exception as e:
            logger.exception(
                'Error al enviar email',
                extra={
                    'to_email': payload.to_email,
                    'template_name': payload.template_name,
                },
            )
            return EmailResult(
                success=False,
                message=f'Error al enviar email: {str(e)}',
                email_sent_to=payload.to_email,
            )

    def _send_via_brevo_api(
        self,
        payload: EmailInput,
        from_email: str,
        from_name: str,
        html_content: str,
    ) -> EmailResult:
        """Envía email usando la API HTTPS de Brevo."""
        api_key = getattr(settings, 'BREVO_API_KEY', None)
        api_url = getattr(settings, 'BREVO_API_URL', 'https://api.brevo.com/v3/smtp/email')

        if not api_key:
            return EmailResult(
                success=False,
                message='BREVO_API_KEY no está configurado para envío por API.',
                email_sent_to=payload.to_email,
            )

        request_payload = {
            'sender': {
                'name': from_name,
                'email': from_email,
            },
            'to': [{'email': payload.to_email}],
            'subject': payload.subject,
            'htmlContent': html_content,
        }

        request = urllib.request.Request(
            url=api_url,
            data=json.dumps(request_payload).encode('utf-8'),
            method='POST',
            headers={
                'accept': 'application/json',
                'content-type': 'application/json',
                'api-key': api_key,
            },
        )

        try:
            with urllib.request.urlopen(request, timeout=settings.EMAIL_TIMEOUT) as response:
                status_code = response.getcode()
                if status_code not in {200, 201, 202}:
                    body = response.read().decode('utf-8', errors='ignore')
                    return EmailResult(
                        success=False,
                        message=f'Brevo API respondió con estado {status_code}: {body}',
                        email_sent_to=payload.to_email,
                    )

        except urllib.error.HTTPError as e:
            body = e.read().decode('utf-8', errors='ignore')
            return EmailResult(
                success=False,
                message=f'Error HTTP Brevo API ({e.code}): {body}',
                email_sent_to=payload.to_email,
            )
        except urllib.error.URLError as e:
            return EmailResult(
                success=False,
                message=f'Error de conexión con Brevo API: {e.reason}',
                email_sent_to=payload.to_email,
            )

        return EmailResult(
            success=True,
            message='Email enviado exitosamente vía Brevo API.',
            email_sent_to=payload.to_email,
        )
