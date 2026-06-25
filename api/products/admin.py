"""
Configuración del admin de Django para productos crediticios (REFACTORIZADO).
"""

from django.contrib import admin
from api.products.models import CreditProduct, ProductRequirement


@admin.register(CreditProduct)
class CreditProductAdmin(admin.ModelAdmin):
    """Admin para el modelo CreditProduct (SIMPLIFICADO)."""
    
    list_display = [
        'id',
        'name',
        'code',
        'product_type',
        'is_active',
        'display_order',
        'created_at',
    ]
    
    list_filter = [
        'product_type',
        'is_active',
        'created_at',
    ]
    
    search_fields = [
        'name',
        'code',
        'description',
    ]
    
    readonly_fields = [
        'id',
        'created_at',
        'updated_at',
    ]
    
    fieldsets = (
        ('Información Básica', {
            'fields': (
                'id',
                'name',
                'code',
                'product_type',
                'description',
                'is_active',
                'display_order',
            )
        }),
        ('Información de Marketing', {
            'fields': (
                'target_audience',
                'benefits',
                'terms_and_conditions',
            )
        }),
        ('Metadata UI', {
            'fields': (
                'icon',
                'color',
            )
        }),
        ('Sistema', {
            'fields': (
                'institution',
                'created_at',
                'updated_at',
            )
        }),
    )


@admin.register(ProductRequirement)
class ProductRequirementAdmin(admin.ModelAdmin):
    """Admin para el modelo ProductRequirement."""
    
    list_display = [
        'id',
        'product',
        'requirement_name',
        'is_mandatory',
        'display_order',
    ]
    
    list_filter = [
        'is_mandatory',
        'product__product_type',
    ]
    
    search_fields = [
        'requirement_name',
        'description',
        'product__name',
    ]
    
    readonly_fields = [
        'id',
        'created_at',
        'updated_at',
    ]
