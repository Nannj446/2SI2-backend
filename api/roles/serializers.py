from rest_framework import serializers

from api.models import FinancialInstitution, Permission, Role


# Parte erick sprint 0
class RoleSerializer(serializers.ModelSerializer):
    permission_ids = serializers.PrimaryKeyRelatedField(
        source='permissions',
        queryset=Permission.objects.filter(is_active=True),
        many=True,
        required=False,
        write_only=True,
    )
    permissions = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Role
        fields = (
            'id',
            'institution',
            'name',
            'description',
            'is_active',
            'permissions',
            'permission_ids',
            'created_at',
            'updated_at',
        )
        read_only_fields = ('id', 'permissions', 'created_at', 'updated_at')

    def validate_institution(self, value: FinancialInstitution) -> FinancialInstitution:
        if not value.is_active:
            raise serializers.ValidationError('La entidad financiera esta inactiva.')
        return value

    def validate_name(self, value: str) -> str:
        normalized_name = ' '.join(value.split())
        if not normalized_name:
            raise serializers.ValidationError('El nombre del rol es obligatorio.')
        return normalized_name

    def validate(self, attrs: dict) -> dict:
        institution = attrs.get('institution') or getattr(self.instance, 'institution', None)
        name = attrs.get('name') or getattr(self.instance, 'name', None)

        if institution and name:
            queryset = Role.objects.filter(institution=institution, name__iexact=name)
            if self.instance:
                queryset = queryset.exclude(pk=self.instance.pk)
            if queryset.exists():
                raise serializers.ValidationError({'name': 'Ya existe un rol con este nombre en la entidad.'})

        return attrs

    def create(self, validated_data):
        permissions = validated_data.pop('permissions', [])
        role = Role.objects.create(**validated_data)
        if permissions:
            role.permissions.set(permissions)
        return role

    def update(self, instance, validated_data):
        permissions = validated_data.pop('permissions', None)
        role = super().update(instance, validated_data)

        if permissions is not None:
            role.permissions.set(permissions)

        return role

    def get_permissions(self, obj: Role) -> list[dict]:
        return [
            {
                'id': permission.id,
                'code': permission.code,
                'name': permission.name,
                'description': permission.description,
            }
            for permission in obj.permissions.filter(is_active=True).order_by('name')
        ]


class PermissionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Permission
        fields = ('id', 'code', 'name', 'description', 'is_active')
        read_only_fields = fields


class RolePermissionAssignmentSerializer(serializers.Serializer):
    permission_ids = serializers.PrimaryKeyRelatedField(
        queryset=Permission.objects.filter(is_active=True),
        many=True,
        allow_empty=True,
    )

    def save(self, **kwargs):
        role: Role = self.context['role']
        permissions = self.validated_data['permission_ids']
        role.permissions.set(permissions)
        return role



# ============================================================
# SPRINT 8: Asignación de Permisos a Roles (Panel Tenant)
# ============================================================

class RolePermissionSerializer(serializers.Serializer):
    """
    Serializer para asignar permisos a un rol.
    Versión simplificada para el endpoint de asignación.
    """
    
    permission_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=True,
        help_text="Lista de IDs de permisos a asignar al rol"
    )
    
    def validate_permission_ids(self, value):
        """Valida que los IDs de permisos existan y estén activos."""
        if not value:
            raise serializers.ValidationError("Debe proporcionar al menos un permiso")
        
        # Verificar que todos los permisos existan y estén activos
        existing_permissions = Permission.objects.filter(
            id__in=value,
            is_active=True
        )
        existing_count = existing_permissions.count()
        
        if existing_count != len(value):
            invalid_ids = set(value) - set(existing_permissions.values_list('id', flat=True))
            raise serializers.ValidationError(
                f"Los siguientes IDs de permisos no existen o están inactivos: {invalid_ids}"
            )
        
        return value


class AvailablePermissionSerializer(serializers.ModelSerializer):
    """
    Serializer para listar permisos disponibles para asignar.
    Incluye información adicional útil para el frontend.
    """
    
    is_assigned = serializers.SerializerMethodField()
    
    class Meta:
        model = Permission
        fields = ['id', 'code', 'name', 'description', 'is_active', 'is_assigned']
    
    def get_is_assigned(self, obj):
        """
        Indica si el permiso está asignado al rol actual.
        Requiere que se pase el rol en el contexto.
        """
        role = self.context.get('role')
        if role:
            return obj.roles.filter(id=role.id).exists()
        return False
