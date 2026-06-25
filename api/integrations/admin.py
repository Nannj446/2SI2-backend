"""
Admin configuration for integrations module
"""

from django.contrib import admin
from .models import ExternalIntegration, IntegrationLog


@admin.register(ExternalIntegration)
class ExternalIntegrationAdmin(admin.ModelAdmin):
    """Admin para ExternalIntegration"""
    
    list_display = [
        'name',
        'integration_type',
        'status',
        'is_default',
        'institution',
        'success_count',
        'error_count',
        'last_success_at',
        'last_error_at',
    ]
    
    list_filter = [
        'integration_type',
        'status',
        'is_default',
        'institution',
    ]
    
    search_fields = [
        'name',
        'description',
        'institution__name',
    ]
    
    readonly_fields = [
        'last_sync_at',
        'last_success_at',
        'last_error_at',
        'last_error_message',
        'error_count',
        'success_count',
        'created_at',
        'updated_at',
    ]
    
    fieldsets = (
        ('Información Básica', {
            'fields': (
                'institution',
                'integration_type',
                'name',
                'description',
                'status',
                'is_default',
            )
        }),
        ('Configuración', {
            'fields': (
                'configuration',
                'webhook_url',
                'webhook_secret',
            )
        }),
        ('Métricas', {
            'fields': (
                'last_sync_at',
                'last_success_at',
                'last_error_at',
                'last_error_message',
                'error_count',
                'success_count',
            )
        }),
        ('Notas', {
            'fields': ('notes',)
        }),
        ('Metadatos', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        """Optimizar queries"""
        qs = super().get_queryset(request)
        return qs.select_related('institution')


@admin.register(IntegrationLog)
class IntegrationLogAdmin(admin.ModelAdmin):
    """Admin para IntegrationLog"""
    
    list_display = [
        'integration',
        'action',
        'status',
        'duration_ms',
        'created_at',
        'user',
    ]
    
    list_filter = [
        'integration__integration_type',
        'action',
        'status',
        'created_at',
    ]
    
    search_fields = [
        'integration__name',
        'error_message',
        'error_code',
        'user__email',
    ]
    
    readonly_fields = [
        'integration',
        'action',
        'status',
        'request_data',
        'response_data',
        'error_message',
        'error_code',
        'duration_ms',
        'user',
        'ip_address',
        'metadata',
        'created_at',
    ]
    
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Información del Log', {
            'fields': (
                'integration',
                'action',
                'status',
                'duration_ms',
                'created_at',
            )
        }),
        ('Datos', {
            'fields': (
                'request_data',
                'response_data',
            )
        }),
        ('Error', {
            'fields': (
                'error_message',
                'error_code',
            ),
            'classes': ('collapse',)
        }),
        ('Contexto', {
            'fields': (
                'user',
                'ip_address',
                'metadata',
            )
        }),
    )
    
    def get_queryset(self, request):
        """Optimizar queries"""
        qs = super().get_queryset(request)
        return qs.select_related('integration', 'user')
