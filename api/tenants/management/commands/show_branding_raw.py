"""
Comando para mostrar el branding raw desde la base de datos.
"""
from django.core.management.base import BaseCommand
from api.tenants.models import TenantBranding, FinancialInstitution


class Command(BaseCommand):
    help = 'Muestra el branding raw desde la base de datos'

    def add_arguments(self, parser):
        parser.add_argument(
            'tenant_id',
            type=int,
            help='ID del tenant',
        )

    def handle(self, *args, **options):
        tenant_id = options['tenant_id']
        
        try:
            tenant = FinancialInstitution.objects.get(id=tenant_id)
        except FinancialInstitution.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'Tenant {tenant_id} no encontrado'))
            return
        
        try:
            branding = TenantBranding.objects.select_related(
                'logo_file', 'favicon_file', 'cover_file'
            ).get(institution=tenant)
            
            self.stdout.write(f'\n🏢 Tenant: {tenant.name} (ID: {tenant.id})')
            self.stdout.write(f'\n📋 Branding ID: {branding.id}')
            self.stdout.write(f'   Display Name: {branding.display_name}')
            self.stdout.write(f'   Activo: {branding.is_active}')
            self.stdout.write(f'   Creado: {branding.created_at}')
            self.stdout.write(f'   Actualizado: {branding.updated_at}')
            
            self.stdout.write(f'\n🎨 Colores (RAW):')
            self.stdout.write(f'   primary_color = "{branding.primary_color}"')
            self.stdout.write(f'   secondary_color = "{branding.secondary_color}"')
            self.stdout.write(f'   accent_color = "{branding.accent_color}"')
            self.stdout.write(f'   background_color = "{branding.background_color}"')
            self.stdout.write(f'   text_color = "{branding.text_color}"')
            
            self.stdout.write(f'\n📁 Archivos (RAW):')
            self.stdout.write(f'   logo_file_id = {branding.logo_file_id}')
            self.stdout.write(f'   favicon_file_id = {branding.favicon_file_id}')
            self.stdout.write(f'   cover_file_id = {branding.cover_file_id}')
            self.stdout.write(f'   logo (deprecado) = {branding.logo}')
            
            if branding.logo_file:
                self.stdout.write(f'\n   Logo File:')
                self.stdout.write(f'      - file_path: {branding.logo_file.file_path}')
                self.stdout.write(f'      - status: {branding.logo_file.status}')
            
            if branding.favicon_file:
                self.stdout.write(f'\n   Favicon File:')
                self.stdout.write(f'      - file_path: {branding.favicon_file.file_path}')
                self.stdout.write(f'      - status: {branding.favicon_file.status}')
            
            if branding.cover_file:
                self.stdout.write(f'\n   Cover File:')
                self.stdout.write(f'      - file_path: {branding.cover_file.file_path}')
                self.stdout.write(f'      - status: {branding.cover_file.status}')
            
            self.stdout.write('\n')
            
        except TenantBranding.DoesNotExist:
            self.stdout.write(self.style.WARNING(f'Branding no encontrado para tenant {tenant_id}'))
