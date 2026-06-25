"""
Vistas para notificaciones push.
"""

from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend


from .models import PushToken, NotificationTemplate, Notification
from .serializers import (
    PushTokenSerializer, PushTokenCreateSerializer,
    NotificationTemplateSerializer, NotificationTemplateCreateSerializer,
    NotificationSerializer, NotificationListSerializer,
    SendNotificationSerializer, UnreadCountSerializer,
    SendBatchNotificationSerializer, MoraAlertSerializer
)
from .services import NotificationService


class PushTokenViewSet(viewsets.ModelViewSet):
    """
    ViewSet para gestionar tokens de dispositivos push.

    list:
        Obtener todos los tokens del usuario actual.

    create:
        Registrar un nuevo token de dispositivo.

    destroy:
        Eliminar un token (desregistrar dispositivo).
    """

    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['device_type', 'is_active']

    def get_queryset(self):
        return PushToken.objects.filter(user=self.request.user)

    def get_serializer_class(self):
        if self.action == 'create':
            return PushTokenCreateSerializer
        return PushTokenSerializer

    def create(self, request, *args, **kwargs):
        """Registra o actualiza un token FCM."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        token = serializer.validated_data['token']
        device_type = serializer.validated_data.get('device_type', 'ANDROID')
        device_name = serializer.validated_data.get('device_name')
        device_id = serializer.validated_data.get('device_id')

        push_token, created = PushToken.objects.update_or_create(
            token=token,
            defaults={
                'user': request.user,
                'institution': getattr(request, 'tenant', None),
                'device_type': device_type,
                'device_name': device_name,
                'device_id': device_id,
                'is_active': True,
                'last_used_at': timezone.now(),
            }
        )

        return Response(
            PushTokenSerializer(push_token).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK
        )

    @action(detail=False, methods=['delete'])
    def unregister(self, request):
        """
        Desregistrar un token específico.
        Endpoint: DELETE /api/notifications/tokens/unregister/?token=xxx
        """
        token = request.query_params.get('token')
        if not token:
            return Response(
                {'error': 'Token es requerido'},
                status=status.HTTP_400_BAD_REQUEST
            )

        deleted, _ = PushToken.objects.filter(
            token=token,
            user=request.user
        ).update(is_active=False)

        if deleted:
            return Response({'message': 'Token desregistrado'})
        return Response(
            {'error': 'Token no encontrado'},
            status=status.HTTP_404_NOT_FOUND
        )


class NotificationViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet para ver y gestionar notificaciones del usuario.
    """

    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['notification_type', 'is_read', 'is_sent']

    def get_queryset(self):
        return Notification.objects.filter(user=self.request.user)

    def get_serializer_class(self):
        if self.action == 'list':
            return NotificationListSerializer
        return NotificationSerializer

    @action(detail=True, methods=['patch'])
    def read(self, request, pk=None):
        """Marcar notificación como leída."""
        notification = self.get_object()
        notification.mark_as_read()
        return Response(NotificationSerializer(notification).data)

    @action(detail=False, methods=['post'])
    def mark_all_read(self, request):
        """Marcar todas las notificaciones como leídas."""
        updated = self.get_queryset().filter(is_read=False).update(
            is_read=True,
            read_at=timezone.now()
        )
        return Response({'updated': updated})

    @action(detail=False, methods=['get'])
    def unread_count(self, request):
        """Obtener cantidad de notificaciones no leídas."""
        count = self.get_queryset().filter(is_read=False).count()
        return Response(UnreadCountSerializer({'count': count}).data)


class NotificationTemplateViewSet(viewsets.ModelViewSet):
    """
    ViewSet para gestionar plantillas de notificaciones.
    Solo staff puede crear/editar plantillas.
    """

    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['notification_type', 'is_active', 'code']

    def get_queryset(self):
        queryset = NotificationTemplate.objects.filter(
            institution=getattr(self.request, 'tenant', None)
        )
        return queryset

    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return NotificationTemplateCreateSerializer
        return NotificationTemplateSerializer

    def perform_create(self, serializer):
        serializer.save(
            institution=getattr(self.request, 'tenant', None),
            created_by=self.request.user
        )

    def create(self, request, *args, **kwargs):
        if not request.user.profile.has_permission('notifications.create_template', getattr(request, 'tenant', None)):
            return Response(
                {'error': 'No tienes permiso para crear plantillas'},
                status=status.HTTP_403_FORBIDDEN
            )
        return super().create(request, *args, **kwargs)


