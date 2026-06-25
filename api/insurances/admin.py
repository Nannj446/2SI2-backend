"""
Django admin configuration for Insurances.
"""
from django.contrib import admin

from .models import Insurer, Insurance, InsuranceCoverage, ProductInsurance, CreditInsurance


@admin.register(Insurer)
class InsurerAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'nit', 'is_active']
    list_filter = ['is_active']
    search_fields = ['name', 'code', 'nit']


class InsuranceCoverageInline(admin.TabularInline):
    model = InsuranceCoverage
    extra = 1


@admin.register(Insurance)
class InsuranceAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'insurance_type', 'insurer', 'is_mandatory', 'is_active']
    list_filter = ['insurance_type', 'insurer', 'is_mandatory', 'is_active']
    search_fields = ['name', 'code']
    inlines = [InsuranceCoverageInline]


@admin.register(InsuranceCoverage)
class InsuranceCoverageAdmin(admin.ModelAdmin):
    list_display = ['name', 'insurance', 'coverage_type', 'value']
    list_filter = ['coverage_type', 'insurance']


@admin.register(ProductInsurance)
class ProductInsuranceAdmin(admin.ModelAdmin):
    list_display = ['product', 'insurance', 'is_required', 'premium_type', 'custom_premium']
    list_filter = ['is_required', 'premium_type']


@admin.register(CreditInsurance)
class CreditInsuranceAdmin(admin.ModelAdmin):
    list_display = ['policy_number', 'active_credit', 'insurance', 'status', 'start_date', 'end_date']
    list_filter = ['status', 'insurance', 'start_date']
    search_fields = ['policy_number', 'active_credit__id']
    date_hierarchy = 'start_date'
