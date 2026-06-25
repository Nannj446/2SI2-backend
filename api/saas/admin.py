"""
Configuración del admin de Django para suscripciones SaaS.
"""

from django.contrib import admin
from django.utils.html import format_html
from .models import SubscriptionPlan, Subscription


@admin.register(SubscriptionPlan)
class SubscriptionPlanAdmin(admin.ModelAdmin):
    """Admin para planes de suscripción."""
    
    list_display = [
        'name',
        'price_display',
        'billing_cycle',
        'trial_days',
        'is_active_badge',
        'is_featured_badge',
        'display_order',
        'created_at',
    ]
    
    list_filter = [
        'is_active',
        'is_featured',
        'billing_cycle',
        'has_ai_scoring',
        'has_workflows',
        'has_api_access',
    ]
    
    search_fields = [
        'name',
        'slug',
        'description',
    ]
    
    readonly_fields = [
        'created_at',
        'updated_at',
        'price_per_month_display',
    ]
    
    fieldsets = (
        ('Información Básica', {
            'fields': (
                'name',
                'slug',
                'description',
            )
        }),
        ('Precio y Facturación', {
            'fields': (
                'price',
                'price_per_month_display',
                'billing_cycle',
                'trial_days',
                'setup_fee',
            )
        }),
        ('Límites de Uso', {
            'fields': (
                'max_users',
                'max_branches',
                'max_products',
                'max_loans_per_month',
                'max_storage_gb',
            )
        }),
        ('Características', {
            'fields': (
                'has_ai_scoring',
                'has_workflows',
                'has_reporting',
                'has_mobile_app',
                'has_api_access',
                'has_white_label',
                'has_priority_support',
                'has_custom_integrations',
            )
        }),
        ('Configuración', {
            'fields': (
                'is_active',
                'is_featured',
                'display_order',
                'features_list',
            )
        }),
        ('Metadata', {
            'fields': (
                'created_at',
                'updated_at',
            ),
            'classes': ('collapse',)
        }),
    )
    
    def price_display(self, obj):
        """Muestra el precio formateado."""
        return f"Bs {obj.price}"
    price_display.short_description = 'Precio'
    
    def price_per_month_display(self, obj):
        """Muestra el precio mensual equivalente."""
        return f"Bs {obj.get_price_per_month():.2f}/mes"
    price_per_month_display.short_description = 'Precio Mensual Equivalente'
    
    def is_active_badge(self, obj):
        """Badge para estado activo."""
        if obj.is_active:
            return format_html(
                '<span style="color: green;">✓ Activo</span>'
            )
        return format_html(
            '<span style="color: red;">✗ Inactivo</span>'
        )
    is_active_badge.short_description = 'Estado'
    
    def is_featured_badge(self, obj):
        """Badge para plan destacado."""
        if obj.is_featured:
            return format_html(
                '<span style="color: gold;">★ Destacado</span>'
            )
        return '-'
    is_featured_badge.short_description = 'Destacado'


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    """Admin para suscripciones."""
    
    list_display = [
        'institution',
        'plan',
        'status_badge',
        'payment_status_badge',
        'start_date',
        'next_billing_date',
        'amount_due_display',
        'usage_indicator',
    ]
    
    list_filter = [
        'status',
        'payment_status',
        'plan',
        'start_date',
    ]
    
    search_fields = [
        'institution__name',
        'plan__name',
        'notes',
    ]
    
    readonly_fields = [
        'created_at',
        'updated_at',
        'total_paid',
        'usage_percentage_display',
        'is_within_limits_display',
        'days_until_renewal_display',
    ]
    
    fieldsets = (
        ('Relaciones', {
            'fields': (
                'institution',
                'plan',
            )
        }),
        ('Estado y Fechas', {
            'fields': (
                'status',
                'start_date',
                'end_date',
                'trial_end_date',
                'next_billing_date',
                'last_billing_date',
                'days_until_renewal_display',
            )
        }),
        ('Facturación', {
            'fields': (
                'payment_status',
                'amount_due',
                'total_paid',
            )
        }),
        ('Uso Actual', {
            'fields': (
                'current_users',
                'current_branches',
                'current_products',
                'current_month_loans',
                'current_storage_gb',
                'usage_percentage_display',
                'is_within_limits_display',
            )
        }),
        ('Notas', {
            'fields': (
                'cancellation_reason',
                'notes',
            )
        }),
        ('Metadata', {
            'fields': (
                'created_at',
                'updated_at',
            ),
            'classes': ('collapse',)
        }),
    )
    
    actions = [
        'activate_subscriptions',
        'suspend_subscriptions',
        'reset_monthly_counters',
    ]
    
    def status_badge(self, obj):
        """Badge para estado de suscripción."""
        colors = {
            'TRIAL': 'blue',
            'ACTIVE': 'green',
            'SUSPENDED': 'orange',
            'CANCELLED': 'red',
            'EXPIRED': 'gray',
        }
        color = colors.get(obj.status, 'gray')
        return format_html(
            '<span style="color: {};">● {}</span>',
            color,
            obj.get_status_display()
        )
    status_badge.short_description = 'Estado'
    
    def payment_status_badge(self, obj):
        """Badge para estado de pago."""
        colors = {
            'PENDING': 'orange',
            'PAID': 'green',
            'OVERDUE': 'red',
            'FAILED': 'red',
        }
        color = colors.get(obj.payment_status, 'gray')
        return format_html(
            '<span style="color: {};">● {}</span>',
            color,
            obj.get_payment_status_display()
        )
    payment_status_badge.short_description = 'Estado de Pago'
    
    def amount_due_display(self, obj):
        """Muestra el monto adeudado formateado."""
        return f"Bs {obj.amount_due}"
    amount_due_display.short_description = 'Monto Adeudado'
    
    def usage_indicator(self, obj):
        """Indicador visual de uso."""
        if not obj.is_within_limits():
            return format_html(
                '<span style="color: red;">⚠ Límite excedido</span>'
            )
        
        usage = obj.get_usage_percentage()
        max_usage = max(usage.values())
        
        if max_usage >= 90:
            return format_html(
                '<span style="color: orange;">⚠ {:.0f}% usado</span>',
                max_usage
            )
        elif max_usage >= 75:
            return format_html(
                '<span style="color: blue;">● {:.0f}% usado</span>',
                max_usage
            )
        return format_html(
            '<span style="color: green;">✓ {:.0f}% usado</span>',
            max_usage
        )
    usage_indicator.short_description = 'Uso'
    
    def usage_percentage_display(self, obj):
        """Muestra el porcentaje de uso detallado."""
        usage = obj.get_usage_percentage()
        html = '<ul style="margin: 0; padding-left: 20px;">'
        html += f'<li>Usuarios: {usage["users"]:.1f}%</li>'
        html += f'<li>Sucursales: {usage["branches"]:.1f}%</li>'
        html += f'<li>Productos: {usage["products"]:.1f}%</li>'
        html += f'<li>Créditos del mes: {usage["loans"]:.1f}%</li>'
        html += f'<li>Almacenamiento: {usage["storage"]:.1f}%</li>'
        html += '</ul>'
        return format_html(html)
    usage_percentage_display.short_description = 'Porcentaje de Uso'
    
    def is_within_limits_display(self, obj):
        """Muestra si está dentro de los límites."""
        if obj.is_within_limits():
            return format_html(
                '<span style="color: green;">✓ Dentro de límites</span>'
            )
        return format_html(
            '<span style="color: red;">✗ Límite excedido</span>'
        )
    is_within_limits_display.short_description = 'Estado de Límites'
    
    def days_until_renewal_display(self, obj):
        """Muestra días hasta renovación."""
        days = obj.days_until_renewal()
        if days is None:
            return '-'
        if days < 0:
            return format_html(
                '<span style="color: red;">Vencido hace {} días</span>',
                abs(days)
            )
        if days <= 7:
            return format_html(
                '<span style="color: orange;">{} días</span>',
                days
            )
        return f'{days} días'
    days_until_renewal_display.short_description = 'Días hasta Renovación'
    
    def activate_subscriptions(self, request, queryset):
        """Acción para activar suscripciones."""
        count = 0
        for subscription in queryset.filter(status='TRIAL'):
            subscription.activate_subscription()
            count += 1
        self.message_user(
            request,
            f'{count} suscripción(es) activada(s) exitosamente.'
        )
    activate_subscriptions.short_description = 'Activar suscripciones seleccionadas'
    
    def suspend_subscriptions(self, request, queryset):
        """Acción para suspender suscripciones."""
        count = 0
        for subscription in queryset.filter(status__in=['TRIAL', 'ACTIVE']):
            subscription.suspend_subscription(reason='Suspendida desde admin')
            count += 1
        self.message_user(
            request,
            f'{count} suscripción(es) suspendida(s) exitosamente.'
        )
    suspend_subscriptions.short_description = 'Suspender suscripciones seleccionadas'
    
    def reset_monthly_counters(self, request, queryset):
        """Acción para resetear contadores mensuales."""
        count = 0
        for subscription in queryset:
            subscription.reset_monthly_counters()
            count += 1
        self.message_user(
            request,
            f'Contadores mensuales reseteados para {count} suscripción(es).'
        )
    reset_monthly_counters.short_description = 'Resetear contadores mensuales'
