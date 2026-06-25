"""
Modelos para SP3: Gestión de Créditos Activos y Pagos.

Incluye:
- ActiveCredit: Crédito activo post-desembolso
- CreditInstallment: Cuota del cronograma de pagos
- CreditPayment: Registro de pago (presencial/online)
- CreditPaymentAllocation: Distribución del pago entre cuotas
- CreditGracePeriod: Período de gracia
- CreditRestructuring: Reestructuración de crédito
- CreditStatusHistory: Historial de cambios de estado
"""

from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator
from decimal import Decimal
from api.core.models import TenantModel


class ActiveCredit(TenantModel):
    """
    Crédito activo post-desembolso.

    Representa la deuda vigente de un cliente después de que su solicitud
    fue aprobada, el contrato firmado y el desembolso realizado.
    """

    class Status(models.TextChoices):
        ACTIVE = 'ACTIVE', 'Al Día'
        PENDING_PAYMENT = 'PENDING_PAYMENT', 'Pago Pendiente'
        IN_ARREARS = 'IN_ARREARS', 'En Mora'
        IN_GRACE_PERIOD = 'IN_GRACE_PERIOD', 'Período de Gracia'
        RESTRUCTURED = 'RESTRUCTURED', 'Reestructurado'
        CANCELLED = 'CANCELLED', 'Cancelado'
        LEGAL = 'LEGAL', 'Cobro Legal'

    # Relaciones
    loan_application = models.OneToOneField(
        'loans.LoanApplication',
        on_delete=models.PROTECT,
        related_name='active_credit',
        verbose_name='Solicitud de Crédito'
    )
    contract = models.OneToOneField(
        'contracts.Contract',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='active_credit',
        verbose_name='Contrato'
    )
    client = models.ForeignKey(
        'clients.Client',
        on_delete=models.PROTECT,
        related_name='active_credits',
        verbose_name='Cliente/Prestatario'
    )
    product = models.ForeignKey(
        'products.CreditProduct',
        on_delete=models.PROTECT,
        related_name='active_credits',
        verbose_name='Producto Crediticio'
    )

    # Identificación
    credit_number = models.CharField(
        max_length=50,
        unique=True,
        verbose_name='Código de Crédito',
        help_text='Número único identificador del crédito activo'
    )

    # Términos financieros
    approved_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        verbose_name='Monto Aprobado'
    )
    currency = models.ForeignKey(
        'loans.Currency',
        on_delete=models.PROTECT,
        related_name='active_credits',
        verbose_name='Moneda'
    )
    annual_interest_rate = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        verbose_name='Tasa de Interés Anual (%)'
    )
    term_periods = models.PositiveIntegerField(
        validators=[MinValueValidator(1)],
        verbose_name='Número de Cuotas'
    )
    payment_frequency = models.ForeignKey(
        'loans.PaymentFrequency',
        on_delete=models.PROTECT,
        related_name='active_credits',
        verbose_name='Frecuencia de Pago'
    )
    amortization_system = models.ForeignKey(
        'loans.AmortizationSystem',
        on_delete=models.PROTECT,
        related_name='active_credits',
        verbose_name='Sistema de Amortización'
    )

    # Fechas
    disbursement_date = models.DateField(
        verbose_name='Fecha de Desembolso'
    )
    first_payment_date = models.DateField(
        verbose_name='Fecha de Primera Cuota'
    )
    maturity_date = models.DateField(
        verbose_name='Fecha de Vencimiento Final'
    )
    next_due_date = models.DateField(
        null=True,
        blank=True,
        verbose_name='Próxima Fecha de Vencimiento'
    )

    # Saldos (se actualizan con cada pago)
    current_balance = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name='Saldo Insoluto'
    )
    total_paid = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name='Total Pagado'
    )
    principal_paid = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name='Capital Pagado'
    )
    interest_paid = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name='Interés Pagado'
    )
    fees_paid = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name='Comisiones Pagadas'
    )
    penalty_paid = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name='Penalidades Pagadas'
    )

    # Estado
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE,
        db_index=True,
        verbose_name='Estado'
    )
    days_in_arrears = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0)],
        verbose_name='Días en Mora'
    )

    # Metadata
    metadata = models.JSONField(
        default=dict,
        blank=True,
        verbose_name='Metadata'
    )
    notes = models.TextField(
        blank=True,
        verbose_name='Notas'
    )

    class Meta:
        db_table = 'active_credits'
        verbose_name = 'Crédito Activo'
        verbose_name_plural = 'Créditos Activos'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['institution', 'status']),
            models.Index(fields=['client', '-created_at']),
            models.Index(fields=['credit_number']),
            models.Index(fields=['next_due_date']),
        ]

    def __str__(self):
        return f"{self.credit_number} - {self.client}"


