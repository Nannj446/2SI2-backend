"""
Serializers para gestión de sucursales.
"""

from django.contrib.auth import get_user_model
from rest_framework import serializers

from api.branches.models import Branch

User = get_user_model()


class BranchListSerializer(serializers.ModelSerializer):
    """Serializer para listado y detalle de sucursales."""

    assigned_users_count = serializers.IntegerField(read_only=True)
    assigned_operations_count = serializers.IntegerField(read_only=True)
    assigned_user_ids = serializers.SerializerMethodField()
    assigned_operation_ids = serializers.SerializerMethodField()

    class Meta:
        model = Branch
        fields = [
            'id',
            'name',
            'address',
            'city',
            'is_active',
            'created_at',
            'assigned_users_count',
            'assigned_operations_count',
            'assigned_user_ids',
            'assigned_operation_ids',
        ]

    def get_assigned_user_ids(self, obj):
        return [user.id for user in obj.assigned_users.all()]

    def get_assigned_operation_ids(self, obj):
        return [operation.id for operation in obj.assigned_loan_applications.all()]


class BranchAssignmentsValidationMixin:
    """Validaciones compartidas para asociaciones de sucursal."""

    def _get_request_tenant(self):
        request = self.context.get('request')
        return getattr(request, 'tenant', None)

    def _validate_users(self, user_ids):
        if not user_ids:
            return []

        tenant = self._get_request_tenant()
        if not tenant:
            raise serializers.ValidationError('Tenant requerido para asociar usuarios.')

        unique_ids = list(dict.fromkeys(user_ids))

        users = User.objects.filter(
            id__in=unique_ids,
            institution_memberships__institution=tenant,
            institution_memberships__is_active=True,
            profile__user_type='tenant_user',
        ).distinct()

        if users.count() != len(unique_ids):
            raise serializers.ValidationError(
                'Uno o más usuarios no pertenecen al tenant actual o no son válidos.'
            )

        return list(users)

    def _validate_operations(self, operation_ids):
        if not operation_ids:
            return []

        tenant = self._get_request_tenant()
        if not tenant:
            raise serializers.ValidationError('Tenant requerido para asociar operaciones.')

        unique_ids = list(dict.fromkeys(operation_ids))

        from api.loans.models import LoanApplication

        operations = LoanApplication.objects.filter(
            id__in=unique_ids,
            institution=tenant,
            is_active=True,
        )

        if operations.count() != len(unique_ids):
            raise serializers.ValidationError(
                'Una o más operaciones no pertenecen al tenant actual o no son válidas.'
            )

        return list(operations)


class CreateBranchSerializer(serializers.ModelSerializer, BranchAssignmentsValidationMixin):
    """Serializer para creación de sucursales."""

    assigned_user_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        required=False,
        allow_empty=True,
        write_only=True,
    )
    assigned_operation_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        required=False,
        allow_empty=True,
        write_only=True,
    )

    class Meta:
        model = Branch
        fields = [
            'name',
            'address',
            'city',
            'is_active',
            'assigned_user_ids',
            'assigned_operation_ids',
        ]

    def validate_name(self, value):
        cleaned = value.strip()
        if not cleaned:
            raise serializers.ValidationError('El nombre es requerido.')
        if len(cleaned) < 3:
            raise serializers.ValidationError('El nombre debe tener al menos 3 caracteres.')
        return cleaned

    def validate_address(self, value):
        cleaned = value.strip()
        if not cleaned:
            raise serializers.ValidationError('La dirección es requerida.')
        return cleaned

    def validate_city(self, value):
        cleaned = value.strip()
        if not cleaned:
            raise serializers.ValidationError('La ciudad es requerida.')
        return cleaned

    def validate(self, attrs):
        tenant = self._get_request_tenant()
        if not tenant:
            raise serializers.ValidationError('Tenant requerido para crear sucursales.')

        name = attrs.get('name')
        if name and Branch.objects.filter(institution=tenant, name__iexact=name).exists():
            raise serializers.ValidationError({'name': 'Ya existe una sucursal con este nombre.'})

        attrs['_validated_users'] = self._validate_users(attrs.pop('assigned_user_ids', []))
        attrs['_validated_operations'] = self._validate_operations(
            attrs.pop('assigned_operation_ids', [])
        )
        return attrs

    def create(self, validated_data):
        request = self.context.get('request')
        tenant = getattr(request, 'tenant', None)

        users = validated_data.pop('_validated_users', [])
        operations = validated_data.pop('_validated_operations', [])

        branch = Branch.objects.create(institution=tenant, **validated_data)
        if users:
            branch.assigned_users.set(users)
        if operations:
            branch.assigned_loan_applications.set(operations)

        return branch


class UpdateBranchSerializer(serializers.ModelSerializer, BranchAssignmentsValidationMixin):
    """Serializer para actualización de sucursales."""

    assigned_user_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        required=False,
        allow_empty=True,
        write_only=True,
    )
    assigned_operation_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        required=False,
        allow_empty=True,
        write_only=True,
    )

    class Meta:
        model = Branch
        fields = [
            'name',
            'address',
            'city',
            'is_active',
            'assigned_user_ids',
            'assigned_operation_ids',
        ]

    def validate(self, attrs):
        tenant = self._get_request_tenant()
        if not tenant:
            raise serializers.ValidationError('Tenant requerido para actualizar sucursales.')

        name = attrs.get('name')
        if name is not None:
            name = name.strip()
            if not name:
                raise serializers.ValidationError({'name': 'El nombre es requerido.'})
            if len(name) < 3:
                raise serializers.ValidationError(
                    {'name': 'El nombre debe tener al menos 3 caracteres.'}
                )
            attrs['name'] = name

            if Branch.objects.filter(
                institution=tenant,
                name__iexact=name,
            ).exclude(id=self.instance.id).exists():
                raise serializers.ValidationError({'name': 'Ya existe una sucursal con este nombre.'})

        if attrs.get('address') is not None:
            address = attrs['address'].strip()
            if not address:
                raise serializers.ValidationError({'address': 'La dirección es requerida.'})
            attrs['address'] = address

        if attrs.get('city') is not None:
            city = attrs['city'].strip()
            if not city:
                raise serializers.ValidationError({'city': 'La ciudad es requerida.'})
            attrs['city'] = city

        if 'assigned_user_ids' in attrs:
            attrs['_validated_users'] = self._validate_users(attrs.pop('assigned_user_ids', []))

        if 'assigned_operation_ids' in attrs:
            attrs['_validated_operations'] = self._validate_operations(
                attrs.pop('assigned_operation_ids', [])
            )

        return attrs

    def update(self, instance, validated_data):
        users = validated_data.pop('_validated_users', None)
        operations = validated_data.pop('_validated_operations', None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if users is not None:
            instance.assigned_users.set(users)

        if operations is not None:
            instance.assigned_loan_applications.set(operations)

        return instance
