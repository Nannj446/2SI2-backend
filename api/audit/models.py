"""
Modelos para el sistema de auditoría y logs de seguridad.
"""
from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()


class AuditLog(models.Model):
    """
    Modelo para registrar todas las acciones importantes del sistema.
    Permite rastrear quién hizo qué, cuándo y desde dónde.
    """
    
    ACTION_TYPES = [
        # Autenticación
        ('login_success', 'Login Exitoso'),
        ('login_failed', 'Login Fallido'),
        ('logout', 'Logout'),
        ('register', 'Registro'),
        ('password_reset_request', 'Solicitud Reset Password'),
        
        # Operaciones CRUD
        ('create', 'Crear'),
        ('update_full', 'Actualización Completa'),
        ('update_partial', 'Actualización Parcial'),
        ('delete', 'Eliminar'),
        ('view', 'Ver Detalle'),
        ('list', 'Listar'),
        
        # Operaciones HTTP específicas
        ('check_exists', 'Verificar Existencia'),
        ('options_request', 'Consulta de Opciones'),
        
        # Operaciones de permisos y roles
        ('permission_change', 'Cambio de Permisos'),
        ('role_assign', 'Asignación de Rol'),
        ('role_remove', 'Remoción de Rol'),
        
        # Operaciones de sistema
        ('tenant_switch', 'Cambio de Tenant'),
        ('security_event', 'Evento de Seguridad'),
        ('system_action', 'Acción del Sistema'),
        
        # Operaciones específicas del negocio
        ('loan_approve', 'Aprobación de Préstamo'),
        ('loan_reject', 'Rechazo de Préstamo'),
        ('client_activate', 'Activación de Cliente'),
        ('client_deactivate', 'Desactivación de Cliente'),
        ('subscription_change', 'Cambio de Suscripción'),
        
        # Operaciones de verificación de identidad (CU-13)
        ('identity_verification_start', 'Verificación de Identidad Iniciada'),
        ('identity_verification_approved', 'Verificación de Identidad Aprobada'),
        ('identity_verification_declined', 'Verificación de Identidad Rechazada'),
        ('identity_verification_error', 'Error en Verificación de Identidad'),
        ('identity_verification_webhook', 'Webhook de Verificación de Identidad Recibido'),
    ]
    
    SEVERITY_LEVELS = [
        ('info', 'Info'),
        ('warning', 'Warning'),
        ('error', 'Error'),
        ('critical', 'Critical'),
    ]
    
    # Quién
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='audit_logs',
        help_text='Usuario que realizó la acción'
    )
    
    # Qué
    action = models.CharField(
        max_length=50,
        choices=ACTION_TYPES,
        help_text='Tipo de acción realizada'
    )
    resource_type = models.CharField(
        max_length=100,
        help_text='Tipo de recurso afectado (ej: User, Role, Institution)'
    )
    resource_id = models.IntegerField(
        null=True,
        blank=True,
        help_text='ID del recurso afectado'
    )
    description = models.TextField(
        help_text='Descripción detallada de la acción'
    )
    
    # Cuándo
    timestamp = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        help_text='Momento en que ocurrió la acción'
    )
    
    # Dónde
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        help_text='Dirección IP desde donde se realizó la acción'
    )
    user_agent = models.TextField(
        null=True,
        blank=True,
        help_text='User agent del navegador/cliente'
    )
    
    # Contexto
    institution = models.ForeignKey(
        'tenants.FinancialInstitution',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='audit_logs',
        help_text='Institución en cuyo contexto se realizó la acción'
    )
    
    # Severidad
    severity = models.CharField(
        max_length=20,
        choices=SEVERITY_LEVELS,
        default='info',
        help_text='Nivel de severidad del evento'
    )
    
    # Datos adicionales
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text='Datos adicionales en formato JSON'
    )
    
    class Meta:
        db_table = 'audit_logs'
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['-timestamp']),
            models.Index(fields=['user', '-timestamp']),
            models.Index(fields=['institution', '-timestamp']),
            models.Index(fields=['action', '-timestamp']),
            models.Index(fields=['severity', '-timestamp']),
        ]
        verbose_name = 'Audit Log'
        verbose_name_plural = 'Audit Logs'
    
    def __str__(self):
        user_str = self.user.email if self.user else 'System'
        return f"{user_str} - {self.action} - {self.resource_type} - {self.timestamp}"


class SecurityEvent(models.Model):
    """
    Modelo para registrar eventos de seguridad específicos.
    """
    
    EVENT_TYPES = [
        ('failed_login', 'Failed Login Attempt'),
        ('account_locked', 'Account Locked'),
        ('suspicious_activity', 'Suspicious Activity'),
        ('unauthorized_access', 'Unauthorized Access Attempt'),
        ('permission_escalation', 'Permission Escalation Attempt'),
        ('data_breach_attempt', 'Data Breach Attempt'),
        ('rate_limit_exceeded', 'Rate Limit Exceeded'),
        ('invalid_token', 'Invalid Token'),
        ('session_hijack', 'Session Hijack Attempt'),
    ]
    
    event_type = models.CharField(
        max_length=50,
        choices=EVENT_TYPES,
        db_index=True,
        help_text='Tipo de evento de seguridad'
    )
    
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='security_events',
        help_text='Usuario relacionado con el evento'
    )
    
    email = models.EmailField(
        null=True,
        blank=True,
        help_text='Email usado en el intento (si aplica)'
    )
    
    ip_address = models.GenericIPAddressField(
        db_index=True,
        help_text='Dirección IP del origen'
    )
    
    user_agent = models.TextField(
        null=True,
        blank=True,
        help_text='User agent del cliente'
    )
    
    timestamp = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        help_text='Momento del evento'
    )
    
    description = models.TextField(
        help_text='Descripción del evento'
    )
    
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text='Datos adicionales del evento'
    )
    
    resolved = models.BooleanField(
        default=False,
        help_text='Si el evento fue revisado y resuelto'
    )
    
    resolved_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text='Momento en que se resolvió'
    )
    
    resolved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='resolved_security_events',
        help_text='Usuario que resolvió el evento'
    )
    
    class Meta:
        db_table = 'security_events'
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['-timestamp']),
            models.Index(fields=['ip_address', '-timestamp']),
            models.Index(fields=['event_type', '-timestamp']),
            models.Index(fields=['resolved', '-timestamp']),
        ]
        verbose_name = 'Security Event'
        verbose_name_plural = 'Security Events'
    
    def __str__(self):
        return f"{self.event_type} - {self.ip_address} - {self.timestamp}"
