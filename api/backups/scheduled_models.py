"""
Modelos para configuración de backups automáticos programados.
"""
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from api.core.models import TimeStampedModel


class BackupScheduleConfig(TimeStampedModel):
    """
    Configuración de backups automáticos para un tenant.
    
    Permite a cada tenant configurar:
    - Frecuencia de backups (diario, semanal, mensual)
    - Hora específica de ejecución
    - Tipo de backup
    - Retención personalizada
    """
    
    class Frequency(models.TextChoices):
        DAILY = 'daily', 'Diario'
        WEEKLY = 'weekly', 'Semanal'
        MONTHLY = 'monthly', 'Mensual'
        CUSTOM = 'custom', 'Personalizado'
    
    class DayOfWeek(models.IntegerChoices):
        MONDAY = 1, 'Lunes'
        TUESDAY = 2, 'Martes'
        WEDNESDAY = 3, 'Miércoles'
        THURSDAY = 4, 'Jueves'
        FRIDAY = 5, 'Viernes'
        SATURDAY = 6, 'Sábado'
        SUNDAY = 7, 'Domingo'
    
    # Relación
    tenant = models.OneToOneField(
        'tenants.FinancialInstitution',
        on_delete=models.CASCADE,
        related_name='backup_schedule',
        verbose_name='Institución Financiera'
    )
    
    # Estado
    is_enabled = models.BooleanField(
        default=False,
        verbose_name='Habilitado',
        help_text='Si está habilitado, se ejecutarán backups automáticos'
    )
    
    # Frecuencia
    frequency = models.CharField(
        max_length=20,
        choices=Frequency.choices,
        default=Frequency.DAILY,
        verbose_name='Frecuencia'
    )
    
    # Hora de ejecución (formato 24h)
    hour = models.IntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(23)],
        default=2,
        verbose_name='Hora',
        help_text='Hora del día (0-23) para ejecutar el backup'
    )
    
    minute = models.IntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(59)],
        default=0,
        verbose_name='Minuto',
        help_text='Minuto de la hora (0-59) para ejecutar el backup'
    )
    
    # Configuración semanal
    day_of_week = models.IntegerField(
        choices=DayOfWeek.choices,
        null=True,
        blank=True,
        verbose_name='Día de la Semana',
        help_text='Para backups semanales: día de la semana (1=Lunes, 7=Domingo)'
    )
    
    # Configuración mensual
    day_of_month = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(31)],
        null=True,
        blank=True,
        verbose_name='Día del Mes',
        help_text='Para backups mensuales: día del mes (1-31)'
    )
    
    # Configuración personalizada (cron expression)
    cron_expression = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name='Expresión Cron',
        help_text='Para frecuencia personalizada: expresión cron (ej: "0 2 * * *")'
    )
    
    # Tipo de backup
    backup_type = models.CharField(
        max_length=20,
        choices=[
            ('full', 'Completo'),
            ('metadata_only', 'Solo Metadatos'),
        ],
        default='full',
        verbose_name='Tipo de Backup'
    )
    
    # Opciones
    include_audit_logs = models.BooleanField(
        default=False,
        verbose_name='Incluir Logs de Auditoría',
        help_text='Si True, incluye logs de auditoría (puede aumentar el tamaño)'
    )
    
    include_physical_files = models.BooleanField(
        default=False,
        verbose_name='Incluir Archivos Físicos',
        help_text='Si True, incluye archivos físicos en ZIP (puede ser muy grande)'
    )
    
    # Retención
    retention_days = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(365)],
        default=30,
        verbose_name='Días de Retención',
        help_text='Número de días que se mantendrán los backups antes de expirar'
    )
    
    max_backups_to_keep = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(100)],
        default=10,
        verbose_name='Máximo de Backups a Mantener',
        help_text='Número máximo de backups automáticos a mantener (los más antiguos se eliminan)'
    )
    
    # Control de ejecución
    last_run_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Última Ejecución',
        help_text='Fecha y hora de la última ejecución exitosa'
    )
    
    next_run_at = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
        verbose_name='Próxima Ejecución',
        help_text='Fecha y hora calculada para la próxima ejecución'
    )
    
    last_backup = models.ForeignKey(
        'backups.TenantBackup',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='schedule_configs',
        verbose_name='Último Backup'
    )
    
    # Notificaciones
    notify_on_success = models.BooleanField(
        default=False,
        verbose_name='Notificar en Éxito',
        help_text='Enviar notificación cuando el backup se complete exitosamente'
    )
    
    notify_on_failure = models.BooleanField(
        default=True,
        verbose_name='Notificar en Fallo',
        help_text='Enviar notificación cuando el backup falle'
    )
    
    notification_emails = models.JSONField(
        default=list,
        blank=True,
        verbose_name='Emails de Notificación',
        help_text='Lista de emails para recibir notificaciones'
    )
    
    # Estadísticas
    total_runs = models.IntegerField(
        default=0,
        verbose_name='Total de Ejecuciones'
    )
    
    successful_runs = models.IntegerField(
        default=0,
        verbose_name='Ejecuciones Exitosas'
    )
    
    failed_runs = models.IntegerField(
        default=0,
        verbose_name='Ejecuciones Fallidas'
    )
    
    class Meta:
        db_table = 'backup_schedule_configs'
        verbose_name = 'Configuración de Backup Programado'
        verbose_name_plural = 'Configuraciones de Backups Programados'
        indexes = [
            models.Index(fields=['is_enabled', 'next_run_at']),
            models.Index(fields=['tenant']),
        ]
    
    def __str__(self):
        status = "Habilitado" if self.is_enabled else "Deshabilitado"
        return f"Backup Schedule - {self.tenant.name} ({self.frequency}, {status})"
    
    @property
    def schedule_description(self):
        """Descripción legible del schedule."""
        if self.frequency == self.Frequency.DAILY:
            return f"Diario a las {self.hour:02d}:{self.minute:02d}"
        elif self.frequency == self.Frequency.WEEKLY:
            day_name = self.DayOfWeek(self.day_of_week).label if self.day_of_week else "?"
            return f"Semanal los {day_name} a las {self.hour:02d}:{self.minute:02d}"
        elif self.frequency == self.Frequency.MONTHLY:
            return f"Mensual el día {self.day_of_month} a las {self.hour:02d}:{self.minute:02d}"
        elif self.frequency == self.Frequency.CUSTOM:
            return f"Personalizado: {self.cron_expression}"
        return "No configurado"
    
    @property
    def success_rate(self):
        """Tasa de éxito en porcentaje."""
        if self.total_runs == 0:
            return 0
        return round((self.successful_runs / self.total_runs) * 100, 2)
    
    def calculate_next_run(self):
        """
        Calcula la próxima fecha de ejecución basada en la configuración.
        
        La hora configurada (hour, minute) se interpreta en la zona horaria
        del sistema (settings.TIME_ZONE), no en UTC.
        
        Returns:
            datetime: Próxima fecha de ejecución en UTC con timezone aware
        """
        from datetime import datetime, timedelta, timezone as dt_timezone
        from zoneinfo import ZoneInfo
        
        now = timezone.now()
        tz_name = timezone.get_current_timezone_name()
        tz = ZoneInfo(tz_name)
        now_local = now.astimezone(tz)
        
        if self.frequency == self.Frequency.DAILY:
            # Próxima ejecución: hoy o mañana a la hora configurada (hora local)
            next_run_local = now_local.replace(
                hour=self.hour, 
                minute=self.minute, 
                second=0, 
                microsecond=0
            )
            if next_run_local <= now_local:
                next_run_local += timedelta(days=1)
            
            return next_run_local.astimezone(dt_timezone.utc)
        
        elif self.frequency == self.Frequency.WEEKLY:
            # Próxima ejecución: próximo día de la semana configurado (hora local)
            if not self.day_of_week:
                return None
            
            now_local = timezone.localtime(now)
            current_weekday = now_local.isoweekday()  # 1=Monday, 7=Sunday
            days_ahead = self.day_of_week - current_weekday
            
            if days_ahead < 0:  # El día ya pasó esta semana
                days_ahead += 7
            elif days_ahead == 0:  # Es hoy
                next_run_local = now_local.replace(
                    hour=self.hour, 
                    minute=self.minute, 
                    second=0, 
                    microsecond=0
                )
                if next_run_local <= now_local:
                    days_ahead = 7
            
            next_run_local = now_local + timedelta(days=days_ahead)
            next_run_local = next_run_local.replace(
                hour=self.hour, 
                minute=self.minute, 
                second=0, 
                microsecond=0
            )
            
            return timezone.make_aware(
                next_run_local.replace(tzinfo=None),
                timezone.get_current_timezone()
            )
        
        elif self.frequency == self.Frequency.MONTHLY:
            # Próxima ejecución: próximo día del mes configurado (hora local)
            if not self.day_of_month:
                return None
            
            now_local = timezone.localtime(now)
            next_run_local = now_local.replace(
                day=self.day_of_month, 
                hour=self.hour, 
                minute=self.minute, 
                second=0, 
                microsecond=0
            )
            
            if next_run_local <= now_local:
                # Avanzar al próximo mes
                if now_local.month == 12:
                    next_run_local = next_run_local.replace(year=now_local.year + 1, month=1)
                else:
                    next_run_local = next_run_local.replace(month=now_local.month + 1)
            
            return timezone.make_aware(
                next_run_local.replace(tzinfo=None),
                timezone.get_current_timezone()
            )
        
        elif self.frequency == self.Frequency.CUSTOM:
            return None
        
        return None
    
    def update_next_run(self):
        """Actualiza el campo next_run_at."""
        self.next_run_at = self.calculate_next_run()
        self.save(update_fields=['next_run_at'])
    
    def should_run_now(self):
        """
        Verifica si el backup debe ejecutarse ahora.
        
        Returns:
            bool: True si debe ejecutarse
        """
        if not self.is_enabled:
            return False
        
        if not self.next_run_at:
            return False
        
        return timezone.now() >= self.next_run_at
    
    def mark_run_success(self, backup):
        """Marca una ejecución como exitosa."""
        self.last_run_at = timezone.now()
        self.last_backup = backup
        self.total_runs += 1
        self.successful_runs += 1
        self.update_next_run()
    
    def mark_run_failure(self):
        """Marca una ejecución como fallida."""
        self.last_run_at = timezone.now()
        self.total_runs += 1
        self.failed_runs += 1
        self.update_next_run()


