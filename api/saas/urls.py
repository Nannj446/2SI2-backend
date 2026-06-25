"""
URLs para gestión de suscripciones SaaS.
"""

from django.urls import path
from .views import (
    # Planes
    SubscriptionPlanListCreateAPIView,
    SubscriptionPlanDetailAPIView,
    # Suscripciones
    SubscriptionListCreateAPIView,
    SubscriptionDetailAPIView,
    ActivateSubscriptionAPIView,
    SuspendSubscriptionAPIView,
    CancelSubscriptionAPIView,
    MySubscriptionAPIView,
    ChangeMySubscriptionPlanAPIView,
    # Admin SaaS
    SaaSStatsAPIView,
    TenantListAPIView,
    TenantDetailAPIView,
    TenantToggleActiveAPIView,
    PermissionListAPIView,
    PermissionDetailAPIView,
    PermissionCreateAPIView,
    PermissionSyncAPIView,
    PermissionCoverageAPIView,
    SaaSUserListAPIView,
    SaaSRoleListAPIView,
    # Billing (Stripe) — BillingCancelSubscriptionAPIView tiene nombre distinto
    # para evitar conflicto con CancelSubscriptionAPIView del admin
    StripeWebhookAPIView,
    CreateCheckoutSessionAPIView,
    CreateCustomerPortalSessionAPIView,
    BillingCancelSubscriptionAPIView,
    ReactivateSubscriptionAPIView,
    InvoiceListAPIView,
    PaymentListAPIView,
    SyncPlanToStripeAPIView,
    VerifyCheckoutSessionAPIView,
    ApplyPendingChangesAPIView,
)

app_name = 'saas'

urlpatterns = [
    # ============================================================
    # PLANES DE SUSCRIPCIÓN
    # ============================================================
    path(
        'plans/',
        SubscriptionPlanListCreateAPIView.as_view(),
        name='plan-list-create'
    ),
    path(
        'plans/<int:id>/',
        SubscriptionPlanDetailAPIView.as_view(),
        name='plan-detail'
    ),
    
    # ============================================================
    # SUSCRIPCIONES
    # ============================================================
    path(
        'subscriptions/',
        SubscriptionListCreateAPIView.as_view(),
        name='subscription-list-create'
    ),
    path(
        'subscriptions/<int:id>/',
        SubscriptionDetailAPIView.as_view(),
        name='subscription-detail'
    ),
    path(
        'subscriptions/<int:id>/activate/',
        ActivateSubscriptionAPIView.as_view(),
        name='subscription-activate'
    ),
    path(
        'subscriptions/<int:id>/suspend/',
        SuspendSubscriptionAPIView.as_view(),
        name='subscription-suspend'
    ),
    path(
        'subscriptions/<int:id>/cancel/',
        CancelSubscriptionAPIView.as_view(),
        name='subscription-cancel'
    ),
    
    # ============================================================
    # MI SUSCRIPCIÓN (Para instituciones)
    # ============================================================
    path(
        'my-subscription/',
        MySubscriptionAPIView.as_view(),
        name='my-subscription'
    ),
    path(
        'my-subscription/change-plan/',
        ChangeMySubscriptionPlanAPIView.as_view(),
        name='change-my-subscription-plan'
    ),
    path(
        'subscriptions/current',
        MySubscriptionAPIView.as_view(),
        name='subscriptions-current'
    ),
    path(
        'subscriptions/change-plan',
        ChangeMySubscriptionPlanAPIView.as_view(),
        name='subscriptions-change-plan'
    ),
    path(
        'subscriptions/cancel',
        BillingCancelSubscriptionAPIView.as_view(),
        name='subscriptions-cancel'
    ),
    path(
        'subscriptions/reactivate',
        ReactivateSubscriptionAPIView.as_view(),
        name='subscriptions-reactivate'
    ),
    path(
        'subscriptions/apply-pending-changes',
        ApplyPendingChangesAPIView.as_view(),
        name='subscriptions-apply-pending-changes'
    ),
    
    # ============================================================
    # ADMINISTRACIÓN SAAS
    # ============================================================
    path(
        'stats/',
        SaaSStatsAPIView.as_view(),
        name='saas-stats'
    ),
    path(
        'tenants/',
        TenantListAPIView.as_view(),
        name='tenant-list'
    ),
    path(
        'tenants/<int:id>/',
        TenantDetailAPIView.as_view(),
        name='tenant-detail'
    ),
    path(
        'tenants/<int:id>/toggle-active/',
        TenantToggleActiveAPIView.as_view(),
        name='tenant-toggle-active'
    ),
    path(
        'permissions/',
        PermissionListAPIView.as_view(),
        name='permission-list'
    ),
    path(
        'permissions/<int:id>/',
        PermissionDetailAPIView.as_view(),
        name='permission-detail'
    ),
    path(
        'permissions/sync/',
        PermissionSyncAPIView.as_view(),
        name='permission-sync'
    ),
    path(
        'permissions/coverage/',
        PermissionCoverageAPIView.as_view(),
        name='permission-coverage'
    ),
    path(
        'users/',
        SaaSUserListAPIView.as_view(),
        name='saas-user-list'
    ),
    path(
        'roles/',
        SaaSRoleListAPIView.as_view(),
        name='saas-role-list'
    ),

    # ============================================================
    # BILLING (STRIPE)
    # ============================================================
    path(
        'billing/webhook/',
        StripeWebhookAPIView.as_view(),
        name='stripe-webhook'
    ),
    path(
        'billing/create-checkout-session/',
        CreateCheckoutSessionAPIView.as_view(),
        name='create-checkout-session'
    ),
    path(
        'billing/create-customer-portal-session/',
        CreateCustomerPortalSessionAPIView.as_view(),
        name='create-customer-portal-session'
    ),
    path(
        'billing/cancel/',
        BillingCancelSubscriptionAPIView.as_view(),
        name='billing-cancel'
    ),
    path(
        'billing/reactivate/',
        ReactivateSubscriptionAPIView.as_view(),
        name='billing-reactivate'
    ),
    path(
        'billing/invoices/',
        InvoiceListAPIView.as_view(),
        name='invoice-list'
    ),
    path(
        'billing/payments/',
        PaymentListAPIView.as_view(),
        name='payment-list'
    ),
    path(
        'billing/verify-payment/',
        VerifyCheckoutSessionAPIView.as_view(),
        name='verify-payment'
    ),

    # ============================================================
    # SINCRONIZACIÓN CON STRIPE
    # ============================================================
    path(
        'plans/<int:id>/sync-to-stripe/',
        SyncPlanToStripeAPIView.as_view(),
        name='sync-plan-to-stripe'
    ),
]
