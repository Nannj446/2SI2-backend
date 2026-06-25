"""
Modelos para gestión de contratos de crédito

Este módulo define los modelos para:
- Contratos de crédito
- Plantillas de contratos
- Firmas digitales
- Tabla de amortización
"""

from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from decimal import Decimal
from api.core.models import TenantModel


class ContractTemplate(TenantModel):
    """
    Plantilla de contrato personalizable por tenant y producto.
    
    Permite definir plantillas HTML con variables dinámicas que se reemplazan
    con datos reales al generar un contrato.
    """
    
    name = models.CharField(
        max_length=200,
        verbose_name='Nombre de la Plantilla'
    )
    code = models.CharField(
        max_length=50,
        verbose_name='Código',
        help_text='Código único identificador de la plantilla'
    )
    
    # Relación con productos (obligatorio - cada plantilla debe estar asociada a un producto)
    product = models.ForeignKey(
        'products.CreditProduct',
        on_delete=models.PROTECT,
        related_name='contract_templates',
        verbose_name='Producto Crediticio',
        help_text='Producto crediticio al que pertenece esta plantilla de contrato'
    )
    
    # Contenido de la plantilla (HTML con variables tipo {{variable}})
    template_content = models.TextField(
        verbose_name='Contenido de la Plantilla',
        help_text='HTML con variables como {{borrower_name}}, {{amount}}, etc.'
    )
    
    # Variables disponibles en la plantilla
    available_variables = models.JSONField(
        default=list,
        blank=True,
        verbose_name='Variables Disponibles',
        help_text='Lista de variables que se pueden usar en la plantilla'
    )
    
    # Configuración
    is_active = models.BooleanField(
        default=True,
        verbose_name='Activa',
        help_text='Solo las plantillas activas pueden usarse para generar contratos'
    )
    is_default = models.BooleanField(
        default=False,
        verbose_name='Plantilla por Defecto',
        help_text='Se usa cuando no hay plantilla específica para el producto'
    )
    requires_guarantor_signature = models.BooleanField(
        default=False,
        verbose_name='Requiere Firma de Garante',
        help_text='Si es True, los garantes deben firmar el contrato'
    )
    
    # Términos legales
    terms_and_conditions = models.TextField(
        blank=True,
        verbose_name='Términos y Condiciones',
        help_text='Términos legales que se incluyen en el contrato'
    )
    legal_clauses = models.JSONField(
        default=list,
        blank=True,
        verbose_name='Cláusulas Legales',
        help_text='Lista de cláusulas legales adicionales'
    )
    
    # Metadata
    description = models.TextField(
        blank=True,
        verbose_name='Descripción',
        help_text='Descripción de la plantilla y su uso'
    )
    version = models.CharField(
        max_length=20,
        default='1.0',
        verbose_name='Versión'
    )
    
    class Meta:
        verbose_name = 'Plantilla de Contrato'
        verbose_name_plural = 'Plantillas de Contrato'
        ordering = ['-is_default', 'name']
        unique_together = [['institution', 'code']]
        indexes = [
            models.Index(fields=['institution', 'is_active']),
            models.Index(fields=['institution', 'product']),
        ]
    
    def __str__(self):
        return f"{self.name} - {self.product.name}"
    
    def get_available_variables(self):
        """
        Retorna las variables disponibles para esta plantilla.
        Si no hay variables definidas, retorna el conjunto estándar.
        """
        if self.available_variables:
            return self.available_variables
        
        # Variables estándar disponibles en todos los contratos
        return [
            'institution_name',
            'institution_address',
            'institution_nit',
            'institution_phone',
            'institution_email',
            'borrower_name',
            'borrower_document',
            'borrower_address',
            'borrower_email',
            'borrower_phone',
            'contract_number',
            'contract_date',
            'start_date',
            'end_date',
            'principal_amount',
            'interest_rate',
            'term_months',
            'monthly_payment',
            'total_amount',
            'first_payment_date',
            'last_payment_date',
            'product_name',
            'product_description',
            # Variables de seguros
            'insurance_total_premium',
            'insurance_monthly_premium',
            'insurance_policies',
            'insurance_beneficiary',
        ]


