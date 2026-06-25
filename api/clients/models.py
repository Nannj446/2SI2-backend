"""
Modelos para gestión de clientes/prestatarios.
"""

from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator, RegexValidator
from api.core.models import TenantModel, TimeStampedModel


class Client(TenantModel, TimeStampedModel):
    """
    Modelo de Cliente/Prestatario.
    
    Representa a una persona natural o jurídica que solicita créditos
    en una institución financiera.
    """
    
    # Tipos de documento
    DOCUMENT_TYPE_CHOICES = [
        ('CI', 'Cédula de Identidad'),
        ('NIT', 'Número de Identificación Tributaria'),
        ('PASSPORT', 'Pasaporte'),
        ('RUC', 'Registro Único de Contribuyentes'),
    ]
    
    # Estado laboral
    EMPLOYMENT_STATUS_CHOICES = [
        ('EMPLOYED', 'Empleado en relación de dependencia'),
        ('SELF_EMPLOYED', 'Trabajador independiente'),
        ('BUSINESS_OWNER', 'Propietario de negocio'),
        ('RETIRED', 'Jubilado'),
        ('UNEMPLOYED', 'Desempleado'),
        ('OTHER', 'Otro'),
    ]
    
    # Tipo de cliente
    CLIENT_TYPE_CHOICES = [
        ('NATURAL', 'Persona Natural'),
        ('JURIDICA', 'Persona Jurídica'),
    ]
    
    # ============================================================
    # RELACIÓN CON USUARIO
    # ============================================================
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='client_profile',
        verbose_name='Usuario',
        help_text='Usuario asociado a este cliente'
    )
    
    # ============================================================
    # DATOS BÁSICOS
    # ============================================================
    client_type = models.CharField(
        max_length=10,
        choices=CLIENT_TYPE_CHOICES,
        default='NATURAL',
        verbose_name='Tipo de Cliente'
    )
    
    document_type = models.CharField(
        max_length=10,
        choices=DOCUMENT_TYPE_CHOICES,
        default='CI',
        verbose_name='Tipo de Documento'
    )
    
    document_number = models.CharField(
        max_length=20,
        verbose_name='Número de Documento',
        validators=[
            RegexValidator(
                regex=r'^[A-Z0-9\-]+$',
                message='El número de documento solo puede contener letras mayúsculas, números y guiones'
            )
        ]
    )
    
    document_extension = models.CharField(
        max_length=5,
        blank=True,
        null=True,
        verbose_name='Extensión CI',
        help_text='Ej: LP, SC, CB, OR, PT, TJ, CH, BE, PD'
    )
    
    birth_date = models.DateField(
        verbose_name='Fecha de Nacimiento'
    )
    
    gender = models.CharField(
        max_length=1,
        choices=[('M', 'Masculino'), ('F', 'Femenino'), ('O', 'Otro')],
        blank=True,
        null=True,
        verbose_name='Género'
    )
    
    # ============================================================
    # DATOS DE CONTACTO
    # ============================================================
    # NOTA: email, first_name, last_name y phone están en auth_user y user_profiles
    # Se acceden mediante properties para mantener compatibilidad
    
    mobile_phone = models.CharField(
        max_length=20,
        verbose_name='Teléfono Móvil',
        blank=True,
        null=True,
        validators=[
            RegexValidator(
                regex=r'^\+?[0-9\s\-\(\)]+$',
                message='Ingrese un número de teléfono válido'
            )
        ]
    )
    
    address = models.TextField(
        verbose_name='Dirección'
    )
    
    city = models.CharField(
        max_length=100,
        verbose_name='Ciudad'
    )
    
    department = models.CharField(
        max_length=100,
        verbose_name='Departamento',
        help_text='Ej: La Paz, Santa Cruz, Cochabamba'
    )
    
    country = models.CharField(
        max_length=100,
        default='Bolivia',
        verbose_name='País'
    )
    
    postal_code = models.CharField(
        max_length=10,
        blank=True,
        null=True,
        verbose_name='Código Postal'
    )
    
    # ============================================================
    # DATOS LABORALES Y FINANCIEROS
    # ============================================================
    employment_status = models.CharField(
        max_length=20,
        choices=EMPLOYMENT_STATUS_CHOICES,
        verbose_name='Estado Laboral'
    )
    
    employer_name = models.CharField(
        max_length=200,
        blank=True,
        null=True,
        verbose_name='Nombre del Empleador/Empresa'
    )
    
    employer_nit = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        verbose_name='NIT del Empleador'
    )
    
    job_title = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name='Cargo'
    )
    
    employment_start_date = models.DateField(
        blank=True,
        null=True,
        verbose_name='Fecha de Inicio Laboral'
    )
    
    monthly_income = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        verbose_name='Ingreso Mensual Neto (Bs)',
        help_text='Ingreso líquido mensual en Bolivianos'
    )
    
    additional_income = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0)],
        verbose_name='Ingresos Adicionales (Bs)',
        help_text='Otros ingresos mensuales'
    )
    
    # ============================================================
    # DATOS DEL SISTEMA
    # ============================================================
    is_active = models.BooleanField(
        default=True,
        verbose_name='Activo'
    )
    
    verified_at = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name='Fecha de Verificación',
        help_text='Fecha en que se verificó la identidad del cliente'
    )
    
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='verified_clients',
        verbose_name='Verificado Por'
    )
    
    kyc_status = models.CharField(
        max_length=20,
        choices=[
            ('PENDING', 'Pendiente'),
            ('VERIFIED', 'Verificado'),
            ('REJECTED', 'Rechazado'),
            ('EXPIRED', 'Expirado'),
        ],
        default='PENDING',
        verbose_name='Estado KYC'
    )
    
    risk_level = models.CharField(
        max_length=10,
        choices=[
            ('LOW', 'Bajo'),
            ('MEDIUM', 'Medio'),
            ('HIGH', 'Alto'),
        ],
        blank=True,
        null=True,
        verbose_name='Nivel de Riesgo'
    )
    
    notes = models.TextField(
        blank=True,
        null=True,
        verbose_name='Notas Internas'
    )
    
    class Meta:
        verbose_name = 'Cliente'
        verbose_name_plural = 'Clientes'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['document_number']),
            models.Index(fields=['institution', 'document_number']),
            models.Index(fields=['kyc_status']),
            models.Index(fields=['is_active']),
            models.Index(fields=['user']),  # Índice para FK user
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['institution', 'document_number'],
                name='unique_client_per_institution'
            )
        ]
    
    def __str__(self):
        return f"{self.get_full_name()} - {self.document_number}"
    
    # ============================================================
    # PROPERTIES PARA ACCEDER A DATOS DEL USUARIO
    # ============================================================
    @property
    def email(self):
        """Email del usuario asociado"""
        return self.user.email if self.user else None
    
    @property
    def first_name(self):
        """Nombre del usuario asociado"""
        return self.user.first_name if self.user else ''
    
    @property
    def last_name(self):
        """Apellido del usuario asociado"""
        return self.user.last_name if self.user else ''
    
    @property
    def phone(self):
        """Teléfono del perfil de usuario"""
        if self.user and hasattr(self.user, 'profile'):
            return self.user.profile.phone
        return ''
    
    def get_full_name(self):
        """Retorna el nombre completo del cliente."""
        if self.user:
            return f"{self.user.first_name} {self.user.last_name}"
        return "Sin nombre"
    
    def get_total_monthly_income(self):
        """Retorna el ingreso mensual total."""
        return self.monthly_income + self.additional_income
    
    def get_age(self):
        """Calcula la edad del cliente."""
        from datetime import date
        today = date.today()
        return today.year - self.birth_date.year - (
            (today.month, today.day) < (self.birth_date.month, self.birth_date.day)
        )


