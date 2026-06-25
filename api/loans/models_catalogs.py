"""
Modelos de catálogos centralizados.

Estos catálogos sirven como "bloques de construcción" para configurar
productos crediticios dinámicamente.
"""

from django.db import models
from django.core.validators import MinValueValidator
from api.core.models import TenantModel, TimeStampedModel


class DocumentType(TenantModel, TimeStampedModel):
    """
    Catálogo de tipos de documento.
    
    Define los tipos de documentos que pueden ser requeridos
    para solicitudes de crédito.
    """
    
    CATEGORY_CHOICES = [
        ('IDENTITY', 'Identificación'),
        ('FINANCIAL', 'Financiero'),
        ('LEGAL', 'Legal'),
        ('COLLATERAL', 'Garantías'),
        ('OTHER', 'Otros'),
    ]
    
    code = models.CharField(
        max_length=50,
        verbose_name='Código',
        help_text='Código único del tipo de documento (ej: ID_DOCUMENT)'
    )
    
    name = models.CharField(
        max_length=200,
        verbose_name='Nombre',
        help_text='Nombre descriptivo del documento'
    )
    
    description = models.TextField(
        blank=True,
        verbose_name='Descripción',
        help_text='Descripción detallada del documento'
    )
    
    category = models.CharField(
        max_length=20,
        choices=CATEGORY_CHOICES,
        default='OTHER',
        verbose_name='Categoría'
    )
    
    default_formats = models.JSONField(
        default=list,
        verbose_name='Formatos Permitidos por Defecto',
        help_text='["PDF", "JPG", "PNG"]'
    )
    
    default_max_size_mb = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=5.00,
        validators=[MinValueValidator(0.01)],
        verbose_name='Tamaño Máximo por Defecto (MB)'
    )
    
    default_validity_days = models.IntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1)],
        verbose_name='Validez por Defecto (días)',
        help_text='Días de validez del documento'
    )
    
    is_active = models.BooleanField(
        default=True,
        verbose_name='Activo',
        db_index=True
    )
    
    display_order = models.IntegerField(
        default=0,
        verbose_name='Orden de Visualización'
    )
    
    icon = models.CharField(
        max_length=50,
        blank=True,
        verbose_name='Ícono',
        help_text='Nombre del ícono de lucide-react'
    )
    
    class Meta:
        db_table = 'document_types'
        verbose_name = 'Tipo de Documento'
        verbose_name_plural = 'Tipos de Documentos'
        ordering = ['display_order', 'name']
        indexes = [
            models.Index(fields=['institution', 'is_active']),
            models.Index(fields=['category']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['institution', 'code'],
                name='unique_document_type_code_per_tenant'
            )
        ]
    
    def __str__(self):
        return f"{self.name} ({self.code})"


class ProductType(TenantModel, TimeStampedModel):
    """Catálogo de tipos de producto crediticio."""
    
    CATEGORY_CHOICES = [
        ('CONSUMER', 'Consumo'),
        ('COMMERCIAL', 'Comercial'),
        ('MORTGAGE', 'Hipotecario'),
        ('AGRICULTURAL', 'Agropecuario'),
    ]
    
    code = models.CharField(
        max_length=50,
        verbose_name='Código',
        help_text='Código único del tipo (ej: PERSONAL, VEHICULAR)'
    )
    
    name = models.CharField(
        max_length=200,
        verbose_name='Nombre'
    )
    
    description = models.TextField(
        blank=True,
        verbose_name='Descripción'
    )
    
    category = models.CharField(
        max_length=20,
        choices=CATEGORY_CHOICES,
        verbose_name='Categoría Principal'
    )
    
    icon = models.CharField(
        max_length=50,
        blank=True,
        verbose_name='Ícono',
        help_text='Nombre del ícono de lucide-react'
    )
    
    color = models.CharField(
        max_length=20,
        blank=True,
        verbose_name='Color',
        help_text='Color para UI (ej: blue, green, purple)'
    )
    
    is_active = models.BooleanField(
        default=True,
        verbose_name='Activo',
        db_index=True
    )
    
    display_order = models.IntegerField(
        default=0,
        verbose_name='Orden de Visualización'
    )
    
    class Meta:
        db_table = 'product_types'
        verbose_name = 'Tipo de Producto'
        verbose_name_plural = 'Tipos de Productos'
        ordering = ['display_order', 'name']
        indexes = [
            models.Index(fields=['institution', 'is_active']),
            models.Index(fields=['category']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['institution', 'code'],
                name='unique_product_type_code_per_tenant'
            )
        ]
    
    def __str__(self):
        return self.name


