"""
Modelos para Gestión de Seguros Asociados al Crédito.
"""
from decimal import Decimal

from django.conf import settings
from django.db import models

from api.core.models import TenantModel, TimeStampedModel


class InsuranceType(models.TextChoices):
    DESGRAVAMEN = 'DESGRAVAMEN', 'Seguro de Desgravamen'
    INCENDIO = 'INCENDIO', 'Seguro de Incendio'
    VEHICULAR = 'VEHICULAR', 'Seguro Vehicular'
    HIPOTECARIO = 'HIPOTECARIO', 'Seguro Hipotecario'
    AGRICOLA = 'AGRICOLA', 'Seguro Agrícola'
    VIDA = 'VIDA', 'Seguro de Vida'
    OTRO = 'OTRO', 'Otro'


class CoverageType(models.TextChoices):
    MONTO_FIJO = 'MONTO_FIJO', 'Monto Fijo'
    PORCENTAJE_SALDO = 'PORCENTAJE_SALDO', 'Porcentaje del Saldo'
    PORCENTAJE_MONTO = 'PORCENTAJE_MONTO', 'Porcentaje del Monto'


class PremiumType(models.TextChoices):
    MONTHLY = 'MONTHLY', 'Mensual (en cuota)'
    LUMP_SUM = 'LUMP_SUM', 'Único al desembolso'
    ANNUAL = 'ANNUAL', 'Anual'
    BALANCE = 'BALANCE', 'Porcentaje del saldo insoluto'


class CreditInsuranceStatus(models.TextChoices):
    ACTIVE = 'ACTIVE', 'Activo'
    EXPIRING_SOON = 'EXPIRING_SOON', 'Por vencer'
    EXPIRED = 'EXPIRED', 'Vencido'
    CANCELLED = 'CANCELLED', 'Cancelado'
    SUSPENDED = 'SUSPENDED', 'Suspendido'


class Insurer(TenantModel):
    """
    Aseguradora - Compañía de seguros.
    """
    name = models.CharField(max_length=200, verbose_name='Nombre')
    code = models.CharField(max_length=50, verbose_name='Código')
    nit = models.CharField(max_length=20, verbose_name='NIT')
    phone = models.CharField(max_length=20, blank=True, verbose_name='Teléfono')
    email = models.EmailField(blank=True, verbose_name='Email')
    address = models.TextField(blank=True, verbose_name='Dirección')
    is_active = models.BooleanField(default=True, verbose_name='Activo')

    class Meta:
        db_table = 'insurance_insurers'
        ordering = ['name']
        verbose_name = 'Aseguradora'
        verbose_name_plural = 'Aseguradoras'
        constraints = [
            models.UniqueConstraint(
                fields=['institution', 'code'],
                name='unique_insurer_code_per_institution'
            )
        ]

    def __str__(self):
        return f"{self.name} ({self.code})"


class Insurance(TenantModel):
    """
    Seguro - Catálogo de seguros disponibles.
    """
    name = models.CharField(max_length=200, verbose_name='Nombre')
    code = models.CharField(max_length=50, verbose_name='Código')
    insurance_type = models.CharField(
        max_length=20,
        choices=InsuranceType.choices,
        default=InsuranceType.DESGRAVAMEN,
        verbose_name='Tipo de Seguro'
    )
    description = models.TextField(blank=True, verbose_name='Descripción')
    insurer = models.ForeignKey(
        Insurer,
        on_delete=models.PROTECT,
        related_name='insurances',
        verbose_name='Aseguradora'
    )
    is_mandatory = models.BooleanField(default=False, verbose_name='Obligatorio')
    is_active = models.BooleanField(default=True, verbose_name='Activo')

    coverage_type = models.CharField(
        max_length=20,
        choices=CoverageType.choices,
        default=CoverageType.PORCENTAJE_SALDO,
        verbose_name='Tipo de Cobertura'
    )
    coverage_value = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        default=Decimal('0.0000'),
        verbose_name='Valor de Cobertura (%)'
    )
    max_coverage_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name='Monto Máximo de Cobertura'
    )

    min_term_months = models.IntegerField(default=1, verbose_name='Plazo mínimo (meses)')
    max_term_months = models.IntegerField(default=360, verbose_name='Plazo máximo (meses)')
    is_renewable = models.BooleanField(default=True, verbose_name='Renovable')
    grace_period_days = models.IntegerField(default=0, verbose_name='Período de gracia (días)')

    premium_type = models.CharField(
        max_length=20,
        choices=PremiumType.choices,
        default=PremiumType.BALANCE,
        verbose_name='Tipo de Prima'
    )
    base_premium = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        default=Decimal('0.0000'),
        verbose_name='Prima Base (%)'
    )

    requires_medical_exam = models.BooleanField(default=False, verbose_name='Requiere examen médico')
    has_deductible = models.BooleanField(default=False, verbose_name='Tiene deducible')
    deductible_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name='Porcentaje Deducible (%)'
    )

    class Meta:
        db_table = 'insurance_insurances'
        ordering = ['name']
        verbose_name = 'Seguro'
        verbose_name_plural = 'Seguros'
        unique_together = [['institution', 'code']]

    def __str__(self):
        return f"{self.name} - {self.insurer.name}"