class Contract(TenantModel):
    """
    Contrato de crédito generado a partir de una solicitud aprobada.
    
    Representa el documento legal formal que vincula a la institución financiera
    con el prestatario, estableciendo los términos y condiciones del crédito.
    """
    
    class Status(models.TextChoices):
        DRAFT = 'DRAFT', 'Borrador'
        PENDING_SIGNATURE = 'PENDING_SIGNATURE', 'Pendiente de Firma'
        PARTIALLY_SIGNED = 'PARTIALLY_SIGNED', 'Parcialmente Firmado'
        ACTIVE = 'ACTIVE', 'Activo'
        CANCELLED = 'CANCELLED', 'Cancelado'
        COMPLETED = 'COMPLETED', 'Completado'
        DEFAULTED = 'DEFAULTED', 'En Mora'
    
    # Relaciones principales
    loan_application = models.OneToOneField(
        'loans.LoanApplication',
        on_delete=models.PROTECT,
        related_name='contract',
        verbose_name='Solicitud de Crédito'
    )
    
    template = models.ForeignKey(
        'contracts.ContractTemplate',
        on_delete=models.PROTECT,
        related_name='contracts',
        verbose_name='Plantilla Utilizada'
    )
    
    # Datos del contrato
    contract_number = models.CharField(
        max_length=50,
        unique=True,
        verbose_name='Número de Contrato',
        help_text='Número único de identificación del contrato'
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
        verbose_name='Estado',
        db_index=True
    )
    
    # Términos financieros (snapshot de la aprobación)
    principal_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        verbose_name='Monto Principal'
    )
    interest_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0')), MaxValueValidator(Decimal('100'))],
        verbose_name='Tasa de Interés Anual (%)'
    )
    term_months = models.PositiveIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(360)],
        verbose_name='Plazo en Meses'
    )
    monthly_payment = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        verbose_name='Cuota Mensual'
    )
    total_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        verbose_name='Monto Total a Pagar',
        help_text='Capital + Intereses'
    )
    
    # Fechas importantes
    contract_date = models.DateField(
        null=True,
        blank=True,
        verbose_name='Fecha del Contrato',
        help_text='Fecha de generación del contrato'
    )
    start_date = models.DateField(
        null=True,
        blank=True,
        verbose_name='Fecha de Inicio',
        help_text='Fecha de inicio del crédito'
    )
    end_date = models.DateField(
        null=True,
        blank=True,
        verbose_name='Fecha de Finalización',
        help_text='Fecha estimada de finalización del crédito'
    )
    first_payment_date = models.DateField(
        null=True,
        blank=True,
        verbose_name='Fecha del Primer Pago',
        help_text='Fecha de vencimiento del primer pago'
    )
    
    # Documentos
    pdf_file = models.ForeignKey(
        'storage.FileResource',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='contracts_as_pdf',
        verbose_name='Archivo PDF del Contrato'
    )
    
    # Firma del prestatario
    borrower_signed_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Fecha de Firma del Prestatario'
    )
    borrower_signature_ip = models.GenericIPAddressField(
        null=True,
        blank=True,
        verbose_name='IP de Firma del Prestatario'
    )
    borrower_signature_data = models.TextField(
        blank=True,
        verbose_name='Datos de Firma del Prestatario',
        help_text='Hash o datos criptográficos de la firma'
    )
    
    # Metadata del contrato
    terms_and_conditions = models.TextField(
        verbose_name='Términos y Condiciones',
        help_text='Términos y condiciones específicos de este contrato'
    )
    special_clauses = models.JSONField(
        default=dict,
        blank=True,
        verbose_name='Cláusulas Especiales',
        help_text='Cláusulas adicionales específicas de este contrato'
    )
    
    # Control de versiones
    version = models.PositiveIntegerField(
        default=1,
        verbose_name='Versión',
        help_text='Versión del contrato (se incrementa si se regenera)'
    )
    
    # Usuarios responsables
    generated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='generated_contracts',
        verbose_name='Generado Por'
    )
    published_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='published_contracts',
        verbose_name='Publicado Por'
    )
    published_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Fecha de Publicación'
    )
    cancelled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='cancelled_contracts',
        verbose_name='Cancelado Por'
    )
    cancelled_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Fecha de Cancelación'
    )
    cancellation_reason = models.TextField(
        blank=True,
        verbose_name='Motivo de Cancelación'
    )
    
    # Notas
    notes = models.TextField(
        blank=True,
        verbose_name='Notas Internas'
    )
    
    class Meta:
        verbose_name = 'Contrato de Crédito'
        verbose_name_plural = 'Contratos de Crédito'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['institution', 'status']),
            models.Index(fields=['institution', 'loan_application']),
            models.Index(fields=['contract_number']),
            models.Index(fields=['contract_date']),
        ]
    
    def __str__(self):
        return f"{self.contract_number} - {self.loan_application.client.get_full_name()}"
    
    def save(self, *args, **kwargs):
        if not self.contract_number:
            self.contract_number = self.generate_contract_number()
        super().save(*args, **kwargs)
    
    def generate_contract_number(self):
        """Genera un número único de contrato"""
        from django.utils import timezone
        import random
        
        year = timezone.now().year
        # Contar contratos del año actual
        count = Contract.objects.filter(
            institution=self.institution,
            created_at__year=year
        ).count() + 1
        
        # Formato: CONT-INST-YEAR-COUNT-RANDOM
        random_suffix = random.randint(1000, 9999)
        return f"CONT-{self.institution.id}-{year}-{count:04d}-{random_suffix}"
    
    @property
    def is_signed_by_borrower(self):
        """Verifica si el prestatario ha firmado"""
        return self.borrower_signed_at is not None
    
    @property
    def requires_guarantor_signatures(self):
        """Verifica si el contrato requiere firmas de garantes"""
        return self.template.requires_guarantor_signature
    
    @property
    def all_signatures_complete(self):
        """Verifica si todas las firmas requeridas están completas"""
        # Verificar firma del prestatario
        if not self.is_signed_by_borrower:
            return False
        
        # Si requiere firmas de garantes, verificar
        if self.requires_guarantor_signatures:
            guarantor_signatures = self.signatures.filter(
                signer_type=ContractSignature.SignerType.GUARANTOR
            )
            
            # Obtener garantes de la solicitud
            guarantors_count = self.loan_application.guarantors.filter(
                status='APPROVED'
            ).count()
            
            if guarantor_signatures.count() < guarantors_count:
                return False
        
        return True
    
    @property
    def pending_signatures(self):
        """Retorna información sobre firmas pendientes"""
        pending = []
        
        if not self.is_signed_by_borrower:
            pending.append({
                'type': 'BORROWER',
                'name': self.loan_application.client.get_full_name(),
                'required': True
            })
        
        if self.requires_guarantor_signatures:
            signed_guarantors = self.signatures.filter(
                signer_type=ContractSignature.SignerType.GUARANTOR
            ).values_list('guarantor_id', flat=True)
            
            unsigned_guarantors = self.loan_application.guarantors.filter(
                status='APPROVED'
            ).exclude(id__in=signed_guarantors)
            
            for guarantor in unsigned_guarantors:
                pending.append({
                    'type': 'GUARANTOR',
                    'name': guarantor.full_name,
                    'required': True
                })
        
        return pending
    
    def can_be_signed(self):
        """Verifica si el contrato puede ser firmado"""
        return self.status in [
            self.Status.PENDING_SIGNATURE,
            self.Status.PARTIALLY_SIGNED
        ]
    
    def can_be_cancelled(self):
        """Verifica si el contrato puede ser cancelado"""
        return self.status in [
            self.Status.DRAFT,
            self.Status.PENDING_SIGNATURE,
            self.Status.PARTIALLY_SIGNED
        ]
    
    def update_status_after_signature(self):
        """
        Actualiza el estado del contrato después de una firma.
        Debe llamarse después de registrar una firma.
        """
        if self.all_signatures_complete:
            self.status = self.Status.ACTIVE
            self.save(update_fields=['status', 'updated_at'])
        elif self.is_signed_by_borrower:
            self.status = self.Status.PARTIALLY_SIGNED
            self.save(update_fields=['status', 'updated_at'])


