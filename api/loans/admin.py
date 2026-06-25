from django.contrib import admin
from .models import LoanApplication, LoanApplicationDocument, LoanApplicationComment
from .models_rejection import RejectionReason
from .models_scoring import CreditEvaluation, CreditBureauQuery, ModelRegistry
from .models_active import (
    ActiveCredit, CreditInstallment, CreditPayment,
    CreditPaymentAllocation, CreditGracePeriod,
    CreditRestructuring, CreditStatusHistory,
)


@admin.register(LoanApplication)
class LoanApplicationAdmin(admin.ModelAdmin):
    list_display = ['application_number', 'client', 'product', 'requested_amount', 'status', 'created_at']
    list_filter = ['status', 'risk_level', 'created_at', 'submitted_at']
    search_fields = ['application_number', 'client__first_name', 'client__last_name', 'client__document_number']
    readonly_fields = ['application_number', 'created_at', 'updated_at']
    
    fieldsets = (
        ('Información Básica', {
            'fields': ('application_number', 'client', 'product', 'institution')
        }),
        ('Detalles de la Solicitud', {
            'fields': ('requested_amount', 'term_months', 'purpose', 'status')
        }),
        ('Evaluación', {
            'fields': ('credit_score', 'risk_level', 'debt_to_income_ratio')
        }),
        ('Términos Aprobados', {
            'fields': ('approved_amount', 'approved_term_months', 'approved_interest_rate', 'monthly_payment')
        }),
        ('Fechas', {
            'fields': ('submitted_at', 'reviewed_at', 'approved_at', 'rejected_at', 'disbursed_at')
        }),
        ('Responsables', {
            'fields': ('reviewed_by', 'approved_by')
        }),
        ('Notas', {
            'fields': ('notes', 'rejection_reason')
        }),
    )


@admin.register(LoanApplicationDocument)
class LoanApplicationDocumentAdmin(admin.ModelAdmin):
    list_display = ['application', 'document_type', 'file_name', 'is_verified', 'created_at']
    list_filter = ['document_type', 'is_verified', 'created_at']
    search_fields = ['application__application_number', 'file_name']


@admin.register(LoanApplicationComment)
class LoanApplicationCommentAdmin(admin.ModelAdmin):
    list_display = ['application', 'user', 'is_internal', 'created_at']
    list_filter = ['is_internal', 'created_at']
    search_fields = ['application__application_number', 'comment']


@admin.register(RejectionReason)
class RejectionReasonAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'category', 'is_active', 'display_order', 'requires_notes']
    list_filter = ['category', 'is_active']
    search_fields = ['name', 'code', 'description']
    ordering = ['display_order', 'name']
    
    fieldsets = (
        ('Información Básica', {
            'fields': ('code', 'name', 'description', 'category')
        }),
        ('Configuración', {
            'fields': ('is_active', 'display_order', 'requires_notes')
        }),
    )
@admin.register(CreditEvaluation)
class CreditEvaluationAdmin(admin.ModelAdmin):
    list_display = [
        'application', 'score_weighted', 'auto_decision',
        'status', 'evaluated_at'
    ]
    list_filter = ['status', 'auto_decision']
    search_fields = [
        'application__application_number',
        'application__client__first_name',
        'application__client__last_name'
    ]
    readonly_fields = [
        'evaluated_at', 'evaluation_time_ms', 'model_version'
    ]


@admin.register(CreditBureauQuery)
class CreditBureauQueryAdmin(admin.ModelAdmin):
    list_display = [
        'application', 'provider', 'status',
        'score_external', 'queried_at'
    ]
    list_filter = ['provider', 'status']
    search_fields = ['application__application_number']


@admin.register(ModelRegistry)
class ModelRegistryAdmin(admin.ModelAdmin):
    list_display = [
        'version', 'algorithm', 'status',
        'is_active', 'training_date'
    ]
    list_filter = ['status', 'is_active']
    search_fields = ['version', 'description']


# SP3: Créditos Activos y Pagos

@admin.register(ActiveCredit)
class ActiveCreditAdmin(admin.ModelAdmin):
    list_display = [
        'credit_number', 'client', 'product', 'approved_amount',
        'current_balance', 'status', 'next_due_date', 'days_in_arrears'
    ]
    list_filter = ['status', 'amortization_system', 'payment_frequency', 'currency']
    search_fields = [
        'credit_number',
        'client__first_name', 'client__last_name', 'client__document_number',
    ]
    readonly_fields = ['credit_number', 'created_at', 'updated_at']
    date_hierarchy = 'disbursement_date'


@admin.register(CreditInstallment)
class CreditInstallmentAdmin(admin.ModelAdmin):
    list_display = [
        'active_credit', 'installment_number', 'due_date',
        'total_amount', 'paid_amount', 'status', 'days_overdue'
    ]
    list_filter = ['status']
    search_fields = ['active_credit__credit_number']
    date_hierarchy = 'due_date'


@admin.register(CreditPayment)
class CreditPaymentAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'active_credit', 'amount', 'payment_date',
        'channel', 'method', 'status'
    ]
    list_filter = ['channel', 'status', 'method']
    search_fields = [
        'active_credit__credit_number',
        'reference_number', 'provider_payment_id'
    ]
    date_hierarchy = 'payment_date'


@admin.register(CreditPaymentAllocation)
class CreditPaymentAllocationAdmin(admin.ModelAdmin):
    list_display = [
        'payment', 'installment', 'amount_applied',
        'principal_covered', 'interest_covered'
    ]
    search_fields = ['payment__active_credit__credit_number']


@admin.register(CreditGracePeriod)
class CreditGracePeriodAdmin(admin.ModelAdmin):
    list_display = [
        'active_credit', 'grace_type', 'start_date',
        'end_date', 'is_active'
    ]
    list_filter = ['grace_type', 'is_active']
    search_fields = ['active_credit__credit_number']


@admin.register(CreditRestructuring)
class CreditRestructuringAdmin(admin.ModelAdmin):
    list_display = [
        'active_credit', 'new_interest_rate', 'new_term_periods',
        'is_active', 'applied_at'
    ]
    list_filter = ['is_active']
    search_fields = ['active_credit__credit_number']


@admin.register(CreditStatusHistory)
class CreditStatusHistoryAdmin(admin.ModelAdmin):
    list_display = [
        'active_credit', 'previous_status', 'new_status',
        'changed_by', 'created_at'
    ]
    search_fields = ['active_credit__credit_number']
