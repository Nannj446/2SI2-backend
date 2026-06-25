"""
Serializers para el sistema de backups.
"""
from rest_framework import serializers
from .models import TenantBackup, BackupManifest, BackupAuditLog


class BackupManifestSerializer(serializers.ModelSerializer):
    """Serializer para BackupManifest."""
    
    total_records = serializers.IntegerField(read_only=True)
    total_files = serializers.IntegerField(read_only=True)
    
    class Meta:
        model = BackupManifest
        fields = [
            'id',
            'schema_version',
            'included_tables',
            'record_counts',
            'storage_paths',
            'file_list',
            'checksums',
            'total_records',
            'total_files',
            'generated_at',
            'metadata'
        ]
        read_only_fields = fields


class TenantBackupSerializer(serializers.ModelSerializer):
    """Serializer completo para TenantBackup."""
    
    tenant_name = serializers.CharField(source='tenant.name', read_only=True)
    requested_by_email = serializers.CharField(
        source='requested_by.email', 
        read_only=True,
        allow_null=True
    )
    duration_seconds = serializers.FloatField(read_only=True)
    total_size_mb = serializers.FloatField(read_only=True)
    is_expired = serializers.BooleanField(read_only=True)
    manifest = BackupManifestSerializer(read_only=True)
    
    class Meta:
        model = TenantBackup
        fields = [
            'id',
            'tenant',
            'tenant_name',
            'requested_by',
            'requested_by_email',
            'backup_type',
            'status',
            'backup_path',
            'manifest_path',
            'record_count',
            'file_count',
            'total_size_bytes',
            'total_size_mb',
            'started_at',
            'completed_at',
            'expires_at',
            'duration_seconds',
            'is_expired',
            'error_message',
            'checksum',
            'notes',
            'manifest',
            'created_at',
            'updated_at'
        ]
        read_only_fields = [
            'status',
            'backup_path',
            'manifest_path',
            'record_count',
            'file_count',
            'total_size_bytes',
            'started_at',
            'completed_at',
            'checksum',
            'created_at',
            'updated_at'
        ]


class TenantBackupListSerializer(serializers.ModelSerializer):
    """Serializer simplificado para listado de backups."""
    
    tenant_name = serializers.CharField(source='tenant.name', read_only=True)
    requested_by_email = serializers.CharField(
        source='requested_by.email', 
        read_only=True,
        allow_null=True
    )
    total_size_mb = serializers.FloatField(read_only=True)
    is_expired = serializers.BooleanField(read_only=True)
    
    class Meta:
        model = TenantBackup
        fields = [
            'id',
            'tenant',
            'tenant_name',
            'requested_by_email',
            'backup_type',
            'status',
            'backup_path',  # Agregado para determinar si es ZIP o JSON
            'total_size_mb',
            'file_count',
            'started_at',
            'completed_at',
            'expires_at',
            'is_expired',
            'created_at'
        ]


class CreateBackupSerializer(serializers.Serializer):
    """Serializer para crear un nuevo backup."""
    
    backup_type = serializers.ChoiceField(
        choices=TenantBackup.BackupType.choices,
        default=TenantBackup.BackupType.FULL,
        help_text="Tipo de backup: full, metadata_only, storage_only"
    )
    notes = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=1000,
        help_text="Notas adicionales sobre el backup"
    )
    include_audit_logs = serializers.BooleanField(
        required=False,
        default=False,
        help_text="Incluir logs de auditoría (puede aumentar significativamente el tamaño)"
    )
    include_physical_files = serializers.BooleanField(
        required=False,
        default=False,
        help_text="Incluir archivos físicos en ZIP (aumenta MUCHO el tamaño y tiempo de procesamiento)"
    )


class DownloadBackupResponseSerializer(serializers.Serializer):
    """Serializer para respuesta de descarga de backup."""
    
    download_url = serializers.URLField(
        help_text="URL firmada para descargar el backup"
    )
    expires_in = serializers.IntegerField(
        help_text="Segundos hasta que expire la URL"
    )
    backup_id = serializers.IntegerField(
        help_text="ID del backup"
    )
    size_mb = serializers.FloatField(
        help_text="Tamaño del backup en MB"
    )


class BackupAuditLogSerializer(serializers.ModelSerializer):
    """Serializer para logs de auditoría de backups."""
    
    actor_email = serializers.CharField(
        source='actor.email',
        read_only=True,
        allow_null=True
    )
    
    class Meta:
        model = BackupAuditLog
        fields = [
            'id',
            'tenant',
            'backup',
            'actor',
            'actor_email',
            'action',
            'severity',
            'description',
            'ip_address',
            'user_agent',
            'metadata',
            'created_at'
        ]
        read_only_fields = fields


class RestoreBackupSerializer(serializers.Serializer):
    """Serializer para restaurar un backup."""
    
    conflict_strategy = serializers.ChoiceField(
        choices=['skip', 'overwrite', 'fail'],
        default='skip',
        help_text=(
            "Estrategia para manejar conflictos:\n"
            "- skip: Omitir registros duplicados (recomendado)\n"
            "- overwrite: Sobrescribir registros existentes (peligroso)\n"
            "- fail: Fallar si hay duplicados"
        )
    )
    restore_files = serializers.BooleanField(
        required=False,
        default=True,
        help_text="Restaurar archivos físicos (solo para backups ZIP)"
    )
    dry_run = serializers.BooleanField(
        required=False,
        default=False,
        help_text="Simular restauración sin escribir en base de datos"
    )


class RestorePreviewSerializer(serializers.Serializer):
    """Serializer para preview de restauración."""
    
    backup_id = serializers.IntegerField(read_only=True)
    tenant_id = serializers.IntegerField(read_only=True)
    tenant_name = serializers.CharField(read_only=True)
    backup_date = serializers.DateTimeField(read_only=True)
    total_records = serializers.IntegerField(read_only=True)
    potential_conflicts = serializers.IntegerField(read_only=True)
    file_count = serializers.IntegerField(read_only=True)
    models = serializers.DictField(read_only=True)


class RestoreResultSerializer(serializers.Serializer):
    """Serializer para resultado de restauración."""
    
    success = serializers.BooleanField(read_only=True)
    backup_id = serializers.IntegerField(read_only=True)
    tenant_id = serializers.IntegerField(read_only=True)
    tenant_name = serializers.CharField(read_only=True)
    import_stats = serializers.DictField(read_only=True)
    files_restored = serializers.IntegerField(read_only=True)
    duration_seconds = serializers.FloatField(read_only=True)
    dry_run = serializers.BooleanField(read_only=True)
