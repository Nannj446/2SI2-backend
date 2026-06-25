"""
Modelos para gestión de integraciones externas
"""

from django.db import models
from django.conf import settings
from api.core.models import TenantModel, TimeStampedModel


class ExternalIntegration(TenantModel):
    """
    Modelo para integraciones externas.
    
    Permite configurar y gestionar conexiones con servicios de terceros
    como Stripe, Didit, Brevo, Supabase, Groq, etc.
    """
    
    INTEGRATION_TYPES = [
        ('STRIPE', 'Stripe - Pagos'),
        ('DIDIT', 'Didit - Verificación Identidad'),
        ('BREVO', 'Brevo - Email'),
        ('SUPABASE', 'Supabase - Storage'),
        ('GROQ', 'GroqCloud - IA'),
        ('CREDIT_BUREAU', 'Bureau de Crédito'),
        ('PAYMENT_GATEWAY', 'Gateway de Pagos'),
        ('NOTIFICATION', 'Servicio de Notificaciones'),
        ('BI_ANALYTICS', 'BI/Analytics'),
        ('ACCOUNTING', 'Sistema Contable'),
        ('DIGITAL_SIGNATURE', 'Firma Digital'),
        ('GOVERNMENT_API', 'API Gubernamental'),
    ]
    
    STATUS_CHOICES = [
        ('ACTIVE', 'Activo'),
        ('INACTIVE', 'Inactivo'),
        ('ERROR', 'Error'),
        ('TESTING', 'En Prueba'),
    ]
    
    integration_type = models.CharField(
        max_length=50,
        choices=INTEGRATION_TYPES,
        verbose_name='Tipo de Integración'
    )
    
    name = models.CharField(
        max_length=200,
        verbose_name='Nombre de la Integración'
    )
    
    description = models.TextField(
        blank=True,
        verbose_name='Descripción'
    )
    
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='ACTIVE',
        verbose_name='Estado'
    )
    
    # Configuración de la integración (API keys, endpoints, etc.)
    configuration = models.JSONField(
        default=dict,
        verbose_name='Configuración',
        help_text='API keys, endpoints, y otros parámetros de configuración'
    )
    
    # Webhook configuration
    webhook_url = models.URLField(
        blank=True,
        verbose_name='URL de Webhook',
        help_text='URL para recibir notificaciones del servicio externo'
    )
    
    webhook_secret = models.CharField(
        max_length=255,
        blank=True,
        verbose_name='Secreto de Webhook'
    )
    
    # Métricas de uso
    last_sync_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Última Sincronización'
    )
    
    last_success_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Último Éxito'
    )
    
    last_error_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Último Error'
    )
    
    last_error_message = models.TextField(
        blank=True,
        verbose_name='Último Mensaje de Error'
    )
    
    error_count = models.PositiveIntegerField(
        default=0,
        verbose_name='Contador de Errores'
    )
    
    success_count = models.PositiveIntegerField(
        default=0,
        verbose_name='Contador de Éxitos'
    )
    
    # Metadata
    is_default = models.BooleanField(
        default=False,
        verbose_name='Integración por Defecto',
        help_text='Si es True, se usa como integración principal para este tipo'
    )
    
    notes = models.TextField(
        blank=True,
        verbose_name='Notas'
    )
    
    class Meta:
        verbose_name = 'Integración Externa'
        verbose_name_plural = 'Integraciones Externas'
        ordering = ['-is_default', 'integration_type', 'name']
        indexes = [
            models.Index(fields=['institution', 'integration_type']),
            models.Index(fields=['institution', 'status']),
            models.Index(fields=['integration_type']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['institution', 'integration_type', 'name'],
                name='unique_integration_name_per_type'
            )
        ]
    
    def __str__(self):
        return f"{self.get_integration_type_display()} - {self.name}"
    
    def increment_success(self):
        """Incrementa el contador de éxitos y actualiza timestamp"""
        from django.utils import timezone
        self.success_count += 1
        self.last_success_at = timezone.now()
        self.save(update_fields=['success_count', 'last_success_at'])
    
    def increment_error(self, error_message=None):
        """Incrementa el contador de errores y actualiza timestamp"""
        from django.utils import timezone
        self.error_count += 1
        self.last_error_at = timezone.now()
        if error_message:
            self.last_error_message = error_message
        self.save(update_fields=['error_count', 'last_error_at', 'last_error_message'])
    
    def test_connection(self):
        """
        Prueba la conexión real con el servicio externo según su tipo.
        Retorna (success: bool, message: str).
        """
        import requests as http_requests

        cfg = self.configuration or {}
        itype = self.integration_type

        try:
            # ── STRIPE ────────────────────────────────────────────────
            if itype == 'STRIPE':
                api_key = cfg.get('api_key') or cfg.get('secret_key')
                if not api_key:
                    return False, "Falta la API key de Stripe (campo: api_key)"
                r = http_requests.get(
                    'https://api.stripe.com/v1/balance',
                    auth=(api_key, ''),
                    timeout=10,
                )
                if r.status_code == 200:
                    return True, "Conexión con Stripe exitosa"
                elif r.status_code == 401:
                    return False, "API key de Stripe inválida (401 Unauthorized)"
                else:
                    return False, f"Stripe respondió con código {r.status_code}"

            # ── GROQ ──────────────────────────────────────────────────
            elif itype == 'GROQ':
                api_key = cfg.get('api_key')
                if not api_key:
                    return False, "Falta la API key de Groq (campo: api_key)"
                r = http_requests.get(
                    'https://api.groq.com/openai/v1/models',
                    headers={'Authorization': f'Bearer {api_key}'},
                    timeout=10,
                )
                if r.status_code == 200:
                    return True, "Conexión con Groq exitosa"
                elif r.status_code == 401:
                    return False, "API key de Groq inválida (401 Unauthorized)"
                else:
                    return False, f"Groq respondió con código {r.status_code}"

            # ── BREVO ─────────────────────────────────────────────────
            elif itype == 'BREVO':
                api_key = cfg.get('api_key')
                if not api_key:
                    return False, "Falta la API key de Brevo (campo: api_key)"
                r = http_requests.get(
                    'https://api.brevo.com/v3/account',
                    headers={'api-key': api_key},
                    timeout=10,
                )
                if r.status_code == 200:
                    return True, "Conexión con Brevo exitosa"
                elif r.status_code == 401:
                    return False, "API key de Brevo inválida (401 Unauthorized)"
                else:
                    return False, f"Brevo respondió con código {r.status_code}"

            # ── SUPABASE ──────────────────────────────────────────────
            elif itype == 'SUPABASE':
                url = cfg.get('url') or cfg.get('supabase_url')
                key = cfg.get('key') or cfg.get('service_key') or cfg.get('anon_key')
                if not url or not key:
                    return False, "Faltan credenciales de Supabase (campos: url, key)"
                r = http_requests.get(
                    f"{url.rstrip('/')}/rest/v1/",
                    headers={
                        'apikey': key,
                        'Authorization': f'Bearer {key}',
                    },
                    timeout=10,
                )
                if r.status_code in (200, 204):
                    return True, "Conexión con Supabase exitosa"
                elif r.status_code == 401:
                    return False, "Credenciales de Supabase inválidas (401 Unauthorized)"
                else:
                    return False, f"Supabase respondió con código {r.status_code}"

            # ── DIDIT ─────────────────────────────────────────────────
            elif itype == 'DIDIT':
                client_id = cfg.get('client_id')
                client_secret = cfg.get('client_secret')
                if not client_id or not client_secret:
                    return False, "Faltan credenciales de Didit (campos: client_id, client_secret)"
                r = http_requests.post(
                    'https://apx.didit.me/auth/v2/token/',
                    data={
                        'grant_type': 'client_credentials',
                        'client_id': client_id,
                        'client_secret': client_secret,
                    },
                    timeout=10,
                )
                if r.status_code == 200:
                    return True, "Conexión con Didit exitosa"
                elif r.status_code in (400, 401):
                    return False, "Credenciales de Didit inválidas"
                else:
                    return False, f"Didit respondió con código {r.status_code}"

            # ── Otros tipos: verificar al menos que la config no esté vacía ──
            else:
                if not cfg:
                    return False, f"No hay configuración para la integración '{self.get_integration_type_display()}'. Agrega las credenciales antes de probar."
                # Intentar ping a un endpoint personalizado si existe
                endpoint = cfg.get('endpoint') or cfg.get('base_url') or cfg.get('url')
                if endpoint:
                    r = http_requests.get(endpoint, timeout=10)
                    if r.status_code < 500:
                        return True, f"Endpoint responde con código {r.status_code}"
                    else:
                        return False, f"El endpoint respondió con error {r.status_code}"
                return True, f"Configuración presente para '{self.get_integration_type_display()}' (sin prueba HTTP específica implementada)"

        except http_requests.exceptions.ConnectionError:
            return False, "No se pudo conectar al servicio (error de red)"
        except http_requests.exceptions.Timeout:
            return False, "La conexión al servicio agotó el tiempo de espera (timeout)"
        except Exception as e:
            return False, f"Error inesperado al probar conexión: {str(e)}"



