"""
Django admin configuration for collateral (garantias).
"""

from django.contrib import admin

from api.garantias.models import (
    Collateral,
    Guarantor,
    CollateralDocument,
    CollateralValuation,
)


@admin.register(Collateral)
class CollateralAdmin(admin.ModelAdmin):
    """Admin for Collateral."""

    list_display = [
        'id',
        'loan_application',
        'collateral_type',
        'estimated_value',
        'appraised_value',
        'coverage_percentage',
        'status',
        'is_active',
        'created_at',
    ]

    list_filter = [
        'collateral_type',
        'status',
        'is_active',
        'created_at',
    ]

    search_fields = [
        'loan_application__application_number',
        'description',
        'property_registry_number',
        'vehicle_plate',
        'vehicle_vin',
    ]

    readonly_fields = [
        'id',
        'created_at',
        'updated_at',
        'approved_at',
    ]


@admin.register(Guarantor)
class GuarantorAdmin(admin.ModelAdmin):
    """Admin for Guarantor."""

    list_display = [
        'id',
        'loan_application',
        'first_name',
        'last_name',
        'document_number',
        'monthly_income',
        'status',
        'is_active',
        'created_at',
    ]

    list_filter = [
        'document_type',
        'employment_type',
        'status',
        'is_active',
        'created_at',
    ]

    search_fields = [
        'first_name',
        'last_name',
        'document_number',
        'email',
    ]

    readonly_fields = [
        'id',
        'created_at',
        'updated_at',
        'approved_at',
    ]


@admin.register(CollateralDocument)
class CollateralDocumentAdmin(admin.ModelAdmin):
    """Admin for CollateralDocument."""

    list_display = [
        'id',
        'collateral',
        'document_type',
        'is_valid',
        'uploaded_by',
        'created_at',
    ]

    list_filter = [
        'document_type',
        'is_valid',
        'created_at',
    ]

    search_fields = [
        'collateral__loan_application__application_number',
        'file_resource__original_name',
    ]

    readonly_fields = [
        'id',
        'created_at',
        'updated_at',
        'verified_at',
    ]


@admin.register(CollateralValuation)
class CollateralValuationAdmin(admin.ModelAdmin):
    """Admin for CollateralValuation."""

    list_display = [
        'id',
        'collateral',
        'valuation_type',
        'appraised_value',
        'valuation_date',
        'approved_at',
        'created_at',
    ]

    list_filter = [
        'valuation_type',
        'valuation_date',
        'approved_at',
    ]

    search_fields = [
        'collateral__loan_application__application_number',
        'appraiser_name',
    ]

    readonly_fields = [
        'id',
        'created_at',
        'updated_at',
        'approved_at',
    ]
