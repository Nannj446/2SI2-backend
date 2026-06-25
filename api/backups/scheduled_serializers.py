"""
Serializers para configuración de backups programados.
"""
from rest_framework import serializers
from django.utils import timezone

from api.backups.scheduled_models import BackupScheduleConfig, ScheduledBackupLog


class BackupScheduleConfigSerializer(serializers.ModelSerializer):
    """Serializer para configuración de backups programados."""
    
    schedule_description = serializers.ReadOnlyField()
    success_rate = serializers.ReadOnlyField()
    tenant_name = serializers.CharField(source='tenant.name', read_only=True)
    last_backup_id = serializers.IntegerField(source='last_backup.id', read_only=True, allow_null=True)
    
    class Meta:
        model = BackupScheduleConfig
        fields = [
            'id',
            'tenant',
            'tenant_name',
            'is_enabled',
            'frequency',
            'hour',
            'minute',
            'day_of_week',
            'day_of_month',
            'cron_expression',
            'backup_type',
            'include_audit_logs',
            'include_physical_files',
            'retention_days',
            'max_backups_to_keep',
            'last_run_at',
            'next_run_at',
            'last_backup_id',
            'notify_on_success',
            'notify_on_failure',
            'notification_emails',
            'total_runs',
            'successful_runs',
            'failed_runs',
            'success_rate',
            'schedule_description',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'last_run_at',
            'next_run_at',
            'last_backup_id',
            'total_runs',
            'successful_runs',
            'failed_runs',
            'created_at',
            'updated_at',
        ]
    
    def validate(self, data):
        """Validaciones personalizadas."""
        frequency = data.get('frequency')
        
        # Validar configuración semanal
        if frequency == BackupScheduleConfig.Frequency.WEEKLY:
            if not data.get('day_of_week'):
                raise serializers.ValidationError({
                    'day_of_week': 'Requerido para backups semanales'
                })
        
        # Validar configuración mensual
        if frequency == BackupScheduleConfig.Frequency.MONTHLY:
            if not data.get('day_of_month'):
                raise serializers.ValidationError({
                    'day_of_month': 'Requerido para backups mensuales'
                })
        
        # Validar configuración personalizada
        if frequency == BackupScheduleConfig.Frequency.CUSTOM:
            if not data.get('cron_expression'):
                raise serializers.ValidationError({
                    'cron_expression': 'Requerido para backups personalizados'
                })
        
        # Validar hora y minuto
        hour = data.get('hour', 0)
        minute = data.get('minute', 0)
        
        if not (0 <= hour <= 23):
            raise serializers.ValidationError({
                'hour': 'Debe estar entre 0 y 23'
            })
        
        if not (0 <= minute <= 59):
            raise serializers.ValidationError({
                'minute': 'Debe estar entre 0 y 59'
            })
        
        return data
    
    def create(self, validated_data):
        """Crea configuración y calcula next_run_at."""
        config = super().create(validated_data)
        
        # Calcular próxima ejecución si está habilitado
        if config.is_enabled:
            config.update_next_run()
        
        return config
    
    def update(self, instance, validated_data):
        """Actualiza configuración y recalcula next_run_at si es necesario."""
        # DEBUG: Log de datos recibidos
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"UPDATE - validated_data: {validated_data}")
        logger.info(f"UPDATE - instance before: hour={instance.hour}, minute={instance.minute}, enabled={instance.is_enabled}")
        
        # Detectar cambios en campos que afectan el schedule
        schedule_fields = ['frequency', 'hour', 'minute', 'day_of_week', 'day_of_month', 'cron_expression']
        schedule_changed = any(
            field in validated_data and validated_data[field] != getattr(instance, field)
            for field in schedule_fields
        )
        
        # Detectar cambio en is_enabled
        enabled_changed = 'is_enabled' in validated_data and validated_data['is_enabled'] != instance.is_enabled
        
        instance = super().update(instance, validated_data)
        
        logger.info(f"UPDATE - instance after: hour={instance.hour}, minute={instance.minute}, enabled={instance.is_enabled}")
        logger.info(f"UPDATE - schedule_changed={schedule_changed}, enabled_changed={enabled_changed}")
        
        # Recalcular next_run_at si cambió el schedule o se habilitó
        if (schedule_changed or enabled_changed) and instance.is_enabled:
            instance.update_next_run()
            logger.info(f"UPDATE - next_run_at recalculado: {instance.next_run_at}")
        elif enabled_changed and not instance.is_enabled:
            # Si se deshabilitó, limpiar next_run_at
            instance.next_run_at = None
            instance.save(update_fields=['next_run_at'])
            logger.info("UPDATE - next_run_at limpiado (deshabilitado)")
        
        return instance


class BackupScheduleConfigCreateSerializer(serializers.ModelSerializer):
    """Serializer simplificado para crear configuración de backups."""
    
    class Meta:
        model = BackupScheduleConfig
        fields = [
            'tenant',
            'is_enabled',
            'frequency',
            'hour',
            'minute',
            'day_of_week',
            'day_of_month',
            'cron_expression',
            'backup_type',
            'include_audit_logs',
            'include_physical_files',
            'retention_days',
            'max_backups_to_keep',
            'notify_on_success',
            'notify_on_failure',
            'notification_emails',
        ]
    
    def validate(self, data):
        """Validaciones personalizadas."""
        frequency = data.get('frequency')
        
        if frequency == BackupScheduleConfig.Frequency.WEEKLY and not data.get('day_of_week'):
            raise serializers.ValidationError({
                'day_of_week': 'Requerido para backups semanales'
            })
        
        if frequency == BackupScheduleConfig.Frequency.MONTHLY and not data.get('day_of_month'):
            raise serializers.ValidationError({
                'day_of_month': 'Requerido para backups mensuales'
            })
        
        if frequency == BackupScheduleConfig.Frequency.CUSTOM and not data.get('cron_expression'):
            raise serializers.ValidationError({
                'cron_expression': 'Requerido para backups personalizados'
            })
        
        return data


