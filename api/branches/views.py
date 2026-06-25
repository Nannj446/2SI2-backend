"""
Views para gestión de sucursales.
"""

from django.db.models import Q
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from api.branches.models import Branch
from api.branches.serializers import (
    BranchListSerializer,
    CreateBranchSerializer,
    UpdateBranchSerializer,
)
from api.core.pagination import StandardResultsSetPagination
from api.saas.services import (
    CheckSubscriptionLimitsInput,
    CheckSubscriptionLimitsService,
    UpdateUsageCountersInput,
    UpdateUsageCountersService,
)


def _is_tenant_admin(request) -> bool:
    """Valida que el usuario sea administrador del tenant autenticado."""
    if not request.user.is_authenticated:
        return False

    if not request.tenant:
        return False

    if not hasattr(request.user, 'profile'):
        return False

    if request.user.profile.is_saas_admin():
        return False

    return request.user.user_roles.filter(
        institution=request.tenant,
        is_active=True,
        role__is_active=True,
    ).filter(
        Q(role__name__iexact='Administrador de Institución') |
        Q(role__name__icontains='admin')
    ).exists()


class BranchListCreateAPIView(APIView):
    """
    GET /api/branches/ -> listar sucursales del tenant autenticado
    POST /api/branches/ -> crear sucursal
    """

    permission_classes = [IsAuthenticated]

    def _validate_access(self, request):
        if not request.tenant:
            return Response(
                {
                    'success': False,
                    'message': 'Tenant requerido para gestionar sucursales.',
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not _is_tenant_admin(request):
            return Response(
                {
                    'success': False,
                    'message': 'Solo un ADMIN del tenant puede gestionar sucursales.',
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        return None

    def get(self, request):
        access_error = self._validate_access(request)
        if access_error:
            return access_error

        is_active = request.query_params.get('is_active')

        queryset = Branch.objects.filter(
            institution=request.tenant,
        ).prefetch_related(
            'assigned_users',
            'assigned_loan_applications',
        ).order_by('name')

        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == 'true')

        paginator = StandardResultsSetPagination()
        paginated_queryset = paginator.paginate_queryset(queryset, request)
        serializer = BranchListSerializer(paginated_queryset, many=True)
        return paginator.get_paginated_response(serializer.data)

    def post(self, request):
        access_error = self._validate_access(request)
        if access_error:
            return access_error

        serializer = CreateBranchSerializer(data=request.data, context={'request': request})
        if not serializer.is_valid():
            return Response(
                {
                    'success': False,
                    'message': 'Datos inválidos.',
                    'errors': serializer.errors,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        is_active = serializer.validated_data.get('is_active', True)
        if is_active:
            limits_service = CheckSubscriptionLimitsService()
            limits_result = limits_service.execute(
                CheckSubscriptionLimitsInput(institution=request.tenant, action='add_branch')
            )
            if not limits_result.allowed:
                return Response(
                    {
                        'success': False,
                        'message': limits_result.message,
                        'errors': {'subscription': limits_result.message},
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

        branch = serializer.save()

        if branch.is_active:
            usage_service = UpdateUsageCountersService()
            usage_service.execute(
                UpdateUsageCountersInput(institution=request.tenant, branches_delta=1)
            )

        response_serializer = BranchListSerializer(branch)
        return Response(
            {
                'success': True,
                'message': 'Sucursal creada exitosamente.',
                'branch': response_serializer.data,
            },
            status=status.HTTP_201_CREATED,
        )


class BranchDetailAPIView(APIView):
    """
    PUT /api/branches/{id}/ -> actualizar sucursal
    DELETE /api/branches/{id}/ -> eliminar/desactivar sucursal
    """

    permission_classes = [IsAuthenticated]

    def _validate_access(self, request):
        if not request.tenant:
            return Response(
                {
                    'success': False,
                    'message': 'Tenant requerido para gestionar sucursales.',
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not _is_tenant_admin(request):
            return Response(
                {
                    'success': False,
                    'message': 'Solo un ADMIN del tenant puede gestionar sucursales.',
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        return None

    def _get_branch(self, request, branch_id):
        return Branch.objects.filter(
            id=branch_id,
            institution=request.tenant,
        ).prefetch_related(
            'assigned_users',
            'assigned_loan_applications',
        ).first()

    def put(self, request, branch_id):
        access_error = self._validate_access(request)
        if access_error:
            return access_error

        branch = self._get_branch(request, branch_id)
        if not branch:
            return Response(
                {
                    'success': False,
                    'message': 'Sucursal no encontrada.',
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        previous_active_state = branch.is_active

        serializer = UpdateBranchSerializer(branch, data=request.data, context={'request': request})
        if not serializer.is_valid():
            return Response(
                {
                    'success': False,
                    'message': 'Datos inválidos.',
                    'errors': serializer.errors,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        new_active_state = serializer.validated_data.get('is_active', branch.is_active)

        if not previous_active_state and new_active_state:
            limits_service = CheckSubscriptionLimitsService()
            limits_result = limits_service.execute(
                CheckSubscriptionLimitsInput(institution=request.tenant, action='add_branch')
            )
            if not limits_result.allowed:
                return Response(
                    {
                        'success': False,
                        'message': limits_result.message,
                        'errors': {'subscription': limits_result.message},
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

        updated_branch = serializer.save()

        usage_service = UpdateUsageCountersService()
        if previous_active_state and not updated_branch.is_active:
            usage_service.execute(
                UpdateUsageCountersInput(institution=request.tenant, branches_delta=-1)
            )
        elif not previous_active_state and updated_branch.is_active:
            usage_service.execute(
                UpdateUsageCountersInput(institution=request.tenant, branches_delta=1)
            )

        response_serializer = BranchListSerializer(updated_branch)
        return Response(
            {
                'success': True,
                'message': 'Sucursal actualizada exitosamente.',
                'branch': response_serializer.data,
            },
            status=status.HTTP_200_OK,
        )

    def delete(self, request, branch_id):
        access_error = self._validate_access(request)
        if access_error:
            return access_error

        branch = self._get_branch(request, branch_id)
        if not branch:
            return Response(
                {
                    'success': False,
                    'message': 'Sucursal no encontrada.',
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        if not branch.is_active:
            return Response(
                {
                    'success': True,
                    'message': 'La sucursal ya estaba desactivada.',
                },
                status=status.HTTP_200_OK,
            )

        branch.is_active = False
        branch.save(update_fields=['is_active', 'updated_at'])

        usage_service = UpdateUsageCountersService()
        usage_service.execute(
            UpdateUsageCountersInput(institution=request.tenant, branches_delta=-1)
        )

        return Response(
            {
                'success': True,
                'message': 'Sucursal desactivada exitosamente.',
            },
            status=status.HTTP_200_OK,
        )
