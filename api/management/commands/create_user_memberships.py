"""
Comando para crear membresías de usuarios a instituciones.
"""
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from api.tenants.models import FinancialInstitution, FinancialInstitutionMembership
from api.users.models import UserProfile

User = get_user_model()


class Command(BaseCommand):
    help = 'Crea membresías para usuarios sin institución asociada'

    def add_arguments(self, parser):
        parser.add_argument(
            '--user-id',
            type=int,
            help='ID del usuario específico'
        )
        parser.add_argument(
            '--institution-id',
            type=int,
            help='ID de la institución específica'
        )
        parser.add_argument(
            '--all',
            action='store_true',
            help='Crear membresías para todos los usuarios sin membresía'
        )

    def handle(self, *args, **options):
        if options['user_id'] and options['institution_id']:
            # Crear membresía específica
            self._create_membership_for_user(options['user_id'], options['institution_id'])
        elif options['all']:
            # Crear membresías para todos los usuarios sin membresía
            self._create_memberships_for_all_users()
        else:
            self.stdout.write(
                self.style.WARNING(
                    'Usa --user-id <ID> --institution-id <ID> para crear membresía específica '
                    'o --all para crear membresías automáticas'
                )
            )

    def _create_membership_for_user(self, user_id, institution_id):
        """Crea una membresía específica."""
        try:
            user = User.objects.get(id=user_id)
            institution = FinancialInstitution.objects.get(id=institution_id)
            
            # Verificar si ya tiene membresía activa
            existing = FinancialInstitutionMembership.objects.filter(
                user=user,
                is_active=True
            ).first()
            
            if existing:
                self.stdout.write(
                    self.style.WARNING(
                        f'{user.email} ya tiene membresía activa en {existing.institution.name}'
                    )
                )
                return
            
            # Crear membresía
            membership = FinancialInstitutionMembership.objects.create(
                user=user,
                institution=institution,
                is_active=True
            )
            
            self.stdout.write(
                self.style.SUCCESS(
                    f'Membresía creada: {user.email} → {institution.name}'
                )
            )
            
        except User.DoesNotExist:
            self.stdout.write(
                self.style.ERROR(f'Usuario con ID {user_id} no encontrado')
            )
        except FinancialInstitution.DoesNotExist:
            self.stdout.write(
                self.style.ERROR(f'Institución con ID {institution_id} no encontrada')
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error creando membresía: {str(e)}')
            )

    def _create_memberships_for_all_users(self):
        """Crea membresías automáticas para usuarios sin membresía."""
        # Obtener usuarios sin membresía activa
        users_without_membership = User.objects.exclude(
            institution_memberships__is_active=True
        ).filter(is_active=True)
        
        # Obtener instituciones disponibles
        institutions = list(FinancialInstitution.objects.filter(is_active=True))
        
        if not institutions:
            self.stdout.write(
                self.style.ERROR('No hay instituciones disponibles')
            )
            return
        
        # Usar la primera institución como default
        default_institution = institutions[0]
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Asignando usuarios a institución por defecto: {default_institution.name}'
            )
        )
        
        created_count = 0
        for user in users_without_membership:
            try:
                # Verificar si el usuario tiene perfil
                if not hasattr(user, 'profile'):
                    # Crear perfil si no existe
                    UserProfile.objects.create(
                        user=user,
                        user_type='admin'  # Tipo por defecto
                    )
                
                # Crear membresía
                membership = FinancialInstitutionMembership.objects.create(
                    user=user,
                    institution=default_institution,
                    is_active=True
                )
                
                self.stdout.write(
                    self.style.SUCCESS(
                        f'Membresía creada: {user.email} → {default_institution.name}'
                    )
                )
                created_count += 1
                
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(
                        f'Error creando membresía para {user.email}: {str(e)}'
                    )
                )
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Proceso completado. {created_count} membresías creadas.'
            )
        )