class IntegrationLog(TimeStampedModel):
    """
    Log de actividad de integraciones externas.
    
    Registra todas las llamadas a servicios externos para auditoría
    y monitoreo.
    """
    
    ACTION_CHOICES = [
        ('PAYMENT_PROCESSED', 'Pago Procesado'),
        ('IDENTITY_VERIFIED', 'Identidad Verificada'),
        ('EMAIL_SENT', 'Email Enviado'),
        ('FILE_UPLOADED', 'Archivo Subido'),
        ('AI_REQUEST', 'Solicitud IA'),
        ('CREDIT_CHECK', 'Consulta Crédito'),
        ('WEBHOOK_RECEIVED', 'Webhook Recibido'),
        ('SYNC', 'Sincronización'),
        ('TEST_CONNECTION', 'Prueba de Conexión'),
        ('OTHER', 'Otro'),
    ]
    
    STATUS_CHOICES = [
        ('SUCCESS', 'Éxito'),
        ('FAILED', 'Fallo'),
        ('PENDING', 'Pendiente'),
        ('TIMEOUT', 'Timeout'),
    ]
    
    integration = models.ForeignKey(
        ExternalIntegration,
        on_delete=models.CASCADE,
        related_name='logs',
        verbose_name='Integración'
    )
    
    action = models.CharField(
        max_length=50,
        choices=ACTION_CHOICES,
        verbose_name='Acción'
    )
    
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        verbose_name='Estado'
    )
    
    # Datos de la solicitud
    request_data = models.JSONField(
        default=dict,
        blank=True,
        verbose_name='Datos de Solicitud'
    )
    
    # Datos de la respuesta
    response_data = models.JSONField(
        default=dict,
        blank=True,
        verbose_name='Datos de Respuesta'
    )
    
    # Información de error
    error_message = models.TextField(
        blank=True,
        verbose_name='Mensaje de Error'
    )
    
    error_code = models.CharField(
        max_length=50,
        blank=True,
        verbose_name='Código de Error'
    )
    
    # Métricas
    duration_ms = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name='Duración (ms)'
    )
    
    # Contexto adicional
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='integration_logs',
        verbose_name='Usuario'
    )
    
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        verbose_name='Dirección IP'
    )
    
    metadata = models.JSONField(
        default=dict,
        blank=True,
        verbose_name='Metadatos Adicionales'
    )
    
    class Meta:
        verbose_name = 'Log de Integración'
        verbose_name_plural = 'Logs de Integraciones'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['integration', 'created_at']),
            models.Index(fields=['integration', 'status']),
            models.Index(fields=['action']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"{self.integration} - {self.get_action_display()} - {self.get_status_display()}"