class CreditInstallment(TenantModel):
    """
    Cuota del cronograma de pagos de un crédito activo.

    Cada fila representa un período de pago con su desglose financiero:
    capital, interés, seguro, comisión, penalidad.
    """

    class Status(models.TextChoices):
        PENDING = 'PENDING', 'Pendiente'
        PAID = 'PAID', 'Pagada'
        PARTIAL = 'PARTIAL', 'Parcial'
        OVERDUE = 'OVERDUE', 'Vencida'
        IN_GRACE = 'IN_GRACE', 'En Gracia'
        REPROGRAMMED = 'REPROGRAMMED', 'Reprogramada'
        CANCELLED = 'CANCELLED', 'Cancelada'

    active_credit = models.ForeignKey(
        ActiveCredit,
        on_delete=models.CASCADE,
        related_name='installments',
        verbose_name='Crédito Activo'
    )

    # Numeración
    installment_number = models.PositiveIntegerField(
        verbose_name='Número de Cuota'
    )

    # Fechas
    due_date = models.DateField(
        verbose_name='Fecha de Vencimiento'
    )
    paid_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Fecha de Pago'
    )
    days_overdue = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0)],
        verbose_name='Días de Mora'
    )

    # Desglose financiero
    opening_balance = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name='Saldo Inicial'
    )
    principal_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name='Capital'
    )
    interest_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name='Interés'
    )
    insurance_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name='Seguro'
    )
    fee_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name='Comisión'
    )
    penalty_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name='Penalidad'
    )
    total_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        verbose_name='Total Cuota'
    )

    # Pago
    paid_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name='Monto Pagado'
    )
    closing_balance = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name='Saldo Final'
    )

    # Estado
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
        verbose_name='Estado'
    )

    # Trazabilidad
    original_due_date = models.DateField(
        null=True,
        blank=True,
        verbose_name='Fecha de Vencimiento Original',
        help_text='Fecha antes de reestructuración o gracia'
    )
    restructuring = models.ForeignKey(
        'loans.CreditRestructuring',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='installments',
        verbose_name='Reestructuración'
    )
    metadata = models.JSONField(
        default=dict,
        blank=True,
        verbose_name='Metadata'
    )
    insurance_detail = models.JSONField(
        default=dict,
        blank=True,
        verbose_name='Detalle de Seguro',
        help_text='Detalles de los seguros aplicados a esta cuota'
    )

    class Meta:
        db_table = 'credit_installments'
        verbose_name = 'Cuota'
        verbose_name_plural = 'Cuotas'
        ordering = ['installment_number']
        indexes = [
            models.Index(fields=['active_credit', 'status']),
            models.Index(fields=['due_date']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['active_credit', 'installment_number'],
                name='unique_installment_number_per_credit'
            )
        ]

    def __str__(self):
        return f"Cuota #{self.installment_number} - {self.active_credit.credit_number}"


