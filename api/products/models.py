"""
Modelos para gestión de productos crediticios (REFACTORIZADO).

Los productos ahora son simples contenedores de información básica y marketing.
La configuración técnica (montos, tasas, plazos, etc.) está en CreditProductParameter
dentro de TenantRuleSet.
"""

from django.db import models
from api.core.models import TenantModel, TimeStampedModel


class CreditProduct(TenantModel, TimeStampedModel):
    """
    Modelo de Producto Crediticio (REFACTORIZADO).
    
    Ahora incluye relaciones directas con:
    - Conjunto de Reglas (RuleSet)
    - Documentos Requeridos (M2M con DocumentType)
    - Parámetros (a través de CreditProductParameter)
    - Workflow (a través de WorkflowStageDefinition)
    - Scoring (a través de DecisionThreshold)
    
    Flujo:
    1. Admin crea/edita producto y selecciona:
       - Conjunto de Reglas
       - Tipo de Producto
       - Documentos Requeridos
       - Parámetros
       - Workflow
       - Scoring
    2. Al seleccionar un Conjunto de Reglas, se filtran las opciones disponibles
    3. Los parámetros técnicos se vinculan al producto
    """
    
    # ============================================================
    # INFORMACIÓN BÁSICA
    # ============================================================
    name = models.CharField(
        max_length=200,
        verbose_name='Nombre del Producto'
    )
    
    code = models.CharField(
        max_length=50,
        unique=True,
        verbose_name='Código del Producto',
        help_text='Código único identificador del producto'
    )
    
    product_type = models.ForeignKey(
        'loans.ProductType',
        on_delete=models.PROTECT,
        related_name='products',
        verbose_name='Tipo de Producto',
        help_text='Tipo de producto desde catálogo centralizado'
    )
    
    description = models.TextField(
        verbose_name='Descripción',
        help_text='Descripción detallada del producto crediticio'
    )
    
    # ============================================================
    # RELACIÓN CON CONJUNTO DE REGLAS
    # ============================================================
    rule_set = models.ForeignKey(
        'loans.TenantRuleSet',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='credit_products',
        verbose_name='Conjunto de Reglas',
        help_text='Conjunto de reglas asociado a este producto'
    )
    
    # ============================================================
    # CONFIGURACIÓN ESPECÍFICA DEL PRODUCTO
    # ============================================================
    # El producto puede seleccionar configuraciones específicas del rule_set
    
    selected_parameter = models.ForeignKey(
        'loans.CreditProductParameter',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='products_using',
        verbose_name='Parámetro Seleccionado',
        help_text='Parámetro específico del conjunto de reglas a usar'
    )
    
    selected_eligibility_rules = models.ManyToManyField(
        'loans.EligibilityRule',
        blank=True,
        related_name='products_using',
        verbose_name='Reglas de Elegibilidad',
        help_text='Reglas de elegibilidad específicas a aplicar'
    )
    
    selected_threshold = models.ForeignKey(
        'loans.DecisionThreshold',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='products_using',
        verbose_name='Umbral de Decisión',
        help_text='Umbral de scoring/decisión a usar'
    )
    
    # ============================================================
    # DOCUMENTOS REQUERIDOS (M2M)
    # ============================================================
    required_documents = models.ManyToManyField(
        'loans.DocumentType',
        through='ProductDocumentRequirement',
        related_name='products_requiring',
        verbose_name='Documentos Requeridos',
        help_text='Documentos que serán requeridos para este producto'
    )
    
    # ============================================================
    # ESTADO
    # ============================================================
    is_active = models.BooleanField(
        default=True,
        verbose_name='Activo',
        help_text='Indica si el producto está disponible para solicitudes',
        db_index=True
    )
    
    display_order = models.IntegerField(
        default=0,
        verbose_name='Orden de Visualización',
        help_text='Orden en que se muestra el producto (menor primero)'
    )
    
    # ============================================================
    # INFORMACIÓN DE MARKETING
    # ============================================================
    target_audience = models.TextField(
        blank=True,
        verbose_name='Público Objetivo',
        help_text='Descripción del perfil de cliente ideal'
    )
    
    benefits = models.JSONField(
        default=list,
        blank=True,
        verbose_name='Beneficios',
        help_text='Lista de beneficios del producto'
    )
    
    terms_and_conditions = models.TextField(
        blank=True,
        verbose_name='Términos y Condiciones'
    )
    
    # ============================================================
    # METADATA PARA UI
    # ============================================================
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
    
    class Meta:
        verbose_name = 'Producto Crediticio'
        verbose_name_plural = 'Productos Crediticios'
        ordering = ['display_order', 'name']
        indexes = [
            models.Index(fields=['institution', 'is_active']),
            models.Index(fields=['product_type']),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.code})"
    
    # ============================================================
    # MÉTODOS DE ACCESO A CONFIGURACIÓN
    # ============================================================
    def get_parameters(self):
        """
        Obtiene los parámetros del producto desde el conjunto de reglas asociado.
        
        Returns:
            CreditProductParameter o None si no existe
        """
        if not self.rule_set:
            return None
        
        from api.loans.models_rules import CreditProductParameter
        
        try:
            return CreditProductParameter.objects.get(
                rule_set=self.rule_set
            )
        except CreditProductParameter.DoesNotExist:
            return None
    
    def get_active_parameters(self):
        """
        DEPRECATED: Usar get_parameters() en su lugar.
        Mantiene compatibilidad con código existente.
        """
        return self.get_parameters()
    
    def get_documents(self):
        """
        Obtiene los documentos requeridos configurados para este producto.
        
        Returns:
            QuerySet de ProductDocumentRequirement
        """
        return self.document_requirements_config.select_related('document_type').all()
    
    def get_active_documents(self):
        """
        DEPRECATED: Usar get_documents() en su lugar.
        Mantiene compatibilidad con código existente.
        """
        return self.get_documents()
    
    def get_workflow_stages(self):
        """
        Obtiene las etapas de workflow del conjunto de reglas asociado.
        
        Returns:
            QuerySet de WorkflowStageDefinition
        """
        if not self.rule_set:
            from api.loans.models_rules import WorkflowStageDefinition
            return WorkflowStageDefinition.objects.none()
        
        return self.rule_set.workflow_stages.order_by('stage_order')
    
    def get_active_workflow_stages(self):
        """
        DEPRECATED: Usar get_workflow_stages() en su lugar.
        Mantiene compatibilidad con código existente.
        """
        return self.get_workflow_stages()
    
    # ============================================================
    # MÉTODOS DE VALIDACIÓN (usan parámetros del producto)
    # ============================================================
    def is_amount_valid(self, amount):
        """
        Verifica si el monto está dentro del rango permitido.
        
        Args:
            amount: Monto a validar
            
        Returns:
            bool: True si es válido
        """
        params = self.get_parameters()
        if not params:
            return False
        return params.min_amount <= amount <= params.max_amount
    
    def is_term_valid(self, term_months):
        """
        Verifica si el plazo está dentro del rango permitido.
        
        Args:
            term_months: Plazo en meses a validar
            
        Returns:
            bool: True si es válido
        """
        params = self.get_parameters()
        if not params:
            return False
        return params.min_term_months <= term_months <= params.max_term_months