class ContractSignature(TenantModel):
    """
    Registro de firmas digitales en un contrato.
    
    Almacena información detallada sobre cada firma realizada en el contrato,
    incluyendo datos de auditoría y verificación.
    """
    
    class SignerType(models.TextChoices):
        BORROWER = 'BORROWER', 'Prestatario'
        GUARANTOR = 'GUARANTOR', 'Garante'
        INSTITUTION = 'INSTITUTION', 'Institución'
    
    class SignatureMethod(models.TextChoices):
        DIGITAL = 'DIGITAL', 'Firma Digital Simple'
        BIOMETRIC = 'BIOMETRIC', 'Firma Biométrica'
        OTP = 'OTP', 'Verificación OTP'
        DOCUSIGN = 'DOCUSIGN', 'DocuSign'
        ADOBE_SIGN = 'ADOBE_SIGN', 'Adobe Sign'
    
    contract = models.ForeignKey(
        'contracts.Contract',
        on_delete=models.CASCADE,
        related_name='signatures',
        verbose_name='Contrato'
    )
    
    signer_type = models.CharField(
        max_length=20,
        choices=SignerType.choices,
        verbose_name='Tipo de Firmante'
    )
    
    # Referencia al firmante (puede ser usuario o garante)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='contract_signatures',
        verbose_name='Usuario Firmante'
    )
    
    guarantor = models.ForeignKey(
        'garantias.Guarantor',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='contract_signatures',
        verbose_name='Garante Firmante'
    )
    
    # Datos de la firma
    signed_at = models.DateTimeField(
        verbose_name='Fecha y Hora de Firma'
    )
    signature_method = models.CharField(
        max_length=50,
        choices=SignatureMethod.choices,
        default=SignatureMethod.DIGITAL,
        verbose_name='Método de Firma'
    )
    signature_data = models.TextField(
        verbose_name='Datos de la Firma',
        help_text='Hash criptográfico o datos de verificación de la firma'
    )
    
    # Datos de auditoría
    ip_address = models.GenericIPAddressField(
        verbose_name='Dirección IP'
    )
    device_info = models.JSONField(
        default=dict,
        blank=True,
        verbose_name='Información del Dispositivo',
        help_text='User-agent, sistema operativo, navegador, etc.'
    )
    geolocation = models.JSONField(
        default=dict,
        blank=True,
        verbose_name='Geolocalización',
        help_text='Datos de ubicación si están disponibles'
    )
    
    # Verificación adicional
    identity_verified = models.BooleanField(
        default=False,
        verbose_name='Identidad Verificada',
        help_text='Si se verificó la identidad antes de firmar'
    )
    verification_method = models.CharField(
        max_length=50,
        blank=True,
        verbose_name='Método de Verificación',
        help_text='Método usado para verificar identidad (2FA, biométrico, etc.)'
    )
    
    # Metadata
    notes = models.TextField(
        blank=True,
        verbose_name='Notas'
    )
    
    class Meta:
        verbose_name = 'Firma de Contrato'
        verbose_name_plural = 'Firmas de Contrato'
        ordering = ['signed_at']
        indexes = [
            models.Index(fields=['contract', 'signer_type']),
            models.Index(fields=['signed_at']),
        ]
    
    def __str__(self):
        signer_name = self.get_signer_name()
        return f"{self.get_signer_type_display()} - {signer_name} - {self.signed_at}"
    
    def get_signer_name(self):
        """Retorna el nombre del firmante"""
        if self.signer_type == self.SignerType.BORROWER and self.user:
            return self.user.get_full_name() or self.user.email
        elif self.signer_type == self.SignerType.GUARANTOR and self.guarantor:
            return self.guarantor.full_name
        elif self.signer_type == self.SignerType.INSTITUTION and self.user:
            return self.user.get_full_name() or self.user.email
        return 'Desconocido'
    
    def clean(self):
        """Validación del modelo"""
        from django.core.exceptions import ValidationError
        
        # Validar que se especifique el firmante correcto según el tipo
        if self.signer_type == self.SignerType.GUARANTOR and not self.guarantor:
            raise ValidationError({
                'guarantor': 'Debe especificar el garante para firmas de tipo GUARANTOR'
            })
        
        if self.signer_type in [self.SignerType.BORROWER, self.SignerType.INSTITUTION] and not self.user:
            raise ValidationError({
                'user': f'Debe especificar el usuario para firmas de tipo {self.signer_type}'
            })


