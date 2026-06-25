"""
Servicios para gestión de suscripciones SaaS.
"""
import json
import stripe
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Optional
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .models import SubscriptionPlan, Subscription, Invoice, Payment, StripeWebhookEvent


def _sanitize_for_json(data):
    """Convierte un dict con Decimals/StripeObjects a JSON-safe dict."""
    if not isinstance(data, dict):
        return data

    def _convert(obj):
        if isinstance(obj, Decimal):
            return float(obj)
        if hasattr(obj, 'to_dict'):
            return obj.to_dict()
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        return str(obj)

    return json.loads(json.dumps(data, default=_convert))


@dataclass(frozen=True)
class AssignFreePlanInput:
    """Input para asignar plan gratuito a una institución."""
    institution: object


@dataclass(frozen=True)
class AssignFreePlanResult:
    """Resultado de asignación de plan gratuito."""
    subscription: object
    plan: object
    is_new: bool


class AssignFreePlanService:
    """Servicio para asignar plan gratuito a instituciones nuevas."""

    @transaction.atomic
    def execute(self, payload: AssignFreePlanInput) -> AssignFreePlanResult:
        """
        Asigna el plan gratuito a una institución si no tiene suscripción.
        
        Args:
            payload: AssignFreePlanInput con la institución
            
        Returns:
            AssignFreePlanResult con la suscripción creada o existente
        """
        institution = payload.institution
        
        # Verificar si ya tiene suscripción
        try:
            existing_subscription = Subscription.objects.get(institution=institution)
            return AssignFreePlanResult(
                subscription=existing_subscription,
                plan=existing_subscription.plan,
                is_new=False
            )
        except Subscription.DoesNotExist:
            pass
        
        # Obtener o crear plan gratuito
        free_plan, _ = SubscriptionPlan.objects.get_or_create(
            slug='gratuito',
            defaults={
                'name': 'Plan Gratuito',
                'description': 'Plan gratuito con funcionalidades básicas para empezar',
                'price': 0.00,
                'billing_cycle': 'MONTHLY',
                'trial_days': 0,
                'setup_fee': 0.00,
                
                # Límites básicos pero funcionales
                'max_users': 3,
                'max_branches': 1,
                'max_products': 2,
                'max_loans_per_month': 20,
                'max_storage_gb': 1,
                
                # Características básicas
                'has_ai_scoring': False,
                'has_workflows': False,
                'has_reporting': True,
                'has_mobile_app': True,
                'has_api_access': False,
                'has_white_label': False,
                'has_priority_support': False,
                'has_custom_integrations': False,
                
                'is_active': True,
                'is_featured': False,
                'display_order': -1,
                'features_list': [
                    'Hasta 3 usuarios',
                    'Hasta 2 productos crediticios',
                    'Hasta 20 solicitudes por mes',
                    'App móvil para clientes',
                    'Reportes básicos',
                    '1 GB de almacenamiento',
                    'Soporte por email'
                ]
            }
        )
        
        # Crear suscripción gratuita
        subscription = Subscription.objects.create(
            institution=institution,
            plan=free_plan,
            status='ACTIVE',
            start_date=date.today(),
            payment_status='PAID',
            next_billing_date=date.today() + timedelta(days=30),
            
            # Contadores iniciales
            current_users=1,
            current_branches=1,
            current_products=0,
            current_month_loans=0,
            current_storage_gb=0,
            
            notes='Suscripción gratuita asignada automáticamente al registrar institución'
        )
        
        return AssignFreePlanResult(
            subscription=subscription,
            plan=free_plan,
            is_new=True
        )


@dataclass(frozen=True)
class CheckSubscriptionLimitsInput:
    """Input para verificar límites de suscripción."""
    institution: object
    action: str  # 'add_user', 'add_branch', 'add_product', 'add_loan', etc.


@dataclass(frozen=True)
class CheckSubscriptionLimitsResult:
    """Resultado de verificación de límites."""
    allowed: bool
    current_usage: dict
    limits: dict
    message: str


