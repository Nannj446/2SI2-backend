"""
Vistas para solicitudes de crédito
"""

from rest_framework import generics, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404

from api.core.permissions import HasPermission
from api.core.pagination import StandardResultsSetPagination
from .models import LoanApplication, LoanApplicationDocument, LoanApplicationComment
from .serializers.loan_serializers import (
    LoanApplicationSerializer,
    LoanApplicationListSerializer,
    CreateLoanApplicationSerializer,
    UpdateLoanApplicationSerializer,
    SubmitLoanApplicationSerializer,
    ReviewLoanApplicationSerializer,
    ApproveLoanApplicationSerializer,
    RejectLoanApplicationSerializer,
    DisburseLoanApplicationSerializer,
    LoanApplicationDocumentSerializer,
    LoanApplicationCommentSerializer,
)
from .services.loan_application_service import LoanApplicationService


class LoanApplicationListCreateAPIView(generics.ListCreateAPIView):
    """
    GET: Lista todas las solicitudes de crédito de la institución
    POST: Crea una nueva solicitud de crédito
    """
    permission_classes = [IsAuthenticated, HasPermission]
    required_permissions = {
        'GET': 'loans.view',
        'POST': 'loans.create',
    }
    pagination_class = StandardResultsSetPagination
    
    def get_queryset(self):
        queryset = LoanApplication.objects.filter(
            institution=self.request.user.institution,
            is_active=True
        ).select_related(
            'client', 'product', 'reviewed_by', 'approved_by'
        ).order_by('-created_at')
        
        # Filtros
        status_filter = self.request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        client_id = self.request.query_params.get('client')
        if client_id:
            queryset = queryset.filter(client_id=client_id)
        
        product_id = self.request.query_params.get('product')
        if product_id:
            queryset = queryset.filter(product_id=product_id)
        
        risk_level = self.request.query_params.get('risk_level')
        if risk_level:
            queryset = queryset.filter(risk_level=risk_level)
        
        return queryset
    
    def get_serializer_class(self):
        if self.request.method == 'POST':
            return CreateLoanApplicationSerializer
        return LoanApplicationListSerializer
    
    def perform_create(self, serializer):
        serializer.save()


class LoanApplicationDetailAPIView(generics.RetrieveUpdateDestroyAPIView):
    """
    GET: Obtiene detalle de una solicitud
    PATCH: Actualiza una solicitud (solo en borrador)
    DELETE: Desactiva una solicitud
    """
    permission_classes = [IsAuthenticated, HasPermission]
    required_permissions = {
        'GET': 'loans.view',
        'PATCH': 'loans.edit',
        'DELETE': 'loans.delete',
    }
    
    def get_queryset(self):
        return LoanApplication.objects.filter(
            institution=self.request.user.institution
        ).select_related(
            'client', 'product', 'reviewed_by', 'approved_by'
        ).prefetch_related('documents', 'comments')
    
    def get_serializer_class(self):
        if self.request.method == 'PATCH':
            return UpdateLoanApplicationSerializer
        return LoanApplicationSerializer
    
    def perform_destroy(self, instance):
        """Soft delete"""
        instance.is_active = False
        instance.save()


class LoanApplicationSubmitAPIView(generics.GenericAPIView):
    """POST: Enviar solicitud para revisión"""
    permission_classes = [IsAuthenticated, HasPermission]
    required_permissions = {'POST': 'loans.submit'}
    serializer_class = SubmitLoanApplicationSerializer
    
    def get_queryset(self):
        return LoanApplication.objects.filter(
            institution=self.request.user.institution
        )
    
    def post(self, request, pk):
        application = get_object_or_404(self.get_queryset(), pk=pk)
        serializer = self.get_serializer(application, data=request.data)
        serializer.is_valid(raise_exception=True)
        
        try:
            application = LoanApplicationService.submit_application(application)
            return Response(
                LoanApplicationSerializer(application).data,
                status=status.HTTP_200_OK
            )
        except ValueError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )


class LoanApplicationReviewAPIView(generics.GenericAPIView):
    """POST: Iniciar revisión y actualizar evaluación"""
    permission_classes = [IsAuthenticated, HasPermission]
    required_permissions = {'POST': 'loans.review'}
    serializer_class = ReviewLoanApplicationSerializer
    
    def get_queryset(self):
        return LoanApplication.objects.filter(
            institution=self.request.user.institution
        )
    
    def post(self, request, pk):
        application = get_object_or_404(self.get_queryset(), pk=pk)
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        try:
            # Iniciar revisión si está en estado SUBMITTED
            if application.status == LoanApplication.Status.SUBMITTED:
                application = LoanApplicationService.start_review(
                    application,
                    request.user
                )
            
            # Actualizar evaluación
            application = LoanApplicationService.update_evaluation(
                application,
                **serializer.validated_data
            )
            
            return Response(
                LoanApplicationSerializer(application).data,
                status=status.HTTP_200_OK
            )
        except ValueError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )


