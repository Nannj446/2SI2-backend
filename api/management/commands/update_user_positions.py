"""
Management command para actualizar los cargos de usuarios existentes.
"""
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from api.models import UserProfile, UserRole

User = get_user_model()


class Command(BaseCommand):
    help = 'Actualiza los cargos de usuarios que no tienen cargo asignado'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Muestra qué se haría sin aplicar cambios',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        self.stdout.write(self.style.SUCCESS('=' * 80))
        self.stdout.write(self.style.SUCCESS('ACTUALIZACIÓN DE CARGOS DE USUARIOS'))
        self.stdout.write(self.style.SUCCESS('=' * 80))
        
        if dry_run:
            self.stdout.write(self.style.WARNING('\n⚠️  MODO DRY-RUN: No se aplicarán cambios\n'))
        
        # Obtener usuarios sin cargo
        users_without_position = User.objects.filter(
            profile__position=''
        ).select_related('profile')
        
        total_users = users_without_position.count()
        self.stdout.write(f'\nUsuarios sin cargo: {total_users}\n')
        
        if total_users == 0:
            self.stdout.write(self.style.SUCCESS('✓ Todos los usuarios tienen cargo asignado'))
            return
        
        updated_count = 0
        
        for user in users_without_position:
            # Determinar cargo basado en el tipo de usuario y roles
            if user.profile.user_type == 'saas_admin':
                position = 'Administrador SaaS'
            else:
                # Obtener el primer rol activo del usuario
                user_role = UserRole.objects.filter(
                    user=user,
                    is_active=True
                ).select_related('role').first()
                
                if user_role:
                    # Mapear nombre de rol a cargo
                    role_name = user_role.role.name
                    position = self._map_role_to_position(role_name)
                else:
                    # Sin roles, asignar cargo genérico
                    position = 'Empleado'
            
            self.stdout.write(f'  {user.email}')
            self.stdout.write(f'    Tipo: {user.profile.user_type}')
            self.stdout.write(f'    Cargo asignado: {position}')
            
            if not dry_run:
                user.profile.position = position
                user.profile.save()
                updated_count += 1
            
            self.stdout.write('')
        
        self.stdout.write(self.style.SUCCESS('=' * 80))
        if dry_run:
            self.stdout.write(self.style.WARNING(f'Se actualizarían {total_users} usuarios'))
        else:
            self.stdout.write(self.style.SUCCESS(f'✓ {updated_count} usuarios actualizados'))
        self.stdout.write(self.style.SUCCESS('=' * 80))
    
    def _map_role_to_position(self, role_name: str) -> str:
        """
        Mapea el nombre de un rol a un cargo apropiado.
        
        Args:
            role_name: Nombre del rol
        
        Returns:
            str: Cargo correspondiente
        """
        role_to_position = {
            'Administrador de Institución': 'Administrador',
            'Gerente de Crédito': 'Gerente de Crédito',
            'Analista de Crédito Senior': 'Analista Senior',
            'Analista de Crédito Junior': 'Analista Junior',
            'Oficial de Crédito': 'Oficial de Crédito',
            'Oficial de Cobranza': 'Oficial de Cobranza',
            'Verificador': 'Verificador de Documentos',
            'Auditor': 'Auditor',
        }
        
        return role_to_position.get(role_name, 'Empleado')
