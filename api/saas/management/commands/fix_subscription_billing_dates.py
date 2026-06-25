"""
Corrige next_billing_date en suscripciones que lo tienen NULL.
"""
from django.core.management.base import BaseCommand
from datetime import date, datetime, timedelta
from api.saas.models import Subscription, SubscriptionPlan


class Command(BaseCommand):
    help = 'Corrige next_billing_date NULL en suscripciones existentes'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='Solo mostrar, no aplicar cambios')
        parser.add_argument('--apply', action='store_true', help='Aplicar correcciones')

    def handle(self, *args, **options):
        dry_run = not options.get('apply', False)

        subscriptions = Subscription.objects.filter(next_billing_date__isnull=True)
        total = subscriptions.count()

        self.stdout.write(f'Suscripciones con next_billing_date NULL: {total}')

        if total == 0:
            self.stdout.write(self.style.SUCCESS('Nada que corregir.'))
            return

        free_days = 30

        for sub in subscriptions.select_related('plan', 'institution'):
            try:
                new_date = None

                if sub.stripe_subscription_id:
                    try:
                        import stripe
                        from django.conf import settings
                        stripe.api_key = settings.STRIPE_SECRET_KEY
                        stripe_sub = stripe.Subscription.retrieve(sub.stripe_subscription_id)
                        from django.utils import timezone
                        stripe_sub_dict = stripe_sub.to_dict() if hasattr(stripe_sub, 'to_dict') else {}
                        current_period_end = stripe_sub_dict.get('current_period_end')
                        if current_period_end:
                            new_date = datetime.fromtimestamp(
                                current_period_end, tz=timezone.utc
                            ).date()
                    except Exception:
                        pass

                if not new_date:
                    if sub.plan.billing_cycle == 'MONTHLY':
                        days = 30
                    elif sub.plan.billing_cycle == 'QUARTERLY':
                        days = 90
                    elif sub.plan.billing_cycle == 'ANNUAL':
                        days = 365
                    else:
                        days = free_days

                    if sub.start_date:
                        new_date = sub.start_date + timedelta(days=days)
                    else:
                        new_date = date.today() + timedelta(days=days)

                if not dry_run:
                    sub.next_billing_date = new_date
                    sub.save(update_fields=['next_billing_date'])

                icon = '[SAVE]' if not dry_run else '[DRY]'
                self.stdout.write(
                    f'  {icon} {sub.institution.name}: next_billing_date = {new_date}'
                )
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'  [ERR] Suscripcion {sub.id}: {str(e)}')
                )

        if dry_run:
            self.stdout.write(self.style.WARNING(f'\nModo dry-run. {total} suscripciones necesitan correccion.'))
            self.stdout.write(self.style.WARNING('Usa --apply para aplicar las correcciones.'))
        else:
            self.stdout.write(self.style.SUCCESS(f'\nCorreccion completada para {total} suscripciones.'))
