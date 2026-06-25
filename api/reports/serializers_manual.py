"""
Serializers para Reportes Manuales.

Autor: Sistema FinCore
Fecha: 2026-05-11
"""

from rest_framework import serializers


class ManualReportFilterSerializer(serializers.Serializer):
    """Serializer para validar filtros de reportes manuales."""
    
    # Filtros comunes
    scope = serializers.ChoiceField(choices=['TENANT', 'SAAS'], required=False, default='TENANT')
    search = serializers.CharField(required=False, allow_blank=True, max_length=200)
    date_from = serializers.DateField(required=False)
    date_to = serializers.DateField(required=False)
    page = serializers.IntegerField(required=False, min_value=1, default=1)
    page_size = serializers.IntegerField(required=False, min_value=1, max_value=1000, default=100)
    
    # Filtros específicos de clientes
    status = serializers.CharField(required=False)
    kyc_status = serializers.CharField(required=False)
    risk_level = serializers.CharField(required=False)
    city = serializers.CharField(required=False, max_length=100)
    department = serializers.CharField(required=False, max_length=100)
    employment_status = serializers.CharField(required=False)
    income_min = serializers.DecimalField(required=False, max_digits=15, decimal_places=2)
    income_max = serializers.DecimalField(required=False, max_digits=15, decimal_places=2)
    
    # Filtros específicos de productos
    product_type_id = serializers.IntegerField(required=False)
    min_amount_from = serializers.DecimalField(required=False, max_digits=15, decimal_places=2)
    min_amount_to = serializers.DecimalField(required=False, max_digits=15, decimal_places=2)
    max_amount_from = serializers.DecimalField(required=False, max_digits=15, decimal_places=2)
    max_amount_to = serializers.DecimalField(required=False, max_digits=15, decimal_places=2)
    
    # Filtros específicos de solicitudes
    product_id = serializers.IntegerField(required=False)
    client_id = serializers.IntegerField(required=False)
    branch_id = serializers.IntegerField(required=False)
    assigned_to_id = serializers.IntegerField(required=False)
    identity_verification_status = serializers.CharField(required=False)
    documents_status = serializers.CharField(required=False)
    submitted_from = serializers.DateField(required=False)
    submitted_to = serializers.DateField(required=False)
    amount_min = serializers.DecimalField(required=False, max_digits=15, decimal_places=2)
    amount_max = serializers.DecimalField(required=False, max_digits=15, decimal_places=2)
    
    # Filtros específicos de auditoría
    user_id = serializers.IntegerField(required=False)
    action = serializers.CharField(required=False)
    resource_type = serializers.CharField(required=False)
    resource_id = serializers.IntegerField(required=False)
    severity = serializers.CharField(required=False)
    ip_address = serializers.IPAddressField(required=False)
    
    # Filtros específicos de usuarios
    is_active = serializers.BooleanField(required=False, allow_null=True, default=None)
    role = serializers.CharField(required=False)


class ExportRequestSerializer(serializers.Serializer):
    """Serializer para solicitudes de exportación."""
    
    report_type = serializers.ChoiceField(
        choices=['clients', 'products', 'applications', 'audit', 'users', 'branches'],
        required=True
    )
    filters = serializers.DictField(required=False, default=dict)
    include_chart = serializers.BooleanField(required=False, default=False)
    chart_type = serializers.CharField(required=False, allow_blank=True)


class ReportDataSerializer(serializers.Serializer):
    """Serializer para datos de reporte."""
    
    report_type = serializers.CharField()
    filters_applied = serializers.DictField()
    summary = serializers.DictField()
    chart_data = serializers.DictField()
    rows = serializers.ListField()
    pagination = serializers.DictField()
