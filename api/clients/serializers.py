"""
Serializers para gestión de clientes.
"""

from rest_framework import serializers
from api.clients.models import Client, ClientDocument


class ClientSerializer(serializers.ModelSerializer):
    """Serializer completo para lectura de clientes."""
    
    # Campos del usuario (via properties)
    email = serializers.EmailField(source='user.email', read_only=True)
    first_name = serializers.CharField(source='user.first_name', read_only=True)
    last_name = serializers.CharField(source='user.last_name', read_only=True)
    phone = serializers.CharField(source='user.profile.phone', read_only=True)
    
    # Campos calculados
    full_name = serializers.CharField(source='get_full_name', read_only=True)
    total_monthly_income = serializers.DecimalField(
        source='get_total_monthly_income',
        max_digits=12,
        decimal_places=2,
        read_only=True
    )
    age = serializers.IntegerField(source='get_age', read_only=True)
    
    # Campos de display
    client_type_display = serializers.CharField(source='get_client_type_display', read_only=True)
    document_type_display = serializers.CharField(source='get_document_type_display', read_only=True)
    employment_status_display = serializers.CharField(source='get_employment_status_display', read_only=True)
    kyc_status_display = serializers.CharField(source='get_kyc_status_display', read_only=True)
    
    class Meta:
        model = Client
        fields = [
            'id',
            'client_type',
            'client_type_display',
            'first_name',
            'last_name',
            'full_name',
            'document_type',
            'document_type_display',
            'document_number',
            'document_extension',
            'birth_date',
            'age',
            'gender',
            'email',
            'phone',
            'mobile_phone',
            'address',
            'city',
            'department',
            'country',
            'postal_code',
            'employment_status',
            'employment_status_display',
            'employer_name',
            'employer_nit',
            'job_title',
            'employment_start_date',
            'monthly_income',
            'additional_income',
            'total_monthly_income',
            'is_active',
            'verified_at',
            'kyc_status',
            'kyc_status_display',
            'risk_level',
            'notes',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'id',
            'verified_at',
            'created_at',
            'updated_at',
        ]


class CreateClientSerializer(serializers.ModelSerializer):
    """
    Serializer para crear clientes con validaciones.
    
    NOTA: Los campos first_name, last_name, email, phone ya no están en el modelo Client.
    Estos deben ser manejados al crear el usuario asociado.
    Este serializer solo maneja los campos específicos del cliente.
    """
    
    class Meta:
        model = Client
        fields = [
            'user',  # FK al usuario
            'client_type',
            'document_type',
            'document_number',
            'document_extension',
            'birth_date',
            'gender',
            'mobile_phone',
            'address',
            'city',
            'department',
            'country',
            'postal_code',
            'employment_status',
            'employer_name',
            'employer_nit',
            'job_title',
            'employment_start_date',
            'monthly_income',
            'additional_income',
            'notes',
        ]
    
    def validate_document_number(self, value):
        """Valida que el número de documento no esté vacío."""
        if not value or not value.strip():
            raise serializers.ValidationError('El número de documento es requerido')
        return value.strip().upper()
    
    def validate_monthly_income(self, value):
        """Valida que el ingreso mensual sea positivo."""
        if value <= 0:
            raise serializers.ValidationError('El ingreso mensual debe ser mayor a 0')
        return value
    
    def validate(self, attrs):
        """Validaciones a nivel de objeto."""
        # Validar edad mínima (18 años)
        from datetime import date
        birth_date = attrs.get('birth_date')
        if birth_date:
            today = date.today()
            age = today.year - birth_date.year - (
                (today.month, today.day) < (birth_date.month, birth_date.day)
            )
            if age < 18:
                raise serializers.ValidationError({
                    'birth_date': 'El cliente debe ser mayor de 18 años'
                })
        
        return attrs


class UpdateClientSerializer(serializers.ModelSerializer):
    """
    Serializer para actualización parcial de clientes.
    
    NOTA: Los campos first_name, last_name, email, phone están en auth_user y user_profiles.
    Para actualizarlos, se debe actualizar el usuario asociado, no el cliente directamente.
    """
    
    class Meta:
        model = Client
        fields = [
            'mobile_phone',
            'address',
            'city',
            'department',
            'employment_status',
            'employer_name',
            'employer_nit',
            'job_title',
            'employment_start_date',
            'monthly_income',
            'additional_income',
            'notes',
            'is_active',
        ]
    
    def validate_monthly_income(self, value):
        """Valida que el ingreso mensual sea positivo."""
        if value is not None and value <= 0:
            raise serializers.ValidationError('El ingreso mensual debe ser mayor a 0')
        return value


class ClientDocumentSerializer(serializers.ModelSerializer):
    """Serializer para documentos de clientes."""
    
    category_display = serializers.CharField(source='get_category_display', read_only=True)
    uploaded_by_name = serializers.SerializerMethodField()
    verified_by_name = serializers.SerializerMethodField()
    
    class Meta:
        model = ClientDocument
        fields = [
            'id',
            'category',
            'category_display',
            'document_name',
            'file',
            'file_size',
            'mime_type',
            'uploaded_by',
            'uploaded_by_name',
            'verified',
            'verified_at',
            'verified_by',
            'verified_by_name',
            'notes',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'id',
            'file_size',
            'mime_type',
            'uploaded_by',
            'verified_at',
            'verified_by',
            'created_at',
            'updated_at',
        ]
    
    def get_uploaded_by_name(self, obj):
        """Retorna el nombre del usuario que subió el documento."""
        if obj.uploaded_by:
            return f"{obj.uploaded_by.first_name} {obj.uploaded_by.last_name}"
        return None
    
    def get_verified_by_name(self, obj):
        """Retorna el nombre del usuario que verificó el documento."""
        if obj.verified_by:
            return f"{obj.verified_by.first_name} {obj.verified_by.last_name}"
        return None


class ClientListSerializer(serializers.ModelSerializer):
    """Serializer simplificado para listado de clientes."""
    
    full_name = serializers.CharField(source='get_full_name', read_only=True)
    age = serializers.IntegerField(source='get_age', read_only=True)
    kyc_status_display = serializers.CharField(source='get_kyc_status_display', read_only=True)
    
    class Meta:
        model = Client
        fields = [
            'id',
            'full_name',
            'document_type',
            'document_number',
            'age',
            'email',
            'phone',
            'city',
            'monthly_income',
            'kyc_status',
            'kyc_status_display',
            'is_active',
            'created_at',
        ]
