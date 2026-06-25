"""
Serializers para el sistema de auditoría.
"""
from rest_framework import serializers
from api.audit.models import AuditLog, SecurityEvent


class AuditLogSerializer(serializers.ModelSerializer):
    """Serializer para logs de auditoría."""
    
    user_email = serializers.EmailField(source='user.email', read_only=True)
    user_name = serializers.SerializerMethodField()
    institution_name = serializers.CharField(source='institution.name', read_only=True)
    action_display = serializers.CharField(source='get_action_display', read_only=True)
    severity_display = serializers.CharField(source='get_severity_display', read_only=True)
    
    class Meta:
        model = AuditLog
        fields = [
            'id',
            'user',
            'user_email',
            'user_name',
            'action',
            'action_display',
            'resource_type',
            'resource_id',
            'description',
            'timestamp',
            'ip_address',
            'user_agent',
            'institution',
            'institution_name',
            'severity',
            'severity_display',
            'metadata',
        ]
        read_only_fields = fields
    
    def get_user_name(self, obj):
        """Obtiene el nombre completo del usuario."""
        if obj.user:
            return f"{obj.user.first_name} {obj.user.last_name}".strip() or obj.user.email
        return "Sistema"


class AuditLogListSerializer(serializers.ModelSerializer):
    """Serializer simplificado para listado de logs."""
    
    user_email = serializers.EmailField(source='user.email', read_only=True)
    institution_name = serializers.CharField(source='institution.name', read_only=True)
    action_display = serializers.CharField(source='get_action_display', read_only=True)
    severity_display = serializers.CharField(source='get_severity_display', read_only=True)
    
    class Meta:
        model = AuditLog
        fields = [
            'id',
            'user_email',
            'action',
            'action_display',
            'resource_type',
            'resource_id',
            'description',
            'timestamp',
            'ip_address',
            'institution_name',
            'severity',
            'severity_display',
        ]
        read_only_fields = fields


class SecurityEventSerializer(serializers.ModelSerializer):
    """Serializer para eventos de seguridad."""
    
    user_email = serializers.EmailField(source='user.email', read_only=True)
    user_name = serializers.SerializerMethodField()
    event_type_display = serializers.CharField(source='get_event_type_display', read_only=True)
    resolved_by_email = serializers.EmailField(source='resolved_by.email', read_only=True)
    
    class Meta:
        model = SecurityEvent
        fields = [
            'id',
            'event_type',
            'event_type_display',
            'user',
            'user_email',
            'user_name',
            'email',
            'ip_address',
            'user_agent',
            'timestamp',
            'description',
            'metadata',
            'resolved',
            'resolved_at',
            'resolved_by',
            'resolved_by_email',
        ]
        read_only_fields = [
            'id',
            'event_type',
            'user',
            'email',
            'ip_address',
            'user_agent',
            'timestamp',
            'description',
            'metadata',
        ]
    
    def get_user_name(self, obj):
        """Obtiene el nombre completo del usuario."""
        if obj.user:
            return f"{obj.user.first_name} {obj.user.last_name}".strip() or obj.user.email
        return obj.email or "Desconocido"


class SecurityEventListSerializer(serializers.ModelSerializer):
    """Serializer simplificado para listado de eventos de seguridad."""
    
    user_email = serializers.EmailField(source='user.email', read_only=True)
    event_type_display = serializers.CharField(source='get_event_type_display', read_only=True)
    
    class Meta:
        model = SecurityEvent
        fields = [
            'id',
            'event_type',
            'event_type_display',
            'user_email',
            'email',
            'ip_address',
            'timestamp',
            'description',
            'resolved',
        ]
        read_only_fields = fields


class ResolveSecurityEventSerializer(serializers.Serializer):
    """Serializer para resolver un evento de seguridad."""
    
    notes = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text="Notas sobre la resolución del evento"
    )