class InsuranceCoverage(TenantModel):
    """
    Cobertura específica de un seguro.
    """
    insurance = models.ForeignKey(
        Insurance,
        on_delete=models.CASCADE,
        related_name='coverages',
        verbose_name='Seguro'
    )
    name = models.CharField(max_length=200, verbose_name='Nombre de Cobertura')
    coverage_type = models.CharField(
        max_length=20,
        choices=CoverageType.choices,
        default=CoverageType.MONTO_FIJO,
        verbose_name='Tipo de Cobertura'
    )
    value = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name='Valor'
    )
    max_value = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name='Valor Máximo'
    )
    conditions = models.TextField(blank=True, verbose_name='Condiciones')
    exclusions = models.TextField(blank=True, verbose_name='Exclusiones')
    display_order = models.IntegerField(default=0, verbose_name='Orden de visualización')

    class Meta:
        db_table = 'insurance_coverages'
        ordering = ['display_order', 'name']
        verbose_name = 'Cobertura'
        verbose_name_plural = 'Coberturas'

    def __str__(self):
        return f"{self.insurance.name} - {self.name}"


class ProductInsurance(TenantModel):
    """
    Asociación entre producto crediticio y seguros.
    Define qué seguros están asociados a un producto y si son obligatorios.
    """
    product = models.ForeignKey(
        'products.CreditProduct',
        on_delete=models.CASCADE,
        related_name='insurance_associations',
        verbose_name='Producto Crediticio'
    )
    insurance = models.ForeignKey(
        Insurance,
        on_delete=models.CASCADE,
        related_name='product_associations',
        verbose_name='Seguro'
    )
    is_required = models.BooleanField(default=False, verbose_name='Obligatorio')
    premium_type = models.CharField(
        max_length=20,
        choices=PremiumType.choices,
        default=PremiumType.BALANCE,
        verbose_name='Tipo de Prima'
    )
    custom_premium = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        null=True,
        blank=True,
        verbose_name='Prima Personalizada (%)'
    )
    display_order = models.IntegerField(default=0, verbose_name='Orden de visualización')

    class Meta:
        db_table = 'insurance_product_insurances'
        ordering = ['display_order']
        verbose_name = 'Seguro de Producto'
        verbose_name_plural = 'Seguros de Productos'
        unique_together = [['product', 'insurance']]

    def __str__(self):
        req = 'Obligatorio' if self.is_required else 'Opcional'
        return f"{self.product.name} - {self.insurance.name} ({req})"


class CreditInsurance(TenantModel):
    """
    Seguro asociado a un crédito específico (póliza).
    """
    active_credit = models.ForeignKey(
        'loans.ActiveCredit',
        on_delete=models.CASCADE,
        related_name='insurances',
        verbose_name='Crédito Activo'
    )
    insurance = models.ForeignKey(
        Insurance,
        on_delete=models.PROTECT,
        related_name='credit_insurances',
        verbose_name='Seguro'
    )
    policy_number = models.CharField(max_length=100, verbose_name='Número de Póliza')
    start_date = models.DateField(verbose_name='Fecha de Inicio')
    end_date = models.DateField(verbose_name='Fecha de Vencimiento')
    total_premium = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name='Prima Total'
    )
    premium_paid = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name='Prima Pagada'
    )
    status = models.CharField(
        max_length=20,
        choices=CreditInsuranceStatus.choices,
        default=CreditInsuranceStatus.ACTIVE,
        verbose_name='Estado'
    )
    beneficiary_name = models.CharField(max_length=200, verbose_name='Nombre del Beneficiario')
    beneficiary_nit = models.CharField(max_length=20, blank=True, verbose_name='NIT del Beneficiario')
    notes = models.TextField(blank=True, verbose_name='Notas')

    class Meta:
        db_table = 'insurance_credit_insurances'
        ordering = ['-start_date']
        verbose_name = 'Póliza de Seguro'
        verbose_name_plural = 'Pólizas de Seguros'

    def __str__(self):
        return f"{self.policy_number} - {self.active_credit}"

    @property
    def is_active(self):
        return self.status == CreditInsuranceStatus.ACTIVE

    @property
    def is_expired(self):
        from django.utils import timezone
        return self.end_date < timezone.now().date()

    @property
    def days_until_expiry(self):
        from django.utils import timezone
        delta = self.end_date - timezone.now().date()
        return delta.days
