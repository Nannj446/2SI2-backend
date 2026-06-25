"""
Comando para verificar los usuarios de Banco Union
"""
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from api.tenants.models import FinancialInstitution, FinancialInstitutionMembership

User = get_user_model()


class Command(BaseCommand):
    help = 'Verifica los usuarios de Banco Union'

    def handle(self, *args, **options):
        try:
            banco_union = FinancialInstitution.objects.get(slug='banco-union')
            
            self.stdout.write(self.style.SUCCESS(f'\n=== BANCO UNION (ID: {banco_union.id}) ===\n'))
            
            # Contar membresías totales
            total_memberships = banco_union.memberships.count()
            self.stdout.write(f'Total de membresías: {total_memberships}')
            
            # Contar membresías activas
            active_memberships = banco_union.memberships.filter(is_active=True).count()
            self.stdout.write(f'Membresías activas: {active_memberships}')
            
            # Contar membresías inactivas
            inactive_memberships = banco_union.memberships.filter(is_active=False).count()
            self.stdout.write(f'Membresías inactivas: {inactive_memberships}')
            
            # Listar todas las membresías
            self.stdout.write(self.style.SUCCESS('\n=== LISTA DE MEMBRESÍAS ===\n'))
            memberships = banco_union.memberships.select_related('user').order_by('-created_at')
            
            for i, membership in enumerate(memberships, 1):
                user = membership.user
                status = '✓ ACTIVA' if membership.is_active else '✗ INACTIVA'
                self.stdout.write(
                    f'{i}. {status} | User ID: {user.id} | Email: {user.email} | '
                    f'Nombre: {user.first_name} {user.last_name} | '
                    f'Fecha: {membership.created_at.strftime("%Y-%m-%d %H:%M")}'
                )
            
            # Verificar si hay duplicados
            self.stdout.write(self.style.SUCCESS('\n=== VERIFICACIÓN DE DUPLICADOS ===\n'))
            user_ids = list(memberships.values_list('user_id', flat=True))
            unique_user_ids = set(user_ids)
            
            if len(user_ids) != len(unique_user_ids):
                self.stdout.write(self.style.WARNING(
                    f'¡ATENCIÓN! Hay usuarios duplicados: {len(user_ids)} membresías para {len(unique_user_ids)} usuarios únicos'
                ))
                
                # Encontrar duplicados
                from collections import Counter
                duplicates = [user_id for user_id, count in Counter(user_ids).items() if count > 1]
                
                for user_id in duplicates:
                    user = User.objects.get(id=user_id)
                    user_memberships = memberships.filter(user_id=user_id)
                    self.stdout.write(self.style.ERROR(
                        f'\nUsuario duplicado: {user.email} (ID: {user_id}) - {user_memberships.count()} membresías:'
                    ))
                    for m in user_memberships:
                        self.stdout.write(
                            f'  - Membresía ID: {m.id} | Activa: {m.is_active} | '
                            f'Creada: {m.created_at.strftime("%Y-%m-%d %H:%M")}'
                        )
            else:
                self.stdout.write(self.style.SUCCESS('No hay usuarios duplicados'))
            
            # Verificar la anotación que usa la vista
            self.stdout.write(self.style.SUCCESS('\n=== VERIFICACIÓN DE ANOTACIÓN (como en la vista) ===\n'))
            from django.db.models import Count, Q
            
            institution_with_count = FinancialInstitution.objects.annotate(
                users_count=Count('memberships', filter=Q(memberships__is_active=True))
            ).get(id=banco_union.id)
            
            self.stdout.write(f'users_count (anotación con is_active=True): {institution_with_count.users_count}')
            
            institution_with_all_count = FinancialInstitution.objects.annotate(
                all_users_count=Count('memberships')
            ).get(id=banco_union.id)
            
            self.stdout.write(f'all_users_count (anotación sin filtro): {institution_with_all_count.all_users_count}')
            
        except FinancialInstitution.DoesNotExist:
            self.stdout.write(self.style.ERROR('Banco Union no encontrado'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error: {str(e)}'))
