"""
Vistas para gestión de suscripciones SaaS.
"""

from decimal import Decimal
from rest_framework import generics, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from django.shortcuts import get_object_or_404
from django.http import Http404
from django.db.models import Count, Q, Sum
from django.contrib.auth import get_user_model
from drf_spectacular.utils import extend_schema, extend_schema_view

from .models import SubscriptionPlan, Subscription, Invoice, Payment, StripeWebhookEvent
from .services import _sanitize_for_json
from .serializers import (
    SubscriptionPlanSerializer,
    SubscriptionPlanListSerializer,
    CreateSubscriptionPlanSerializer,
    UpdateSubscriptionPlanSerializer,
    SubscriptionSerializer,
    SubscriptionListSerializer,
    CreateSubscriptionSerializer,
    UpdateSubscriptionSerializer,
    ActivateSubscriptionSerializer,
    SuspendSubscriptionSerializer,
    CancelSubscriptionSerializer,
    InvoiceSerializer,
    PaymentSerializer,
)
from api.core.permissions import IsSaaSAdmin
from api.core.pagination import StandardResultsSetPagination
from api.tenants.models import FinancialInstitution

User = get_user_model()


# ============================================================
# VISTAS DE PLANES DE SUSCRIPCIÓN
# ============================================================

@extend_schema_view(
    get=extend_schema(
        summary="Listar planes de suscripción",
        description="Obtiene la lista de todos los planes de suscripción disponibles",
        tags=["SaaS - Planes"]
    ),
    post=extend_schema(
        summary="Crear plan de suscripción",
        description="Crea un nuevo plan de suscripción (solo SaaS Admin)",
        tags=["SaaS - Planes"]
    )
)
class SubscriptionPlanListCreateAPIView(generics.ListCreateAPIView):
    """
    Vista para listar y crear planes de suscripción.
    
    GET: Lista todos los planes (públicos si is_active=True)
    POST: Crea un nuevo plan (solo SaaS Admin)
    """
    queryset = SubscriptionPlan.objects.all()
    pagination_class = StandardResultsSetPagination
    
    def get_serializer_class(self):
        if self.request.method == 'POST':
            return CreateSubscriptionPlanSerializer
        return SubscriptionPlanSerializer  # Usar serializer completo en lugar del simplificado
    
    def get_permissions(self):
        if self.request.method == 'POST':
            return [IsAuthenticated(), IsSaaSAdmin()]
        return []
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filtrar solo planes activos para usuarios no admin
        if not self.request.user.is_authenticated or not (
            hasattr(self.request.user, 'profile') and 
            self.request.user.profile.is_saas_admin()
        ):
            queryset = queryset.filter(is_active=True)
        
        # Ordenar por display_order y precio
        return queryset.order_by('display_order', 'price')


@extend_schema_view(
    get=extend_schema(
        summary="Obtener detalle de plan",
        description="Obtiene los detalles completos de un plan de suscripción",
        tags=["SaaS - Planes"]
    ),
    patch=extend_schema(
        summary="Actualizar plan",
        description="Actualiza un plan de suscripción existente (solo SaaS Admin)",
        tags=["SaaS - Planes"]
    ),
    delete=extend_schema(
        summary="Desactivar plan",
        description="Desactiva un plan de suscripción (solo SaaS Admin)",
        tags=["SaaS - Planes"]
    )
)
class SubscriptionPlanDetailAPIView(generics.RetrieveUpdateDestroyAPIView):
    """
    Vista para obtener, actualizar y desactivar planes de suscripción.
    
    GET: Obtiene detalle del plan
    PATCH: Actualiza el plan (solo SaaS Admin)
    DELETE: Desactiva el plan (solo SaaS Admin)
    """
    queryset = SubscriptionPlan.objects.all()
    serializer_class = SubscriptionPlanSerializer
    lookup_field = 'id'
    
    def get_serializer_class(self):
        if self.request.method == 'PATCH':
            return UpdateSubscriptionPlanSerializer
        return SubscriptionPlanSerializer
    
    def get_permissions(self):
        if self.request.method in ['PATCH', 'DELETE']:
            return [IsAuthenticated(), IsSaaSAdmin()]
        return []
    
    def perform_destroy(self, instance):
        """Desactiva el plan en lugar de eliminarlo."""
        instance.is_active = False
        instance.save()


# ============================================================
# VISTAS DE SUSCRIPCIONES
# ============================================================

@extend_schema_view(
    get=extend_schema(
        summary="Listar suscripciones",
        description="Obtiene la lista de todas las suscripciones (solo SaaS Admin)",
        tags=["SaaS - Suscripciones"]
    ),
    post=extend_schema(
        summary="Crear suscripción",
        description="Crea una nueva suscripción para una institución (solo SaaS Admin)",
        tags=["SaaS - Suscripciones"]
    )
)
class SubscriptionListCreateAPIView(generics.ListCreateAPIView):
    """
    Vista para listar y crear suscripciones.
    
    GET: Lista todas las suscripciones (solo SaaS Admin)
    POST: Crea una nueva suscripción (solo SaaS Admin)
    """
    queryset = Subscription.objects.select_related('institution', 'plan').all()
    permission_classes = [IsAuthenticated, IsSaaSAdmin]
    pagination_class = StandardResultsSetPagination
    
    def get_serializer_class(self):
        if self.request.method == 'POST':
            return CreateSubscriptionSerializer
        return SubscriptionListSerializer
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filtros opcionales
        status = self.request.query_params.get('status')
        payment_status = self.request.query_params.get('payment_status')
        institution_id = self.request.query_params.get('institution')
        
        if status:
            queryset = queryset.filter(status=status)
        
        if payment_status:
            queryset = queryset.filter(payment_status=payment_status)
        
        if institution_id:
            queryset = queryset.filter(institution_id=institution_id)
        
        return queryset.order_by('-created_at')


@extend_schema_view(
    get=extend_schema(
        summary="Obtener detalle de suscripción",
        description="Obtiene los detalles completos de una suscripción",
        tags=["SaaS - Suscripciones"]
    ),
    patch=extend_schema(
        summary="Actualizar suscripción",
        description="Actualiza una suscripción existente (solo SaaS Admin)",
        tags=["SaaS - Suscripciones"]
    ),
    delete=extend_schema(
        summary="Cancelar suscripción",
        description="Cancela una suscripción (solo SaaS Admin)",
        tags=["SaaS - Suscripciones"]
    )
)
class SubscriptionDetailAPIView(generics.RetrieveUpdateDestroyAPIView):
    """
    Vista para obtener, actualizar y cancelar suscripciones.
    
    GET: Obtiene detalle de la suscripción
    PATCH: Actualiza la suscripción (solo SaaS Admin)
    DELETE: Cancela la suscripción (solo SaaS Admin)
    """
    queryset = Subscription.objects.select_related('institution', 'plan').all()
    serializer_class = SubscriptionSerializer
    permission_classes = [IsAuthenticated, IsSaaSAdmin]
    lookup_field = 'id'
    
    def get_serializer_class(self):
        if self.request.method == 'PATCH':
            return UpdateSubscriptionSerializer
        return SubscriptionSerializer
    
    def perform_destroy(self, instance):
        """Cancela la suscripción en lugar de eliminarla."""
        instance.cancel_subscription(reason="Cancelada por administrador")