class CreditPayment(TenantModel):
    """
    Registro de un pago aplicado a un crédito activo.

    Soporta dos canales:
    - PRESENTIAL: Registrado por staff (caja, ventanilla, transferencia)
    - ONLINE: Iniciado por el cliente vía portal de pagos
    """

    class Channel(models.TextChoices):
        PRESENTIAL = 'PRESENTIAL', 'Presencial'
        ONLINE = 'ONLINE', 'En Línea'

    class Status(models.TextChoices):
        PENDING_CONFIRMATION = 'PENDING_CONFIRMATION', 'Pendiente de Confirmación'
        CONFIRMED = 'CONFIRMED', 'Confirmado'
        FAILED = 'FAILED', 'Fallido'
        CANCELLED = 'CANCELLED', 'Cancelado'
        REVERSED = 'REVERSED', 'Reversado'
        REFUNDED = 'REFUNDED', 'Reembolsado'
        MANUAL_REVIEW = 'MANUAL_REVIEW', 'Revisión Manual'

    active_credit = models.ForeignKey(
        ActiveCredit,
        on_delete=models.PROTECT,
        related_name='payments',
        verbose_name='Crédito Activo'
    )

    # Monto y moneda
    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        verbose_name='Monto'
    )
    currency = models.ForeignKey(
        'loans.Currency',
        on_delete=models.PROTECT,
        related_name='payments',
        verbose_name='Moneda'
    )

    # Fechas
    payment_date = models.DateField(
        verbose_name='Fecha de Pago'
    )
    confirmed_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Fecha de Confirmación'
    )

    # Canal y método
    channel = models.CharField(
        max_length=20,
        choices=Channel.choices,
        verbose_name='Canal'
    )
    method = models.CharField(
        max_length=50,
        verbose_name='Método de Pago',
        help_text='CASH, TRANSFER, QR, CARD, etc.'
    )

    # Referencias
    reference_number = models.CharField(
        max_length=100,
        blank=True,
        verbose_name='Número de Referencia/Comprobante'
    )

    # Proveedor (pagos online)
    provider = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        verbose_name='Proveedor de Pago',
        help_text='STRIPE, PAGO_PAR, etc.'
    )
    provider_payment_id = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        verbose_name='ID de Pago en Proveedor'
    )
    provider_event_id = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        unique=True,
        verbose_name='ID de Evento en Proveedor',
        help_text='Para idempotencia de webhooks'
    )

    # Estado
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING_CONFIRMATION,
        db_index=True,
        verbose_name='Estado'
    )

    # Quién registró o confirmó
    registered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='registered_payments',
        verbose_name='Registrado por'
    )
    confirmed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='confirmed_payments',
        verbose_name='Confirmado por'
    )

    # Comprobante (presencial)
    receipt_file = models.ForeignKey(
        'storage.FileResource',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='payment_receipts',
        verbose_name='Comprobante'
    )

    notes = models.TextField(
        blank=True,
        verbose_name='Notas'
    )
    metadata = models.JSONField(
        default=dict,
        blank=True,
        verbose_name='Metadata'
    )

    class Meta:
        db_table = 'credit_payments'
        verbose_name = 'Pago'
        verbose_name_plural = 'Pagos'
        ordering = ['-payment_date', '-created_at']
        indexes = [
            models.Index(fields=['active_credit', '-payment_date']),
            models.Index(fields=['status']),
            models.Index(fields=['channel']),
            models.Index(fields=['provider_payment_id']),
        ]

    def __str__(self):
        return f"Pago {self.reference_number or self.id} - {self.get_channel_display()}"


class CreditPaymentAllocation(TenantModel):
    """
    Distribución de un pago entre cuotas.

    Registra cómo se repartió el monto del pago entre una o más cuotas,
    con desglose de qué porción cubrió capital, interés, seguro, etc.
    """

    payment = models.ForeignKey(
        CreditPayment,
        on_delete=models.CASCADE,
        related_name='allocations',
        verbose_name='Pago'
    )
    installment = models.ForeignKey(
        CreditInstallment,
        on_delete=models.PROTECT,
        related_name='payment_allocations',
        verbose_name='Cuota'
    )

    amount_applied = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        verbose_name='Monto Aplicado'
    )

    # Desglose de lo que cubrió
    principal_covered = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name='Capital Cubierto'
    )
    interest_covered = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name='Interés Cubierto'
    )
    insurance_covered = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name='Seguro Cubierto'
    )
    fee_covered = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name='Comisión Cubierta'
    )
    penalty_covered = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name='Penalidad Cubierta'
    )

    class Meta:
        db_table = 'credit_payment_allocations'
        verbose_name = 'Distribución de Pago'
        verbose_name_plural = 'Distribuciones de Pago'
        constraints = [
            models.UniqueConstraint(
                fields=['payment', 'installment'],
                name='unique_payment_installment_allocation'
            )
        ]

    def __str__(self):
        return f"Pago {self.payment_id} → Cuota #{self.installment.installment_number}: {self.amount_applied}"