class CheckSubscriptionLimitsService:
    """Servicio para verificar límites de suscripción."""

    def execute(self, payload: CheckSubscriptionLimitsInput) -> CheckSubscriptionLimitsResult:
        """
        Verifica si una acción está permitida según los límites del plan.
        
        Args:
            payload: CheckSubscriptionLimitsInput con institución y acción
            
        Returns:
            CheckSubscriptionLimitsResult con el resultado de la verificación
        """
        try:
            subscription = Subscription.objects.select_related('plan').get(
                institution=payload.institution,
                status__in=['TRIAL', 'ACTIVE']
            )
        except Subscription.DoesNotExist:
            return CheckSubscriptionLimitsResult(
                allowed=False,
                current_usage={},
                limits={},
                message='No hay suscripción activa para esta institución.'
            )
        
        plan = subscription.plan
        
        # Obtener uso actual y límites
        current_usage = {
            'users': subscription.current_users,
            'branches': subscription.current_branches,
            'products': subscription.current_products,
            'loans_this_month': subscription.current_month_loans,
            'storage_gb': float(subscription.current_storage_gb),
        }
        
        limits = {
            'users': plan.max_users,
            'branches': plan.max_branches,
            'products': plan.max_products,
            'loans_per_month': plan.max_loans_per_month,
            'storage_gb': plan.max_storage_gb,
        }
        
        # Verificar límite según la acción
        allowed = True
        message = 'Acción permitida'
        
        if payload.action == 'add_user':
            if subscription.current_users >= plan.max_users:
                allowed = False
                message = f'Límite de usuarios alcanzado ({plan.max_users}). Actualiza tu plan para agregar más usuarios.'

        elif payload.action == 'add_branch':
            if subscription.current_branches >= plan.max_branches:
                allowed = False
                message = f'Límite de sucursales alcanzado ({plan.max_branches}). Actualiza tu plan para agregar más sucursales.'
        
        elif payload.action == 'add_product':
            if subscription.current_products >= plan.max_products:
                allowed = False
                message = f'Límite de productos alcanzado ({plan.max_products}). Actualiza tu plan para agregar más productos.'
        
        elif payload.action == 'add_loan':
            if subscription.current_month_loans >= plan.max_loans_per_month:
                allowed = False
                message = f'Límite de créditos mensuales alcanzado ({plan.max_loans_per_month}). Actualiza tu plan o espera al próximo mes.'
        
        elif payload.action == 'check_storage':
            if subscription.current_storage_gb >= plan.max_storage_gb:
                allowed = False
                message = f'Límite de almacenamiento alcanzado ({plan.max_storage_gb} GB). Actualiza tu plan para más espacio.'
        
        return CheckSubscriptionLimitsResult(
            allowed=allowed,
            current_usage=current_usage,
            limits=limits,
            message=message
        )


@dataclass(frozen=True)
class UpdateUsageCountersInput:
    """Input para actualizar contadores de uso."""
    institution: object
    users_delta: int = 0
    branches_delta: int = 0
    products_delta: int = 0
    loans_delta: int = 0
    storage_delta: float = 0.0


class UpdateUsageCountersService:
    """Servicio para actualizar contadores de uso de suscripción."""

    @transaction.atomic
    def execute(self, payload: UpdateUsageCountersInput) -> bool:
        """
        Actualiza los contadores de uso de la suscripción.
        
        Args:
            payload: UpdateUsageCountersInput con los deltas a aplicar
            
        Returns:
            bool: True si se actualizó correctamente
        """
        try:
            subscription = Subscription.objects.select_for_update().get(
                institution=payload.institution,
                status__in=['TRIAL', 'ACTIVE']
            )
        except Subscription.DoesNotExist:
            return False
        
        # Actualizar contadores
        if payload.users_delta != 0:
            subscription.current_users = max(0, subscription.current_users + payload.users_delta)

        if payload.branches_delta != 0:
            subscription.current_branches = max(0, subscription.current_branches + payload.branches_delta)
        
        if payload.products_delta != 0:
            subscription.current_products = max(0, subscription.current_products + payload.products_delta)
        
        if payload.loans_delta != 0:
            subscription.current_month_loans = max(0, subscription.current_month_loans + payload.loans_delta)
        
        if payload.storage_delta != 0:
            subscription.current_storage_gb = max(0, subscription.current_storage_gb + payload.storage_delta)
        
        subscription.save()
        return True


