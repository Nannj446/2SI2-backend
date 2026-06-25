from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from api.models import FinancialInstitution
from api.registration.services import RegisterUserInput, RegisterUserService


class RegisterUserSerializer(serializers.Serializer):
    company_name = serializers.CharField(max_length=255)
    institution_type = serializers.ChoiceField(choices=FinancialInstitution.InstitutionType.choices)
    first_name = serializers.CharField(max_length=150)
    last_name = serializers.CharField(max_length=150)
    email = serializers.EmailField(max_length=254)
    password = serializers.CharField(write_only=True, min_length=8, trim_whitespace=False)
    confirm_password = serializers.CharField(write_only=True, min_length=8, trim_whitespace=False)
    selected_plan_id = serializers.IntegerField(required=False, allow_null=True)

    def to_internal_value(self, data):
        normalized_data = dict(data)
        field_aliases = {
            'companyName': 'company_name',
            'institutionType': 'institution_type',
            'firstName': 'first_name',
            'lastName': 'last_name',
            'confirmPassword': 'confirm_password',
            'selectedPlanId': 'selected_plan_id',
        }

        for source_key, target_key in field_aliases.items():
            if source_key in normalized_data and target_key not in normalized_data:
                normalized_data[target_key] = normalized_data[source_key]

        return super().to_internal_value(normalized_data)

    def validate_company_name(self, value: str) -> str:
        normalized_name = ' '.join(value.split())
        if not normalized_name:
            raise serializers.ValidationError('El nombre de la entidad financiera es obligatorio.')
        return normalized_name

    def validate_first_name(self, value: str) -> str:
        normalized_name = value.strip()
        if not normalized_name:
            raise serializers.ValidationError('El nombre es obligatorio.')
        return normalized_name

    def validate_last_name(self, value: str) -> str:
        normalized_last_name = value.strip()
        if not normalized_last_name:
            raise serializers.ValidationError('El apellido es obligatorio.')
        return normalized_last_name

    def validate_email(self, value: str) -> str:
        normalized_email = value.strip().lower()
        user_model = get_user_model()

        if user_model.objects.filter(email__iexact=normalized_email).exists():
            raise serializers.ValidationError('Ya existe un usuario registrado con este correo.')

        if user_model.objects.filter(username__iexact=normalized_email).exists():
            raise serializers.ValidationError('Ya existe un usuario registrado con este correo.')

        return normalized_email

    def validate_password(self, value: str) -> str:
        validate_password(value)
        return value

    def validate(self, attrs: dict) -> dict:
        if attrs['password'] != attrs['confirm_password']:
            raise serializers.ValidationError(
                {'confirm_password': 'La confirmacion de la contrasena no coincide.'}
            )
        return attrs

    def create(self, validated_data: dict):
        validated_data.pop('confirm_password')
        service = RegisterUserService()
        return service.execute(RegisterUserInput(**validated_data))