class LoanApplicationCalculateScoreAPIView(generics.GenericAPIView):
    """POST: Calcular score automático"""
    permission_classes = [IsAuthenticated, HasPermission]
    required_permissions = {'POST': 'loans.review'}
    
    def get_queryset(self):
        return LoanApplication.objects.filter(
            institution=self.request.user.institution
        )
    
    def post(self, request, pk):
        application = get_object_or_404(self.get_queryset(), pk=pk)
        
        # Calcular score
        score = LoanApplicationService.calculate_score(application)
        risk_level = LoanApplicationService.determine_risk_level(score)
        debt_ratio = LoanApplicationService.calculate_debt_to_income_ratio(application)
        
        # Actualizar aplicación
        application.credit_score = score
        application.risk_level = risk_level
        application.debt_to_income_ratio = debt_ratio
        application.save()
        
        return Response({
            'credit_score': score,
            'risk_level': risk_level,
            'debt_to_income_ratio': debt_ratio,
        }, status=status.HTTP_200_OK)


class LoanApplicationApproveAPIView(generics.GenericAPIView):
    """POST: Aprobar solicitud"""
    permission_classes = [IsAuthenticated, HasPermission]
    required_permissions = {'POST': 'loans.approve'}
    serializer_class = ApproveLoanApplicationSerializer
    
    def get_queryset(self):
        return LoanApplication.objects.filter(
            institution=self.request.user.institution
        )
    
    def post(self, request, pk):
        application = get_object_or_404(self.get_queryset(), pk=pk)
        serializer = self.get_serializer(application, data=request.data)
        serializer.is_valid(raise_exception=True)
        
        try:
            application = LoanApplicationService.approve_application(
                application,
                approver=request.user,
                **serializer.validated_data
            )
            return Response(
                LoanApplicationSerializer(application).data,
                status=status.HTTP_200_OK
            )
        except ValueError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )


class LoanApplicationRejectAPIView(generics.GenericAPIView):
    """POST: Rechazar solicitud"""
    permission_classes = [IsAuthenticated, HasPermission]
    required_permissions = {'POST': 'loans.reject'}
    serializer_class = RejectLoanApplicationSerializer
    
    def get_queryset(self):
        return LoanApplication.objects.filter(
            institution=self.request.user.institution
        )
    
    def post(self, request, pk):
        application = get_object_or_404(self.get_queryset(), pk=pk)
        serializer = self.get_serializer(application, data=request.data)
        serializer.is_valid(raise_exception=True)
        
        try:
            application = LoanApplicationService.reject_application(
                application,
                reviewer=request.user,
                **serializer.validated_data
            )
            return Response(
                LoanApplicationSerializer(application).data,
                status=status.HTTP_200_OK
            )
        except ValueError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )


class LoanApplicationDisburseAPIView(generics.GenericAPIView):
    """POST: Desembolsar solicitud aprobada"""
    permission_classes = [IsAuthenticated, HasPermission]
    required_permissions = {'POST': 'loans.disburse'}
    serializer_class = DisburseLoanApplicationSerializer
    
    def get_queryset(self):
        return LoanApplication.objects.filter(
            institution=self.request.user.institution
        )
    
    def post(self, request, pk):
        application = get_object_or_404(self.get_queryset(), pk=pk)
        serializer = self.get_serializer(application, data=request.data)
        serializer.is_valid(raise_exception=True)
        
        try:
            application = LoanApplicationService.disburse_application(
                application,
                **serializer.validated_data
            )
            return Response(
                LoanApplicationSerializer(application).data,
                status=status.HTTP_200_OK
            )
        except ValueError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )


class LoanApplicationDocumentListCreateAPIView(generics.ListCreateAPIView):
    """
    GET: Lista documentos de una solicitud
    POST: Sube un nuevo documento
    """
    permission_classes = [IsAuthenticated, HasPermission]
    required_permissions = {
        'GET': 'loans.view',
        'POST': 'loans.upload_documents',
    }
    serializer_class = LoanApplicationDocumentSerializer
    
    def get_queryset(self):
        application_id = self.kwargs.get('application_id')
        return LoanApplicationDocument.objects.filter(
            application_id=application_id,
            application__institution=self.request.user.institution
        ).select_related('uploaded_by', 'verified_by')
    
    def perform_create(self, serializer):
        application_id = self.kwargs.get('application_id')
        application = get_object_or_404(
            LoanApplication,
            id=application_id,
            institution=self.request.user.institution
        )
        
        file = self.request.FILES.get('file')
        serializer.save(
            application=application,
            institution=self.request.user.institution,
            uploaded_by=self.request.user,
            file_name=file.name if file else '',
            file_size=file.size if file else 0
        )


class LoanApplicationCommentListCreateAPIView(generics.ListCreateAPIView):
    """
    GET: Lista comentarios de una solicitud
    POST: Agrega un nuevo comentario
    """
    permission_classes = [IsAuthenticated, HasPermission]
    required_permissions = {
        'GET': 'loans.view',
        'POST': 'loans.comment',
    }
    serializer_class = LoanApplicationCommentSerializer
    
    def get_queryset(self):
        application_id = self.kwargs.get('application_id')
        return LoanApplicationComment.objects.filter(
            application_id=application_id,
            application__institution=self.request.user.institution
        ).select_related('user')
    
    def perform_create(self, serializer):
        application_id = self.kwargs.get('application_id')
        application = get_object_or_404(
            LoanApplication,
            id=application_id,
            institution=self.request.user.institution
        )
        
        serializer.save(
            application=application,
            institution=self.request.user.institution,
            user=self.request.user
        )
