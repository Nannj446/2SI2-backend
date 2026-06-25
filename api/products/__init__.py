"""
Módulo products - Gestión de productos crediticios.

IMPORTANTE: No importamos modelos aquí para evitar problemas de carga circular.
Los modelos deben importarse directamente desde sus módulos:
    from api.products.models import CreditProduct, ProductRequirement
"""

default_app_config = 'api.products.apps.ProductsConfig'
