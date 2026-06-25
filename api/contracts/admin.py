"""
Configuración del admin de Django para contratos
"""

from django.contrib import admin
from api.contracts.models import (
    Contract,
    ContractTemplate,
    ContractSignature,
    ContractAmortizationSchedule,
    ContractDocument
)


@admin.register(ContractTemplate)
class ContractTemplateAdmin(admin.ModelAdmin):
    """Admin para plantillas de contratos"""
    
    list_display = [
        'name',
        'code',
        'product',
        'is_active',
        'is_default',
        'requires_guarantor_signature',
        'version',
        'created_at',
    ]
    list_filter = [
        'is_active',
        'is_default',
        'requires_guarantor_signature',
        'created_at',
    ]
    search_fields = [
        'name',
        'code',
        'description',
    ]
    readonly_fields = [
        'created_at',
        'updated_at',
    ]
    fieldsets = (
        ('Información Básica', {
            'fields': (
                'name',
                'code',
                'product',
                'description',
                'version',
            )
        }),
        ('Configuración', {
            'fields': (
                'is_active',
                'is_default',
                'requires_guarantor_signature',
            )
        }),
        ('Contenido', {
            'fields': (
                'template_content',
                'available_variables',
            )
        }),
        ('Términos Legales', {
            'fields': (
                'terms_and_conditions',
                'legal_clauses',
            )
        }),
        ('Metadata', {
            'fields': (
                'created_at',
                'updated_at',
            )
        }),
    )


class ContractSignatureInline(admin.TabularInline):
    """Inline para firmas de contrato"""
    model = ContractSignature
    extra = 0
    readonly_fields = [
        'signer_type',
        'user',
        'guarantor',
        'signed_at',
        'signature_method',
        'ip_address',
        'identity_verified',
    ]
    can_delete = False


class ContractAmortizationScheduleInline(admin.TabularInline):
    """Inline para tabla de amortización"""
    model = ContractAmortizationSchedule
    extra = 0
    readonly_fields = [
        'payment_number',
        'due_date',
        'principal_amount',
        'interest_amount',
        'total_payment',
        'remaining_balance',
        'is_paid',
        'paid_at',
    ]
    can_delete = False
    
    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Contract)
class ContractAdmin(admin.ModelAdmin):
    """Admin para contratos"""
    
    list_display = [
        'contract_number',
        'loan_application',
        'status',
        'principal_amount',
        'term_months',
        'contract_date',
        'is_signed_by_borrower',
        'all_signatures_complete',
        'created_at',
    ]
    list_filter = [
        'status',
        'contract_date',
        'created_at',
    ]
    search_fields = [
        'contract_number',
        'loan_application__application_number',
        'loan_application__client__full_name',
    ]
    readonly_fields = [
        'contract_number',
        'is_signed_by_borrower',
        'requires_guarantor_signatures',
        'all_signatures_complete',
        'created_at',
        'updated_at',
    ]
    inlines = [
        ContractSignatureInline,
        ContractAmortizationScheduleInline,
    ]
    fieldsets = (
        ('Información Básica', {
            'fields': (
                'contract_number',
                'loan_application',
                'template',
                'status',
                'version',
            )
        }),
        ('Términos Financieros', {
            'fields': (
                'principal_amount',
                'interest_rate',
                'term_months',
                'monthly_payment',
                'total_amount',
            )
        }),
        ('Fechas', {
            'fields': (
                'contract_date',
                'start_date',
                'end_date',
                'first_payment_date',
            )
        }),
        ('Documentos', {
            'fields': (
                'pdf_file',
            )
        }),
        ('Firma del Prestatario', {
            'fields': (
                'borrower_signed_at',
                'borrower_signature_ip',
                'borrower_signature_data',
                'is_signed_by_borrower',
            )
        }),
        ('Estado de Firmas', {
            'fields': (
                'requires_guarantor_signatures',
                'all_signatures_complete',
            )
        }),
        ('Términos y Condiciones', {
            'fields': (
                'terms_and_conditions',
                'special_clauses',
            ),
            'classes': ('collapse',),
        }),
        ('Control', {
            'fields': (
                'generated_by',
                'published_by',
                'published_at',
                'cancelled_by',
                'cancelled_at',
                'cancellation_reason',
                'notes',
            )
        }),
        ('Metadata', {
            'fields': (
                'created_at',
                'updated_at',
            )
        }),
    )
    
    def has_delete_permission(self, request, obj=None):
        """Solo permitir eliminar contratos en DRAFT"""
        if obj and obj.status != Contract.Status.DRAFT:
            return False
        return super().has_delete_permission(request, obj)


@admin.register(ContractSignature)
class ContractSignatureAdmin(admin.ModelAdmin):
    """Admin para firmas de contratos"""
    
    list_display = [
        'contract',
        'signer_type',
        'get_signer_name',
        'signed_at',
        'signature_method',
        'ip_address',
        'identity_verified',
    ]
    list_filter = [
        'signer_type',
        'signature_method',
        'identity_verified',
        'signed_at',
    ]
    search_fields = [
        'contract__contract_number',
        'user__email',
        'guarantor__full_name',
    ]
    readonly_fields = [
        'contract',
        'signer_type',
        'user',
        'guarantor',
        'signed_at',
        'signature_method',
        'signature_data',
        'ip_address',
        'device_info',
        'geolocation',
        'identity_verified',
        'verification_method',
        'created_at',
    ]
    
    def has_add_permission(self, request):
        """No permitir agregar firmas manualmente"""
        return False
    
    def has_delete_permission(self, request, obj=None):
        """No permitir eliminar firmas"""
        return False


@admin.register(ContractAmortizationSchedule)
class ContractAmortizationScheduleAdmin(admin.ModelAdmin):
    """Admin para tabla de amortización"""
    
    list_display = [
        'contract',
        'payment_number',
        'due_date',
        'total_payment',
        'remaining_balance',
        'is_paid',
        'paid_at',
    ]
    list_filter = [
        'is_paid',
        'due_date',
    ]
    search_fields = [
        'contract__contract_number',
    ]
    readonly_fields = [
        'contract',
        'payment_number',
        'due_date',
        'principal_amount',
        'interest_amount',
        'total_payment',
        'remaining_balance',
        'created_at',
        'updated_at',
    ]
    
    def has_add_permission(self, request):
        """No permitir agregar cuotas manualmente"""
        return False


@admin.register(ContractDocument)
class ContractDocumentAdmin(admin.ModelAdmin):
    """Admin para documentos adicionales de contratos"""
    
    list_display = [
        'contract',
        'document_type',
        'title',
        'uploaded_by',
        'is_required',
        'created_at',
    ]
    list_filter = [
        'document_type',
        'is_required',
        'created_at',
    ]
    search_fields = [
        'contract__contract_number',
        'title',
        'description',
    ]
    readonly_fields = [
        'uploaded_by',
        'created_at',
        'updated_at',
    ]