class ContractAmortizationSchedule(TenantModel):
    """
    Tabla de amortización del contrato.
    
    Representa el plan de pagos del crédito, con cada cuota detallada
    incluyendo capital, intereses y saldo pendiente.
    """
    
    contract = models.ForeignKey(
        'contracts.Contract',
        on_delete=models.CASCADE,
        related_name='amortization_schedule',
        verbose_name='Contrato'
    )
    
    payment_number = models.PositiveIntegerField(
        verbose_name='Número de Cuota',
        help_text='Número secuencial de la cuota (1, 2, 3, ...)'
    )
    due_date = models.DateField(
        verbose_name='Fecha de Vencimiento'
    )
    
    # Montos de la cuota
    principal_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0'))],
        verbose_name='Monto de Capital'
    )
    interest_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0'))],
        verbose_name='Monto de Interés'
    )
    insurance_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0'))],
        verbose_name='Monto de Seguro'
    )
    total_payment = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0'))],
        verbose_name='Cuota Total',
        help_text='Capital + Interés + Seguro'
    )
    remaining_balance = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0'))],
        verbose_name='Saldo Pendiente',
        help_text='Saldo de capital después de esta cuota'
    )
    
    # Estado del pago
    is_paid = models.BooleanField(
        default=False,
        verbose_name='Pagado'
    )
    paid_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Fecha de Pago'
    )
    paid_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0'),
        validators=[MinValueValidator(Decimal('0'))],
        verbose_name='Monto Pagado'
    )
    
    # Referencia al pago (para futura integración con módulo de pagos)
    payment_reference = models.CharField(
        max_length=100,
        blank=True,
        verbose_name='Referencia de Pago'
    )
    
    # Notas
    notes = models.TextField(
        blank=True,
        verbose_name='Notas'
    )
    
    class Meta:
        verbose_name = 'Cuota de Amortización'
        verbose_name_plural = 'Tabla de Amortización'
        ordering = ['contract', 'payment_number']
        unique_together = [['contract', 'payment_number']]
        indexes = [
            models.Index(fields=['contract', 'payment_number']),
            models.Index(fields=['contract', 'due_date']),
            models.Index(fields=['contract', 'is_paid']),
        ]
    
    def __str__(self):
        return f"Cuota #{self.payment_number} - {self.contract.contract_number}"
    
    @property
    def is_overdue(self):
        """Verifica si la cuota está vencida"""
        from django.utils import timezone
        if self.is_paid:
            return False
        return timezone.now().date() > self.due_date
    
    @property
    def days_overdue(self):
        """Calcula los días de mora"""
        from django.utils import timezone
        if not self.is_overdue:
            return 0
        return (timezone.now().date() - self.due_date).days


