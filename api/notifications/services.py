"""
Servicios para envío de notificaciones push via Firebase Cloud Messaging.
"""

import logging
import json
import os
from typing import Optional
from dataclasses import dataclass
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)


@dataclass
class FCMNotificationResult:
    """Resultado de envío de notificación."""
    success: bool
    message_id: Optional[str] = None
    error: Optional[str] = None
    should_delete_token: bool = False


class FirebaseMessagingService:
    """
    Servicio para enviar notificaciones via Firebase Cloud Messaging usando
    Firebase Admin SDK.
    
    Funciona automáticamente en:
    - Railway (GCP) usando Application Default Credentials
    - Local development usando variable FIREBASE_CREDENTIALS_JSON
    """
    
    _instance = None
    _initialized = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        logger.info(f"FirebaseMessagingService.__init__ called, _initialized = {FirebaseMessagingService._initialized}")
        if FirebaseMessagingService._initialized:
            logger.info("FirebaseMessagingService.__init__: Ya inicializado, retornando")
            return
            
        self._messaging = None
        self._initialize_firebase()
        FirebaseMessagingService._initialized = True
    
    def _initialize_firebase(self):
        """Inicializa Firebase Admin SDK."""
        logger.info("FirebaseMessagingService: Iniciando _initialize_firebase()")
        
        try:
            import firebase_admin
            from firebase_admin import credentials, messaging
            
            # Si ya está inicializado, usar existente
            if firebase_admin._apps:
                self._messaging = messaging
                logger.info("FirebaseMessagingService: Firebase ya estaba inicializado")
                return
            
            # Intentar cargar credenciales de variables individuales
            project_id = os.environ.get('FIREBASE_PROJECT_ID')
            private_key = os.environ.get('FIREBASE_PRIVATE_KEY')
            client_email = os.environ.get('FIREBASE_CLIENT_EMAIL')
            
            if project_id and private_key and client_email:
                # Convertir escapes \n (backslash+n) a saltos de línea reales
                private_key = private_key.replace('\\n', '\n')
                
                creds_dict = {
                    'type': 'service_account',
                    'project_id': project_id,
                    'private_key': private_key,
                    'client_email': client_email,
                    'token_uri': os.environ.get('FIREBASE_TOKEN_URI', 'https://oauth2.googleapis.com/token'),
                    'auth_uri': os.environ.get('FIREBASE_AUTH_URI', 'https://accounts.google.com/o/oauth2/auth'),
                }
                private_key_id = os.environ.get('FIREBASE_PRIVATE_KEY_ID')
                if private_key_id:
                    creds_dict['private_key_id'] = private_key_id
                auth_provider_x509_cert_url = os.environ.get('FIREBASE_AUTH_PROVIDER_X509_CERT_URL')
                if auth_provider_x509_cert_url:
                    creds_dict['auth_provider_x509_cert_url'] = auth_provider_x509_cert_url
                client_x509_cert_url = os.environ.get('FIREBASE_CLIENT_X509_CERT_URL')
                if client_x509_cert_url:
                    creds_dict['client_x509_cert_url'] = client_x509_cert_url
                    
                creds = credentials.Certificate(creds_dict)
                firebase_admin.initialize_app(creds)
                self._messaging = messaging
                logger.info("FirebaseMessagingService: Firebase inicializado con variables individuales")
                return
            
            # En Railway/GCP, intentar Application Default Credentials
            try:
                firebase_admin.initialize_app()
                self._messaging = messaging
                logger.info("FirebaseMessagingService: Firebase inicializado con Application Default Credentials")
                return
            except Exception as e:
                logger.warning(f"FirebaseMessagingService: ADC no disponibles: {e}")
            
            logger.error("FirebaseMessagingService: No se encontraron credenciales de Firebase")
            
        except ImportError:
            logger.error("FirebaseMessagingService: firebase_admin no está instalado. Instalar con: pip install firebase-admin")
        except Exception as e:
            logger.error(f"FirebaseMessagingService: Error inicializando: {e}")
    
    def send_to_token(
        self,
        token: str,
        title: str,
        body: str,
        data: Optional[dict] = None,
        image_url: Optional[str] = None,
        click_action: Optional[str] = None,
        badge: Optional[int] = None,
        sound: str = 'default',
    ) -> FCMNotificationResult:
        """
        Envía una notificación a un token específico usando Firebase Admin SDK.

        Args:
            token: FCM token del dispositivo
            title: Título de la notificación
            body: Cuerpo de la notificación
            data: Datos adicionales a enviar
            image_url: URL de imagen (opcional)
            click_action: Deep link o acción al tocar (opcional)
            badge: Número de badge (iOS)
            sound: Nombre del sonido

        Returns:
            FCMNotificationResult con el resultado
        """
        if not self._messaging:
            return FCMNotificationResult(
                success=False,
                error="Firebase no está inicializado"
            )
        
        try:
            # Construir mensaje
            notification = self._messaging.Notification(
                title=title,
                body=body,
                image=image_url
            )
            
            android_config = self._messaging.AndroidConfig(
                priority='high',
                notification=self._messaging.AndroidNotification(
                    channel_id='fincore_notifications',
                    default_sound=True,
                    default_vibrate_timings=True,
                )
            )
            
            apns_config = self._messaging.APNSConfig(
                payload=self._messaging.APNSPayload(
                    aps=self._messaging.Aps(
                        badge=badge or 0,
                        sound='default' if sound == 'default' else sound,
                    )
                )
            )
            
            # Datos personalizados (todos los valores deben ser strings para FCM)
            message_data = data or {}
            message_data = {k: str(v) for k, v in message_data.items()}
            if click_action:
                message_data['click_action'] = click_action
            
            message = self._messaging.Message(
                notification=notification,
                data=message_data,
                token=token,
                android=android_config,
                apns=apns_config,
            )
            
            # Enviar
            response = self._messaging.send(message)
            
            return FCMNotificationResult(
                success=True,
                message_id=response
            )
            
        except Exception as e:
            logger.error(f"Error enviando FCM: {e}")
            
            # Verificar si el token es inválido
            error_str = str(e).lower()
            should_delete = (
                'invalidregistration' in error_str or
                'notregistered' in error_str or
                'requested entity was not found' in error_str or
                'no devices' in error_str
            )
            
            return FCMNotificationResult(
                success=False,
                error=str(e),
                should_delete_token=should_delete
            )
    
    def send_to_tokens(
        self,
        tokens: list[str],
        title: str,
        body: str,
        data: Optional[dict] = None,
        image_url: Optional[str] = None,
        click_action: Optional[str] = None,
    ) -> tuple[int, int, list[str]]:
        """
        Envía una notificación a múltiples tokens.

        Args:
            tokens: Lista de FCM tokens
            title: Título
            body: Cuerpo
            data: Datos adicionales
            image_url: URL de imagen
            click_action: Deep link

        Returns:
            Tuple (success_count, failure_count, failed_tokens)
        """
        success_count = 0
        failed_tokens = []

        for token in tokens:
            result = self.send_to_token(
                token=token,
                title=title,
                body=body,
                data=data,
                image_url=image_url,
                click_action=click_action,
            )

            if result.success:
                success_count += 1
            else:
                failed_tokens.append(token)

        return success_count, len(failed_tokens), failed_tokens
    
    def send_to_topic(
        self,
        topic: str,
        title: str,
        body: str,
        data: Optional[dict] = None,
        image_url: Optional[str] = None,
    ) -> FCMNotificationResult:
        """
        Envía una notificación a todos los dispositivos suscritos a un topic.

        Args:
            topic: Nombre del topic
            title: Título
            body: Cuerpo
            data: Datos adicionales
            image_url: URL de imagen

        Returns:
            FCMNotificationResult
        """
        if not self._messaging:
            return FCMNotificationResult(
                success=False,
                error="Firebase no está inicializado"
            )
        
        try:
            notification = self._messaging.Notification(
                title=title,
                body=body,
                image=image_url
            )
            
            message_data = data or {}
            message_data = {k: str(v) for k, v in message_data.items()}
            
            message = self._messaging.Message(
                notification=notification,
                data=message_data,
                topic=topic,
            )
            
            response = self._messaging.send(message)
            
            return FCMNotificationResult(
                success=True,
                message_id=response
            )
            
        except Exception as e:
            logger.error(f"Error enviando FCM a topic: {e}")
            return FCMNotificationResult(
                success=False,
                error=str(e)
            )


