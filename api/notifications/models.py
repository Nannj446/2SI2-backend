"""
Modelos para gestión de notificaciones push.
"""

from django.db import models
from django.conf import settings
from api.core.models import TenantModel, TimeStampedModel


class DeviceType(models.TextChoices):
    ANDROID = 'ANDROID', 'Android'
    IOS = 'IOS', 'iOS'
    WEB = 'WEB', 'Web'


class NotificationType(models.TextChoices):
    MORA_ALERT = 'MORA_ALERT', 'Alerta de Mora'
    PAYMENT_REMINDER = 'PAYMENT_REMINDER', 'Recordatorio de Pago'
    STATUS_CHANGE = 'STATUS_CHANGE', 'Cambio de Estado'
    NEW_MESSAGE = 'NEW_MESSAGE', 'Nuevo Mensaje'
    SYSTEM = 'SYSTEM', 'Sistema'
    MARKETING = 'MARKETING', 'Marketing'
    GENERAL = 'GENERAL', 'General'


class PushToken(TenantModel):
    """
    Token de dispositivo para notificaciones push.
    Cada usuario puede tener múltiples tokens (múltiples dispositivos).
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='push_tokens',
        verbose_name='Usuario'
    )

    token = models.CharField(
        max_length=500,
        verbose_name='FCM Token',
        help_text='Token de Firebase Cloud Messaging'
    )

    device_type = models.CharField(
        max_length=10,
        choices=DeviceType.choices,
        default=DeviceType.ANDROID,
        verbose_name='Tipo de Dispositivo'
    )

    device_name = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name='Nombre del Dispositivo',
        help_text='Ej: iPhone 15, Chrome on Windows'
    )

    device_id = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name='ID del Dispositivo',
        help_text='Identificador único del dispositivo'
    )

    is_active = models.BooleanField(
        default=True,
        verbose_name='Activo'
    )

    last_used_at = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name='Último Uso'
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Token Push'
        verbose_name_plural = 'Tokens Push'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'is_active']),
            models.Index(fields=['token']),
            models.Index(fields=['device_type']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['token'],
                condition=models.Q(is_active=True),
                name='unique_active_token'
            )
        ]

    def __str__(self):
        return f"{self.user.email} - {self.device_type} ({self.device_name or 'Unknown'})"


class NotificationTemplate(TenantModel):
    """
    Plantillas de notificaciones para reutilización.
    Permiten crear notificaciones parametrizadas.
    """

    code = models.CharField(
        max_length=50,
        verbose_name='Código',
        help_text='Código único para identificar la plantilla'
    )

    name = models.CharField(
        max_length=100,
        verbose_name='Nombre'
    )

    notification_type = models.CharField(
        max_length=20,
        choices=NotificationType.choices,
        default=NotificationType.GENERAL,
        verbose_name='Tipo de Notificación'
    )

    title_template = models.CharField(
        max_length=200,
        verbose_name='Título',
        help_text='Título de la notificación. Usar {{variable}} para parámetros.'
    )

    body_template = models.TextField(
        verbose_name='Cuerpo',
        help_text='Cuerpo de la notificación. Usar {{variable}} para parámetros.'
    )

    data_json = models.JSONField(
        default=dict,
        blank=True,
        verbose_name='Datos Adicionales',
        help_text='Datos adicionales en formato JSON para enviar con la notificación'
    )

    is_active = models.BooleanField(
        default=True,
        verbose_name='Activo'
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='notification_templates_created',
        verbose_name='Creado Por'
    )

    class Meta:
        verbose_name = 'Plantilla de Notificación'
        verbose_name_plural = 'Plantillas de Notificaciones'
        ordering = ['name']
        indexes = [
            models.Index(fields=['code']),
            models.Index(fields=['notification_type']),
            models.Index(fields=['is_active']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['institution', 'code'],
                name='unique_template_code_per_institution'
            )
        ]

    def __str__(self):
        return f"{self.code} - {self.name}"

    def render(self, context: dict) -> tuple:
        """
        Renderiza la plantilla con el contexto dado.
        Retorna (title, body, data)
        """
        title = self.title_template
        body = self.body_template

        for key, value in context.items():
            placeholder = f"{{{{{key}}}}}"
            title = title.replace(placeholder, str(value))
            body = body.replace(placeholder, str(value))

        return title, body, self.data_json


class Notification(TenantModel):
    """
    Notificación enviada a un usuario.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notifications',
        verbose_name='Usuario'
    )

    notification_type = models.CharField(
        max_length=20,
        choices=NotificationType.choices,
        default=NotificationType.GENERAL,
        verbose_name='Tipo de Notificación'
    )

    title = models.CharField(
        max_length=200,
        verbose_name='Título'
    )

    body = models.TextField(
        verbose_name='Cuerpo'
    )

    data_json = models.JSONField(
        default=dict,
        blank=True,
        verbose_name='Datos Adicionales'
    )

    image_url = models.URLField(
        blank=True,
        null=True,
        verbose_name='URL de Imagen'
    )

    click_action = models.CharField(
        max_length=200,
        blank=True,
        null=True,
        verbose_name='Acción al Hacer Click',
        help_text='Ruta o deep link a abrir cuando se toca la notificación'
    )

    is_read = models.BooleanField(
        default=False,
        verbose_name='Leída'
    )

    read_at = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name='Fecha de Lectura'
    )

    is_sent = models.BooleanField(
        default=False,
        verbose_name='Enviada'
    )

    sent_at = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name='Fecha de Envío'
    )

    failed_at = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name='Fecha de Fallo'
    )

    error_message = models.TextField(
        blank=True,
        null=True,
        verbose_name='Mensaje de Error'
    )

    sent_via = models.CharField(
        max_length=10,
        blank=True,
        null=True,
        choices=DeviceType.choices,
        verbose_name='Enviada Via'
    )

    class Meta:
        verbose_name = 'Notificación'
        verbose_name_plural = 'Notificaciones'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'is_read']),
            models.Index(fields=['notification_type']),
            models.Index(fields=['created_at']),
            models.Index(fields=['is_sent']),
        ]

    def __str__(self):
        return f"{self.user.email} - {self.title[:30]}"

    def mark_as_read(self):
        if not self.is_read:
            from django.utils import timezone
            self.is_read = True
            self.read_at = timezone.now()
            self.save(update_fields=['is_read', 'read_at'])

    def mark_as_sent(self):
        from django.utils import timezone
        self.is_sent = True
        self.sent_at = timezone.now()
        self.save(update_fields=['is_sent', 'sent_at'])

    def mark_as_failed(self, error_message: str):
        from django.utils import timezone
        self.failed_at = timezone.now()
        self.error_message = error_message
        self.save(update_fields=['failed_at', 'error_message'])
