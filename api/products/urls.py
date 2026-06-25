"""
URLs para gestión de productos crediticios.
"""

from django.urls import path
from api.products.views import (
    CreditProductListCreateAPIView,
    CreditProductDetailAPIView,
    CreditProductParametersAPIView,
    CreditProductCalculateAPIView,
    CreditProductRangesAPIView,
    CreditProductWithParametersAPIView,
)

app_name = 'products'

urlpatterns = [
    # Gestión de productos
    path('', CreditProductListCreateAPIView.as_view(), name='product-list-create'),
    path('<int:product_id>/', CreditProductDetailAPIView.as_view(), name='product-detail'),
    
    # Parámetros y configuración
    path('<int:product_id>/parameters/', CreditProductParametersAPIView.as_view(), name='product-parameters'),
    path('<int:product_id>/full/', CreditProductWithParametersAPIView.as_view(), name='product-full'),
    path('<int:product_id>/ranges/', CreditProductRangesAPIView.as_view(), name='product-ranges'),
    
    # Cálculos
    path('<int:product_id>/calculate/', CreditProductCalculateAPIView.as_view(), name='product-calculate'),
]