# Mantener compatibilidad con el código existente
class FCMService(FirebaseMessagingService):
    """
    Alias para compatibilidad. Usa FirebaseMessagingService internamente.
    """
    pass


class NotificationService:
    """
    Servicio de más alto nivel para gestión de notificaciones.
    Coordina entre modelos, FCM y logging.
    """

    def __init__(self):
        self.fcm_service = FCMService()

    def send_to_user(
        self,
        user,
        title: str,
        body: str,
        notification_type: str = 'GENERAL',
        data: Optional[dict] = None,
        image_url: Optional[str] = None,
        click_action: Optional[str] = None,
        save_notification: bool = True,
    ) -> tuple[bool, Optional[str]]:
        """
        Envía una notificación a un usuario.

        Args:
            user: Instancia de usuario
            title: Título
            body: Cuerpo
            notification_type: Tipo de notificación
            data: Datos adicionales
            image_url: URL de imagen
            click_action: Deep link
            save_notification: Si True, guarda en BD

        Returns:
            Tuple (success, error_message)
        """
        from .models import Notification, PushToken

        tokens = PushToken.objects.filter(
            user=user,
            is_active=True
        ).values_list('token', flat=True)

        if not tokens:
            logger.info(f"No active tokens for user {user.id}")
            return False, "No active devices"

        success_count = 0
        last_error = None

        for token in tokens:
            result = self.fcm_service.send_to_token(
                token=token,
                title=title,
                body=body,
                data=data,
                image_url=image_url,
                click_action=click_action,
            )

            if result.success:
                success_count += 1
                if result.should_delete_token:
                    PushToken.objects.filter(token=token).update(is_active=False)
            else:
                last_error = result.error
                if result.should_delete_token:
                    PushToken.objects.filter(token=token).update(is_active=False)

        if save_notification:
            Notification.objects.create(
                user=user,
                notification_type=notification_type,
                title=title,
                body=body,
                data_json=data or {},
                image_url=image_url,
                click_action=click_action,
                is_sent=success_count > 0,
                sent_at=timezone.now() if success_count > 0 else None,
            )

        if success_count > 0:
            return True, None

        return False, last_error

    def send_batch(
        self,
        user_ids: list[int],
        title: str,
        body: str,
        notification_type: str = 'GENERAL',
        data: Optional[dict] = None,
    ) -> dict:
        """
        Envía notificación a múltiples usuarios.

        Returns:
            Dict con estadísticas
        """
        from django.contrib.auth import get_user_model
        from .models import PushToken, Notification

        User = get_user_model()
        users = User.objects.filter(id__in=user_ids)

        total_sent = 0
        total_failed = 0
        users_notified = 0

        for user in users:
            tokens = list(PushToken.objects.filter(
                user=user,
                is_active=True
            ).values_list('token', flat=True))

            if not tokens:
                continue

            success, _ = self.send_to_user(
                user=user,
                title=title,
                body=body,
                notification_type=notification_type,
                data=data,
                save_notification=False,
            )

            if success:
                users_notified += 1

            Notification.objects.create(
                user=user,
                notification_type=notification_type,
                title=title,
                body=body,
                data_json=data or {},
                is_sent=success,
                sent_at=timezone.now() if success else None,
            )

            total_sent += len([t for t in tokens if t])

        return {
            'total_users': len(user_ids),
            'users_notified': users_notified,
            'notifications_sent': total_sent,
            'notifications_failed': total_failed,
        }

    def send_to_admin_topic(
        self,
        institution_id: int,
        title: str,
        body: str,
        notification_type: str = 'GENERAL',
        data: Optional[dict] = None,
        image_url: Optional[str] = None,
        click_action: Optional[str] = None,
    ) -> tuple[bool, Optional[str]]:
        """
        Envía una notificación a todos los admins web de una institución.
        Envía directamente a cada token WEB registrado en la institución.

        Args:
            institution_id: ID de la institución
            title: Título
            body: Cuerpo
            notification_type: Tipo de notificación
            data: Datos adicionales
            image_url: URL de imagen
            click_action: Deep link

        Returns:
            Tuple (success, error_message)
        """
        from .models import PushToken

        web_tokens = PushToken.objects.filter(
            institution_id=institution_id,
            device_type='WEB',
            is_active=True
        ).values_list('token', flat=True)

        if not web_tokens:
            logger.info(f"No web push tokens found for institution {institution_id}")
            return False, "No web tokens registered"

        success_count = 0
        failed_count = 0

        for token in web_tokens:
            result = self.fcm_service.send_to_token(
                token=token,
                title=title,
                body=body,
                data=data,
                image_url=image_url,
                click_action=click_action,
            )

            if result.success:
                success_count += 1
            else:
                failed_count += 1
                if result.should_delete_token:
                    PushToken.objects.filter(token=token).update(is_active=False)

        logger.info(f"Admin web notification sent: {success_count} success, {failed_count} failed for institution {institution_id}")

        if success_count > 0:
            return True, None

        return False, f"All {failed_count} notifications failed"


