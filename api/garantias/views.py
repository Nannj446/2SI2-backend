"""
API views for collateral (garantias) and guarantors.
"""

from rest_framework import status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from django.shortcuts import get_object_or_404

from api.core.pagination import StandardResultsSetPagination
from api.core.permissions import require_permission
from api.garantias.models import (
    Collateral,
    Guarantor,
    CollateralDocument,
    CollateralValuation,
)
from api.garantias.serializers import (
    CollateralListSerializer,
    CollateralDetailSerializer,
    CollateralCreateSerializer,
    CollateralUpdateSerializer,
    GuarantorListSerializer,
    GuarantorDetailSerializer,
    GuarantorCreateSerializer,
    GuarantorUpdateSerializer,
    CollateralDocumentSerializer,
    CollateralDocumentUploadSerializer,
    CollateralDocumentVerifySerializer,
    CollateralValuationSerializer,
    CollateralValuationCreateSerializer,
)
from api.garantias.services import (
    CollateralService,
    GuarantorService,
    CollateralDocumentService,
    CollateralValuationService,
    CollateralValidationError,
    GuarantorValidationError,
    CollateralDocumentError,
)


def _has_permission(request, permission_code: str) -> bool:
    """Helper to check permissions on the active tenant."""
    if not hasattr(request.user, 'profile'):
        return False

    if request.user.profile.is_saas_admin():
        return True

    if not request.tenant:
        return False

    return request.user.profile.has_permission(permission_code, request.tenant)