class CreditGracePeriod(TenantModel):
    """
    Período de gracia aplicado a un crédito activo.

    Tipos:
    - FULL_GRACE: No se cobra capital ni interés durante la gracia
    - INTEREST_ONLY: Solo se pagan intereses
    - PARTIAL_PAYMENT: Pago reducido, diferencia se capitaliza
    """

    class GraceType(models.TextChoices):
        FULL_GRACE = 'FULL_GRACE', 'Gracia Total (capital + interés)'
        INTEREST_ONLY = 'INTEREST_ONLY', 'Solo Intereses'
        PARTIAL_PAYMENT = 'PARTIAL_PAYMENT', 'Pago Parcial'

    active_credit = models.ForeignKey(
        ActiveCredit,
        on_delete=models.CASCADE,
        related_name='grace_periods',
        verbose_name='Crédito Activo'
    )

    grace_type = models.CharField(
        max_length=30,
        choices=GraceType.choices,
        verbose_name='Tipo de Gracia'
    )
    start_date = models.DateField(
        verbose_name='Fecha de Inicio'
    )
    end_date = models.DateField(
        verbose_name='Fecha de Fin'
    )
    reason = models.TextField(
        verbose_name='Motivo'
    )
    applied_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='applied_graces',
        verbose_name='Aplicado por'
    )
    is_active = models.BooleanField(
        default=True,
        db_index=True,
        verbose_name='Activo'
    )
    metadata = models.JSONField(
        default=dict,
        blank=True,
        verbose_name='Metadata'
    )

    class Meta:
        db_table = 'credit_grace_periods'
        verbose_name = 'Período de Gracia'
        verbose_name_plural = 'Períodos de Gracia'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['active_credit', 'is_active']),
        ]

    def __str__(self):
        return f"Gracia {self.get_grace_type_display()} - {self.active_credit.credit_number}"


class CreditRestructuring(TenantModel):
    """
    Reestructuración de un crédito activo.

    Guarda snapshot de condiciones originales y aplica nuevos términos.
    Las cuotas pagadas no se modifican; las pendientes se marcan REPROGRAMMED
    y se genera un nuevo cronograma.
    """

    active_credit = models.ForeignKey(
        ActiveCredit,
        on_delete=models.CASCADE,
        related_name='restructurings',
        verbose_name='Crédito Activo'
    )

    # Condiciones originales (snapshot inmutable)
    original_terms = models.JSONField(
        verbose_name='Condiciones Originales',
        help_text='Snapshot de term_periods, interest_rate, payment_frequency, amortization_system'
    )

    # Nuevas condiciones
    new_term_periods = models.PositiveIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1)],
        verbose_name='Nuevo Plazo (cuotas)'
    )
    new_interest_rate = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name='Nueva Tasa de Interés Anual (%)'
    )
    new_payment_frequency = models.ForeignKey(
        'loans.PaymentFrequency',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='restructurings',
        verbose_name='Nueva Frecuencia de Pago'
    )
    new_amortization_system = models.ForeignKey(
        'loans.AmortizationSystem',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='restructurings',
        verbose_name='Nuevo Sistema de Amortización'
    )
    new_first_payment_date = models.DateField(
        null=True,
        blank=True,
        verbose_name='Nueva Fecha de Primera Cuota'
    )

    reason = models.TextField(
        verbose_name='Motivo'
    )
    applied_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='applied_restructurings',
        verbose_name='Aplicado por'
    )
    applied_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Fecha de Aplicación'
    )

    # Cronograma anterior (snapshot inmutable)
    previous_schedule_snapshot = models.JSONField(
        verbose_name='Cronograma Anterior',
        help_text='Snapshot del cronograma antes de la reestructuración'
    )

    # Estado
    is_active = models.BooleanField(
        default=True,
        db_index=True,
        verbose_name='Activo'
    )
    metadata = models.JSONField(
        default=dict,
        blank=True,
        verbose_name='Metadata'
    )

    class Meta:
        db_table = 'credit_restructurings'
        verbose_name = 'Reestructuración'
        verbose_name_plural = 'Reestructuraciones'
        ordering = ['-applied_at']
        indexes = [
            models.Index(fields=['active_credit', 'is_active']),
        ]

    def __str__(self):
        return f"Reestructuración - {self.active_credit.credit_number} ({self.applied_at:%Y-%m-%d})"


