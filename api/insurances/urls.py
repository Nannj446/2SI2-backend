"""
URLs para Gestión de Seguros.
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    InsurerViewSet, InsuranceViewSet, InsuranceCoverageViewSet,
    ProductInsuranceListView, ProductInsuranceDetailView, ProductInsuranceCalculateView,
    CreditInsuranceViewSet, CreditInsuranceSummaryView,
    CreditInsuranceMarkExpiringView, CreditInsuranceSuspendView, CreditInsuranceCancelView
)
from .views_reports import (
    InsuranceSummaryReportView,
    InsuranceExpiringSoonReportView,
    InsuranceExpiredReportView,
    InsuranceDistributionByTypeView,
    InsurancePremiumsByMonthView,
    InsuranceByInsurerView,
    CreditsWithoutInsuranceView,
)


router = DefaultRouter()
router.register(r'insurers', InsurerViewSet, basename='insurer')
router.register(r'insurances', InsuranceViewSet, basename='insurance')

urlpatterns = [
    path('', include(router.urls)),
    path(
        'insurances/<int:insurance_pk>/coverages/',
        InsuranceCoverageViewSet.as_view({'get': 'list', 'post': 'create'}),
        name='insurance-coverages-list'
    ),
    path(
        'insurances/<int:insurance_pk>/coverages/<int:pk>/',
        InsuranceCoverageViewSet.as_view({
            'get': 'retrieve',
            'put': 'update',
            'patch': 'partial_update',
            'delete': 'destroy'
        }),
        name='insurance-coverage-detail'
    ),
    path(
        'insurances/calculate-premium/',
        InsuranceViewSet.as_view({'post': 'calculate_premium'}),
        name='insurance-calculate-premium'
    ),
    path(
        'active-credits/<int:credit_pk>/insurances/',
        CreditInsuranceViewSet.as_view({
            'get': 'list',
            'post': 'create'
        }),
        name='credit-insurance-list'
    ),
    path(
        'active-credits/<int:credit_pk>/insurances/<int:pk>/',
        CreditInsuranceViewSet.as_view({
            'get': 'retrieve',
            'put': 'update',
            'patch': 'partial_update',
            'delete': 'destroy'
        }),
        name='credit-insurance-detail'
    ),
    path(
        'active-credits/<int:credit_pk>/insurances/<int:pk>/mark-expiring/',
        CreditInsuranceMarkExpiringView.as_view(),
        name='credit-insurance-mark-expiring'
    ),
    path(
        'active-credits/<int:credit_pk>/insurances/<int:pk>/suspend/',
        CreditInsuranceSuspendView.as_view(),
        name='credit-insurance-suspend'
    ),
    path(
        'active-credits/<int:credit_pk>/insurances/<int:pk>/cancel/',
        CreditInsuranceCancelView.as_view(),
        name='credit-insurance-cancel'
    ),
    path(
        'active-credits/<int:credit_pk>/insurances/summary/',
        CreditInsuranceSummaryView.as_view(),
        name='credit-insurance-summary'
    ),
    path(
        'products/<int:product_pk>/insurances/',
        ProductInsuranceListView.as_view(),
        name='product-insurance-list'
    ),
    path(
        'products/<int:product_pk>/insurances/<int:pk>/',
        ProductInsuranceDetailView.as_view(),
        name='product-insurance-detail'
    ),
    path(
        'products/<int:product_pk>/insurances/calculate/',
        ProductInsuranceCalculateView.as_view(),
        name='product-insurance-calculate'
    ),
    # Report endpoints
    path(
        'reports/insurances/summary/',
        InsuranceSummaryReportView.as_view(),
        name='insurance-summary-report'
    ),
    path(
        'reports/insurances/expiring-soon/',
        InsuranceExpiringSoonReportView.as_view(),
        name='insurance-expiring-soon-report'
    ),
    path(
        'reports/insurances/expired/',
        InsuranceExpiredReportView.as_view(),
        name='insurance-expired-report'
    ),
    path(
        'reports/insurances/distribution-by-type/',
        InsuranceDistributionByTypeView.as_view(),
        name='insurance-distribution-report'
    ),
    path(
        'reports/insurances/premiums-by-month/',
        InsurancePremiumsByMonthView.as_view(),
        name='insurance-premiums-report'
    ),
    path(
        'reports/insurances/by-insurer/',
        InsuranceByInsurerView.as_view(),
        name='insurance-by-insurer-report'
    ),
    path(
        'reports/credits-without-insurance/',
        CreditsWithoutInsuranceView.as_view(),
        name='credits-without-insurance-report'
    ),
]
