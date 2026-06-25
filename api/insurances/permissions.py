"""
Permisos para Gestión de Seguros.
"""
from rest_framework import permissions


class CanManageInsuranceCatalog(permissions.BasePermission):
    """
    Permiso para gestionar el catálogo de seguros (aseguradoras y tipos).
    Requiere ser staff o tener rol con este permiso.
    """

    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False

        if request.user.is_superuser:
            return True

        if hasattr(request.user, 'profile') and request.user.profile.is_saas_admin:
            return True

        if hasattr(request, 'tenant') and request.tenant:
            from api.roles.models import UserRole
            return UserRole.objects.filter(
                user=request.user,
                institution=request.tenant,
                role__permissions__codename='manage_insurance_catalog',
                is_active=True
            ).exists()

        return False


class CanViewInsurance(permissions.BasePermission):
    """
    Permiso para ver seguros.
    """

    def has_permission(self, request, view):
        return request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        if request.user.is_superuser:
            return True

        if hasattr(request.user, 'profile') and request.user.profile.is_saas_admin:
            return True

        if hasattr(request, 'tenant'):
            return obj.institution == request.tenant

        return False


class CanAssociateInsuranceToCredit(permissions.BasePermission):
    """
    Permiso para asociar seguros a un crédito.
    """

    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False

        if request.user.is_superuser:
            return True

        if hasattr(request.user, 'profile') and request.user.profile.is_saas_admin:
            return True

        if hasattr(request, 'tenant') and request.tenant:
            from api.roles.models import UserRole
            return UserRole.objects.filter(
                user=request.user,
                institution=request.tenant,
                role__permissions__codename='associate_insurance_to_credit',
                is_active=True
            ).exists()

        return False


class CanManageProductInsurance(permissions.BasePermission):
    """
    Permiso para gestionar seguros asociados a productos crediticios.
    """

    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False

        if request.user.is_superuser:
            return True

        if hasattr(request.user, 'profile') and request.user.profile.is_saas_admin:
            return True

        if hasattr(request, 'tenant') and request.tenant:
            from api.roles.models import UserRole
            return UserRole.objects.filter(
                user=request.user,
                institution=request.tenant,
                role__permissions__codename='manage_product_insurance',
                is_active=True
            ).exists()

        return False
