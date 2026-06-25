"""
Configuración del admin para backups.
"""
from django.contrib import admin
from .models import TenantBackup, BackupManifest, BackupAuditLog


@admin.register(TenantBackup)
class TenantBackupAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'tenant', 'backup_type', 'status', 
        'total_size_mb', 'file_count', 'created_at'
    ]
    list_filter = ['status', 'backup_type', 'created_at']
    search_fields = ['tenant__name', 'notes']
    readonly_fields = [
        'created_at', 'updated_at', 'started_at', 
        'completed_at', 'checksum'
    ]
    fieldsets = (
        ('Información Básica', {
            'fields': ('tenant', 'requested_by', 'backup_type', 'status')
        }),
        ('Storage', {
            'fields': ('backup_path', 'manifest_path')
        }),
        ('Métricas', {
            'fields': ('record_count', 'file_count', 'total_size_bytes')
        }),
        ('Tiempos', {
            'fields': ('started_at', 'completed_at', 'expires_at')
        }),
        ('Integridad', {
            'fields': ('checksum', 'error_message')
        }),
        ('Notas', {
            'fields': ('notes',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(BackupManifest)
class BackupManifestAdmin(admin.ModelAdmin):
    list_display = ['id', 'backup', 'schema_version', 'total_records', 'generated_at']
    list_filter = ['schema_version', 'generated_at']
    search_fields = ['backup__tenant__name']
    readonly_fields = ['generated_at', 'created_at', 'updated_at']


@admin.register(BackupAuditLog)
class BackupAuditLogAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'tenant', 'action', 'severity', 
        'actor', 'ip_address', 'created_at'
    ]
    list_filter = ['action', 'severity', 'created_at']
    search_fields = ['tenant__name', 'actor__email', 'description']
    readonly_fields = ['created_at', 'updated_at']
    fieldsets = (
        ('Información Básica', {
            'fields': ('tenant', 'backup', 'actor', 'action', 'severity')
        }),
        ('Descripción', {
            'fields': ('description',)
        }),
        ('Contexto', {
            'fields': ('ip_address', 'user_agent')
        }),
        ('Metadata', {
            'fields': ('metadata',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