# ============================================================
# ACCIONES ESPECIALES DE SUSCRIPCIONES
# ============================================================

@extend_schema(
    summary="Activar suscripción",
    description="Activa una suscripción después del período de prueba",
    tags=["SaaS - Suscripciones"],
    request=ActivateSubscriptionSerializer,
    responses={200: SubscriptionSerializer}
)
class ActivateSubscriptionAPIView(generics.GenericAPIView):
    """
    Vista para activar una suscripción después del trial.
    """
    queryset = Subscription.objects.all()
    serializer_class = ActivateSubscriptionSerializer
    permission_classes = [IsAuthenticated, IsSaaSAdmin]
    lookup_field = 'id'
    
    def post(self, request, *args, **kwargs):
        subscription = self.get_object()
        
        if subscription.status != 'TRIAL':
            return Response(
                {'error': 'Solo se pueden activar suscripciones en período de prueba'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # Activar suscripción
        subscription.activate_subscription()
        
        # Agregar información de pago si se proporcionó
        if serializer.validated_data.get('payment_method'):
            subscription.notes = f"Método de pago: {serializer.validated_data['payment_method']}"
            if serializer.validated_data.get('transaction_id'):
                subscription.notes += f"\nID de transacción: {serializer.validated_data['transaction_id']}"
            subscription.save()
        
        return Response(
            SubscriptionSerializer(subscription).data,
            status=status.HTTP_200_OK
        )


@extend_schema(
    summary="Suspender suscripción",
    description="Suspende una suscripción activa",
    tags=["SaaS - Suscripciones"],
    request=SuspendSubscriptionSerializer,
    responses={200: SubscriptionSerializer}
)
class SuspendSubscriptionAPIView(generics.GenericAPIView):
    """
    Vista para suspender una suscripción.
    """
    queryset = Subscription.objects.all()
    serializer_class = SuspendSubscriptionSerializer
    permission_classes = [IsAuthenticated, IsSaaSAdmin]
    lookup_field = 'id'
    
    def post(self, request, *args, **kwargs):
        subscription = self.get_object()
        
        if subscription.status not in ['TRIAL', 'ACTIVE']:
            return Response(
                {'error': 'Solo se pueden suspender suscripciones activas o en prueba'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # Suspender suscripción
        subscription.suspend_subscription(
            reason=serializer.validated_data['reason']
        )
        
        return Response(
            SubscriptionSerializer(subscription).data,
            status=status.HTTP_200_OK
        )


@extend_schema(
    summary="Cancelar suscripción",
    description="Cancela una suscripción",
    tags=["SaaS - Suscripciones"],
    request=CancelSubscriptionSerializer,
    responses={200: SubscriptionSerializer}
)
class CancelSubscriptionAPIView(generics.GenericAPIView):
    """
    Vista para cancelar una suscripción.
    """
    queryset = Subscription.objects.all()
    serializer_class = CancelSubscriptionSerializer
    permission_classes = [IsAuthenticated, IsSaaSAdmin]
    lookup_field = 'id'
    
    def post(self, request, *args, **kwargs):
        subscription = self.get_object()
        
        if subscription.status == 'CANCELLED':
            return Response(
                {'error': 'Esta suscripción ya está cancelada'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # Cancelar suscripción
        subscription.cancel_subscription(
            reason=serializer.validated_data['reason']
        )
        
        return Response(
            SubscriptionSerializer(subscription).data,
            status=status.HTTP_200_OK
        )


@extend_schema(
    summary="Obtener mi suscripción",
    description="Obtiene la suscripción de la institución del usuario autenticado",
    tags=["SaaS - Suscripciones"],
    responses={200: SubscriptionSerializer}
)
class MySubscriptionAPIView(generics.RetrieveAPIView):
    """
    Vista para que una institución obtenga su propia suscripción.
    """
    serializer_class = SubscriptionSerializer
    permission_classes = [IsAuthenticated]
    
    def get_object(self):
        """Obtiene la suscripción de la institución del usuario."""
        from django.http import Http404
        
        user = self.request.user
        
        # Obtener la institución del usuario a través de membresías
        membership = user.institution_memberships.filter(is_active=True).first()
        if not membership:
            raise Http404('Usuario no pertenece a ninguna institución')
        
        try:
            return Subscription.objects.select_related('plan').get(
                institution=membership.institution
            )
        except Subscription.DoesNotExist:
            raise Http404('No se encontró suscripción para esta institución')
    
    def retrieve(self, request, *args, **kwargs):
        """Maneja la respuesta cuando no hay suscripción."""
        try:
            return super().retrieve(request, *args, **kwargs)
        except Http404:
            # Obtener información de la institución del usuario
            membership = request.user.institution_memberships.filter(is_active=True).first()
            institution_info = None
            if membership:
                institution_info = {
                    'id': membership.institution.id,
                    'name': membership.institution.name,
                }
            
            # Si no hay suscripción, retornar información útil
            return Response({
                'has_subscription': False,
                'message': 'No tienes una suscripción activa',
                'institution': institution_info,
                'available_plans_url': '/api/saas/plans/',
            }, status=status.HTTP_200_OK)


@extend_schema(
    summary="Cambiar plan de suscripción",
    description="Permite a un administrador de institución cambiar el plan de suscripción",
    tags=["SaaS - Suscripciones"],
    request={
        "application/json": {
            "type": "object",
            "properties": {
                "plan_id": {
                    "type": "integer",
                    "description": "ID del nuevo plan de suscripción"
                }
            },
            "required": ["plan_id"]
        }
    },
    responses={200: SubscriptionSerializer}
)
class ChangeMySubscriptionPlanAPIView(generics.GenericAPIView):
    """
    Vista para que un administrador de institución cambie el plan de suscripción.
    
    Solo los usuarios con rol de administrador en su institución pueden cambiar el plan.
    """
    serializer_class = SubscriptionSerializer
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        """Cambia el plan de suscripción de la institución."""
        user = request.user
        
        # Obtener la institución del usuario
        membership = user.institution_memberships.filter(is_active=True).first()
        if not membership:
            return Response(
                {'error': 'Usuario no pertenece a ninguna institución'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        institution = membership.institution
        
        # Verificar que el usuario sea administrador de la institución
        from api.roles.models import UserRole
        is_admin = UserRole.objects.filter(
            user=user,
            institution=institution,
            role__name__icontains='Administrador',
            is_active=True
        ).exists()
        
        if not is_admin:
            return Response(
                {'error': 'Solo los administradores de la institución pueden cambiar el plan de suscripción'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Obtener la suscripción actual
        try:
            subscription = Subscription.objects.select_related('plan').get(
                institution=institution
            )
        except Subscription.DoesNotExist:
            return Response(
                {'error': 'No se encontró suscripción para esta institución'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Validar que se envió el plan_id
        plan_id = request.data.get('plan_id')
        if not plan_id:
            return Response(
                {'error': 'Se requiere el campo plan_id'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Obtener el nuevo plan
        try:
            new_plan = SubscriptionPlan.objects.get(id=plan_id, is_active=True)
        except SubscriptionPlan.DoesNotExist:
            return Response(
                {'error': 'Plan de suscripción no encontrado o no disponible'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Verificar que no sea el mismo plan
        if subscription.plan.id == new_plan.id:
            return Response(
                {'error': 'Ya tienes este plan activo'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Cambiar el plan a través del servicio de Stripe
        from .services import StripeSubscriptionService
        from django.db import transaction
        
        stripe_service = StripeSubscriptionService()
        old_plan_name = subscription.plan.name
        
        try:
            with transaction.atomic():
                result = stripe_service.change_plan(subscription, new_plan)
                
                if result.get('requires_checkout'):
                    return Response({
                        'requires_checkout': True,
                        'url': result.get('url'),
                        'session_id': result.get('session_id'),
                        'message': result.get('message'),
                    }, status=status.HTTP_200_OK)
                
                # Agregar nota del cambio
                note = f"Plan cambiado de '{old_plan_name}' a '{new_plan.name}' por {user.email}. Detalle: {result.get('message', '')}"
                if subscription.notes:
                    subscription.notes += f"\n{note}"
                else:
                    subscription.notes = note
                subscription.save()
                
                # Serializar y retornar
                serializer = self.get_serializer(subscription)
                data = serializer.data
                data['message'] = result.get('message')
                return Response(data, status=status.HTTP_200_OK)
        except ValueError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            return Response(
                {'error': f'Error al cambiar de plan: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


# ============================================================
# VISTAS DE ADMINISTRACIÓN SAAS
# ============================================================

@extend_schema(
    summary="Obtener estadísticas del sistema SaaS",
    description="Obtiene estadísticas generales del sistema para el panel de administración SaaS",
    tags=["SaaS - Admin"],
    responses={200: {
        "type": "object",
        "properties": {
            "total_institutions": {"type": "integer"},
            "active_institutions": {"type": "integer"},
            "total_subscriptions": {"type": "integer"},
            "active_subscriptions": {"type": "integer"},
            "trial_subscriptions": {"type": "integer"},
            "total_users": {"type": "integer"},
            "total_revenue": {"type": "string"},
            "monthly_revenue": {"type": "string"},
        }
    }}
)
class SaaSStatsAPIView(APIView):
    """
    Vista para obtener estadísticas del sistema SaaS.
    """
    permission_classes = [IsAuthenticated, IsSaaSAdmin]
    
    def get(self, request):
        """Obtiene estadísticas generales del sistema."""
        
        # Estadísticas de instituciones
        total_institutions = FinancialInstitution.objects.count()
        active_institutions = FinancialInstitution.objects.filter(is_active=True).count()
        
        # Estadísticas de suscripciones
        total_subscriptions = Subscription.objects.count()
        active_subscriptions = Subscription.objects.filter(status='ACTIVE').count()
        trial_subscriptions = Subscription.objects.filter(status='TRIAL').count()
        suspended_subscriptions = Subscription.objects.filter(status='SUSPENDED').count()
        cancelled_subscriptions = Subscription.objects.filter(status='CANCELLED').count()
        
        # Estadísticas de usuarios
        total_users = User.objects.count()
        
        # Ingresos (suma de total_paid de todas las suscripciones)
        revenue_data = Subscription.objects.aggregate(
            total_revenue=Sum('total_paid')
        )
        total_revenue = revenue_data['total_revenue'] or 0
        
        # Ingresos mensuales estimados (suma de amount_due de suscripciones activas)
        monthly_revenue_data = Subscription.objects.filter(
            status__in=['ACTIVE', 'TRIAL']
        ).aggregate(
            monthly_revenue=Sum('amount_due')
        )
        monthly_revenue = monthly_revenue_data['monthly_revenue'] or 0
        
        # Instituciones por tipo
        from django.db.models import Count
        institutions_by_type = {}
        type_counts = FinancialInstitution.objects.values('institution_type').annotate(
            count=Count('id')
        )
        for item in type_counts:
            institutions_by_type[item['institution_type']] = item['count']
        
        # Total de roles en el sistema
        from api.roles.models import Role
        total_roles = Role.objects.count()
        
        return Response({
            'total_institutions': total_institutions,
            'active_institutions': active_institutions,
            'inactive_institutions': total_institutions - active_institutions,
            'total_subscriptions': total_subscriptions,
            'active_subscriptions': active_subscriptions,
            'trial_subscriptions': trial_subscriptions,
            'suspended_subscriptions': suspended_subscriptions,
            'cancelled_subscriptions': cancelled_subscriptions,
            'total_users': total_users,
            'total_revenue': str(total_revenue),
            'monthly_revenue': str(monthly_revenue),
            'institutions_by_type': institutions_by_type,
            'total_roles': total_roles,
        })


@extend_schema(
    summary="Listar instituciones (tenants)",
    description="Obtiene la lista de todas las instituciones financieras registradas",
    tags=["SaaS - Admin"]
)
class TenantListAPIView(generics.ListAPIView):
    """
    Vista para listar todas las instituciones (tenants).
    """
    permission_classes = [IsAuthenticated, IsSaaSAdmin]
    pagination_class = StandardResultsSetPagination
    
    def get_queryset(self):
        queryset = FinancialInstitution.objects.annotate(
            users_count=Count('memberships', filter=Q(memberships__is_active=True), distinct=True),
            roles_count=Count('role_set', distinct=True)
        ).select_related('subscription').all()
        
        # Filtros opcionales
        status_filter = self.request.query_params.get('status')
        search = self.request.query_params.get('search')
        
        if status_filter == 'active':
            queryset = queryset.filter(is_active=True)
        elif status_filter == 'inactive':
            queryset = queryset.filter(is_active=False)
        
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) |
                Q(slug__icontains=search)
            )
        
        return queryset.order_by('-created_at')
    
    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        page = self.paginate_queryset(queryset)
        
        data = []
        for institution in (page if page is not None else queryset):
            # Obtener suscripción
            try:
                subscription = Subscription.objects.get(institution=institution)
                subscription_data = {
                    'id': subscription.id,
                    'plan_name': subscription.plan.name,
                    'status': subscription.status,
                    'start_date': subscription.start_date,
                }
            except Subscription.DoesNotExist:
                subscription_data = None
            
            data.append({
                'id': institution.id,
                'name': institution.name,
                'slug': institution.slug,
                'institution_type': institution.institution_type,
                'is_active': institution.is_active,
                'users_count': institution.users_count,
                'roles_count': institution.roles_count,
                'subscription': subscription_data,
                'created_at': institution.created_at,
            })
        
        if page is not None:
            return self.get_paginated_response(data)
        
        return Response(data)


@extend_schema(
    summary="Obtener detalle de institución",
    description="Obtiene los detalles completos de una institución específica",
    tags=["SaaS - Admin"]
)
class TenantDetailAPIView(APIView):
    """
    Vista para obtener el detalle de una institución específica.
    """
    permission_classes = [IsAuthenticated, IsSaaSAdmin]
    
    def get(self, request, id):
        """Obtiene el detalle de una institución."""
        try:
            institution = FinancialInstitution.objects.annotate(
                users_count=Count('memberships', filter=Q(memberships__is_active=True), distinct=True),
                roles_count=Count('role_set', distinct=True)
            ).get(id=id)
        except FinancialInstitution.DoesNotExist:
            return Response(
                {'error': 'Institución no encontrada'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Obtener suscripción con límites del plan
        try:
            subscription = Subscription.objects.select_related('plan').get(institution=institution)
            subscription_data = {
                'id': subscription.id,
                'plan_name': subscription.plan.name,
                'status': subscription.status,
                'start_date': subscription.start_date,
                'end_date': subscription.end_date,
                'current_users': subscription.current_users,
                'current_branches': subscription.current_branches,
                'current_products': subscription.current_products,
                'current_storage_gb': float(subscription.current_storage_gb),
                # Límites del plan
                'max_users': subscription.plan.max_users,
                'max_branches': subscription.plan.max_branches,
                'max_products': subscription.plan.max_products,
                'max_storage_gb': subscription.plan.max_storage_gb,
                # Porcentajes de uso
                'usage_percentage': subscription.get_usage_percentage(),
                'is_within_limits': subscription.is_within_limits(),
            }
        except Subscription.DoesNotExist:
            subscription_data = None
        
        # Obtener estadísticas de usuarios
        from api.roles.models import UserRole
        total_users = institution.memberships.filter(is_active=True).count()
        users_with_roles = UserRole.objects.filter(
            institution=institution,
            is_active=True
        ).values('user').distinct().count()
        
        # Obtener estadísticas de roles
        from api.roles.models import Role
        total_roles = Role.objects.filter(institution=institution).count()
        active_roles = Role.objects.filter(institution=institution, is_active=True).count()
        
        # Obtener todos los usuarios de la institución (activos e inactivos)
        all_memberships = institution.memberships.select_related('user').order_by('-created_at')
        
        all_users = []
        for membership in all_memberships:
            user = membership.user
            all_users.append({
                'id': user.id,
                'email': user.email,
                'full_name': user.get_full_name() if hasattr(user, 'get_full_name') else f"{user.first_name} {user.last_name}".strip() or user.email,
                'joined_at': membership.created_at,
                'is_active': membership.is_active,
            })
        
        # Construir respuesta
        data = {
            'id': institution.id,
            'name': institution.name,
            'slug': institution.slug,
            'institution_type': institution.institution_type,
            'is_active': institution.is_active,
            'created_at': institution.created_at,
            'updated_at': institution.updated_at,
            'created_by': {
                'id': institution.created_by.id,
                'email': institution.created_by.email,
                'full_name': institution.created_by.get_full_name() if hasattr(institution.created_by, 'get_full_name') else f"{institution.created_by.first_name} {institution.created_by.last_name}".strip() or institution.created_by.email,
            } if institution.created_by else None,
            'users_count': institution.users_count,
            'roles_count': institution.roles_count,
            'subscription': subscription_data,
            'stats': {
                'total_users': total_users,
                'users_with_roles': users_with_roles,
                'users_without_roles': total_users - users_with_roles,
                'total_roles': total_roles,
                'active_roles': active_roles,
                'inactive_roles': total_roles - active_roles,
            },
            'all_users': all_users,
        }
        
        return Response(data)


@extend_schema(
    summary="Listar permisos del sistema",
    description="Obtiene la lista de todos los permisos disponibles en el sistema",
    tags=["SaaS - Admin"]
)
class PermissionListAPIView(APIView):
    """
    Vista para listar todos los permisos del sistema.
    """
    permission_classes = [IsAuthenticated, IsSaaSAdmin]
    
    def get(self, request):
        """Obtiene la lista de permisos en formato plano."""
        from django.contrib.auth.models import Permission
        from django.contrib.contenttypes.models import ContentType
        
        # Obtener todos los permisos
        permissions = Permission.objects.select_related('content_type').all()
        
        # Filtros opcionales
        search = request.query_params.get('search')
        module = request.query_params.get('module')
        is_active = request.query_params.get('is_active')
        
        if search:
            permissions = permissions.filter(
                Q(name__icontains=search) |
                Q(codename__icontains=search)
            )
        
        if module:
            permissions = permissions.filter(content_type__app_label=module)
        
        # Convertir a lista plana
        permissions_list = []
        for perm in permissions:
            permissions_list.append({
                'id': perm.id,
                'name': perm.name,
                'code': perm.codename,
                'description': perm.name,
                'module': perm.content_type.app_label,
                'is_active': True,  # Los permisos de Django siempre están activos
                'created_at': None,
                'updated_at': None,
            })
        
        return Response(permissions_list)


# ============================================================
# VISTAS DE GESTIÓN DE PERMISOS SAAS
# ============================================================

@extend_schema(
    summary="Obtener detalle de permiso",
    description="Obtiene los detalles de un permiso específico",
    tags=["SaaS - Permisos"]
)
class PermissionDetailAPIView(APIView):
    """
    Vista para obtener el detalle de un permiso específico.
    """
    permission_classes = [IsAuthenticated, IsSaaSAdmin]
    
    def get(self, request, id):
        """Obtiene el detalle de un permiso."""
        from django.contrib.auth.models import Permission
        
        try:
            permission = Permission.objects.select_related('content_type').get(id=id)
        except Permission.DoesNotExist:
            return Response(
                {'error': 'Permiso no encontrado'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        data = {
            'id': permission.id,
            'name': permission.name,
            'code': permission.codename,
            'description': permission.name,
            'module': permission.content_type.app_label,
            'is_active': True,
            'created_at': None,
            'updated_at': None,
        }
        
        return Response(data)
    
    def patch(self, request, id):
        """Actualiza un permiso (limitado)."""
        return Response(
            {'error': 'Los permisos del sistema no se pueden modificar directamente'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    def delete(self, request, id):
        """Elimina un permiso (no permitido)."""
        return Response(
            {'error': 'Los permisos del sistema no se pueden eliminar'},
            status=status.HTTP_400_BAD_REQUEST
        )


@extend_schema(
    summary="Crear permiso personalizado",
    description="Crea un nuevo permiso personalizado (no implementado)",
    tags=["SaaS - Permisos"]
)
class PermissionCreateAPIView(APIView):
    """
    Vista para crear permisos personalizados.
    """
    permission_classes = [IsAuthenticated, IsSaaSAdmin]
    
    def post(self, request):
        """Crea un permiso personalizado."""
        return Response(
            {'error': 'La creación de permisos personalizados no está implementada'},
            status=status.HTTP_501_NOT_IMPLEMENTED
        )


@extend_schema(
    summary="Sincronizar permisos",
    description="Sincroniza los permisos del sistema con la base de datos",
    tags=["SaaS - Permisos"]
)
class PermissionSyncAPIView(APIView):
    """
    Vista para sincronizar permisos del sistema.
    """
    permission_classes = [IsAuthenticated, IsSaaSAdmin]
    
    def post(self, request):
        """Sincroniza permisos del sistema."""
        from django.core.management import call_command
        from io import StringIO
        
        try:
            # Ejecutar migrate para crear permisos
            out = StringIO()
            call_command('migrate', '--run-syncdb', stdout=out)
            
            from django.contrib.auth.models import Permission
            total_permissions = Permission.objects.count()
            
            return Response({
                'message': 'Permisos sincronizados correctamente',
                'total_permissions': total_permissions,
                'permissions_added': 0,  # No podemos saber cuántos se agregaron
            })
        except Exception as e:
            return Response(
                {'error': f'Error al sincronizar permisos: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


@extend_schema(
    summary="Reporte de cobertura de permisos",
    description="Obtiene un reporte de cobertura de permisos en roles",
    tags=["SaaS - Permisos"]
)
class PermissionCoverageAPIView(APIView):
    """
    Vista para obtener reporte de cobertura de permisos.
    """
    permission_classes = [IsAuthenticated, IsSaaSAdmin]
    
    def get(self, request):
        """Obtiene reporte de cobertura de permisos."""
        from django.contrib.auth.models import Permission
        from api.roles.models import Role
        
        # Total de permisos
        total_permissions = Permission.objects.count()
        active_permissions = total_permissions  # Todos están activos por defecto
        
        # Permisos por módulo
        permissions_by_module = {}
        perms = Permission.objects.select_related('content_type').all()
        for perm in perms:
            module = perm.content_type.app_label
            permissions_by_module[module] = permissions_by_module.get(module, 0) + 1
        
        # Roles con todos los permisos
        total_roles = Role.objects.count()
        admin_roles = Role.objects.filter(name__icontains='admin').count()
        
        # Calcular cobertura (simplificado)
        coverage_percentage = 0
        if total_roles > 0:
            roles_with_permissions = Role.objects.filter(permissions__isnull=False).distinct().count()
            coverage_percentage = (roles_with_permissions / total_roles) * 100
        
        return Response({
            'total_permissions': total_permissions,
            'active_permissions': active_permissions,
            'inactive_permissions': 0,
            'permissions_by_module': permissions_by_module,
            'admin_roles_with_all_permissions': admin_roles,
            'total_admin_roles': admin_roles,
            'coverage_percentage': round(coverage_percentage, 2),
        })


@extend_schema(
    summary="Activar/Desactivar institución",
    description="Activa o desactiva una institución financiera",
    tags=["SaaS - Admin"]
)
class TenantToggleActiveAPIView(APIView):
    """
    Vista para activar/desactivar una institución.
    """
    permission_classes = [IsAuthenticated, IsSaaSAdmin]
    
    def patch(self, request, id):
        """Activa o desactiva una institución."""
        try:
            institution = FinancialInstitution.objects.get(id=id)
        except FinancialInstitution.DoesNotExist:
            return Response(
                {'error': 'Institución no encontrada'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        is_active = request.data.get('is_active')
        if is_active is None:
            return Response(
                {'error': 'El campo is_active es requerido'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        institution.is_active = is_active
        institution.save()
        
        return Response({
            'message': f'Institución {"activada" if is_active else "desactivada"} correctamente',
            'institution': {
                'id': institution.id,
                'name': institution.name,
                'is_active': institution.is_active,
            }
        })


@extend_schema(
    summary="Listar usuarios del sistema",
    description="Obtiene la lista de todos los usuarios (simplificado)",
    tags=["SaaS - Admin"]
)
class SaaSUserListAPIView(APIView):
    """
    Vista para listar usuarios del sistema.
    """
    permission_classes = [IsAuthenticated, IsSaaSAdmin]
    
    def get(self, request):
        """Lista usuarios del sistema."""
        users = User.objects.all()[:100]  # Limitar a 100 para no sobrecargar
        
        data = []
        for user in users:
            full_name = user.get_full_name() if hasattr(user, 'get_full_name') else f"{user.first_name} {user.last_name}".strip() or user.email
            data.append({
                'id': user.id,
                'email': user.email,
                'full_name': full_name,
                'is_active': user.is_active,
                'date_joined': user.date_joined,
            })
        
        return Response(data)


@extend_schema(
    summary="Listar roles del sistema",
    description="Obtiene la lista de todos los roles (simplificado)",
    tags=["SaaS - Admin"]
)
class SaaSRoleListAPIView(APIView):
    """
    Vista para listar roles del sistema.
    """
    permission_classes = [IsAuthenticated, IsSaaSAdmin]

    def get(self, request):
        """Lista roles del sistema."""
        from api.roles.models import Role

        roles = Role.objects.select_related('institution').all()[:100]

        data = []
        for role in roles:
            data.append({
                'id': role.id,
                'name': role.name,
                'institution': role.institution.name if role.institution else None,
                'is_active': role.is_active,
                'created_at': role.created_at,
            })

        return Response(data)


# ============================================================
# VISTAS DE BILLING (STRIPE)
# ============================================================

import stripe
from django.conf import settings
from django.utils import timezone
from datetime import datetime, date, timedelta


class StripeWebhookAPIView(APIView):
    """
    Endpoint para recibir webhooks de Stripe.
    """
    permission_classes = []  # No requiere autenticación (Stripe firma los requests)

    def post(self, request):
        """Procesa un webhook de Stripe."""
        stripe.api_key = settings.STRIPE_SECRET_KEY
        webhook_secret = settings.STRIPE_WEBHOOK_SECRET

        payload = request.body
        sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')

        try:
            event = stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
        except ValueError:
            return Response({'error': 'Invalid payload'}, status=status.HTTP_400_BAD_REQUEST)
        except stripe.error.SignatureVerificationError:
            return Response({'error': 'Invalid signature'}, status=status.HTTP_400_BAD_REQUEST)

        existing = StripeWebhookEvent.objects.filter(stripe_event_id=event.id).first()
        if existing:
            return Response({'status': 'already_processed'}, status=status.HTTP_200_OK)

        webhook_event = StripeWebhookEvent.objects.create(
            stripe_event_id=event.id,
            event_type=event.type,
            payload=event.to_dict(),
            status='received'
        )

        try:
            from .services import BillingService
            billing_service = BillingService()

            if event.type == 'checkout.session.completed':
                billing_service.handle_checkout_session_completed(event.data.object)
            elif event.type == 'invoice.payment_succeeded':
                billing_service.handle_invoice_payment_succeeded(event.data.object)
            elif event.type == 'invoice.payment_failed':
                billing_service.handle_invoice_payment_failed(event.data.object)
            elif event.type == 'customer.subscription.deleted':
                billing_service.handle_customer_subscription_deleted(event.data.object)
            elif event.type == 'customer.subscription.updated':
                billing_service.handle_subscription_updated(event.data.object)

            webhook_event.status = 'processed'
            webhook_event.processed_at = timezone.now()
            webhook_event.save()

        except Exception as e:
            import traceback
            webhook_event.status = 'failed'
            webhook_event.error_message = f"{str(e)}\n\n{traceback.format_exc()}"
            webhook_event.save()
            import logging
            logger = logging.getLogger('django')
            logger.error(f"Webhook error: {str(e)}\n{traceback.format_exc()}")

        return Response({'status': 'processed'}, status=status.HTTP_200_OK)


class CreateCheckoutSessionAPIView(APIView):
    """
    Crea una sesión de Stripe Checkout para iniciar/comprar una suscripción.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        """Crea una sesión de checkout."""
        from .services import StripeSubscriptionService

        user = request.user
        plan_id = request.data.get('plan_id')
        billing_cycle = request.data.get('billing_cycle', 'MONTHLY')

        if not plan_id:
            return Response(
                {'error': 'El campo plan_id es requerido'},
                status=status.HTTP_400_BAD_REQUEST
            )

        membership = user.institution_memberships.filter(is_active=True).first()
        if not membership:
            return Response(
                {'error': 'Usuario no pertenece a ninguna institución'},
                status=status.HTTP_400_BAD_REQUEST
            )

        institution = membership.institution

        try:
            subscription = Subscription.objects.select_related('plan', 'institution').get(
                institution=institution
            )
        except Subscription.DoesNotExist:
            return Response(
                {'error': 'No se encontró suscripción para esta institución'},
                status=status.HTTP_404_NOT_FOUND
            )

        try:
            plan = SubscriptionPlan.objects.get(id=plan_id, is_active=True)
        except SubscriptionPlan.DoesNotExist:
            return Response(
                {'error': 'Plan no encontrado o no disponible'},
                status=status.HTTP_404_NOT_FOUND
            )

        stripe_service = StripeSubscriptionService()

        try:
            email = user.email
            name = f"{user.first_name} {user.last_name}".strip() or user.email
            result = stripe_service.create_checkout_session(
                subscription=subscription,
                plan=plan,
                billing_cycle=billing_cycle,
                email=email,
                name=name
            )

            if result.get('requires_payment') and result.get('url'):
                return Response({
                    'url': result['url'],
                    'session_id': result['session_id'],
                    'requires_payment': True
                })
            else:
                return Response({
                    'message': 'Plan gratuito asignado correctamente',
                    'url': None,
                    'session_id': None,
                    'requires_payment': False
                })

        except Exception as e:
            import traceback
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"CreateCheckoutSession error: {str(e)}\n{traceback.format_exc()}")
            return Response(
                {'error': f'Error al crear sesión de checkout: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class CreateCustomerPortalSessionAPIView(APIView):
    """
    Crea una sesión del Stripe Customer Portal.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        """Crea una sesión del portal de cliente."""
        from .services import StripeSubscriptionService

        user = request.user

        membership = user.institution_memberships.filter(is_active=True).first()
        if not membership:
            return Response(
                {'error': 'Usuario no pertenece a ninguna institución'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            subscription = Subscription.objects.select_related('institution').get(
                institution=membership.institution
            )
        except Subscription.DoesNotExist:
            return Response(
                {'error': 'No se encontró suscripción'},
                status=status.HTTP_404_NOT_FOUND
            )

        if not subscription.stripe_customer_id:
            return Response(
                {'error': 'No hay método de pago registrado'},
                status=status.HTTP_400_BAD_REQUEST
            )

        stripe_service = StripeSubscriptionService()

        try:
            result = stripe_service.create_customer_portal_session(subscription)
            return Response(result)
        except Exception as e:
            return Response(
                {'error': f'Error al crear portal: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class BillingCancelSubscriptionAPIView(APIView):
    """
    Programa la cancelación de la suscripción al final del período actual.
    (Versión Billing/Stripe — distinta de CancelSubscriptionAPIView del admin SaaS)
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        """Programa la cancelación."""
        from .services import StripeSubscriptionService

        user = request.user

        membership = user.institution_memberships.filter(is_active=True).first()
        if not membership:
            return Response(
                {'error': 'Usuario no pertenece a ninguna institución'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            subscription = Subscription.objects.get(institution=membership.institution)
        except Subscription.DoesNotExist:
            return Response(
                {'error': 'No se encontró suscripción'},
                status=status.HTTP_404_NOT_FOUND
            )

        if subscription.status in ['CANCELLED', 'EXPIRED']:
            return Response(
                {'error': 'La suscripción ya está cancelada'},
                status=status.HTTP_400_BAD_REQUEST
            )

        stripe_service = StripeSubscriptionService()

        try:
            result = stripe_service.cancel_subscription(subscription)
            return Response(result)
        except Exception as e:
            return Response(
                {'error': f'Error al cancelar: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class ReactivateSubscriptionAPIView(APIView):
    """
    Reactiva una suscripción pendiente de cancelación.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        """Reactiva la suscripción."""
        from .services import StripeSubscriptionService

        user = request.user

        membership = user.institution_memberships.filter(is_active=True).first()
        if not membership:
            return Response(
                {'error': 'Usuario no pertenece a ninguna institución'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            subscription = Subscription.objects.get(institution=membership.institution)
        except Subscription.DoesNotExist:
            return Response(
                {'error': 'No se encontró suscripción'},
                status=status.HTTP_404_NOT_FOUND
            )

        if subscription.status != 'PENDING_CANCELLATION':
            return Response(
                {'error': 'La suscripción no está pendiente de cancelación'},
                status=status.HTTP_400_BAD_REQUEST
            )

        stripe_service = StripeSubscriptionService()

        try:
            result = stripe_service.reactivate_subscription(subscription)
            return Response(result)
        except Exception as e:
            return Response(
                {'error': f'Error al reactivar: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class InvoiceListAPIView(generics.ListAPIView):
    """
    Lista las facturas de la suscripción del tenant.
    """
    serializer_class = None  # Se define después
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        from .serializers import InvoiceSerializer
        return InvoiceSerializer

    def get_queryset(self):
        user = self.request.user

        membership = user.institution_memberships.filter(is_active=True).first()
        if not membership:
            return Invoice.objects.none()

        try:
            subscription = Subscription.objects.get(institution=membership.institution)
            return Invoice.objects.filter(subscription=subscription).order_by('-created_at')
        except Subscription.DoesNotExist:
            return Invoice.objects.none()


class PaymentListAPIView(generics.ListAPIView):
    """
    Lista los pagos de la suscripción del tenant.
    """
    serializer_class = None  # Se define después
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        from .serializers import PaymentSerializer
        return PaymentSerializer

    def get_queryset(self):
        user = self.request.user

        membership = user.institution_memberships.filter(is_active=True).first()
        if not membership:
            return Payment.objects.none()

        try:
            subscription = Subscription.objects.get(institution=membership.institution)
            return Payment.objects.filter(subscription=subscription).order_by('-created_at')
        except Subscription.DoesNotExist:
            return Payment.objects.none()


class SyncPlanToStripeAPIView(APIView):
    """
    Sincroniza un plan con Stripe (crea/actualiza producto y precios).
    Solo SaaS Admin.
    """
    permission_classes = [IsAuthenticated, IsSaaSAdmin]

    def post(self, request, id):
        """Sincroniza el plan con Stripe."""
        from .services import StripeSubscriptionService

        try:
            plan = SubscriptionPlan.objects.get(id=id)
        except SubscriptionPlan.DoesNotExist:
            return Response(
                {'error': 'Plan no encontrado'},
                status=status.HTTP_404_NOT_FOUND
            )

        stripe_service = StripeSubscriptionService()

        try:
            updated_plan = stripe_service.sync_plan_to_stripe(plan)
            return Response({
                'message': 'Plan sincronizado con Stripe',
                'stripe_product_id': updated_plan.stripe_product_id,
                'stripe_price_monthly_id': updated_plan.stripe_price_monthly_id,
                'stripe_price_quarterly_id': updated_plan.stripe_price_quarterly_id,
                'stripe_price_annual_id': updated_plan.stripe_price_annual_id,
            })
        except Exception as e:
            return Response(
                {'error': f'Error al sincronizar: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class VerifyCheckoutSessionAPIView(APIView):
    """
    Verifica el estado de una sesión de checkout y actualiza la suscripción.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """Verifica el estado de una sesión de checkout."""
        import logging
        session_id = request.query_params.get('session_id')

        if not session_id:
            return Response(
                {'error': 'session_id es requerido'},
                status=status.HTTP_400_BAD_REQUEST
            )

        stripe.api_key = settings.STRIPE_SECRET_KEY

        try:
            session = stripe.checkout.Session.retrieve(session_id)

            if session.payment_status == 'paid' or session.status == 'complete':
                # ── CORRECCIÓN: En stripe>=5 el metadata es un StripeObject,
                # no un dict. El método correcto es .to_dict() (no dict() ni .get()).
                raw_metadata = session.metadata
                if raw_metadata is None:
                    metadata = {}
                elif isinstance(raw_metadata, dict):
                    metadata = raw_metadata
                else:
                    # StripeObject → dict usando el método oficial de Stripe v5
                    metadata = raw_metadata.to_dict()

                subscription_id = metadata.get('subscription_id')
                plan_id = metadata.get('plan_id')

                if subscription_id:
                    try:
                        subscription = Subscription.objects.select_related('plan').get(
                            id=int(subscription_id)
                        )

                        # Validar que el pago este realmente completado
                        invoice = None
                        payment_verified = session.payment_status == 'paid' or session.status == 'complete'

                        if session.subscription:
                            try:
                                stripe_subscription = stripe.Subscription.retrieve(session.subscription)
                                if stripe_subscription:
                                    stripe_sub_dict = stripe_subscription.to_dict() if hasattr(stripe_subscription, 'to_dict') else {}

                                    subscription.stripe_subscription_id = session.subscription

                                    current_period_start = stripe_sub_dict.get('current_period_start')
                                    current_period_end = stripe_sub_dict.get('current_period_end')
                                    if current_period_start:
                                        subscription.start_date = datetime.fromtimestamp(
                                            current_period_start, tz=timezone.utc
                                        ).date()
                                    elif not subscription.start_date:
                                        subscription.start_date = date.today()
                                    if current_period_end:
                                        subscription.next_billing_date = datetime.fromtimestamp(
                                            current_period_end, tz=timezone.utc
                                        ).date()
                                    elif not subscription.next_billing_date:
                                        subscription.next_billing_date = date.today() + timedelta(days=30)

                                    subscription.stripe_status = stripe_sub_dict.get('status') or 'active'

                                    # Intentar sincronizar factura desde Stripe
                                    latest_invoice_id = stripe_sub_dict.get('latest_invoice')
                                    if latest_invoice_id:
                                        stripe_inv = stripe.Invoice.retrieve(latest_invoice_id)
                                        if stripe_inv:
                                            amount_paid = stripe_inv.get("amount_paid", 0) / 100
                                            currency = stripe_inv.get("currency", "usd").upper()
                                            invoice = self._create_invoice_from_stripe(
                                                subscription, stripe_inv, amount_paid, currency
                                            )
                                            subscription.total_paid = subscription.total_paid + Decimal(str(amount_paid))
                            except Exception:
                                pass

                        # Fallback: crear factura desde datos de la sesion de checkout
                        if not invoice and payment_verified:
                            logger = logging.getLogger('django')
                            logger.info(
                                f"VerifyPayment: session_id={session.id} "
                                f"amount_total={session.amount_total} "
                                f"plan_id={plan_id} "
                                f"subscription.plan_id={subscription.plan_id} "
                                f"subscription.plan.price={subscription.plan.price}"
                            )
                            amount_paid = (session.amount_total or 0) / 100
                            if amount_paid <= 0 and plan_id:
                                try:
                                    paid_plan = SubscriptionPlan.objects.get(id=int(plan_id))
                                    amount_paid = float(paid_plan.price)
                                except SubscriptionPlan.DoesNotExist:
                                    amount_paid = float(subscription.plan.price) if subscription.plan.price else 0
                            elif amount_paid <= 0:
                                amount_paid = float(subscription.plan.price) if subscription.plan.price else 0

                            currency = (session.currency or 'usd').upper()
                            if amount_paid > 0:
                                invoice = self._create_invoice_from_session(
                                    subscription, session, amount_paid, currency
                                )
                                subscription.total_paid = subscription.total_paid + Decimal(str(amount_paid))

                        if not payment_verified:
                            raise ValueError("El pago no fue completado en Stripe")

                        if plan_id:
                            try:
                                new_plan = SubscriptionPlan.objects.get(id=int(plan_id))
                                subscription.plan = new_plan
                            except SubscriptionPlan.DoesNotExist:
                                pass

                        subscription.payment_status = 'PAID'
                        subscription.status = 'ACTIVE'
                        subscription.save()

                        return Response({
                            'status': 'paid',
                            'subscription': {
                                'id': subscription.id,
                                'plan_name': subscription.plan.name,
                                'status': subscription.status,
                                'payment_status': subscription.payment_status,
                            }
                        })
                    except Subscription.DoesNotExist:
                        pass
                    except Exception as stripe_err:
                        import logging
                        logger = logging.getLogger(__name__)
                        logger.error(f"Error verificando pago: {str(stripe_err)}", exc_info=True)
                        return Response(
                            {'error': f'Error al verificar el pago: {str(stripe_err)}'},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR
                        )

                return Response({
                    'status': 'paid',
                    'message': 'Pago confirmado pero no se encontro la suscripcion'
                })

            return Response({
                'status': session.payment_status or session.status,
                'message': 'El pago aún no ha sido completado'
            })

        except stripe.error.InvalidRequestError as e:
            return Response(
                {'error': f'Sesión no encontrada: {str(e)}'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            import traceback
            import logging
            logger = logging.getLogger('django')
            logger.error(f"verify-payment error: {str(e)}\n{traceback.format_exc()}")
            return Response(
                {'error': f'Error al verificar: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def _create_invoice_from_stripe(self, subscription, stripe_inv, amount_paid, currency):
        invoice, _ = Invoice.objects.update_or_create(
            stripe_invoice_id=stripe_inv.id,
            defaults={
                "subscription": subscription,
                "invoice_number": stripe_inv.get("number", stripe_inv.id),
                "amount": amount_paid,
                "currency": currency,
                "status": "paid",
                "hosted_invoice_url": stripe_inv.get("hosted_invoice_url"),
                "invoice_pdf": stripe_inv.get("invoice_pdf"),
                "paid_at": timezone.now(),
                "metadata": _sanitize_for_json(stripe_inv.to_dict() if hasattr(stripe_inv, 'to_dict') else stripe_inv),
            }
        )
        if stripe_inv.get("payment_intent"):
            Payment.objects.update_or_create(
                stripe_payment_intent_id=stripe_inv.get("payment_intent"),
                defaults={
                    "subscription": subscription,
                    "invoice": invoice,
                    "amount": amount_paid,
                    "currency": currency,
                    "status": "succeeded",
                    "payment_method_type": "card",
                    "metadata": _sanitize_for_json(stripe_inv.to_dict() if hasattr(stripe_inv, 'to_dict') else stripe_inv),
                }
            )
        return invoice

    def _create_invoice_from_session(self, subscription, session, amount_paid, currency):
        import logging
        logger = logging.getLogger(__name__)

        stripe_invoice_id = f"cs_{session.id}"
        invoice, created = Invoice.objects.update_or_create(
            stripe_invoice_id=stripe_invoice_id,
            defaults={
                "subscription": subscription,
                "invoice_number": f"INV-{subscription.id}-{date.today().strftime('%Y%m%d')}-{session.id[:8]}",
                "amount": amount_paid,
                "currency": currency,
                "status": "paid",
                "paid_at": timezone.now(),
                "metadata": {"source": "checkout_session", "session_id": session.id},
            }
        )

        if not created:
            logger.info(f"Invoice already exists for session {session.id}, updating amount to {amount_paid}")
            if abs(float(invoice.amount) - amount_paid) > 0.01:
                invoice.amount = amount_paid
                invoice.save(update_fields=['amount'])
            return invoice

        logger.info(f"Invoice created: #{invoice.id} amount={amount_paid} currency={currency}")

        payment_intent = getattr(session, 'payment_intent', None)
        if payment_intent:
            Payment.objects.update_or_create(
                stripe_payment_intent_id=payment_intent,
                defaults={
                    "subscription": subscription,
                    "invoice": invoice,
                    "amount": amount_paid,
                    "currency": currency,
                    "status": "succeeded",
                    "payment_method_type": "card",
                    "metadata": {"source": "checkout_session", "session_id": session.id},
                }
            )

        # Buscar la factura real de Stripe para obtener la URL (solo para facturas nuevas)
        if not invoice.hosted_invoice_url:
            try:
                if subscription.stripe_subscription_id:
                    real_inv = stripe.Invoice.list(
                        subscription=subscription.stripe_subscription_id,
                        limit=3,
                    )
                elif subscription.stripe_customer_id:
                    real_inv = stripe.Invoice.list(
                        customer=subscription.stripe_customer_id,
                        limit=3,
                    )
                else:
                    real_inv = None

                if real_inv and real_inv.data:
                    for inv_obj in real_inv.data:
                        inv_dict = inv_obj.to_dict() if hasattr(inv_obj, 'to_dict') else {}
                        inv_url = inv_dict.get('hosted_invoice_url')
                        if inv_url:
                            invoice.hosted_invoice_url = inv_url
                            invoice.invoice_pdf = inv_dict.get('invoice_pdf')
                            # NO pisar el stripe_invoice_id porque el de Stripe tiene amount=0
                            invoice.save(update_fields=['hosted_invoice_url', 'invoice_pdf'])
                            logger.info(f"  Assigned URL from Stripe invoice {inv_dict.get('id')}")
                            break
            except Exception as e:
                logger.warning(f"Could not fetch Stripe invoice URL: {e}")

        return invoice


class ApplyPendingChangesAPIView(APIView):
    """
    Endpoint para aplicar downgrades y cancelaciones programadas que han expirado.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        from .services import StripeSubscriptionService
        
        stripe_service = StripeSubscriptionService()
        try:
            result = stripe_service.apply_pending_changes()
            return Response(result, status=status.HTTP_200_OK)
        except Exception as e:
            return Response(
                {'error': f'Error al aplicar cambios pendientes: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

