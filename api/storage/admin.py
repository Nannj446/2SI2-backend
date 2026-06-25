"""
Configuración del admin de Django para storage.
"""
from django.contrib import admin

from .models import FileAccessLog, FileResource


@admin.register(FileResource)
class FileResourceAdmin(admin.ModelAdmin):
    """Admin para FileResource."""
    
    list_display = [
        'stored_name',
        'resource_type',
        'category',
        'tenant',
        'size_mb',
        'status',
        'uploaded_by',
        'created_at',
    ]
    list_filter = [
        'resource_type',
        'status',
        'visibility',
        'created_at',
    ]
    search_fields = [
        'original_name',
        'stored_name',
        'file_path',
        'tenant__name',
    ]
    readonly_fields = [
        'id',
        'created_at',
        'updated_at',
        'checksum',
    ]
    
    def size_mb(self, obj):
        """Mostrar tamaño en MB."""
        return f"{obj.size / (1024 * 1024):.2f} MB"
    size_mb.short_description = 'Tamaño'


@admin.register(FileAccessLog)
class FileAccessLogAdmin(admin.ModelAdmin):
    """Admin para FileAccessLog."""
    
    list_display = [
        'file_resource',
        'action',
        'user',
        'ip_address',
        'created_at',
    ]
    list_filter = [
        'action',
        'created_at',
    ]
    search_fields = [
        'file_resource__stored_name',
        'user__email',
        'ip_address',
    ]
    readonly_fields = [
        'created_at',
        'updated_at',
    ]
