"""
Comando para generar reportes de seguridad.
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from collections import Counter
from api.audit.models import SecurityEvent, AuditLog


class Command(BaseCommand):
    help = 'Genera un reporte de seguridad del sistema'

    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=7,
            help='Número de días a analizar (default: 7)'
        )
        parser.add_argument(
            '--detailed',
            action='store_true',
            help='Mostrar reporte detallado'
        )

    def handle(self, *args, **options):
        days = options['days']
        detailed = options['detailed']
        
        self.stdout.write(self.style.SUCCESS(f'\n=== REPORTE DE SEGURIDAD - Últimos {days} días ===\n'))
        
        # Calcular fecha de inicio
        start_date = timezone.now() - timedelta(days=days)
        
        # Obtener eventos de seguridad
        security_events = SecurityEvent.objects.filter(timestamp__gte=start_date)
        
        # Obtener logs de auditoría
        audit_logs = AuditLog.objects.filter(timestamp__gte=start_date)
        
        # Resumen de eventos de seguridad
        self._print_security_events_summary(security_events)
        
        # Resumen de auditoría
        self._print_audit_summary(audit_logs)
        
        # IPs sospechosas
        self._print_suspicious_ips(security_events)
        
        # Eventos no resueltos
        self._print_unresolved_events(security_events)
        
        if detailed:
            self._print_detailed_events(security_events)
        
        self.stdout.write(self.style.SUCCESS('\n=== FIN DEL REPORTE ===\n'))

    def _print_security_events_summary(self, events):
        """Imprime resumen de eventos de seguridad."""
        self.stdout.write(self.style.WARNING('\n📊 EVENTOS DE SEGURIDAD\n'))
        
        total = events.count()
        unresolved = events.filter(resolved=False).count()
        
        self.stdout.write(f'Total de eventos: {total}')
        self.stdout.write(self.style.ERROR(f'Eventos no resueltos: {unresolved}'))
        
        # Contar por tipo
        event_types = Counter(events.values_list('event_type', flat=True))
        
        self.stdout.write('\nPor tipo de evento:')
        for event_type, count in event_types.most_common():
            self.stdout.write(f'  - {event_type}: {count}')

    def _print_audit_summary(self, logs):
        """Imprime resumen de auditoría."""
        self.stdout.write(self.style.WARNING('\n📝 AUDITORÍA\n'))
        
        total = logs.count()
        self.stdout.write(f'Total de acciones auditadas: {total}')
        
        # Contar por acción
        actions = Counter(logs.values_list('action', flat=True))
        
        self.stdout.write('\nPor tipo de acción:')
        for action, count in actions.most_common():
            self.stdout.write(f'  - {action}: {count}')
        
        # Contar por severidad
        severities = Counter(logs.values_list('severity', flat=True))
        
        self.stdout.write('\nPor severidad:')
        for severity, count in severities.most_common():
            style = self.style.ERROR if severity in ['error', 'critical'] else self.style.WARNING
            self.stdout.write(style(f'  - {severity}: {count}'))

    def _print_suspicious_ips(self, events):
        """Imprime IPs con actividad sospechosa."""
        self.stdout.write(self.style.WARNING('\n🚨 IPs SOSPECHOSAS\n'))
        
        # Contar eventos por IP
        ip_counts = Counter(events.values_list('ip_address', flat=True))
        
        # Mostrar IPs con más de 5 eventos
        suspicious = [(ip, count) for ip, count in ip_counts.items() if count > 5]
        
        if suspicious:
            self.stdout.write('IPs con más de 5 eventos de seguridad:')
            for ip, count in sorted(suspicious, key=lambda x: x[1], reverse=True):
                self.stdout.write(self.style.ERROR(f'  - {ip}: {count} eventos'))
        else:
            self.stdout.write(self.style.SUCCESS('No se detectaron IPs sospechosas'))

    def _print_unresolved_events(self, events):
        """Imprime eventos no resueltos."""
        self.stdout.write(self.style.WARNING('\n⚠️  EVENTOS NO RESUELTOS\n'))
        
        unresolved = events.filter(resolved=False).order_by('-timestamp')[:10]
        
        if unresolved:
            self.stdout.write(f'Mostrando los 10 más recientes:\n')
            for event in unresolved:
                self.stdout.write(
                    f'  [{event.timestamp.strftime("%Y-%m-%d %H:%M")}] '
                    f'{event.event_type} - {event.ip_address} - {event.description}'
                )
        else:
            self.stdout.write(self.style.SUCCESS('Todos los eventos están resueltos'))

    def _print_detailed_events(self, events):
        """Imprime eventos detallados."""
        self.stdout.write(self.style.WARNING('\n📋 EVENTOS DETALLADOS\n'))
        
        for event in events.order_by('-timestamp')[:20]:
            self.stdout.write(f'\n{"-" * 80}')
            self.stdout.write(f'Tipo: {event.event_type}')
            self.stdout.write(f'Fecha: {event.timestamp}')
            self.stdout.write(f'IP: {event.ip_address}')
            if event.user:
                self.stdout.write(f'Usuario: {event.user.email}')
            self.stdout.write(f'Descripción: {event.description}')
            self.stdout.write(f'Resuelto: {"Sí" if event.resolved else "No"}')
