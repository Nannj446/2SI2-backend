"""
URLs para el módulo de contratos
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from api.contracts import views

# Router para ViewSets
router = DefaultRouter()
router.register(r'contracts', views.ContractViewSet, basename='contract')
router.register(r'contract-templates', views.ContractTemplateViewSet, basename='contracttemplate')
router.register(
    r'contract-amortization',
    views.ContractAmortizationScheduleViewSet,
    basename='contractamortization'
)

app_name = 'contracts'

urlpatterns = [
    path('', include(router.urls)),
]
