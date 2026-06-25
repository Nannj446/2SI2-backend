"""
Serializers para gestión de archivos en Supabase Storage.
"""
from rest_framework import serializers

from api.storage.models import FileResource, FileAccessLog


class FileResourceSerializer(serializers.ModelSerializer):
    """Serializer para FileResource."""
    
    tenant_name = serializers.CharField(source='tenant.name', read_only=True)
    uploaded_by_name = serializers.SerializerMethodField(read_only=True)
    signed_url = serializers.SerializerMethodField(read_only=True)
    
    class Meta:
        model = FileResource
        fields = [
            'id',
            'tenant',
            'tenant_name',
            'resource_type',
            'entity_type',
            'entity_id',
            'original_name',
            'stored_name',
            'file_path',
            'bucket',
            'mime_type',
            'extension',
            'size',
            'category',
            'visibility',
            'uploaded_by',
            'uploaded_by_name',
            'status',
            'replaced_by',
            'checksum',
            'metadata',
            'signed_url',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'id',
            'tenant',
            'stored_name',
            'file_path',
            'bucket',
            'checksum',
            'created_at',
            'updated_at',
        ]
    
    def get_uploaded_by_name(self, obj):
        """Obtener nombre del usuario que subió el archivo."""
        if obj.uploaded_by:
            return f"{obj.uploaded_by.first_name} {obj.uploaded_by.last_name}".strip() or obj.uploaded_by.email
        return None
    
    def get_signed_url(self, obj):
        """Obtener URL firmada para acceso temporal."""
        if obj.status == FileResource.Status.ACTIVE:
            try:
                return obj.get_signed_url(expires_in=3600)
            except Exception:
                return None
        return None


class FileAccessLogSerializer(serializers.ModelSerializer):
    """Serializer para FileAccessLog."""
    
    file_name = serializers.CharField(source='file_resource.original_name', read_only=True)
    user_name = serializers.SerializerMethodField(read_only=True)
    
    class Meta:
        model = FileAccessLog
        fields = [
            'id',
            'file_resource',
            'file_name',
            'user',
            'user_name',
            'action',
            'ip_address',
            'user_agent',
            'metadata',
            'created_at',
        ]
        read_only_fields = ['id', 'created_at']
    
    def get_user_name(self, obj):
        """Obtener nombre del usuario."""
        if obj.user:
            return f"{obj.user.first_name} {obj.user.last_name}".strip() or obj.user.email
        return None


# ============================================================================
# Serializers para Endpoints Genéricos
# ============================================================================

class FileListSerializer(serializers.ModelSerializer):
    """Serializer simplificado para listado de archivos."""
    
    uploaded_by_name = serializers.SerializerMethodField()
    file_size_formatted = serializers.SerializerMethodField()
    
    class Meta:
        model = FileResource
        fields = [
            'id',
            'resource_type',
            'category',
            'original_name',
            'size',
            'file_size_formatted',
            'mime_type',
            'status',
            'uploaded_by_name',
            'entity_type',
            'entity_id',
            'metadata',
            'created_at',
        ]
    
    def get_uploaded_by_name(self, obj):
        """Obtener nombre del usuario."""
        if obj.uploaded_by:
            return f"{obj.uploaded_by.first_name} {obj.uploaded_by.last_name}".strip() or obj.uploaded_by.email
        return None
    
    def get_file_size_formatted(self, obj):
        """Formatear tamaño."""
        if obj.size < 1024:
            return f"{obj.size} B"
        elif obj.size < 1024 * 1024:
            return f"{obj.size / 1024:.1f} KB"
        elif obj.size < 1024 * 1024 * 1024:
            return f"{obj.size / (1024 * 1024):.1f} MB"
        else:
            return f"{obj.size / (1024 * 1024 * 1024):.1f} GB"


class FileUploadSerializer(serializers.Serializer):
    """Serializer para upload de archivos genéricos."""
    
    file = serializers.FileField(required=True, help_text='Archivo a subir')
    
    resource_type = serializers.CharField(
        required=True,
        help_text='Tipo de recurso: branding, customer_document, loan_document, general',
    )
    
    category = serializers.CharField(
        required=False,
        default='general',
        help_text='Categoría del archivo (depende del resource_type)',
    )
    
    related_object_type = serializers.CharField(
        required=False,
        allow_null=True,
        allow_blank=True,
        help_text='Tipo de objeto relacionado (ej: customer, loan, borrower)',
    )
    
    related_object_id = serializers.IntegerField(
        required=False,
        allow_null=True,
        help_text='ID del objeto relacionado',
    )
    
    description = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=500,
        help_text='Descripción opcional del archivo',
    )
    
    def validate_file(self, value):
        """Validar que el archivo no esté vacío."""
        if not value:
            raise serializers.ValidationError('El archivo es requerido')
        
        if value.size == 0:
            raise serializers.ValidationError('El archivo está vacío')
        
        return value
    
    def validate(self, data):
        """Validaciones cruzadas."""
        # Si se proporciona related_object_id, debe haber related_object_type
        if data.get('related_object_id') and not data.get('related_object_type'):
            raise serializers.ValidationError({
                'related_object_type': 'Requerido cuando se proporciona related_object_id'
            })
        
        return data