class PaymentFrequency(TenantModel, TimeStampedModel):
    """Catálogo de frecuencias de pago."""
    
    code = models.CharField(
        max_length=50,
        verbose_name='Código',
        help_text='Código único (ej: MONTHLY, BIWEEKLY)'
    )
    
    name = models.CharField(
        max_length=200,
        verbose_name='Nombre',
        help_text='Nombre descriptivo (ej: Mensual, Quincenal)'
    )
    
    days_between_payments = models.IntegerField(
        validators=[MinValueValidator(1)],
        verbose_name='Días entre Pagos',
        help_text='Número de días entre cada pago'
    )
    
    payments_per_year = models.IntegerField(
        validators=[MinValueValidator(1)],
        verbose_name='Pagos por Año',
        help_text='Cantidad de pagos en un año'
    )
    
    is_active = models.BooleanField(
        default=True,
        verbose_name='Activo',
        db_index=True
    )
    
    display_order = models.IntegerField(
        default=0,
        verbose_name='Orden de Visualización'
    )
    
    class Meta:
        db_table = 'payment_frequencies'
        verbose_name = 'Frecuencia de Pago'
        verbose_name_plural = 'Frecuencias de Pago'
        ordering = ['display_order', 'name']
        indexes = [
            models.Index(fields=['institution', 'is_active']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['institution', 'code'],
                name='unique_payment_frequency_code_per_tenant'
            )
        ]
    
    def __str__(self):
        return self.name


class AmortizationSystem(TenantModel, TimeStampedModel):
    """Catálogo de sistemas de amortización."""
    
    code = models.CharField(
        max_length=50,
        verbose_name='Código',
        help_text='Código único (ej: FRENCH, GERMAN)'
    )
    
    name = models.CharField(
        max_length=200,
        verbose_name='Nombre',
        help_text='Nombre del sistema'
    )
    
    description = models.TextField(
        blank=True,
        verbose_name='Descripción',
        help_text='Descripción del método de cálculo'
    )
    
    formula_type = models.CharField(
        max_length=50,
        verbose_name='Tipo de Fórmula',
        help_text='Identificador del algoritmo de cálculo'
    )
    
    is_active = models.BooleanField(
        default=True,
        verbose_name='Activo',
        db_index=True
    )
    
    display_order = models.IntegerField(
        default=0,
        verbose_name='Orden de Visualización'
    )
    
    class Meta:
        db_table = 'amortization_systems'
        verbose_name = 'Sistema de Amortización'
        verbose_name_plural = 'Sistemas de Amortización'
        ordering = ['display_order', 'name']
        indexes = [
            models.Index(fields=['institution', 'is_active']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['institution', 'code'],
                name='unique_amortization_system_code_per_tenant'
            )
        ]
    
    def __str__(self):
        return self.name


class Currency(TenantModel, TimeStampedModel):
    """Catálogo de monedas."""
    
    code = models.CharField(
        max_length=3,
        verbose_name='Código ISO',
        help_text='Código ISO 4217 (ej: BOB, USD, EUR)'
    )
    
    name = models.CharField(
        max_length=100,
        verbose_name='Nombre',
        help_text='Nombre de la moneda'
    )
    
    symbol = models.CharField(
        max_length=10,
        verbose_name='Símbolo',
        help_text='Símbolo de la moneda (ej: Bs, $, €)'
    )
    
    exchange_rate_to_base = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        default=1.0000,
        validators=[MinValueValidator(0.0001)],
        verbose_name='Tipo de Cambio a Moneda Base',
        help_text='Tipo de cambio respecto a la moneda base (BOB)'
    )
    
    is_base_currency = models.BooleanField(
        default=False,
        verbose_name='Moneda Base',
        help_text='Indica si es la moneda base del sistema'
    )
    
    is_active = models.BooleanField(
        default=True,
        verbose_name='Activo',
        db_index=True
    )
    
    display_order = models.IntegerField(
        default=0,
        verbose_name='Orden de Visualización'
    )
    
    class Meta:
        db_table = 'currencies'
        verbose_name = 'Moneda'
        verbose_name_plural = 'Monedas'
        ordering = ['display_order', 'name']
        indexes = [
            models.Index(fields=['institution', 'is_active']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['institution', 'code'],
                name='unique_currency_code_per_tenant'
            ),
            models.UniqueConstraint(
                fields=['institution'],
                condition=models.Q(is_base_currency=True),
                name='unique_base_currency_per_tenant'
            )
        ]
    
    def __str__(self):
        return f"{self.name} ({self.code})"
