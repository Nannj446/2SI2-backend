"""
Comando para asignar plan gratuito a instituciones existentes.
"""
from django.core.management.base import BaseCommand
from django.db import transaction

from api.tenants.models import FinancialInstitution
from api.saas.services import AssignFreePlanService, AssignFreePlanInput


class Command(BaseCommand):
    """Comando para asignar plan gratuito a instituciones existentes."""
    
    help = 'Asigna el plan gratuito a todas las instituciones que no tienen suscripción'
    
    def add_arguments(self, parser):
        """Agregar argumentos del comando."""
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Ejecutar en modo simulación sin hacer cambios reales',
        )
        
        parser.add_argument(
            '--institution-id',
            type=int,
            help='Asignar plan solo a una institución específica (por ID)',
        )
    
    def handle(self, *args, **options):
        """Ejecutar el comando."""
        dry_run = options['dry_run']
        institution_id = options.get('institution_id')
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING('🔍 MODO SIMULACIÓN - No se harán cambios reales')
            )
        
        # Obtener instituciones
        if institution_id:
            try:
                institutions = [FinancialInstitution.objects.get(id=institution_id)]
                self.stdout.write(f'📋 Procesando institución específica: ID {institution_id}')
            except FinancialInstitution.DoesNotExist:
                self.stdout.write(
                    self.style.ERROR(f'❌ Institución con ID {institution_id} no encontrada')
                )
                return
        else:
            institutions = FinancialInstitution.objects.filter(is_active=True)
            self.stdout.write(f'📋 Procesando {institutions.count()} instituciones activas')
        
        service = AssignFreePlanService()
        processed = 0
        assigned = 0
        already_had = 0
        errors = 0
        
        for institution in institutions:
            processed += 1
            
            try:
                if not dry_run:
                    with transaction.atomic():
                        result = service.execute(AssignFreePlanInput(institution=institution))
                        
                        if result.is_new:
                            assigned += 1
                            self.stdout.write(
                                self.style.SUCCESS(
                                    f'✅ {institution.name} (ID: {institution.id}) - '
                                    f'Plan gratuito asignado'
                                )
                            )
                        else:
                            already_had += 1
                            self.stdout.write(
                                f'ℹ️  {institution.name} (ID: {institution.id}) - '
                                f'Ya tenía suscripción: {result.subscription.plan.name}'
                            )
                else:
                    # Modo simulación - solo verificar si ya tiene suscripción
                    from api.saas.models import Subscription
                    try:
                        existing = Subscription.objects.get(institution=institution)
                        already_had += 1
                        self.stdout.write(
                            f'ℹ️  {institution.name} (ID: {institution.id}) - '
                            f'Ya tiene suscripción: {existing.plan.name}'
                        )
                    except Subscription.DoesNotExist:
                        assigned += 1
                        self.stdout.write(
                            self.style.SUCCESS(
                                f'✅ {institution.name} (ID: {institution.id}) - '
                                f'Se asignaría plan gratuito'
                            )
                        )
                        
            except Exception as e:
                errors += 1
                self.stdout.write(
                    self.style.ERROR(
                        f'❌ Error en {institution.name} (ID: {institution.id}): {str(e)}'
                    )
                )
        
        # Resumen final
        self.stdout.write('\n' + '='*60)
        self.stdout.write(self.style.SUCCESS('📊 RESUMEN:'))
        self.stdout.write(f'   Instituciones procesadas: {processed}')
        
        if dry_run:
            self.stdout.write(f'   Se asignarían planes: {assigned}')
        else:
            self.stdout.write(f'   Planes asignados: {assigned}')
            
        self.stdout.write(f'   Ya tenían suscripción: {already_had}')
        
        if errors > 0:
            self.stdout.write(self.style.ERROR(f'   Errores: {errors}'))
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING('\n💡 Ejecuta sin --dry-run para aplicar los cambios')
            )
        else:
            self.stdout.write(
                self.style.SUCCESS('\n🎉 Proceso completado exitosamente')
            )