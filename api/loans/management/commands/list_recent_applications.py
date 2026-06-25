"""
Management command para listar solicitudes recientes

Uso:
    python manage.py list_recent_applications
"""

from django.core.management.base import BaseCommand
from api.loans.models import LoanApplication


class Command(BaseCommand):
    help = 'Lista las solicitudes más recientes'

    def handle(self, *args, **options):
        self.stdout.write(f"\n{'='*80}")
        self.stdout.write(f"SOLICITUDES RECIENTES")
        self.stdout.write(f"{'='*80}\n")
        
        apps = LoanApplication.objects.all().order_by('-created_at')[:10]
        
        for app in apps:
            self.stdout.write(f"\n📋 ID: {app.id}")
            self.stdout.write(f"   Número: {app.application_number}")
            self.stdout.write(f"   Cliente: {app.client}")
            self.stdout.write(f"   Producto: {app.product.name if app.product else 'N/A'}")
            self.stdout.write(f"   Estado: {app.status}")
            self.stdout.write(f"   KYC: {app.identity_verification_status}")
            self.stdout.write(f"   Creado: {app.created_at.strftime('%Y-%m-%d %H:%M:%S')}")
        
        self.stdout.write(f"\n{'='*80}\n")