class CreditStatusHistory(TenantModel):
    """
    Historial de cambios de estado del crédito activo.

    Registra cada transición de estado con el usuario responsable y motivo.
    """

    active_credit = models.ForeignKey(
        ActiveCredit,
        on_delete=models.CASCADE,
        related_name='status_history',
        verbose_name='Crédito Activo'
    )
    previous_status = models.CharField(
        max_length=20,
        verbose_name='Estado Anterior'
    )
    new_status = models.CharField(
        max_length=20,
        verbose_name='Nuevo Estado'
    )
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='Cambiado por'
    )
    reason = models.TextField(
        blank=True,
        verbose_name='Motivo'
    )
    metadata = models.JSONField(
        default=dict,
        blank=True,
        verbose_name='Metadata'
    )

    class Meta:
        db_table = 'credit_status_history'
        verbose_name = 'Historial de Estado'
        verbose_name_plural = 'Historiales de Estado'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['active_credit', '-created_at']),
        ]

    def __str__(self):
        return f"{self.active_credit.credit_number}: {self.previous_status} → {self.new_status}"


class CreditSupportRequest(TenantModel):
    """
    Solicitud de apoyo de pago enviada por el cliente desde mobile.

    El cliente puede solicitar período de gracia o reestructuración.
    El banco revisa la solicitud desde web y decide si la aprueba o rechaza.
    La aplicación real solo ocurre cuando el banco aprueba.
    """

    class RequestType(models.TextChoices):
        GRACE_PERIOD = 'GRACE_PERIOD', 'Período de Gracia'
        RESTRUCTURING = 'RESTRUCTURING', 'Reestructuración'

    class RequestStatus(models.TextChoices):
        PENDING = 'PENDING', 'Pendiente de revisión'
        UNDER_REVIEW = 'UNDER_REVIEW', 'En revisión'
        APPROVED = 'APPROVED', 'Aprobada'
        REJECTED = 'REJECTED', 'Rechazada'
        CANCELLED = 'CANCELLED', 'Cancelada'

    class ReasonCategory(models.TextChoices):
        INCOME_REDUCTION = 'income_reduction', 'Disminución temporal de ingresos'
        ILLNESS = 'illness', 'Enfermedad'
        JOB_LOSS = 'job_loss', 'Pérdida de empleo'
        FAMILY_EMERGENCY = 'family_emergency', 'Emergencia familiar'
        ECONOMIC_HARDSHIP = 'economic_hardship', 'Dificultad económica temporal'
        OTHER = 'other', 'Otro'

    active_credit = models.ForeignKey(
        'ActiveCredit',
        on_delete=models.CASCADE,
        related_name='support_requests',
        verbose_name='Crédito Activo'
    )
    client = models.ForeignKey(
        'clients.Client',
        on_delete=models.PROTECT,
        related_name='support_requests',
        verbose_name='Cliente'
    )
    request_type = models.CharField(
        max_length=20,
        choices=RequestType.choices,
        verbose_name='Tipo de Solicitud'
    )
    reason_category = models.CharField(
        max_length=30,
        choices=ReasonCategory.choices,
        verbose_name='Motivo Principal'
    )
    description = models.TextField(
        verbose_name='Descripción Detallada'
    )
    requested_months = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name='Meses Solicitados',
        help_text='Cantidad de meses solicitados para gracia o nuevo plazo'
    )
    contact_phone = models.CharField(
        max_length=20,
        blank=True,
        verbose_name='Teléfono de Contacto'
    )
    status = models.CharField(
        max_length=20,
        choices=RequestStatus.choices,
        default=RequestStatus.PENDING,
        db_index=True,
        verbose_name='Estado'
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_support_requests',
        verbose_name='Revisado por'
    )
    reviewed_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Fecha de Revisión'
    )
    bank_response = models.TextField(
        blank=True,
        verbose_name='Respuesta del Banco'
    )
    approved_terms_snapshot = models.JSONField(
        null=True,
        blank=True,
        verbose_name='Snapshot de Términos Aprobados',
        help_text='Condiciones aprobadas (solo cuando status=APPROVED)'
    )
    requires_more_info = models.BooleanField(
        default=False,
        verbose_name='Requiere Más Información'
    )
    requested_info = models.TextField(
        blank=True,
        verbose_name='Información Solicitada'
    )

    class Meta:
        db_table = 'credit_support_requests'
        verbose_name = 'Solicitud de Apoyo de Pago'
        verbose_name_plural = 'Solicitudes de Apoyo de Pago'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['active_credit', '-created_at']),
            models.Index(fields=['client', '-created_at']),
            models.Index(fields=['status']),
            models.Index(fields=['request_type', 'status']),
        ]

    def __str__(self):
        return f"{self.get_request_type_display()} - {self.active_credit.credit_number} ({self.get_status_display()})"
