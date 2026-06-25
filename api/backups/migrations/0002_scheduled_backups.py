# Generated migration for scheduled backups

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.core.validators


class Migration(migrations.Migration):

    dependencies = [
        ('backups', '0001_initial'),
        ('tenants', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='BackupScheduleConfig',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Fecha de Creación')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Fecha de Actualización')),
                ('is_enabled', models.BooleanField(default=False, help_text='Si está habilitado, se ejecutarán backups automáticos', verbose_name='Habilitado')),
                ('frequency', models.CharField(choices=[('daily', 'Diario'), ('weekly', 'Semanal'), ('monthly', 'Mensual'), ('custom', 'Personalizado')], default='daily', max_length=20, verbose_name='Frecuencia')),
                ('hour', models.IntegerField(default=2, help_text='Hora del día (0-23) para ejecutar el backup', validators=[django.core.validators.MinValueValidator(0), django.core.validators.MaxValueValidator(23)], verbose_name='Hora')),
                ('minute', models.IntegerField(default=0, help_text='Minuto de la hora (0-59) para ejecutar el backup', validators=[django.core.validators.MinValueValidator(0), django.core.validators.MaxValueValidator(59)], verbose_name='Minuto')),
                ('day_of_week', models.IntegerField(blank=True, choices=[(1, 'Lunes'), (2, 'Martes'), (3, 'Miércoles'), (4, 'Jueves'), (5, 'Viernes'), (6, 'Sábado'), (7, 'Domingo')], help_text='Para backups semanales: día de la semana (1=Lunes, 7=Domingo)', null=True, verbose_name='Día de la Semana')),
                ('day_of_month', models.IntegerField(blank=True, help_text='Para backups mensuales: día del mes (1-31)', null=True, validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(31)], verbose_name='Día del Mes')),
                ('cron_expression', models.CharField(blank=True, help_text='Para frecuencia personalizada: expresión cron (ej: "0 2 * * *")', max_length=100, null=True, verbose_name='Expresión Cron')),
                ('backup_type', models.CharField(choices=[('full', 'Completo'), ('metadata_only', 'Solo Metadatos')], default='full', max_length=20, verbose_name='Tipo de Backup')),
                ('include_audit_logs', models.BooleanField(default=False, help_text='Si True, incluye logs de auditoría (puede aumentar el tamaño)', verbose_name='Incluir Logs de Auditoría')),
                ('include_physical_files', models.BooleanField(default=False, help_text='Si True, incluye archivos físicos en ZIP (puede ser muy grande)', verbose_name='Incluir Archivos Físicos')),
                ('retention_days', models.IntegerField(default=30, help_text='Número de días que se mantendrán los backups antes de expirar', validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(365)], verbose_name='Días de Retención')),
                ('max_backups_to_keep', models.IntegerField(default=10, help_text='Número máximo de backups automáticos a mantener (los más antiguos se eliminan)', validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(100)], verbose_name='Máximo de Backups a Mantener')),
                ('last_run_at', models.DateTimeField(blank=True, help_text='Fecha y hora de la última ejecución exitosa', null=True, verbose_name='Última Ejecución')),
                ('next_run_at', models.DateTimeField(blank=True, db_index=True, help_text='Fecha y hora calculada para la próxima ejecución', null=True, verbose_name='Próxima Ejecución')),
                ('notify_on_success', models.BooleanField(default=False, help_text='Enviar notificación cuando el backup se complete exitosamente', verbose_name='Notificar en Éxito')),
                ('notify_on_failure', models.BooleanField(default=True, help_text='Enviar notificación cuando el backup falle', verbose_name='Notificar en Fallo')),
                ('notification_emails', models.JSONField(blank=True, default=list, help_text='Lista de emails para recibir notificaciones', verbose_name='Emails de Notificación')),
                ('total_runs', models.IntegerField(default=0, verbose_name='Total de Ejecuciones')),
                ('successful_runs', models.IntegerField(default=0, verbose_name='Ejecuciones Exitosas')),
                ('failed_runs', models.IntegerField(default=0, verbose_name='Ejecuciones Fallidas')),
                ('last_backup', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='schedule_configs', to='backups.tenantbackup', verbose_name='Último Backup')),
                ('tenant', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='backup_schedule', to='tenants.financialinstitution', verbose_name='Institución Financiera')),
            ],
            options={
                'verbose_name': 'Configuración de Backup Programado',
                'verbose_name_plural': 'Configuraciones de Backups Programados',
                'db_table': 'backup_schedule_configs',
                'indexes': [
                    models.Index(fields=['is_enabled', 'next_run_at'], name='backup_sche_is_enab_idx'),
                    models.Index(fields=['tenant'], name='backup_sche_tenant_idx'),
                ],
            },
        ),
        migrations.CreateModel(
            name='ScheduledBackupLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Fecha de Creación')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Fecha de Actualización')),
                ('status', models.CharField(choices=[('success', 'Exitoso'), ('failed', 'Fallido'), ('skipped', 'Omitido')], max_length=20, verbose_name='Estado')),
                ('started_at', models.DateTimeField(auto_now_add=True, verbose_name='Inicio')),
                ('completed_at', models.DateTimeField(blank=True, null=True, verbose_name='Fin')),
                ('duration_seconds', models.FloatField(blank=True, null=True, verbose_name='Duración (segundos)')),
                ('error_message', models.TextField(blank=True, null=True, verbose_name='Mensaje de Error')),
                ('error_traceback', models.TextField(blank=True, null=True, verbose_name='Traceback del Error')),
                ('metadata', models.JSONField(blank=True, default=dict, help_text='Información adicional sobre la ejecución', verbose_name='Metadata')),
                ('backup', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='scheduled_logs', to='backups.tenantbackup', verbose_name='Backup')),
                ('schedule_config', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='execution_logs', to='backups.backupscheduleconfig', verbose_name='Configuración')),
            ],
            options={
                'verbose_name': 'Log de Backup Programado',
                'verbose_name_plural': 'Logs de Backups Programados',
                'db_table': 'scheduled_backup_logs',
                'ordering': ['-started_at'],
                'indexes': [
                    models.Index(fields=['schedule_config', '-started_at'], name='scheduled_b_schedul_idx'),
                    models.Index(fields=['status'], name='scheduled_b_status_idx'),
                ],
            },
        ),
    ]