class ContractDocument(TenantModel):
    """
    Documentos adicionales relacionados con el contrato.
    
    Permite adjuntar documentos complementarios al contrato principal,
    como anexos, addendums, documentos de garantía, etc.
    """
    
    class DocumentType(models.TextChoices):
        ADDENDUM = 'ADDENDUM', 'Addendum'
        ANNEX = 'ANNEX', 'Anexo'
        GUARANTEE = 'GUARANTEE', 'Documento de Garantía'
        INSURANCE = 'INSURANCE', 'Póliza de Seguro'
        AMENDMENT = 'AMENDMENT', 'Enmienda'
        OTHER = 'OTHER', 'Otro'
    
    contract = models.ForeignKey(
        'contracts.Contract',
        on_delete=models.CASCADE,
        related_name='additional_documents',
        verbose_name='Contrato'
    )
    
    document_type = models.CharField(
        max_length=20,
        choices=DocumentType.choices,
        verbose_name='Tipo de Documento'
    )
    
    title = models.CharField(
        max_length=200,
        verbose_name='Título'
    )
    
    description = models.TextField(
        blank=True,
        verbose_name='Descripción'
    )
    
    file = models.ForeignKey(
        'storage.FileResource',
        on_delete=models.PROTECT,
        related_name='contract_documents',
        verbose_name='Archivo'
    )
    
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='uploaded_contract_documents',
        verbose_name='Subido Por'
    )
    
    is_required = models.BooleanField(
        default=False,
        verbose_name='Requerido',
        help_text='Si es un documento obligatorio'
    )
    
    class Meta:
        verbose_name = 'Documento de Contrato'
        verbose_name_plural = 'Documentos de Contrato'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.title} - {self.contract.contract_number}"