class BackupScheduleConfigUpdateSerializer(serializers.ModelSerializer):
    """Serializer para actualizar configuración de backups."""
    
    class Meta:
        model = BackupScheduleConfig
        fields = [
            'is_enabled',
            'frequency',
            'hour',
            'minute',
            'day_of_week',
            'day_of_month',
            'cron_expression',
            'backup_type',
            'include_audit_logs',
            'include_physical_files',
            'retention_days',
            'max_backups_to_keep',
            'notify_on_success',
            'notify_on_failure',
            'notification_emails',
        ]
    
    def validate(self, data):
        freq = data.get('frequency', getattr(self.instance, 'frequency', None))
        
        if freq == BackupScheduleConfig.Frequency.WEEKLY:
            day = data.get('day_of_week', getattr(self.instance, 'day_of_week', None))
            if not day:
                raise serializers.ValidationError({
                    'day_of_week': 'Requerido para backups semanales'
                })
        
        if freq == BackupScheduleConfig.Frequency.MONTHLY:
            dom = data.get('day_of_month', getattr(self.instance, 'day_of_month', None))
            if not dom:
                raise serializers.ValidationError({
                    'day_of_month': 'Requerido para backups mensuales'
                })
        
        if freq == BackupScheduleConfig.Frequency.CUSTOM:
            cron = data.get('cron_expression', getattr(self.instance, 'cron_expression', None))
            if not cron:
                raise serializers.ValidationError({
                    'cron_expression': 'Requerido para backups personalizados'
                })
        
        hour = data.get('hour', getattr(self.instance, 'hour', 0) if self.instance else 0)
        minute = data.get('minute', getattr(self.instance, 'minute', 0) if self.instance else 0)
        
        if not (0 <= hour <= 23):
            raise serializers.ValidationError({'hour': 'Debe estar entre 0 y 23'})
        if not (0 <= minute <= 59):
            raise serializers.ValidationError({'minute': 'Debe estar entre 0 y 59'})
        
        return data
    
    def update(self, instance, validated_data):
        """Actualiza configuración y recalcula next_run_at si es necesario."""
        import logging
        logger = logging.getLogger(__name__)
        
        logger.info(f"UPDATE - Datos recibidos: {validated_data}")
        logger.info(f"UPDATE - Antes: hour={instance.hour}, minute={instance.minute}, enabled={instance.is_enabled}")
        
        # Detectar cambios en campos que afectan el schedule
        schedule_fields = ['frequency', 'hour', 'minute', 'day_of_week', 'day_of_month', 'cron_expression']
        schedule_changed = any(
            field in validated_data and validated_data[field] != getattr(instance, field)
            for field in schedule_fields
        )
        
        # Detectar cambio en is_enabled
        enabled_changed = 'is_enabled' in validated_data and validated_data['is_enabled'] != instance.is_enabled
        
        # Actualizar campos
        for field, value in validated_data.items():
            setattr(instance, field, value)
        instance.save()
        
        logger.info(f"UPDATE - Después: hour={instance.hour}, minute={instance.minute}, enabled={instance.is_enabled}")
        logger.info(f"UPDATE - schedule_changed={schedule_changed}, enabled_changed={enabled_changed}")
        
        # Recalcular next_run_at si cambió el schedule o se habilitó
        if (schedule_changed or enabled_changed) and instance.is_enabled:
            instance.update_next_run()
            logger.info(f"UPDATE - next_run_at recalculado: {instance.next_run_at}")
        elif enabled_changed and not instance.is_enabled:
            # Si se deshabilitó, limpiar next_run_at
            instance.next_run_at = None
            instance.save(update_fields=['next_run_at'])
            logger.info("UPDATE - next_run_at limpiado (deshabilitado)")
        
        return instance


class ScheduledBackupLogSerializer(serializers.ModelSerializer):
    """Serializer para logs de ejecuciones programadas."""
    
    tenant_name = serializers.CharField(source='schedule_config.tenant.name', read_only=True)
    backup_id = serializers.IntegerField(source='backup.id', read_only=True, allow_null=True)
    
    class Meta:
        model = ScheduledBackupLog
        fields = [
            'id',
            'schedule_config',
            'tenant_name',
            'backup_id',
            'status',
            'started_at',
            'completed_at',
            'duration_seconds',
            'error_message',
            'error_traceback',
            'metadata',
            'created_at',
        ]
        read_only_fields = fields


class BackupScheduleStatusSerializer(serializers.Serializer):
    """Serializer para el estado de un schedule."""
    
    config_id = serializers.IntegerField()
    tenant_id = serializers.IntegerField()
    tenant_name = serializers.CharField()
    is_enabled = serializers.BooleanField()
    frequency = serializers.CharField()
    schedule_description = serializers.CharField()
    last_run_at = serializers.DateTimeField(allow_null=True)
    next_run_at = serializers.DateTimeField(allow_null=True)
    total_runs = serializers.IntegerField()
    successful_runs = serializers.IntegerField()
    failed_runs = serializers.IntegerField()
    success_rate = serializers.FloatField()
    last_backup_id = serializers.IntegerField(allow_null=True)
    recent_logs = serializers.ListField(child=serializers.DictField())
