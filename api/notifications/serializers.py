"""
Serializers para notificaciones push.
"""

from rest_framework import serializers
from .models import PushToken, NotificationTemplate, Notification, NotificationType, DeviceType


class PushTokenSerializer(serializers.ModelSerializer):
    """Serializer para tokens de dispositivos."""

    class Meta:
        model = PushToken
        fields = [
            'id', 'token', 'device_type', 'device_name',
            'device_id', 'is_active', 'last_used_at', 'created_at'
        ]
        read_only_fields = ['id', 'created_at', 'last_used_at']


class PushTokenCreateSerializer(serializers.ModelSerializer):
    """Serializer para registrar un nuevo token."""

    class Meta:
        model = PushToken
        fields = ['token', 'device_type', 'device_name', 'device_id']

    def validate_token(self, value):
        if not value or len(value) < 50:
            raise serializers.ValidationError("Token inválido.")
        return value


class NotificationTemplateSerializer(serializers.ModelSerializer):
    """Serializer para plantillas de notificaciones."""

    class Meta:
        model = NotificationTemplate
        fields = [
            'id', 'code', 'name', 'notification_type',
            'title_template', 'body_template', 'data_json',
            'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class NotificationTemplateCreateSerializer(serializers.ModelSerializer):
    """Serializer para crear plantillas."""

    class Meta:
        model = NotificationTemplate
        fields = [
            'code', 'name', 'notification_type',
            'title_template', 'body_template', 'data_json', 'is_active'
        ]

    def validate_code(self, value):
        if not value.isalnum() and '_' not in value:
            raise serializers.ValidationError(
                "El código solo puede contener letras, números y guiones bajos."
            )
        return value.upper()


class NotificationSerializer(serializers.ModelSerializer):
    """Serializer para notificaciones."""

    notification_type_display = serializers.CharField(
        source='get_notification_type_display',
        read_only=True
    )

    time_ago = serializers.SerializerMethodField()

    class Meta:
        model = Notification
        fields = [
            'id', 'notification_type', 'notification_type_display',
            'title', 'body', 'data_json', 'image_url', 'click_action',
            'is_read', 'read_at', 'is_sent', 'sent_at',
            'created_at', 'time_ago'
        ]
        read_only_fields = [
            'id', 'is_read', 'read_at', 'is_sent', 'sent_at',
            'created_at'
        ]

    def get_time_ago(self, obj) -> str:
        """Retorna string relativo de tiempo desde creación."""
        from django.utils import timezone
        from datetime import timedelta

        if not obj.created_at:
            return ''

        now = timezone.now()
        diff = now - obj.created_at

        if diff < timedelta(minutes=1):
            return 'Ahora'
        elif diff < timedelta(hours=1):
            minutes = int(diff.total_seconds() / 60)
            return f'Hace {minutes} min'
        elif diff < timedelta(days=1):
            hours = int(diff.total_seconds() / 3600)
            return f'Hace {hours} hr'
        elif diff < timedelta(days=7):
            days = diff.days
            return f'Hace {days} día{"s" if days > 1 else ""}'
        else:
            return obj.created_at.strftime('%d/%m/%Y')


class NotificationListSerializer(serializers.ModelSerializer):
    """Serializer simplificado para listar notificaciones."""

    notification_type_display = serializers.CharField(
        source='get_notification_type_display',
        read_only=True
    )

    time_ago = serializers.SerializerMethodField()

    class Meta:
        model = Notification
        fields = [
            'id', 'notification_type', 'notification_type_display',
            'title', 'body', 'image_url', 'is_read',
            'created_at', 'time_ago'
        ]

    def get_time_ago(self, obj) -> str:
        from django.utils import timezone
        from datetime import timedelta

        if not obj.created_at:
            return ''

        now = timezone.now()
        diff = now - obj.created_at

        if diff < timedelta(minutes=1):
            return 'Ahora'
        elif diff < timedelta(hours=1):
            minutes = int(diff.total_seconds() / 60)
            return f'Hace {minutes} min'
        elif diff < timedelta(days=1):
            hours = int(diff.total_seconds() / 3600)
            return f'Hace {hours} hr'
        elif diff < timedelta(days=7):
            days = diff.days
            return f'Hace {days} día{"s" if days > 1 else ""}'
        else:
            return obj.created_at.strftime('%d/%m/%Y')


class SendNotificationSerializer(serializers.Serializer):
    """Serializer para enviar una notificación."""

    user_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        help_text='IDs de usuarios destinatarios'
    )

    notification_type = serializers.ChoiceField(
        choices=NotificationType.choices,
        default=NotificationType.GENERAL
    )

    title = serializers.CharField(max_length=200)
    body = serializers.CharField()
    data_json = serializers.JSONField(required=False, default=dict)
    image_url = serializers.URLField(required=False, allow_blank=True)
    click_action = serializers.CharField(max_length=200, required=False, allow_blank=True)

    template_id = serializers.IntegerField(
        required=False,
        help_text='ID de plantilla para usar (reemplaza title/body/data_json)'
    )

    template_context = serializers.JSONField(
        required=False,
        default=dict,
        help_text='Contexto para renderizar la plantilla'
    )


class SendBatchNotificationSerializer(serializers.Serializer):
    """Serializer para envío batch de notificaciones."""

    user_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        help_text='IDs de usuarios destinatarios'
    )

    notification_type = serializers.ChoiceField(
        choices=NotificationType.choices,
        default=NotificationType.GENERAL
    )

    title = serializers.CharField(max_length=200)
    body = serializers.CharField()
    data_json = serializers.JSONField(required=False, default=dict)

    template_id = serializers.IntegerField(required=False)
    template_context = serializers.JSONField(required=False, default=dict)


class MoraAlertSerializer(serializers.Serializer):
    """Serializer para alertas de mora."""

    minimum_overdue_days = serializers.IntegerField(
        default=1,
        min_value=1,
        help_text='Días mínimos de mora para incluir'
    )

    include_amount = serializers.BooleanField(
        default=True,
        help_text='Incluir monto total en mora'
    )


class UnreadCountSerializer(serializers.Serializer):
    """Serializer para contar notificaciones no leídas."""

    count = serializers.IntegerField()
