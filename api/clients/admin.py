"""
Configuración del admin de Django para clientes.
"""

from django.contrib import admin
from api.clients.models import Client, ClientDocument


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    """Admin para el modelo Client."""
    
    list_display = [
        'id',
        'get_full_name',
        'document_number',
        'email',
        'phone',
        'city',
        'kyc_status',
        'is_active',
        'created_at',
    ]
    
    list_filter = [
        'client_type',
        'document_type',
        'kyc_status',
        'is_active',
        'employment_status',
        'department',
        'created_at',
    ]
    
    search_fields = [
        'first_name',
        'last_name',
        'document_number',
        'email',
        'phone',
    ]
    
    readonly_fields = [
        'id',
        'created_at',
        'updated_at',
        'verified_at',
    ]
    
    fieldsets = (
        ('Información Básica', {
            'fields': (
                'id',
                'client_type',
                'first_name',
                'last_name',
                'document_type',
                'document_number',
                'document_extension',
                'birth_date',
                'gender',
            )
        }),
        ('Contacto', {
            'fields': (
                'email',
                'phone',
                'mobile_phone',
                'address',
                'city',
                'department',
                'country',
                'postal_code',
            )
        }),
        ('Información Laboral y Financiera', {
            'fields': (
                'employment_status',
                'employer_name',
                'employer_nit',
                'job_title',
                'employment_start_date',
                'monthly_income',
                'additional_income',
            )
        }),
        ('Estado del Sistema', {
            'fields': (
                'institution',
                'is_active',
                'kyc_status',
                'verified_at',
                'verified_by',
                'risk_level',
                'notes',
            )
        }),
        ('Fechas', {
            'fields': (
                'created_at',
                'updated_at',
            )
        }),
    )
    
    def get_full_name(self, obj):
        """Retorna el nombre completo."""
        return obj.get_full_name()
    get_full_name.short_description = 'Nombre Completo'


@admin.register(ClientDocument)
class ClientDocumentAdmin(admin.ModelAdmin):
    """Admin para el modelo ClientDocument."""
    
    list_display = [
        'id',
        'client',
        'category',
        'document_name',
        'verified',
        'uploaded_by',
        'created_at',
    ]
    
    list_filter = [
        'category',
        'verified',
        'created_at',
    ]
    
    search_fields = [
        'document_name',
        'client__first_name',
        'client__last_name',
        'client__document_number',
    ]
    
    readonly_fields = [
        'id',
        'file_size',
        'mime_type',
        'uploaded_by',
        'verified_at',
        'verified_by',
        'created_at',
        'updated_at',
    ]