class SendNotificationView(APIView):
    """
    Endpoint para enviar notificaciones push.

    POST /api/notifications/send/
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = SendNotificationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data
        service = NotificationService()

        template_id = data.get('template_id')
        title = data.get('title')
        body = data.get('body')
        notification_type = data.get('notification_type', 'GENERAL')
        data_json = data.get('data_json', {})
        image_url = data.get('image_url')
        click_action = data.get('click_action')

        if template_id:
            try:
                template = NotificationTemplate.objects.get(
                    id=template_id,
                    institution=getattr(request, 'tenant', None)
                )
                title, body, template_data = template.render(data.get('template_context', {}))
                data_json = {**template_data, **data_json}
            except NotificationTemplate.DoesNotExist:
                return Response(
                    {'error': 'Plantilla no encontrada'},
                    status=status.HTTP_404_NOT_FOUND
                )

        user_ids = data.get('user_ids', [])
        if not user_ids:
            return Response(
                {'error': 'user_ids es requerido'},
                status=status.HTTP_400_BAD_REQUEST
            )

        result = service.send_batch(
            user_ids=user_ids,
            title=title,
            body=body,
            notification_type=notification_type,
            data=data_json,
        )

        return Response(result)


class SendMoraAlertView(APIView):
    """
    Endpoint para enviar alertas de mora a clientes con cuotas vencidas.

    POST /api/notifications/send/mora/
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = MoraAlertSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data
        minimum_overdue_days = data.get('minimum_overdue_days', 1)
        include_amount = data.get('include_amount', True)

        from api.loans.models import Contract, ContractAmortizationSchedule
        from api.clients.models import Client

        institution = getattr(request, 'tenant', None)
        today = timezone.now().date()

        overdue_contracts = Contract.objects.filter(
            institution=institution,
            status='ACTIVE'
        ).filter(
            amortization_schedule__is_paid=False,
            amortization_schedule__due_date__lt=today
        ).distinct()

        if minimum_overdue_days > 1:
            cutoff_date = today - timezone.timedelta(days=minimum_overdue_days)
            overdue_contracts = overdue_contracts.filter(
                amortization_schedule__due_date__lt=cutoff_date
            )

        client_totals = {}
        for contract in overdue_contracts.select_related('loan_application__client'):
            if not contract.loan_application or not contract.loan_application.client:
                continue

            client = contract.loan_application.client
            client_user = client.user

            overdue_amount = contract.amortization_schedule_set.filter(
                is_paid=False,
                due_date__lt=today
            ).aggregate(
                total=models.Sum('principal_amount') + models.Sum('interest_amount')
            )['total'] or 0

            if client.id not in client_totals:
                client_totals[client.id] = {
                    'user_id': client_user.id,
                    'client_name': client.get_full_name(),
                    'total_amount': 0,
                    'contract_count': 0,
                }

            client_totals[client.id]['total_amount'] += float(overdue_amount)
            client_totals[client.id]['contract_count'] += 1

        service = NotificationService()
        results = []

        for client_id, info in client_totals.items():
            amount_str = f"Bs. {info['total_amount']:.2f}" if include_amount else ""
            title = "Cuota vencida"
            body = f"Tiene {info['contract_count']} cuota(s) vencida(s). Monto: {amount_str}"

            success, _ = service.send_to_user(
                user_id=info['user_id'],
                title=title,
                body=body,
                notification_type='MORA_ALERT',
                data={
                    'type': 'MORA_ALERT',
                    'client_id': client_id,
                    'contract_count': info['contract_count'],
                    'total_amount': info['total_amount'],
                },
                click_action='/loans/active-credits/',
            )

            results.append({
                'client_id': client_id,
                'client_name': info['client_name'],
                'sent': success,
            })

        return Response({
            'total_clients': len(results),
            'sent_count': sum(1 for r in results if r['sent']),
            'results': results,
        })


class RegisterTokenView(APIView):
    """
    Endpoint simple para registrar un token.

    POST /api/notifications/register-token/
    """

    permission_classes = [AllowAny]

    def post(self, request):
        token = request.data.get('token')
        device_type = request.data.get('device_type', 'ANDROID')
        device_name = request.data.get('device_name')
        device_id = request.data.get('device_id')

        if not token:
            return Response(
                {'error': 'Token es requerido'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not request.user.is_authenticated:
            return Response(
                {'error': 'Autenticación requerida'},
                status=status.HTTP_401_UNAUTHORIZED
            )

        from django.db import IntegrityError
        try:
            push_token, created = PushToken.objects.update_or_create(
                token=token,
                defaults={
                    'user': request.user,
                    'institution': getattr(request, 'tenant', None),
                    'device_type': device_type,
                    'device_name': device_name,
                    'device_id': device_id,
                    'is_active': True,
                    'last_used_at': timezone.now(),
                }
            )
        except IntegrityError:
            # El token ya existe activo para otro usuario/tenant, reasignarlo
            PushToken.objects.filter(token=token, is_active=True).update(is_active=False)
            push_token = PushToken.objects.create(
                token=token,
                user=request.user,
                institution=getattr(request, 'tenant', None),
                device_type=device_type,
                device_name=device_name,
                device_id=device_id,
                is_active=True,
                last_used_at=timezone.now(),
            )
            created = True

        return Response(
            PushTokenSerializer(push_token).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK
        )


class UnregisterTokenView(APIView):
    """
    Endpoint simple para desregistrar un token.

    DELETE /api/notifications/unregister-token/
    """

    permission_classes = [IsAuthenticated]

    def delete(self, request):
        token = request.data.get('token') or request.query_params.get('token')

        if not token:
            return Response(
                {'error': 'Token es requerido'},
                status=status.HTTP_400_BAD_REQUEST
            )

        deleted, _ = PushToken.objects.filter(
            token=token,
            user=request.user
        ).update(is_active=False)

        if deleted:
            return Response({'message': 'Token desregistrado correctamente'})
        return Response(
            {'error': 'Token no encontrado'},
            status=status.HTTP_404_NOT_FOUND
        )
