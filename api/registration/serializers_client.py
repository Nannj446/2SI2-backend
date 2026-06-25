from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers
from datetime import date

from api.models import FinancialInstitution
from .services_client import ClientRegisterInput, ClientRegisterService


class PublicInstitutionSerializer(serializers.ModelSerializer):
    """Serializer para mostrar instituciones públicamente"""
    
    institution_type_display = serializers.CharField(source='get_institution_type_display', read_only=True)
    
    class Meta:
        model = FinancialInstitution
        fields = [
            'id', 'name', 'slug', 'institution_type', 
            'institution_type_display', 'is_active'
        ]


class ClientRegisterSerializer(serializers.Serializer):
    """Serializer para registro de clientes"""
    
    # Institución
    institution_id = serializers.IntegerField()
    
    # Datos personales
    first_name = serializers.CharField(max_length=150)
    last_name = serializers.CharField(max_length=150)
    email = serializers.EmailField(max_length=254)
    phone = serializers.CharField(max_length=20)
    
    # Documento de identidad
    document_type = serializers.ChoiceField(choices=[
        ('ci', 'Cédula de Identidad'),
        ('passport', 'Pasaporte'),
        ('nit', 'NIT'),
    ])
    document_number = serializers.CharField(max_length=50)
    
    # Datos adicionales
    date_of_birth = serializers.DateField()
    address = serializers.CharField(max_length=500)
    
    # Credenciales
    password = serializers.CharField(write_only=True, min_length=8)
    confirm_password = serializers.CharField(write_only=True, min_length=8)

    def validate_institution_id(self, value):
        """Validar que la institución existe y está activa"""
        try:
            institution = FinancialInstitution.objects.get(
                id=value, 
                is_active=True
            )
            return value
        except FinancialInstitution.DoesNotExist:
            raise serializers.ValidationError(
                'La institución financiera seleccionada no está disponible.'
            )

    def validate_first_name(self, value):
        """Validar nombre"""
        normalized_name = value.strip()
        if not normalized_name:
            raise serializers.ValidationError('El nombre es obligatorio.')
        return normalized_name

    def validate_last_name(self, value):
        """Validar apellido"""
        normalized_name = value.strip()
        if not normalized_name:
            raise serializers.ValidationError('El apellido es obligatorio.')
        return normalized_name

    def validate_email(self, value):
        """Validar que el email no esté en uso"""
        normalized_email = value.strip().lower()
        user_model = get_user_model()

        if user_model.objects.filter(email__iexact=normalized_email).exists():
            raise serializers.ValidationError(
                'Ya existe un usuario registrado con este correo electrónico.'
            )

        return normalized_email

    def validate_phone(self, value):
        """Validar teléfono"""
        phone = value.strip()
        if not phone:
            raise serializers.ValidationError('El teléfono es obligatorio.')
        
        # Validación básica de formato
        if len(phone) < 8:
            raise serializers.ValidationError(
                'El teléfono debe tener al menos 8 dígitos.'
            )
        
        return phone

    def validate_document_number(self, value):
        """Validar número de documento"""
        document = value.strip()
        if not document:
            raise serializers.ValidationError(
                'El número de documento es obligatorio.'
            )
        return document

    def validate_date_of_birth(self, value):
        """Validar fecha de nacimiento"""
        if not value:
            raise serializers.ValidationError(
                'La fecha de nacimiento es obligatoria.'
            )
        
        # Validar que sea mayor de edad (18 años)
        today = date.today()
        age = today.year - value.year - ((today.month, today.day) < (value.month, value.day))
        
        if age < 18:
            raise serializers.ValidationError(
                'Debe ser mayor de 18 años para registrarse.'
            )
        
        if age > 120:
            raise serializers.ValidationError(
                'La fecha de nacimiento no es válida.'
            )
        
        return value

    def validate_address(self, value):
        """Validar dirección"""
        address = value.strip()
        if not address:
            raise serializers.ValidationError('La dirección es obligatoria.')
        return address

    def validate_password(self, value):
        """Validar contraseña"""
        validate_password(value)
        return value

    def validate(self, attrs):
        """Validaciones cruzadas"""
        # Validar confirmación de contraseña
        if attrs['password'] != attrs['confirm_password']:
            raise serializers.ValidationError({
                'confirm_password': 'La confirmación de contraseña no coincide.'
            })
        
        # Validar combinación documento + institución (único)
        institution_id = attrs['institution_id']
        document_number = attrs['document_number']
        
        # Aquí podrías agregar validación de documento único por institución
        # si tienes un modelo ClientProfile
        
        return attrs

    def create(self, validated_data):
        """Crear cliente usando el servicio"""
        validated_data.pop('confirm_password')
        service = ClientRegisterService()
        return service.execute(ClientRegisterInput(**validated_data))