class ClientDocument(TenantModel, TimeStampedModel):
    """
    Documentos asociados a un cliente.
    """
    
    DOCUMENT_CATEGORY_CHOICES = [
        ('IDENTITY', 'Documento de Identidad'),
        ('INCOME', 'Comprobante de Ingresos'),
        ('ADDRESS', 'Comprobante de Domicilio'),
        ('EMPLOYMENT', 'Documento Laboral'),
        ('BANK', 'Extracto Bancario'),
        ('TAX', 'Documento Tributario'),
        ('OTHER', 'Otro'),
    ]
    
    client = models.ForeignKey(
        Client,
        on_delete=models.CASCADE,
        related_name='documents',
        verbose_name='Cliente'
    )
    
    category = models.CharField(
        max_length=20,
        choices=DOCUMENT_CATEGORY_CHOICES,
        verbose_name='Categoría'
    )
    
    document_name = models.CharField(
        max_length=200,
        verbose_name='Nombre del Documento'
    )
    
    file = models.FileField(
        upload_to='clients/documents/%Y/%m/',
        verbose_name='Archivo'
    )
    
    file_size = models.IntegerField(
        verbose_name='Tamaño del Archivo (bytes)',
        blank=True,
        null=True
    )
    
    mime_type = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name='Tipo MIME'
    )
    
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='uploaded_client_documents',
        verbose_name='Subido Por'
    )
    
    verified = models.BooleanField(
        default=False,
        verbose_name='Verificado'
    )
    
    verified_at = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name='Fecha de Verificación'
    )
    
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='verified_client_documents',
        verbose_name='Verificado Por'
    )
    
    notes = models.TextField(
        blank=True,
        null=True,
        verbose_name='Notas'
    )
    
    class Meta:
        verbose_name = 'Documento de Cliente'
        verbose_name_plural = 'Documentos de Clientes'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.document_name} - {self.client.get_full_name()}"