class ProductDocumentRequirement(TenantModel, TimeStampedModel):
    """
    Tabla intermedia para la relación M2M entre CreditProduct y DocumentType.
    
    Permite configurar qué documentos son requeridos para cada producto
    y si son obligatorios u opcionales.
    """
    
    product = models.ForeignKey(
        CreditProduct,
        on_delete=models.CASCADE,
        related_name='document_requirements_config',
        verbose_name='Producto'
    )
    
    document_type = models.ForeignKey(
        'loans.DocumentType',
        on_delete=models.CASCADE,
        related_name='product_requirements_config',
        verbose_name='Tipo de Documento'
    )
    
    is_mandatory = models.BooleanField(
        default=True,
        verbose_name='Obligatorio',
        help_text='Si el documento es obligatorio para este producto'
    )
    
    display_order = models.IntegerField(
        default=0,
        verbose_name='Orden de Visualización'
    )
    
    max_validity_days = models.IntegerField(
        null=True,
        blank=True,
        verbose_name='Vigencia Máxima (días)',
        help_text='Sobrescribe el valor por defecto del DocumentType'
    )
    
    allowed_formats = models.JSONField(
        default=list,
        blank=True,
        verbose_name='Formatos Permitidos',
        help_text='Sobrescribe el valor por defecto del DocumentType'
    )
    
    max_file_size_mb = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name='Tamaño Máximo (MB)',
        help_text='Sobrescribe el valor por defecto del DocumentType'
    )
    
    class Meta:
        verbose_name = 'Documento Requerido del Producto'
        verbose_name_plural = 'Documentos Requeridos del Producto'
        ordering = ['display_order', 'document_type__name']
        constraints = [
            models.UniqueConstraint(
                fields=['product', 'document_type'],
                name='unique_document_per_product'
            )
        ]
    
    def __str__(self):
        return f"{self.document_type.name} - {self.product.name}"
    
    def get_allowed_formats(self):
        """Obtiene formatos permitidos con fallback a DocumentType"""
        if self.allowed_formats:
            return self.allowed_formats
        return self.document_type.default_formats
    
    def get_max_file_size_mb(self):
        """Obtiene tamaño máximo con fallback a DocumentType"""
        if self.max_file_size_mb is not None:
            return self.max_file_size_mb
        return self.document_type.default_max_size_mb
    
    def get_max_validity_days(self):
        """Obtiene validez máxima con fallback a DocumentType"""
        if self.max_validity_days is not None:
            return self.max_validity_days
        return self.document_type.default_validity_days


class ProductRequirement(TenantModel, TimeStampedModel):
    """
    Requisitos específicos adicionales para un producto crediticio.
    """
    
    product = models.ForeignKey(
        CreditProduct,
        on_delete=models.CASCADE,
        related_name='additional_requirements',
        verbose_name='Producto'
    )
    
    requirement_name = models.CharField(
        max_length=200,
        verbose_name='Nombre del Requisito'
    )
    
    description = models.TextField(
        verbose_name='Descripción'
    )
    
    is_mandatory = models.BooleanField(
        default=True,
        verbose_name='Obligatorio'
    )
    
    display_order = models.IntegerField(
        default=0,
        verbose_name='Orden'
    )
    
    class Meta:
        verbose_name = 'Requisito de Producto'
        verbose_name_plural = 'Requisitos de Productos'
        ordering = ['display_order', 'requirement_name']
    
    def __str__(self):
        return f"{self.requirement_name} - {self.product.name}"