class StripeSubscriptionService:
    """Servicio para integrar con Stripe para suscripciones SaaS."""

    def __init__(self):
        stripe.api_key = settings.STRIPE_SECRET_KEY

    @staticmethod
    def _sanitize_metadata(data):
        """Convierte un dict de Stripe a JSON-safe (usa la funcion del modulo)."""
        return _sanitize_for_json(data)

    def get_stripe_price_id(self, plan: SubscriptionPlan, billing_cycle: str) -> Optional[str]:
        """Obtiene el price_id de Stripe según el ciclo de facturación."""
        if billing_cycle == 'MONTHLY':
            return plan.stripe_price_monthly_id
        elif billing_cycle == 'QUARTERLY':
            return plan.stripe_price_quarterly_id
        elif billing_cycle == 'ANNUAL':
            return plan.stripe_price_annual_id
        return plan.stripe_price_monthly_id

    def sync_plan_to_stripe(self, plan: SubscriptionPlan) -> SubscriptionPlan:
        """
        Sincroniza un plan con Stripe (crea/actualiza producto y precios).
        
        Args:
            plan: SubscriptionPlan a sincronizar
            
        Returns:
            Plan actualizado con los IDs de Stripe
        """
        if plan.price == 0:
            return plan

        product_id = plan.stripe_product_id
        product_name = f"{plan.name} - {plan.get_billing_cycle_display()}"

        if not product_id:
            product = stripe.Product.create(
                name=plan.name,
                description=plan.description or "",
                metadata={"plan_id": str(plan.id), "plan_slug": plan.slug},
            )
            product_id = product.id
            plan.stripe_product_id = product_id
            plan.save()
        else:
            product = stripe.Product.retrieve(product_id)
            if product.name != product_name:
                stripe.Product.modify(product_id, name=product_name)

        interval_map = {'MONTHLY': 'month', 'QUARTERLY': 'month', 'ANNUAL': 'year'}
        interval_count_map = {'MONTHLY': 1, 'QUARTERLY': 3, 'ANNUAL': 1}

        for cycle in ['MONTHLY', 'QUARTERLY', 'ANNUAL']:
            price_field = f'stripe_price_{cycle.lower()}_id'
            existing_price_id = getattr(plan, price_field)

            # Los Price en Stripe son inmutables (no se puede cambiar unit_amount,
            # currency ni recurring). Solo verificamos que el existente siga activo;
            # si no existe o está archivado, creamos uno nuevo.
            if existing_price_id:
                try:
                    existing_price = stripe.Price.retrieve(existing_price_id)
                    if existing_price.get('active', False):
                        # El precio ya existe y está activo: lo mantenemos
                        setattr(plan, price_field, existing_price_id)
                        continue  # No hace falta crear uno nuevo
                except stripe.error.InvalidRequestError:
                    pass  # El price_id no existe en Stripe, creamos uno nuevo

            # Crear nuevo Price para este ciclo de facturación
            unit_amount = int(float(plan.price) * 100)
            # Para ciclo ANNUAL se cobra el precio * 12 (precio anual total)
            if cycle == 'ANNUAL':
                unit_amount = int(float(plan.price) * 12 * 100)

            new_price = stripe.Price.create(
                product=product_id,
                unit_amount=unit_amount,
                currency=getattr(settings, 'STRIPE_DEFAULT_CURRENCY', 'usd'),
                recurring={
                    'interval': interval_map[cycle],
                    'interval_count': interval_count_map[cycle],
                },
                metadata={"plan_id": str(plan.id), "billing_cycle": cycle},
            )
            setattr(plan, price_field, new_price.id)

        plan.save()
        return plan

    def _get_or_create_customer(self, subscription: Subscription, email: str, name: str) -> str:
        """Obtiene o crea un customer en Stripe."""
        if subscription.stripe_customer_id:
            try:
                stripe.Customer.retrieve(subscription.stripe_customer_id)
                return subscription.stripe_customer_id
            except stripe.error.InvalidRequestError:
                subscription.stripe_customer_id = None
                subscription.save()

        customer = stripe.Customer.create(
            email=email,
            name=name,
            metadata={
                "institution_id": str(subscription.institution.id),
                "institution_name": subscription.institution.name,
                "subscription_id": str(subscription.id),
            },
        )
        subscription.stripe_customer_id = customer.id
        subscription.save()
        return customer.id

    def create_checkout_session(
        self,
        subscription: Subscription,
        plan: SubscriptionPlan,
        billing_cycle: str,
        email: str,
        name: str,
    ) -> dict:
        """
        Crea una sesión de Stripe Checkout para iniciar/comprar una suscripción.
        
        Args:
            subscription: Suscripción existente o None para nueva
            plan: Plan a contratar
            billing_cycle: Ciclo de facturación (MONTHLY, QUARTERLY, ANNUAL)
            email: Email del usuario
            name: Nombre del usuario
            
        Returns:
            dict con session_id y url de Stripe
        """
        if not subscription:
            raise ValueError("Subscription es requerida")

        # Plan gratuito: asignar directo
        if plan.price == 0:
            subscription.plan = plan
            subscription.pending_plan = None
            subscription.status = 'ACTIVE'
            subscription.payment_status = 'PAID'
            subscription.start_date = date.today()
            subscription.save()
            return {"url": None, "session_id": None, "requires_payment": False, "message": "Plan gratuito asignado correctamente."}

        # Plan pago: SIEMPRE crear nueva sesion de checkout
        # No usar change_plan porque la subscripcion de Stripe puede estar en mal estado
        # (ej: creada por un checkout anterior incompleto o corrupto)
        customer_id = self._get_or_create_customer(subscription, email, name)

        price_id = self.get_stripe_price_id(plan, billing_cycle)

        if not price_id:
            plan = self.sync_plan_to_stripe(plan)
            price_id = self.get_stripe_price_id(plan, billing_cycle)
            if not price_id:
                raise ValueError(f"No se pudo obtener price_id para el plan {plan.name}")

        success_url = getattr(settings, 'STRIPE_SUCCESS_URL', f'{settings.FRONTEND_URL}/subscription/success?session_id={{CHECKOUT_SESSION_ID}}')
        cancel_url = getattr(settings, 'STRIPE_CANCEL_URL', f'{settings.FRONTEND_URL}/subscription/plans?canceled=true')

        metadata = {
            "institution_id": str(subscription.institution.id),
            "subscription_id": str(subscription.id),
            "plan_id": str(plan.id),
            "billing_cycle": billing_cycle,
        }

        subscription_data: dict = {"metadata": metadata}
        # Solo aplicar trial si es una suscripcion NUEVA (no tiene stripe_subscription_id ni status ACTIVO)
        if plan.trial_days > 0 and not subscription.stripe_subscription_id and subscription.status not in ['ACTIVE', 'PAST_DUE', 'PENDING_DOWNGRADE', 'PENDING_CANCELLATION']:
            subscription_data["trial_period_days"] = plan.trial_days

        session = stripe.checkout.Session.create(
            customer=customer_id,
            payment_method_types=["card"],
            line_items=[{"price": price_id, "quantity": 1}],
            mode="subscription",
            success_url=success_url,
            cancel_url=cancel_url,
            metadata=metadata,
            subscription_data=subscription_data,
        )

        return {"url": session.url, "session_id": session.id, "requires_payment": True}

    def create_customer_portal_session(self, subscription: Subscription) -> dict:
        """
        Crea una sesión del Stripe Customer Portal.
        """
        if not subscription.stripe_customer_id:
            raise ValueError("No existe stripe_customer_id")

        return_url = f"{settings.FRONTEND_URL}/subscription/current"

        session = stripe.billing_portal.Session.create(
            customer=subscription.stripe_customer_id,
            return_url=return_url,
        )
        return {"url": session.url}

    def cancel_subscription(self, subscription: Subscription) -> dict:
        """
        Programa la cancelación de la suscripción al final del período.
        """
        from api.audit.services import AuditService

        if subscription.stripe_subscription_id:
            stripe.Subscription.modify(
                subscription.stripe_subscription_id,
                cancel_at_period_end=True,
            )

        subscription.status = 'PENDING_CANCELLATION'
        subscription.cancel_at_period_end = True
        subscription.save()

        # Registrar auditoría
        AuditService.log_action(
            action='subscription_change',
            resource_type='Subscription',
            resource_id=subscription.id,
            description=f"Cancelación de suscripción programada para el final del período actual ({subscription.next_billing_date})",
            institution=subscription.institution,
            severity='warning',
            metadata={
                'event_type': 'SUBSCRIPTION_CANCELLATION_SCHEDULED',
                'old_plan_id': subscription.plan.id,
                'new_plan_id': subscription.plan.id,
                'old_status': 'ACTIVE',
                'new_status': 'PENDING_CANCELLATION',
            }
        )

        return {"message": "Suscripción cancelada. Estará activa hasta el final del período actual."}

    def reactivate_subscription(self, subscription: Subscription) -> dict:
        """
        Reactiva una suscripción que estaba pendiente de cancelación.
        """
        from api.audit.services import AuditService

        if subscription.stripe_subscription_id and subscription.cancel_at_period_end:
            stripe.Subscription.modify(
                subscription.stripe_subscription_id,
                cancel_at_period_end=False,
            )

        subscription.status = 'ACTIVE'
        subscription.cancel_at_period_end = False
        subscription.save()

        # Registrar auditoría
        AuditService.log_action(
            action='subscription_change',
            resource_type='Subscription',
            resource_id=subscription.id,
            description="Suscripción reactivada antes del vencimiento del período actual",
            institution=subscription.institution,
            severity='info',
            metadata={
                'event_type': 'SUBSCRIPTION_REACTIVATED',
                'old_plan_id': subscription.plan.id,
                'new_plan_id': subscription.plan.id,
                'old_status': 'PENDING_CANCELLATION',
                'new_status': 'ACTIVE',
            }
        )

        return {"message": "Suscripción reactivada."}

    @transaction.atomic
    def change_plan(self, subscription: Subscription, new_plan: SubscriptionPlan) -> dict:
        """
        Cambia el plan de la suscripción (upgrade o downgrade) de forma segura y atómica.
        """
        from api.audit.services import AuditService

        if subscription.status == 'PENDING_CANCELLATION':
            raise ValueError("No se puede cambiar de plan mientras la suscripción esté pendiente de cancelación. Por favor reactívala primero.")

        old_plan = subscription.plan
        old_price = float(old_plan.price) if old_plan.price else 0
        new_price = float(new_plan.price) if new_plan.price else 0
        
        billing_cycle = new_plan.billing_cycle
        price_id = self.get_stripe_price_id(new_plan, billing_cycle)
        if not price_id and new_price > 0:
            new_plan = self.sync_plan_to_stripe(new_plan)
            price_id = self.get_stripe_price_id(new_plan, billing_cycle)

        # Caso A: Si es de pago y tiene una suscripción de Stripe activa
        if subscription.stripe_subscription_id and subscription.status not in ['CANCELLED', 'EXPIRED']:
            stripe_sub = stripe.Subscription.retrieve(subscription.stripe_subscription_id)
            stripe_sub_dict = stripe_sub.to_dict() if hasattr(stripe_sub, 'to_dict') else {}
            items_data = stripe_sub_dict.get('items', {}).get('data', [])
            if not items_data:
                raise ValueError("No se encontraron items en la suscripcion de Stripe")
            sub_item_id = items_data[0].get('id')
            if not sub_item_id:
                raise ValueError("No se pudo obtener el item_id de la suscripcion")
            
            if new_price >= old_price:
                # UPGRADE INMEDIATO
                modified_sub = stripe.Subscription.modify(
                    subscription.stripe_subscription_id,
                    items=[{
                        'id': sub_item_id,
                        'price': price_id,
                    }],
                    proration_behavior='always_invoice',
                    payment_behavior='pending_if_incomplete',
                    metadata={
                        'plan_id': str(new_plan.id),
                        'subscription_id': str(subscription.id),
                    }
                )
                modified_sub_dict = modified_sub.to_dict() if hasattr(modified_sub, 'to_dict') else {}
                
                latest_invoice_id = modified_sub_dict.get('latest_invoice')
                invoice = None
                if latest_invoice_id:
                    invoice = stripe.Invoice.retrieve(latest_invoice_id)
                    invoice_dict = invoice.to_dict() if hasattr(invoice, 'to_dict') else {}
                
                if invoice and invoice_dict.get('status') == 'paid':
                    # Pago completado exitosamente de inmediato (tarjeta en archivo sin SCA)
                    subscription.plan = new_plan
                    subscription.pending_plan = None
                    subscription.status = 'ACTIVE'
                    
                    # Sincronizar fechas
                    current_period_start = modified_sub_dict.get('current_period_start')
                    current_period_end = modified_sub_dict.get('current_period_end')
                    if current_period_start:
                        subscription.start_date = datetime.fromtimestamp(
                            current_period_start, tz=timezone.utc
                        ).date()
                    if current_period_end:
                        subscription.next_billing_date = datetime.fromtimestamp(
                            current_period_end, tz=timezone.utc
                        ).date()
                    subscription.stripe_status = modified_sub_dict.get('status')
                    
                    # Crear Factura localmente
                    amount_paid = invoice_dict.get("amount_paid", 0) / 100
                    currency = invoice_dict.get("currency", "usd").upper()
                    
                    local_invoice, _ = Invoice.objects.update_or_create(
                        stripe_invoice_id=invoice_dict.get("id"),
                        defaults={
                            "subscription": subscription,
                            "invoice_number": invoice_dict.get("number", invoice_dict.get("id")),
                            "amount": amount_paid,
                            "currency": currency,
                            "status": "paid",
                            "hosted_invoice_url": invoice_dict.get("hosted_invoice_url"),
                            "invoice_pdf": invoice_dict.get("invoice_pdf"),
                            "paid_at": timezone.now(),
                            "metadata": _sanitize_for_json(invoice_dict),
                        }
                    )
                    subscription.total_paid = subscription.total_paid + Decimal(str(amount_paid))
                    subscription.save()
                    
                    # Crear Pago localmente
                    if invoice_dict.get("payment_intent"):
                        Payment.objects.update_or_create(
                            stripe_payment_intent_id=invoice_dict.get("payment_intent"),
                            defaults={
                                "subscription": subscription,
                                "invoice": local_invoice,
                                "amount": amount_paid,
                                "currency": currency,
                                "status": "succeeded",
                                "payment_method_type": "card",
                                "metadata": _sanitize_for_json(invoice_dict),
                            }
                        )
                    
                    AuditService.log_action(
                        action='subscription_change',
                        resource_type='Subscription',
                        resource_id=subscription.id,
                        description=f"Plan actualizado (Upgrade inmediato exitoso): de {old_plan.name} a {new_plan.name}",
                        institution=subscription.institution,
                        severity='info',
                        metadata={
                            'event_type': 'PLAN_UPGRADED',
                            'old_plan_id': old_plan.id,
                            'new_plan_id': new_plan.id,
                            'old_status': 'ACTIVE',
                            'new_status': 'ACTIVE',
                        }
                    )
                    
                    return {
                        "requires_checkout": False,
                        "message": f"Tu plan ha sido actualizado exitosamente a {new_plan.name}.",
                        "status": subscription.status,
                    }
                else:
                    # El pago requiere acción (SCA, sin tarjeta o fallido)
                    # No actualizamos el plan local todavía.
                    hosted_invoice_url = invoice_dict.get("hosted_invoice_url") if invoice else None
                    invoice_id = invoice_dict.get("id") if invoice else None
                    
                    return {
                        "requires_checkout": True,
                        "url": hosted_invoice_url,
                        "session_id": invoice_id,
                        "message": "Se requiere pago para activar este plan.",
                    }
            else:
                # DOWNGRADE PROGRAMADO
                stripe.Subscription.modify(
                    subscription.stripe_subscription_id,
                    items=[{
                        'id': sub_item_id,
                        'price': price_id,
                    }],
                    proration_behavior='none',
                )
                
                subscription.pending_plan = new_plan
                subscription.status = 'PENDING_DOWNGRADE'
                subscription.save()
                
                AuditService.log_action(
                    action='subscription_change',
                    resource_type='Subscription',
                    resource_id=subscription.id,
                    description=f"Downgrade programado para el final del período: de {old_plan.name} a {new_plan.name}",
                    institution=subscription.institution,
                    severity='info',
                    metadata={
                        'event_type': 'PLAN_DOWNGRADE_SCHEDULED',
                        'old_plan_id': old_plan.id,
                        'new_plan_id': new_plan.id,
                        'old_status': 'ACTIVE',
                        'new_status': 'PENDING_DOWNGRADE',
                    }
                )
                
                return {
                    "requires_checkout": False,
                    "message": f"El cambio a {new_plan.name} se aplicará al finalizar el período actual ({subscription.next_billing_date}).",
                    "pending_plan_id": new_plan.id,
                    "status": subscription.status,
                }
        
        # Caso B: Si es una suscripción gratuita en la base de datos (sin stripe_subscription_id)
        else:
            if new_price == 0:
                subscription.plan = new_plan
                subscription.pending_plan = None
                subscription.status = 'ACTIVE'
                subscription.save()
                return {
                    "requires_checkout": False,
                    "message": f"Plan actualizado a {new_plan.name}.",
                    "status": subscription.status,
                }
            else:
                return {
                    "requires_checkout": True,
                    "message": "Se requiere pago para activar este plan.",
                }

    @transaction.atomic
    def apply_pending_changes(self) -> dict:
        """
        Busca y aplica todos los cambios de plan (downgrades) y cancelaciones pendientes
        cuyo período de facturación haya finalizado (next_billing_date <= hoy).
        """
        from datetime import date
        from api.audit.services import AuditService
        
        today = date.today()
        downgrades_applied = 0
        cancellations_applied = 0
        
        # 1. Procesar downgrades programados vencidos
        pending_downgrades = Subscription.objects.select_for_update().filter(
            status='PENDING_DOWNGRADE',
            next_billing_date__lte=today
        )
        for sub in pending_downgrades:
            old_plan = sub.plan
            new_plan = sub.pending_plan
            
            if new_plan:
                sub.plan = new_plan
                sub.pending_plan = None
                sub.status = 'ACTIVE'
                sub.save()
                downgrades_applied += 1
                
                # Registrar auditoría
                AuditService.log_action(
                    action='subscription_change',
                    resource_type='Subscription',
                    resource_id=sub.id,
                    description=f"Downgrade aplicado al finalizar el período actual: de {old_plan.name} a {new_plan.name}",
                    institution=sub.institution,
                    severity='info',
                    metadata={
                        'event_type': 'PLAN_DOWNGRADE_APPLIED',
                        'old_plan_id': old_plan.id,
                        'new_plan_id': new_plan.id,
                        'old_status': 'PENDING_DOWNGRADE',
                        'new_status': 'ACTIVE',
                    }
                )

        # 2. Procesar cancelaciones programadas vencidas
        pending_cancellations = Subscription.objects.select_for_update().filter(
            status='PENDING_CANCELLATION',
            next_billing_date__lte=today
        )
        for sub in pending_cancellations:
            old_plan = sub.plan
            sub.status = 'CANCELLED'
            sub.end_date = today
            sub.save()
            cancellations_applied += 1
            
            # Registrar auditoría
            AuditService.log_action(
                action='subscription_change',
                resource_type='Subscription',
                resource_id=sub.id,
                description=f"Suscripción cancelada al finalizar el período actual del plan {old_plan.name}",
                institution=sub.institution,
                severity='warning',
                metadata={
                    'event_type': 'SUBSCRIPTION_CANCELLED',
                    'old_plan_id': old_plan.id,
                    'new_plan_id': old_plan.id,
                    'old_status': 'PENDING_CANCELLATION',
                    'new_status': 'CANCELLED',
                }
            )
            
        return {
            "downgrades_applied": downgrades_applied,
            "cancellations_applied": cancellations_applied,
            "total_processed": downgrades_applied + cancellations_applied,
        }


