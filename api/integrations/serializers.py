"""
Serializadores para gestión de integraciones externas
"""

from rest_framework import serializers
from .models import ExternalIntegration, IntegrationLog


class ExternalIntegrationSerializer(serializers.ModelSerializer):
    """Serializador para ExternalIntegration"""
    
    integration_type_display = serializers.CharField(
        source='get_integration_type_display',
        read_only=True
    )
    status_display = serializers.CharField(
        source='get_status_display',
        read_only=True
    )
    
    class Meta:
        model = ExternalIntegration
        fields = [
            'id',
            'institution',
            'integration_type',
            'integration_type_display',
            'name',
            'description',
            'status',
            'status_display',
            'configuration',
            'webhook_url',
            'webhook_secret',
            'last_sync_at',
            'last_success_at',
            'last_error_at',
            'last_error_message',
            'error_count',
            'success_count',
            'is_default',
            'notes',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'institution',
            'last_sync_at',
            'last_success_at',
            'last_error_at',
            'last_error_message',
            'error_count',
            'success_count',
            'created_at',
            'updated_at',
        ]
    
    def validate_configuration(self, value):
        """Valida que la configuración sea un diccionario"""
        if not isinstance(value, dict):
            raise serializers.ValidationError(
                'La configuración debe ser un objeto JSON válido'
            )
        return value
    
    def validate(self, attrs):
        """Validaciones adicionales"""
        # Si es default, verificar que no haya otra default del mismo tipo
        if attrs.get('is_default', False):
            integration_type = attrs.get('integration_type')
            if integration_type:
                # Verificar si ya existe una default del mismo tipo
                existing = ExternalIntegration.objects.filter(
                    institution=self.context['request'].user.institution,
                    integration_type=integration_type,
                    is_default=True
                ).exclude(id=self.instance.id if self.instance else None)
                
                if existing.exists():
                    raise serializers.ValidationError({
                        'is_default': 'Ya existe una integración por defecto de este tipo'
                    })
        
        return attrs


class ExternalIntegrationListSerializer(serializers.ModelSerializer):
    """Serializador simplificado para listas"""
    
    integration_type_display = serializers.CharField(
        source='get_integration_type_display',
        read_only=True
    )
    status_display = serializers.CharField(
        source='get_status_display',
        read_only=True
    )
    
    class Meta:
        model = ExternalIntegration
        fields = [
            'id',
            'integration_type',
            'integration_type_display',
            'name',
            'status',
            'status_display',
            'is_default',
            'last_success_at',
            'last_error_at',
            'error_count',
            'success_count',
        ]


class IntegrationLogSerializer(serializers.ModelSerializer):
    """Serializador para IntegrationLog"""
    
    action_display = serializers.CharField(
        source='get_action_display',
        read_only=True
    )
    status_display = serializers.CharField(
        source='get_status_display',
        read_only=True
    )
    integration_name = serializers.CharField(
        source='integration.name',
        read_only=True
    )
    integration_type = serializers.CharField(
        source='integration.integration_type',
        read_only=True
    )
    user_email = serializers.CharField(
        source='user.email',
        read_only=True
    )
    
    class Meta:
        model = IntegrationLog
        fields = [
            'id',
            'integration',
            'integration_name',
            'integration_type',
            'action',
            'action_display',
            'status',
            'status_display',
            'request_data',
            'response_data',
            'error_message',
            'error_code',
            'duration_ms',
            'user',
            'user_email',
            'ip_address',
            'metadata',
            'created_at',
        ]
        read_only_fields = [
            'integration',
            'created_at',
        ]


class IntegrationLogListSerializer(serializers.ModelSerializer):
    """Serializador simplificado para listas de logs"""
    
    action_display = serializers.CharField(
        source='get_action_display',
        read_only=True
    )
    status_display = serializers.CharField(
        source='get_status_display',
        read_only=True
    )
    integration_name = serializers.CharField(
        source='integration.name',
        read_only=True
    )
    
    class Meta:
        model = IntegrationLog
        fields = [
            'id',
            'integration_name',
            'action',
            'action_display',
            'status',
            'status_display',
            'error_message',
            'duration_ms',
            'created_at',
        ]