class ScheduledBackupLog(TimeStampedModel):
    """
    Log de ejecuciones de backups programados.
    
    Registra cada intento de ejecución automática:
    éxito, fallo, duración, errores.
    """
    
    class Status(models.TextChoices):
        SUCCESS = 'success', 'Exitoso'
        FAILED = 'failed', 'Fallido'
        SKIPPED = 'skipped', 'Omitido'
    
    # Relaciones
    schedule_config = models.ForeignKey(
        BackupScheduleConfig,
        on_delete=models.CASCADE,
        related_name='execution_logs',
        verbose_name='Configuración'
    )
    
    backup = models.ForeignKey(
        'backups.TenantBackup',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='scheduled_logs',
        verbose_name='Backup'
    )
    
    # Ejecución
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        verbose_name='Estado'
    )
    
    started_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Inicio'
    )
    
    completed_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Fin'
    )
    
    duration_seconds = models.FloatField(
        null=True,
        blank=True,
        verbose_name='Duración (segundos)'
    )
    
    # Error
    error_message = models.TextField(
        blank=True,
        null=True,
        verbose_name='Mensaje de Error'
    )
    
    error_traceback = models.TextField(
        blank=True,
        null=True,
        verbose_name='Traceback del Error'
    )
    
    # Metadata
    metadata = models.JSONField(
        default=dict,
        blank=True,
        verbose_name='Metadata',
        help_text='Información adicional sobre la ejecución'
    )
    
    class Meta:
        db_table = 'scheduled_backup_logs'
        ordering = ['-started_at']
        verbose_name = 'Log de Backup Programado'
        verbose_name_plural = 'Logs de Backups Programados'
        indexes = [
            models.Index(fields=['schedule_config', '-started_at']),
            models.Index(fields=['status']),
        ]
    
    def __str__(self):
        return f"Scheduled Backup Log - {self.schedule_config.tenant.name} ({self.status})"
