"""
URLs para solicitudes de crédito
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .originacion.views import CreditApplicationViewSet
from .views.rule_viewsets import (
    TenantRuleSetViewSet,
    EligibilityRuleViewSet,
    CreditProductParameterViewSet,
    # DocumentRequirementViewSet,  # DEPRECATED: Eliminado
    WorkflowStageDefinitionViewSet,
    DecisionThresholdViewSet,
)
from .views.document_viewsets import (
    ClientDocumentViewSet,
    StaffDocumentViewSet,
)
from .views.timeline_viewsets import (
    ClientApplicationViewSet,
)
from .views.catalog_viewsets import (
    DocumentTypeViewSet,
    ProductTypeViewSet,
    PaymentFrequencyViewSet,
    AmortizationSystemViewSet,
    CurrencyViewSet,
)
from .views.approval_viewsets import (
    WorkflowExecutionViewSet,
    ApprovalQueueViewSet,
    ApprovalDecisionViewSet,
    EscalationViewSet,
    WorkflowMetricsViewSet,
)
# SP3: Créditos Activos y Pagos
from .views.active_viewsets import ActiveCreditViewSet
from .views.payment_viewsets import CreditPaymentViewSet
from .views.client_active_viewsets import MyActiveCreditsViewSet
from .views.stripe_webhook_views import StripeWebhookViewSet
# SP4: Solicitudes de Apoyo de Pago
from .views.support_request_viewsets import SupportRequestViewSet
# Stripe return pages (mobile)
from .views.stripe_return_views import stripe_success, stripe_cancel
from .views.rejection_viewsets import (
    RejectionReasonViewSet,
)

app_name = 'loans'

# Router principal
router = DefaultRouter()

# CU-11: Originación de créditos (ViewSet existente)
router.register(r'credit-applications', CreditApplicationViewSet, basename='credit-application')

# CU-09: Administración de reglas
router.register(r'rule-sets', TenantRuleSetViewSet, basename='rule-set')
router.register(r'eligibility-rules', EligibilityRuleViewSet, basename='eligibility-rule')
router.register(r'product-parameters', CreditProductParameterViewSet, basename='product-parameter')
# router.register(r'document-requirements', DocumentRequirementViewSet, basename='document-requirement')  # DEPRECATED: Eliminado
router.register(r'workflow-stages', WorkflowStageDefinitionViewSet, basename='workflow-stage')
router.register(r'decision-thresholds', DecisionThresholdViewSet, basename='decision-threshold')

# CU-12: Gestión documental
router.register(r'my-documents', ClientDocumentViewSet, basename='my-document')
router.register(r'staff/documents', StaffDocumentViewSet, basename='staff-document')

# CU-07: Timeline y seguimiento
router.register(r'my-applications', ClientApplicationViewSet, basename='my-application')

# CU-18: Créditos activos
# router.register(r'my-active-credits', ActiveCreditsViewSet, basename='my-active-credit')

# CU-16: Sistema de aprobaciones y workflows
router.register(r'workflow-executions', WorkflowExecutionViewSet, basename='workflow-execution')
router.register(r'workflow/metrics', WorkflowMetricsViewSet, basename='workflow-metrics')
router.register(r'approvals/queue', ApprovalQueueViewSet, basename='approval-queue')
router.register(r'approvals/decisions', ApprovalDecisionViewSet, basename='approval-decision')
router.register(r'approvals/escalations', EscalationViewSet, basename='escalation')

# SP3-99: Motivos de rechazo parametrizados
router.register(r'rejection-reasons', RejectionReasonViewSet, basename='rejection-reason')

# Catálogos Centralizados
router.register(r'catalogs/document-types', DocumentTypeViewSet, basename='document-type')
router.register(r'catalogs/product-types', ProductTypeViewSet, basename='product-type')
router.register(r'catalogs/payment-frequencies', PaymentFrequencyViewSet, basename='payment-frequency')
router.register(r'catalogs/amortization-systems', AmortizationSystemViewSet, basename='amortization-system')
router.register(r'catalogs/currencies', CurrencyViewSet, basename='currency')

# SP3: Créditos Activos, Pagos, Cliente Mobile, Stripe y Solicitudes de Apoyo
router.register(r'active-credits', ActiveCreditViewSet, basename='active-credit')
router.register(r'payments', CreditPaymentViewSet, basename='payment')
router.register(r'my-active-credits', MyActiveCreditsViewSet, basename='my-active-credit')
router.register(r'stripe', StripeWebhookViewSet, basename='stripe')
router.register(r'support-requests', SupportRequestViewSet, basename='support-request')

urlpatterns = [
    # URLs del router
    path('', include(router.urls)),

    # Stripe return pages (mobile)
    path('stripe/success/', stripe_success, name='stripe-success'),
    path('stripe/cancel/', stripe_cancel, name='stripe-cancel'),

    # Rutas legacy (compatibilidad) - comentadas hasta que se necesiten
    # path('legacy/', views.LoanApplicationListCreateAPIView.as_view(), name='loan-list-create'),
    # path('legacy/<int:pk>/', views.LoanApplicationDetailAPIView.as_view(), name='loan-detail'),
]