class MoraAlertService:
    """
    Servicio para enviar alertas de mora a clientes con cuotas vencidas.

    Este servicio es ejecutado periódicamente por un scheduler
    para notificar a los clientes sobre sus cuotas en mora.
    """

    def __init__(self):
        self.notification_service = NotificationService()
        self.logger = logging.getLogger(__name__)

    def send_mora_alerts(
        self,
        institution_id: int,
        minimum_overdue_days: int = 1,
        include_amount: bool = True,
    ) -> dict:
        """
        Envía alertas de mora a todos los clientes con cuotas vencidas.

        Args:
            institution_id: ID de la institución financiera
            minimum_overdue_days: Días mínimos de mora para incluir
            include_amount: Si True, incluye el monto total en mora

        Returns:
            Dict con estadísticas {
                'total_clients': int,
                'clients_with_overdue': int,
                'notifications_sent': int,
                'notifications_failed': int,
                'results': list
            }
        """
        from django.db.models import Sum
        from django.contrib.auth import get_user_model
        from api.loans.models import Contract, ContractAmortizationSchedule
        from api.clients.models import Client

        User = get_user_model()

        today = timezone.now().date()
        cutoff_date = today - timezone.timedelta(days=minimum_overdue_days)

        overdue_contracts = Contract.objects.filter(
            institution_id=institution_id,
            status='ACTIVE'
        ).filter(
            amortization_schedule__is_paid=False,
            amortization_schedule__due_date__lt=cutoff_date
        ).select_related('loan_application__client__user')

        client_totals = {}
        for contract in overdue_contracts:
            if not contract.loan_application or not contract.loan_application.client:
                continue

            client = contract.loan_application.client
            if not client.user:
                continue

            overdue_amount = contract.amortization_schedule_set.filter(
                is_paid=False,
                due_date__lt=today
            ).aggregate(
                total=Sum('principal_amount') + Sum('interest_amount')
            )['total'] or 0

            if client.id not in client_totals:
                client_totals[client.id] = {
                    'user': client.user,
                    'client_name': client.get_full_name(),
                    'total_amount': 0,
                    'contract_count': 0,
                }

            client_totals[client.id]['total_amount'] += float(overdue_amount)
            client_totals[client.id]['contract_count'] += 1

        results = []
        notifications_sent = 0
        notifications_failed = 0

        for client_id, info in client_totals.items():
            amount_str = f"Bs. {info['total_amount']:.2f}" if include_amount else ""
            title = "Cuota vencida"
            body = f"Tiene {info['contract_count']} cuota(s) vencida(s). Monto: {amount_str}"

            success, error = self.notification_service.send_to_user(
                user=info['user'],
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

            if success:
                notifications_sent += 1
            else:
                notifications_failed += 1

            results.append({
                'client_id': client_id,
                'client_name': info['client_name'],
                'user_email': info['user'].email,
                'sent': success,
                'error': error,
            })

        self.logger.info(
            f"Mora alerts completed for institution {institution_id}: "
            f"{len(client_totals)} clients with overdue, "
            f"{notifications_sent} sent, {notifications_failed} failed"
        )

        return {
            'total_clients': len(client_totals),
            'clients_with_overdue': len(client_totals),
            'notifications_sent': notifications_sent,
            'notifications_failed': notifications_failed,
            'results': results,
        }

    def send_all_mora_alerts(self, minimum_overdue_days: int = 1) -> dict:
        """
        Envía alertas de mora a TODOS los tenants/instituciones.

        Args:
            minimum_overdue_days: Días mínimos de mora para incluir

        Returns:
            Dict con estadísticas agregadas
        """
        from api.tenants.models import FinancialInstitution

        total_sent = 0
        total_failed = 0
        total_clients = 0
        all_results = []

        active_institutions = FinancialInstitution.objects.filter(is_active=True)

        for institution in active_institutions:
            try:
                result = self.send_mora_alerts(
                    institution_id=institution.id,
                    minimum_overdue_days=minimum_overdue_days,
                )

                total_sent += result['notifications_sent']
                total_failed += result['notifications_failed']
                total_clients += result['clients_with_overdue']
                all_results.append({
                    'institution_id': institution.id,
                    'institution_name': institution.name,
                    'clients_with_overdue': result['clients_with_overdue'],
                    'sent': result['notifications_sent'],
                    'failed': result['notifications_failed'],
                })

            except Exception as e:
                self.logger.error(
                    f"Error sending mora alerts for institution {institution.id}: {str(e)}",
                    exc_info=True
                )
                all_results.append({
                    'institution_id': institution.id,
                    'institution_name': institution.name,
                    'error': str(e),
                })

        self.logger.info(
            f"Mora alerts completed for all institutions: "
            f"{total_clients} total clients, {total_sent} sent, {total_failed} failed"
        )

        return {
            'total_institutions': len(active_institutions),
            'total_clients': total_clients,
            'total_sent': total_sent,
            'total_failed': total_failed,
            'results': all_results,
        }


class CreditApplicationNotificationService:
    """
    Servicio para enviar notificaciones relacionadas con solicitudes de crédito.
    """

    def __init__(self):
        self.notification_service = NotificationService()
        self.logger = logging.getLogger(__name__)

    def send_application_created(self, loan_application) -> tuple[bool, Optional[str]]:
        """
        Envía notificación cuando se crea una nueva solicitud de crédito.

        Args:
            loan_application: Instancia de LoanApplication

        Returns:
            Tuple (success, error_message)
        """
        user = loan_application.client.user
        if not user:
            self.logger.warning(f"No user found for loan application {loan_application.id}")
            return False, "No user associated"

        title = "Solicitud de crédito creada"
        body = f"Se ha creado tu solicitud de crédito #{loan_application.application_number}. "
        body += f"Monto solicitado: Bs. {loan_application.requested_amount}"

        return self.notification_service.send_to_user(
            user=user,
            title=title,
            body=body,
            notification_type='STATUS_CHANGE',
            data={
                'type': 'APPLICATION_CREATED',
                'loan_application_id': loan_application.id,
                'status': loan_application.status,
                'application_number': loan_application.application_number,
            },
            click_action=f'/loans/applications/{loan_application.id}/',
        )

    def send_application_created_to_admin(self, loan_application) -> tuple[bool, Optional[str]]:
        """
        Envía notificación al admin cuando se crea una nueva solicitud de crédito.

        Args:
            loan_application: Instancia de LoanApplication

        Returns:
            Tuple (success, error_message)
        """
        institution = loan_application.institution
        if not institution:
            self.logger.warning(f"No institution found for loan application {loan_application.id}")
            return False, "No institution associated"

        client_name = loan_application.client.get_full_name() if loan_application.client else "Cliente"
        product_name = loan_application.product.name if loan_application.product else "Producto"

        title = "Nueva solicitud de crédito"
        body = f"{client_name} ha creado una solicitud de crédito. "
        body += f"Producto: {product_name}. Monto: Bs. {loan_application.requested_amount}"

        return self.notification_service.send_to_admin_topic(
            institution_id=institution.id,
            title=title,
            body=body,
            notification_type='NEW_APPLICATION',
            data={
                'type': 'NEW_APPLICATION',
                'loan_application_id': loan_application.id,
                'status': loan_application.status,
                'application_number': loan_application.application_number,
                'client_name': client_name,
                'product_name': product_name,
            },
            click_action=f'/loans/{loan_application.id}',
        )

    def send_status_change(self, loan_application, from_status: str, to_status: str) -> tuple[bool, Optional[str]]:
        """
        Envía notificación cuando cambia el estado de una solicitud.

        Args:
            loan_application: Instancia de LoanApplication
            from_status: Estado anterior
            to_status: Nuevo estado

        Returns:
            Tuple (success, error_message)
        """
        user = loan_application.client.user
        if not user:
            self.logger.warning(f"No user found for loan application {loan_application.id}")
            return False, "No user associated"

        title, body = self._get_status_notification(to_status, loan_application)

        return self.notification_service.send_to_user(
            user=user,
            title=title,
            body=body,
            notification_type=self._get_notification_type(to_status),
            data={
                'type': 'STATUS_CHANGE',
                'loan_application_id': loan_application.id,
                'from_status': from_status,
                'to_status': to_status,
                'application_number': loan_application.application_number,
            },
            click_action=f'/loans/applications/{loan_application.id}/',
        )

    def send_rejection_notification(self, loan_application, reason: str = '') -> tuple[bool, Optional[str]]:
        """
        Envía notificación cuando una solicitud es rechazada.

        Args:
            loan_application: Instancia de LoanApplication
            reason: Razón del rechazo

        Returns:
            Tuple (success, error_message)
        """
        user = loan_application.client.user
        if not user:
            self.logger.warning(f"No user found for loan application {loan_application.id}")
            return False, "No user associated"

        title = "Solicitud rechazada"
        body = f"Tu solicitud de crédito #{loan_application.application_number} ha sido rechazada."
        if reason:
            body += f" Motivo: {reason}"

        return self.notification_service.send_to_user(
            user=user,
            title=title,
            body=body,
            notification_type='STATUS_CHANGE',
            data={
                'type': 'APPLICATION_REJECTED',
                'loan_application_id': loan_application.id,
                'reason': reason,
                'application_number': loan_application.application_number,
            },
            click_action=f'/loans/applications/{loan_application.id}/',
        )

    def send_approval_notification(self, loan_application) -> tuple[bool, Optional[str]]:
        """
        Envía notificación cuando una solicitud es aprobada.

        Args:
            loan_application: Instancia de LoanApplication

        Returns:
            Tuple (success, error_message)
        """
        user = loan_application.client.user
        if not user:
            self.logger.warning(f"No user found for loan application {loan_application.id}")
            return False, "No user associated"

        title = "¡Felicitaciones! Crédito aprobado"
        body = f"Tu solicitud de crédito #{loan_application.application_number} ha sido aprobada. "
        body += f"Monto: Bs. {loan_application.approved_amount or loan_application.requested_amount}"

        return self.notification_service.send_to_user(
            user=user,
            title=title,
            body=body,
            notification_type='STATUS_CHANGE',
            data={
                'type': 'APPLICATION_APPROVED',
                'loan_application_id': loan_application.id,
                'approved_amount': str(loan_application.approved_amount or loan_application.requested_amount),
                'application_number': loan_application.application_number,
            },
            click_action=f'/loans/applications/{loan_application.id}/',
        )

    def _get_notification_type(self, status: str) -> str:
        """Retorna el tipo de notificación según el estado."""
        type_mapping = {
            'DRAFT': 'SYSTEM',
            'SUBMITTED': 'STATUS_CHANGE',
            'IN_REVIEW': 'STATUS_CHANGE',
            'OBSERVED': 'STATUS_CHANGE',
            'DOCUMENTS': 'STATUS_CHANGE',
            'KYC': 'STATUS_CHANGE',
            'SCORING': 'STATUS_CHANGE',
            'REVIEW': 'STATUS_CHANGE',
            'APPROVED': 'STATUS_CHANGE',
            'REJECTED': 'STATUS_CHANGE',
            'DISBURSED': 'STATUS_CHANGE',
            'CANCELLED': 'STATUS_CHANGE',
        }
        return type_mapping.get(status, 'SYSTEM')

    def _get_status_notification(self, status: str, loan_application) -> tuple:
        """Retorna título y cuerpo según el estado."""
        messages = {
            'DRAFT': (
                "Solicitud en borrador",
                f"Tu solicitud #{loan_application.application_number} está en borrador."
            ),
            'SUBMITTED': (
                "Solicitud enviada",
                f"Tu solicitud #{loan_application.application_number} ha sido enviada para revisión."
            ),
            'IN_REVIEW': (
                "Solicitud en revisión",
                f"Tu solicitud #{loan_application.application_number} está siendo revisada."
            ),
            'OBSERVED': (
                "Observaciones en tu solicitud",
                f"Tu solicitud #{loan_application.application_number} tiene observaciones. Por favor revisa los comentarios."
            ),
            'DOCUMENTS': (
                "Documentos requeridos",
                f"Se requieren documentos adicionales para tu solicitud #{loan_application.application_number}."
            ),
            'KYC': (
                "Verificación de identidad",
                f"Tu identidad está siendo verificada para la solicitud #{loan_application.application_number}."
            ),
            'SCORING': (
                "Evaluación crediticia",
                f"Tu historial crediticio está siendo evaluado para la solicitud #{loan_application.application_number}."
            ),
            'REVIEW': (
                "En revisión final",
                f"Tu solicitud #{loan_application.application_number} está en revisión final."
            ),
            'APPROVED': (
                "¡Felicitaciones! Crédito aprobado",
                f"Tu solicitud #{loan_application.application_number} ha sido aprobada."
            ),
            'REJECTED': (
                "Solicitud rechazada",
                f"Tu solicitud #{loan_application.application_number} ha sido rechazada."
            ),
            'DISBURSED': (
                "Crédito desembolsado",
                f"Tu crédito #{loan_application.application_number} ha sido desembolsado."
            ),
            'CANCELLED': (
                "Solicitud cancelada",
                f"Tu solicitud #{loan_application.application_number} ha sido cancelada."
            ),
        }
        default_msg = f"Estado actualizado a {status}"
        return messages.get(status, ("Estado actualizado", default_msg))
