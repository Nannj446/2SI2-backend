"""
Configuración del admin de Django para el módulo de reportes.
"""
from django.contrib import admin
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from .models import ReportTemplate, GeneratedReport, VoiceReportRequest


@admin.register(ReportTemplate)
class ReportTemplateAdmin(admin.ModelAdmin):
    """Admin para plantillas de reportes."""
    
    list_display = [
        'id', 'name', 'scope', 'category', 'report_type',
        'institution', 'created_by', 'is_active', 'created_at'
    ]
    list_filter = ['scope', 'category', 'is_active', 'created_at']
    search_fields = ['name', 'description', 'report_type']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        (_('Información Básica'), {
            'fields': ('name', 'description', 'is_active')
        }),
        (_('Configuración del Reporte'), {
            'fields': ('scope', 'category', 'report_type', 'institution')
        }),
        (_('Configuración JSON'), {
            'fields': ('config_json',),
            'classes': ('collapse',)
        }),
        (_('Auditoría'), {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        """Optimizar queryset con select_related."""
        qs = super().get_queryset(request)
        return qs.select_related('institution', 'created_by')


@admin.register(GeneratedReport)
class GeneratedReportAdmin(admin.ModelAdmin):
    """Admin para reportes generados."""
    
    list_display = [
        'id', 'report_type', 'scope', 'status_badge', 'generation_source',
        'requested_by', 'row_count', 'file_format', 'created_at'
    ]
    list_filter = [
        'status', 'scope', 'category', 'generation_source',
        'file_format', 'created_at'
    ]
    search_fields = ['report_type', 'requested_by__email']
    readonly_fields = [
        'created_at', 'updated_at', 'completed_at',
        'processing_time_seconds', 'row_count'
    ]
    
    fieldsets = (
        (_('Información del Reporte'), {
            'fields': ('scope', 'category', 'report_type', 'institution')
        }),
        (_('Estado'), {
            'fields': ('status', 'generation_source', 'error_message')
        }),
        (_('Archivo'), {
            'fields': ('file_format', 'file_resource', 'row_count')
        }),
        (_('Configuración JSON'), {
            'fields': ('config_json',),
            'classes': ('collapse',)
        }),
        (_('Auditoría'), {
            'fields': (
                'requested_by', 'voice_request', 'processing_time_seconds',
                'created_at', 'completed_at', 'updated_at'
            ),
            'classes': ('collapse',)
        }),
    )
    
    def status_badge(self, obj):
        """Muestra el estado con color."""
        colors = {
            'PENDING': '#FCD34D',
            'PROCESSING': '#60A5FA',
            'COMPLETED': '#34D399',
            'FAILED': '#F87171',
        }
        color = colors.get(obj.status, '#9CA3AF')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; '
            'border-radius: 3px; font-weight: bold;">{}</span>',
            color,
            obj.get_status_display()
        )
    status_badge.short_description = _('Estado')
    
    def get_queryset(self, request):
        """Optimizar queryset con select_related."""
        qs = super().get_queryset(request)
        return qs.select_related(
            'institution', 'requested_by', 'file_resource', 'voice_request'
        )


@admin.register(VoiceReportRequest)
class VoiceReportRequestAdmin(admin.ModelAdmin):
    """Admin para solicitudes de reportes por voz."""
    
    list_display = [
        'id', 'scope', 'validation_status_badge', 'requested_by',
        'audio_duration_seconds', 'processing_time_seconds', 'created_at'
    ]
    list_filter = ['validation_status', 'scope', 'created_at']
    search_fields = ['transcription', 'requested_by__email']
    readonly_fields = [
        'created_at', 'updated_at', 'audio_duration_seconds',
        'processing_time_seconds', 'groq_transcription_model', 'groq_chat_model'
    ]
    
    fieldsets = (
        (_('Información Básica'), {
            'fields': ('scope', 'institution', 'requested_by')
        }),
        (_('Audio'), {
            'fields': ('audio_file_resource', 'audio_duration_seconds')
        }),
        (_('Transcripción'), {
            'fields': ('transcription', 'transcription_language')
        }),
        (_('Interpretación'), {
            'fields': (
                'parsed_intent_json', 'validation_status',
                'missing_fields_json', 'unsupported_terms_json'
            ),
            'classes': ('collapse',)
        }),
        (_('Modelos IA'), {
            'fields': ('groq_transcription_model', 'groq_chat_model'),
            'classes': ('collapse',)
        }),
        (_('Auditoría'), {
            'fields': (
                'error_message', 'processing_time_seconds',
                'created_at', 'updated_at'
            ),
            'classes': ('collapse',)
        }),
    )
    
    def validation_status_badge(self, obj):
        """Muestra el estado de validación con color."""
        colors = {
            'VALID': '#34D399',
            'NEEDS_REVIEW': '#FCD34D',
            'INVALID': '#F87171',
        }
        color = colors.get(obj.validation_status, '#9CA3AF')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; '
            'border-radius: 3px; font-weight: bold;">{}</span>',
            color,
            obj.get_validation_status_display()
        )
    validation_status_badge.short_description = _('Estado de Validación')
    
    def get_queryset(self, request):
        """Optimizar queryset con select_related."""
        qs = super().get_queryset(request)
        return qs.select_related('institution', 'requested_by', 'audio_file_resource')