class BillingService:
    """Servicio para procesar eventos de billing de Stripe."""

    def __init__(self):
        stripe.api_key = settings.STRIPE_SECRET_KEY

    def handle_checkout_session_completed(self, event_data: dict) -> Optional[Subscription]:
        """Procesa checkout.session.completed."""
        # En stripe>=5 el event_data puede ser un StripeObject, no un dict puro.
        # El método correcto es .to_dict() — dict() falla porque StripeObject itera por índice.
        if not isinstance(event_data, dict):
            event_data = event_data.to_dict()

        raw_metadata = event_data.get("metadata", {})
        if raw_metadata and not isinstance(raw_metadata, dict) and hasattr(raw_metadata, 'to_dict'):
            metadata = raw_metadata.to_dict()
        else:
            metadata = raw_metadata or {}

        subscription_id = metadata.get("subscription_id")
        plan_id = metadata.get("plan_id")
        institution_id = metadata.get("institution_id")

        if not subscription_id:
            return None

        try:
            subscription = Subscription.objects.select_related('plan', 'institution').get(
                id=int(subscription_id)
            )
        except Subscription.DoesNotExist:
            return None

        stripe_subscription_id = event_data.get("subscription")
        if stripe_subscription_id:
            subscription.stripe_subscription_id = stripe_subscription_id

            stripe_sub = stripe.Subscription.retrieve(stripe_subscription_id)
            if stripe_sub:
                stripe_sub_dict = stripe_sub.to_dict() if hasattr(stripe_sub, 'to_dict') else {}
                current_period_start = stripe_sub_dict.get('current_period_start')
                current_period_end = stripe_sub_dict.get('current_period_end')
                if current_period_start:
                    subscription.start_date = datetime.fromtimestamp(
                        current_period_start, tz=timezone.utc
                    ).date()
                if current_period_end:
                    subscription.next_billing_date = datetime.fromtimestamp(
                        current_period_end, tz=timezone.utc
                    ).date()
                subscription.stripe_status = stripe_sub_dict.get('status')

        if plan_id:
            try:
                new_plan = SubscriptionPlan.objects.get(id=int(plan_id))
                subscription.plan = new_plan
            except SubscriptionPlan.DoesNotExist:
                pass

        if subscription.status in ['PENDING_DOWNGRADE', 'PENDING_CANCELLATION']:
            subscription.status = 'ACTIVE'
            subscription.pending_plan = None
            subscription.cancel_at_period_end = False

        subscription.payment_status = 'PAID'
        subscription.save()

        # Crear Invoice y Payment desde la sesión de checkout
        amount_paid = event_data.get("amount_total", 0) / 100
        currency = event_data.get("currency", "usd").upper()
        stripe_payment_intent_id = event_data.get("payment_intent")

        if amount_paid > 0:
            invoice_number = f"INV-{subscription.id}-{date.today().strftime('%Y%m%d')}"
            invoice, _ = Invoice.objects.update_or_create(
                stripe_invoice_id=event_data.get("invoice") or f"ch_{event_data.get('id')}",
                defaults={
                    "subscription": subscription,
                    "invoice_number": invoice_number,
                    "amount": amount_paid,
                    "currency": currency,
                    "status": "paid",
                    "paid_at": timezone.now(),
                    "metadata": _sanitize_for_json(event_data),
                }
            )

            if stripe_payment_intent_id:
                Payment.objects.update_or_create(
                    stripe_payment_intent_id=stripe_payment_intent_id,
                    defaults={
                        "subscription": subscription,
                        "invoice": invoice,
                        "amount": amount_paid,
                        "currency": currency,
                        "status": "succeeded",
                        "metadata": _sanitize_for_json(event_data),
                    }
                )

            subscription.total_paid = subscription.total_paid + amount_paid
            subscription.save(update_fields=['total_paid'])

        return subscription

    def handle_invoice_payment_succeeded(self, event_data: dict) -> Optional[Invoice]:
        """Procesa invoice.payment_succeeded."""
        if not isinstance(event_data, dict):
            event_data = event_data.to_dict()

        customer_id = event_data.get("customer")
        amount_paid = event_data.get("amount_paid", 0) / 100
        currency = event_data.get("currency", "usd").upper()
        stripe_invoice_id = event_data.get("id")
        stripe_payment_intent_id = event_data.get("payment_intent")
        hosted_invoice_url = event_data.get("hosted_invoice_url")
        invoice_pdf = event_data.get("invoice_pdf")

        if not customer_id:
            return None

        try:
            subscription = Subscription.objects.select_related('institution').get(
                stripe_customer_id=customer_id
            )
        except Subscription.DoesNotExist:
            return None

        invoice, created = Invoice.objects.update_or_create(
            stripe_invoice_id=stripe_invoice_id,
            defaults={
                "subscription": subscription,
                "invoice_number": event_data.get("number", stripe_invoice_id),
                "amount": amount_paid,
                "currency": currency,
                "status": "paid",
                "hosted_invoice_url": hosted_invoice_url,
                "invoice_pdf": invoice_pdf,
                "paid_at": timezone.now(),
                "metadata": event_data,
            }
        )

        # Actualizar next_billing_date desde la subscripcion de Stripe
        stripe_sub_id = event_data.get("subscription") or subscription.stripe_subscription_id
        if stripe_sub_id:
            try:
                stripe_sub = stripe.Subscription.retrieve(stripe_sub_id)
                if stripe_sub:
                    stripe_sub_dict = stripe_sub.to_dict() if hasattr(stripe_sub, 'to_dict') else {}
                    current_period_end = stripe_sub_dict.get('current_period_end')
                    if current_period_end:
                        subscription.next_billing_date = datetime.fromtimestamp(
                            current_period_end, tz=timezone.utc
                        ).date()
            except Exception:
                pass

        subscription.status = "ACTIVE"
        subscription.payment_status = "PAID"
        subscription.grace_until = None
        subscription.total_paid = subscription.total_paid + amount_paid
        subscription.save()

        if stripe_payment_intent_id:
            Payment.objects.update_or_create(
                stripe_payment_intent_id=stripe_payment_intent_id,
                defaults={
                    "subscription": subscription,
                    "invoice": invoice,
                    "amount": amount_paid,
                    "currency": currency,
                    "status": "succeeded",
                    "payment_method_type": event_data.get("payment_method_type", "card"),
                    "metadata": _sanitize_for_json(event_data),
                }
            )

        return invoice

    def handle_invoice_payment_failed(self, event_data: dict) -> Optional[Subscription]:
        """Procesa invoice.payment_failed."""
        if not isinstance(event_data, dict):
            event_data = event_data.to_dict()
        customer_id = event_data.get("customer")
        stripe_invoice_id = event_data.get("id")

        if not customer_id:
            return None

        try:
            subscription = Subscription.objects.get(stripe_customer_id=customer_id)
        except Subscription.DoesNotExist:
            return None

        grace_period_hours = getattr(settings, 'BILLING_GRACE_PERIOD_HOURS', 48)
        subscription.status = "PAST_DUE"
        subscription.payment_status = "FAILED"
        subscription.grace_until = timezone.now() + timedelta(hours=grace_period_hours)
        subscription.save()

        return subscription

    def handle_customer_subscription_deleted(self, event_data: dict) -> Optional[Subscription]:
        """Procesa customer.subscription.deleted (cancelación o expiración)."""
        from api.audit.services import AuditService
        
        if not isinstance(event_data, dict):
            event_data = event_data.to_dict()
        stripe_subscription_id = event_data.get("id")

        if not stripe_subscription_id:
            return None

        try:
            subscription = Subscription.objects.select_related('plan', 'institution').get(
                stripe_subscription_id=stripe_subscription_id
            )
        except Subscription.DoesNotExist:
            return None

        old_status = subscription.status
        old_plan = subscription.plan

        if subscription.status == 'PENDING_DOWNGRADE':
            if subscription.pending_plan:
                subscription.plan = subscription.pending_plan
            else:
                free_plan = SubscriptionPlan.objects.filter(price=0).first()
                if free_plan:
                    subscription.plan = free_plan
            subscription.status = 'ACTIVE'
            subscription.pending_plan = None
            subscription.cancel_at_period_end = False
            
            # Registrar auditoría
            AuditService.log_action(
                action='subscription_change',
                resource_type='Subscription',
                resource_id=subscription.id,
                description=f"Downgrade aplicado al finalizar el período: de {old_plan.name} a {subscription.plan.name}",
                institution=subscription.institution,
                severity='info',
                metadata={
                    'event_type': 'PLAN_DOWNGRADE_APPLIED',
                    'old_plan_id': old_plan.id,
                    'new_plan_id': subscription.plan.id,
                    'old_status': old_status,
                    'new_status': 'ACTIVE',
                }
            )

        elif subscription.status == 'PENDING_CANCELLATION':
            subscription.status = 'CANCELLED'
            subscription.end_date = date.today()
            
            # Registrar auditoría
            AuditService.log_action(
                action='subscription_change',
                resource_type='Subscription',
                resource_id=subscription.id,
                description=f"Suscripción cancelada al finalizar el período del plan {old_plan.name}",
                institution=subscription.institution,
                severity='warning',
                metadata={
                    'event_type': 'SUBSCRIPTION_CANCELLED',
                    'old_plan_id': old_plan.id,
                    'new_plan_id': old_plan.id,
                    'old_status': old_status,
                    'new_status': 'CANCELLED',
                }
            )

        else:
            subscription.status = 'EXPIRED'
            subscription.end_date = date.today()
            
            # Registrar auditoría
            AuditService.log_action(
                action='subscription_change',
                resource_type='Subscription',
                resource_id=subscription.id,
                description=f"Suscripción expirada del plan {old_plan.name}",
                institution=subscription.institution,
                severity='warning',
                metadata={
                    'event_type': 'SUBSCRIPTION_EXPIRED',
                    'old_plan_id': old_plan.id,
                    'new_plan_id': old_plan.id,
                    'old_status': old_status,
                    'new_status': 'EXPIRED',
                }
            )

        subscription.save()
        return subscription

    def handle_subscription_updated(self, event_data: dict) -> Optional[Subscription]:
        """Procesa customer.subscription.updated."""
        if not isinstance(event_data, dict):
            event_data = event_data.to_dict()
        stripe_subscription_id = event_data.get("id")

        if not stripe_subscription_id:
            return None

        try:
            subscription = Subscription.objects.select_related('plan').get(
                stripe_subscription_id=stripe_subscription_id
            )
        except Subscription.DoesNotExist:
            return None

        current_period_start = event_data.get("current_period_start")
        current_period_end = event_data.get("current_period_end")

        if current_period_start:
            subscription.start_date = datetime.fromtimestamp(
                current_period_start, tz=timezone.utc
            ).date()
        if current_period_end:
            subscription.next_billing_date = datetime.fromtimestamp(
                current_period_end, tz=timezone.utc
            ).date()

        subscription.stripe_status = event_data.get("status")

        # Sincronizar plan basado en el price_id de Stripe
        # Pero SOLO si la suscripción no está en PENDING_DOWNGRADE (para no pisar downgrades programados),
        # o si el nuevo plan tiene un precio >= al plan actual (lo que indica un upgrade inmediato).
        items = event_data.get("items", {}).get("data", [])
        if items:
            price_id = items[0].get("price", {}).get("id")
            if price_id:
                from django.db.models import Q
                plan = SubscriptionPlan.objects.filter(
                    Q(stripe_price_monthly_id=price_id) |
                    Q(stripe_price_quarterly_id=price_id) |
                    Q(stripe_price_annual_id=price_id)
                ).first()
                if plan:
                    old_price = float(subscription.plan.price) if subscription.plan.price else 0
                    new_price = float(plan.price) if plan.price else 0
                    
                    if subscription.status != 'PENDING_DOWNGRADE' or new_price >= old_price:
                        subscription.plan = plan

        subscription.save()
        return subscription