class CollateralListCreateAPIView(APIView):
    """
    GET /api/garantias/ - list collaterals
    POST /api/garantias/ - create collateral
    """

    permission_classes = [IsAuthenticated, require_permission('collaterals.view')]

    def get(self, request):
        institution_id = request.user_institution_id
        queryset = Collateral.objects.filter(
            institution_id=institution_id,
            is_active=True,
        ).select_related('loan_application', 'registered_by', 'approved_by')

        loan_application_id = request.query_params.get('loan_application')
        if loan_application_id and loan_application_id not in ('undefined', 'null'):
            queryset = queryset.filter(loan_application_id=loan_application_id)

        status_filter = request.query_params.get('status')
        if status_filter and status_filter not in ('undefined', 'null'):
            queryset = queryset.filter(status=status_filter)

        collateral_type = request.query_params.get('collateral_type')
        if collateral_type and collateral_type not in ('undefined', 'null'):
            queryset = queryset.filter(collateral_type=collateral_type)

        queryset = queryset.order_by('-created_at')

        paginator = StandardResultsSetPagination()
        paginated_queryset = paginator.paginate_queryset(queryset, request)
        serializer = CollateralListSerializer(paginated_queryset, many=True)
        return paginator.get_paginated_response(serializer.data)

    def post(self, request):
        if not _has_permission(request, 'collaterals.create'):
            return Response(
                {'success': False, 'message': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = CollateralCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {'success': False, 'message': 'Invalid data', 'errors': serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        loan_application = serializer.validated_data['loan_application']
        if loan_application.institution_id != request.user_institution_id:
            return Response(
                {'success': False, 'message': 'Loan application not found'},
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            collateral = CollateralService.create_collateral(
                user=request.user,
                loan_application=loan_application,
                data=serializer.validated_data,
            )
        except CollateralValidationError as exc:
            return Response(
                {'success': False, 'message': str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        response_serializer = CollateralDetailSerializer(collateral)
        return Response(
            {
                'success': True,
                'message': 'Collateral created',
                'collateral': response_serializer.data,
            },
            status=status.HTTP_201_CREATED,
        )


class CollateralDetailAPIView(APIView):
    """
    GET /api/garantias/{id}/ - get collateral
    PATCH /api/garantias/{id}/ - update collateral
    DELETE /api/garantias/{id}/ - deactivate collateral
    """

    permission_classes = [IsAuthenticated, require_permission('collaterals.view')]

    def get(self, request, collateral_id):
        collateral = get_object_or_404(
            Collateral.objects.select_related('loan_application', 'registered_by', 'approved_by'),
            id=collateral_id,
            institution_id=request.user_institution_id,
        )
        serializer = CollateralDetailSerializer(collateral)
        return Response({'success': True, 'collateral': serializer.data})

    def patch(self, request, collateral_id):
        if not _has_permission(request, 'collaterals.edit'):
            return Response(
                {'success': False, 'message': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN,
            )

        collateral = get_object_or_404(
            Collateral,
            id=collateral_id,
            institution_id=request.user_institution_id,
        )

        serializer = CollateralUpdateSerializer(
            collateral,
            data=request.data,
            partial=True,
        )
        if not serializer.is_valid():
            return Response(
                {'success': False, 'message': 'Invalid data', 'errors': serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            collateral = CollateralService.update_collateral(
                user=request.user,
                collateral=collateral,
                data=serializer.validated_data,
            )
        except CollateralValidationError as exc:
            return Response(
                {'success': False, 'message': str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        response_serializer = CollateralDetailSerializer(collateral)
        return Response({'success': True, 'collateral': response_serializer.data})

    def delete(self, request, collateral_id):
        if not _has_permission(request, 'collaterals.delete'):
            return Response(
                {'success': False, 'message': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN,
            )

        collateral = get_object_or_404(
            Collateral,
            id=collateral_id,
            institution_id=request.user_institution_id,
        )
        collateral.is_active = False
        collateral.save(update_fields=['is_active', 'updated_at'])
        return Response({'success': True, 'message': 'Collateral deactivated'})


class CollateralApproveAPIView(APIView):
    """POST /api/garantias/{id}/approve/"""

    permission_classes = [IsAuthenticated, require_permission('collaterals.approve')]

    def post(self, request, collateral_id):
        collateral = get_object_or_404(
            Collateral,
            id=collateral_id,
            institution_id=request.user_institution_id,
        )
        notes = request.data.get('notes', '')

        try:
            collateral = CollateralService.approve_collateral(
                user=request.user,
                collateral=collateral,
                notes=notes,
            )
        except CollateralValidationError as exc:
            return Response(
                {'success': False, 'message': str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = CollateralDetailSerializer(collateral)
        return Response({'success': True, 'collateral': serializer.data})


class CollateralRejectAPIView(APIView):
    """POST /api/garantias/{id}/reject/"""

    permission_classes = [IsAuthenticated, require_permission('collaterals.approve')]

    def post(self, request, collateral_id):
        collateral = get_object_or_404(
            Collateral,
            id=collateral_id,
            institution_id=request.user_institution_id,
        )
        reason = request.data.get('reason', '')

        try:
            collateral = CollateralService.reject_collateral(
                user=request.user,
                collateral=collateral,
                reason=reason,
            )
        except CollateralValidationError as exc:
            return Response(
                {'success': False, 'message': str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = CollateralDetailSerializer(collateral)
        return Response({'success': True, 'collateral': serializer.data})


class CollateralReleaseAPIView(APIView):
    """POST /api/garantias/{id}/release/"""

    permission_classes = [IsAuthenticated, require_permission('collaterals.approve')]

    def post(self, request, collateral_id):
        collateral = get_object_or_404(
            Collateral,
            id=collateral_id,
            institution_id=request.user_institution_id,
        )
        notes = request.data.get('notes', '')

        try:
            collateral = CollateralService.release_collateral(
                user=request.user,
                collateral=collateral,
                notes=notes,
            )
        except CollateralValidationError as exc:
            return Response(
                {'success': False, 'message': str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = CollateralDetailSerializer(collateral)
        return Response({'success': True, 'collateral': serializer.data})


class CollateralDocumentsAPIView(APIView):
    """
    GET /api/garantias/{id}/documents/ - list documents
    POST /api/garantias/{id}/documents/ - upload document
    """

    permission_classes = [IsAuthenticated, require_permission('collaterals.view')]
    parser_classes = [MultiPartParser, FormParser]

    def get(self, request, collateral_id):
        collateral = get_object_or_404(
            Collateral,
            id=collateral_id,
            institution_id=request.user_institution_id,
        )
        queryset = CollateralDocument.objects.filter(
            collateral=collateral,
        ).select_related('file_resource', 'uploaded_by', 'verified_by')

        paginator = StandardResultsSetPagination()
        paginated_queryset = paginator.paginate_queryset(queryset, request)
        serializer = CollateralDocumentSerializer(paginated_queryset, many=True)
        return paginator.get_paginated_response(serializer.data)

    def post(self, request, collateral_id):
        if not _has_permission(request, 'collaterals.edit'):
            return Response(
                {'success': False, 'message': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN,
            )

        collateral = get_object_or_404(
            Collateral,
            id=collateral_id,
            institution_id=request.user_institution_id,
        )

        serializer = CollateralDocumentUploadSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {'success': False, 'message': 'Invalid data', 'errors': serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            document = CollateralDocumentService.upload_document(
                collateral=collateral,
                document_type=serializer.validated_data['document_type'],
                file=serializer.validated_data['file'],
                uploaded_by=request.user,
                description=serializer.validated_data.get('description', ''),
                expiry_date=serializer.validated_data.get('expiry_date'),
                notes=serializer.validated_data.get('notes', ''),
            )
        except CollateralDocumentError as exc:
            return Response(
                {'success': False, 'message': str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        response_serializer = CollateralDocumentSerializer(document)
        return Response(
            {'success': True, 'document': response_serializer.data},
            status=status.HTTP_201_CREATED,
        )


class CollateralDocumentVerifyAPIView(APIView):
    """POST /api/garantias/documents/{id}/verify/"""

    permission_classes = [IsAuthenticated, require_permission('collaterals.approve')]

    def post(self, request, document_id):
        document = get_object_or_404(
            CollateralDocument,
            id=document_id,
            institution_id=request.user_institution_id,
        )

        serializer = CollateralDocumentVerifySerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {'success': False, 'message': 'Invalid data', 'errors': serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        document = CollateralDocumentService.verify_document(
            user=request.user,
            document=document,
            is_valid=serializer.validated_data['is_valid'],
            notes=serializer.validated_data.get('notes', ''),
        )

        response_serializer = CollateralDocumentSerializer(document)
        return Response({'success': True, 'document': response_serializer.data})


class CollateralValuationsAPIView(APIView):
    """
    GET /api/garantias/{id}/valuations/ - list valuations
    POST /api/garantias/{id}/valuations/ - create valuation
    """

    permission_classes = [IsAuthenticated, require_permission('collaterals.view')]

    def get(self, request, collateral_id):
        collateral = get_object_or_404(
            Collateral,
            id=collateral_id,
            institution_id=request.user_institution_id,
        )
        queryset = CollateralValuation.objects.filter(
            collateral=collateral,
        ).select_related('approved_by')

        paginator = StandardResultsSetPagination()
        paginated_queryset = paginator.paginate_queryset(queryset, request)
        serializer = CollateralValuationSerializer(paginated_queryset, many=True)
        return paginator.get_paginated_response(serializer.data)

    def post(self, request, collateral_id):
        if not _has_permission(request, 'collaterals.manage_valuations'):
            return Response(
                {'success': False, 'message': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN,
            )

        collateral = get_object_or_404(
            Collateral,
            id=collateral_id,
            institution_id=request.user_institution_id,
        )

        serializer = CollateralValuationCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {'success': False, 'message': 'Invalid data', 'errors': serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        valuation = CollateralValuationService.create_valuation(
            user=request.user,
            collateral=collateral,
            data=serializer.validated_data,
        )

        response_serializer = CollateralValuationSerializer(valuation)
        return Response(
            {'success': True, 'valuation': response_serializer.data},
            status=status.HTTP_201_CREATED,
        )


class CollateralValuationApproveAPIView(APIView):
    """POST /api/garantias/valuations/{id}/approve/"""

    permission_classes = [IsAuthenticated, require_permission('collaterals.manage_valuations')]

    def post(self, request, valuation_id):
        valuation = get_object_or_404(
            CollateralValuation,
            id=valuation_id,
            institution_id=request.user_institution_id,
        )

        valuation = CollateralValuationService.approve_valuation(
            user=request.user,
            valuation=valuation,
        )

        serializer = CollateralValuationSerializer(valuation)
        return Response({'success': True, 'valuation': serializer.data})


class GuarantorListCreateAPIView(APIView):
    """
    GET /api/garantias/guarantors/ - list guarantors
    POST /api/garantias/guarantors/ - create guarantor
    """

    permission_classes = [IsAuthenticated, require_permission('guarantors.view')]

    def get(self, request):
        queryset = Guarantor.objects.filter(
            institution_id=request.user_institution_id,
            is_active=True,
        ).select_related('loan_application', 'approved_by')

        loan_application_id = request.query_params.get('loan_application')
        if loan_application_id and loan_application_id not in ('undefined', 'null'):
            queryset = queryset.filter(loan_application_id=loan_application_id)

        status_filter = request.query_params.get('status')
        if status_filter and status_filter not in ('undefined', 'null'):
            queryset = queryset.filter(status=status_filter)

        queryset = queryset.order_by('-created_at')

        paginator = StandardResultsSetPagination()
        paginated_queryset = paginator.paginate_queryset(queryset, request)
        serializer = GuarantorListSerializer(paginated_queryset, many=True)
        return paginator.get_paginated_response(serializer.data)

    def post(self, request):
        if not _has_permission(request, 'guarantors.create'):
            return Response(
                {'success': False, 'message': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = GuarantorCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {'success': False, 'message': 'Invalid data', 'errors': serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        loan_application = serializer.validated_data['loan_application']
        if loan_application.institution_id != request.user_institution_id:
            return Response(
                {'success': False, 'message': 'Loan application not found'},
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            guarantor = GuarantorService.create_guarantor(
                user=request.user,
                loan_application=loan_application,
                data=serializer.validated_data,
            )
        except GuarantorValidationError as exc:
            return Response(
                {'success': False, 'message': str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        response_serializer = GuarantorDetailSerializer(guarantor)
        return Response(
            {
                'success': True,
                'message': 'Guarantor created',
                'guarantor': response_serializer.data,
            },
            status=status.HTTP_201_CREATED,
        )


class GuarantorDetailAPIView(APIView):
    """
    GET /api/garantias/guarantors/{id}/ - get guarantor
    PATCH /api/garantias/guarantors/{id}/ - update guarantor
    DELETE /api/garantias/guarantors/{id}/ - deactivate guarantor
    """

    permission_classes = [IsAuthenticated, require_permission('guarantors.view')]

    def get(self, request, guarantor_id):
        guarantor = get_object_or_404(
            Guarantor,
            id=guarantor_id,
            institution_id=request.user_institution_id,
        )
        serializer = GuarantorDetailSerializer(guarantor)
        return Response({'success': True, 'guarantor': serializer.data})

    def patch(self, request, guarantor_id):
        if not _has_permission(request, 'guarantors.edit'):
            return Response(
                {'success': False, 'message': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN,
            )

        guarantor = get_object_or_404(
            Guarantor,
            id=guarantor_id,
            institution_id=request.user_institution_id,
        )

        serializer = GuarantorUpdateSerializer(
            guarantor,
            data=request.data,
            partial=True,
        )
        if not serializer.is_valid():
            return Response(
                {'success': False, 'message': 'Invalid data', 'errors': serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            guarantor = GuarantorService.update_guarantor(
                user=request.user,
                guarantor=guarantor,
                data=serializer.validated_data,
            )
        except GuarantorValidationError as exc:
            return Response(
                {'success': False, 'message': str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        response_serializer = GuarantorDetailSerializer(guarantor)
        return Response({'success': True, 'guarantor': response_serializer.data})

    def delete(self, request, guarantor_id):
        if not _has_permission(request, 'guarantors.edit'):
            return Response(
                {'success': False, 'message': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN,
            )

        guarantor = get_object_or_404(
            Guarantor,
            id=guarantor_id,
            institution_id=request.user_institution_id,
        )
        guarantor.is_active = False
        guarantor.save(update_fields=['is_active', 'updated_at'])
        return Response({'success': True, 'message': 'Guarantor deactivated'})


class GuarantorApproveAPIView(APIView):
    """POST /api/garantias/guarantors/{id}/approve/"""

    permission_classes = [IsAuthenticated, require_permission('guarantors.approve')]

    def post(self, request, guarantor_id):
        guarantor = get_object_or_404(
            Guarantor,
            id=guarantor_id,
            institution_id=request.user_institution_id,
        )

        try:
            guarantor = GuarantorService.approve_guarantor(
                user=request.user,
                guarantor=guarantor,
            )
        except GuarantorValidationError as exc:
            return Response(
                {'success': False, 'message': str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = GuarantorDetailSerializer(guarantor)
        return Response({'success': True, 'guarantor': serializer.data})


class GuarantorRejectAPIView(APIView):
    """POST /api/garantias/guarantors/{id}/reject/"""

    permission_classes = [IsAuthenticated, require_permission('guarantors.approve')]

    def post(self, request, guarantor_id):
        guarantor = get_object_or_404(
            Guarantor,
            id=guarantor_id,
            institution_id=request.user_institution_id,
        )
        reason = request.data.get('reason', '')

        try:
            guarantor = GuarantorService.reject_guarantor(
                user=request.user,
                guarantor=guarantor,
                reason=reason,
            )
        except GuarantorValidationError as exc:
            return Response(
                {'success': False, 'message': str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = GuarantorDetailSerializer(guarantor)
        return Response({'success': True, 'guarantor': serializer.data})
