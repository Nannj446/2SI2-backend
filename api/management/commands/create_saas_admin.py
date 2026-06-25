"""
Management command para crear un administrador SaaS
"""
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from api.models import FinancialInstitution, FinancialInstitutionMembership, UserProfile, UserRole, Role

User = get_user_model()


class Command(BaseCommand):
    help = 'Crea un administrador SaaS'

    def add_arguments(self, parser):
        parser.add_argument('email', type=str, help='Email del administrador')
        parser.add_argument('password', type=str, help='Contraseña del administrador')
        parser.add_argument('--first-name', type=str, default='Admin', help='Nombre')
        parser.add_argument('--last-name', type=str, default='SaaS', help='Apellido')

    def handle(self, *args, **options):
        email = options['email']
        password = options['password']
        first_name = options['first_name']
        last_name = options['last_name']
        
        self.stdout.write("=" * 70)
        self.stdout.write("CREANDO ADMINISTRADOR SAAS")
        self.stdout.write("=" * 70)
        self.stdout.write("")
        
        # Verificar si el usuario ya existe
        if User.objects.filter(email=email).exists():
            self.stdout.write(self.style.WARNING(f"⚠️  Usuario con email {email} ya existe"))
            user = User.objects.get(email=email)
            self.stdout.write(f"   Actualizando usuario existente...")
        else:
            # Crear usuario
            username = email.split('@')[0]
            base_username = username
            counter = 1
            while User.objects.filter(username=username).exists():
                username = f"{base_username}{counter}"
                counter += 1
            
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name,
                is_active=True
            )
            self.stdout.write(self.style.SUCCESS(f"✅ Usuario creado: {email}"))
        
        # Obtener o crear institución SaaS Admin HQ
        saas_institution, created = FinancialInstitution.objects.get_or_create(
            slug='admin-hq',
            defaults={
                'name': 'SaaS Admin HQ',
                'institution_type': 'banking',
                'is_active': True,
            }
        )
        
        if created:
            self.stdout.write(self.style.SUCCESS(f"✅ Institución creada: {saas_institution.name}"))
        else:
            self.stdout.write(f"   Institución existente: {saas_institution.name}")
        
        # Crear o actualizar membership
        membership, created = FinancialInstitutionMembership.objects.get_or_create(
            user=user,
            institution=saas_institution,
            defaults={'is_active': True}
        )
        
        if not created and not membership.is_active:
            membership.is_active = True
            membership.save()
            self.stdout.write(f"   Membership reactivado")
        elif created:
            self.stdout.write(self.style.SUCCESS(f"✅ Membership creado"))
        else:
            self.stdout.write(f"   Membership ya existe")
        
        # Actualizar perfil a saas_admin
        if hasattr(user, 'profile'):
            profile = user.profile
            if profile.user_type != 'saas_admin':
                profile.user_type = 'saas_admin'
                profile.save()
                self.stdout.write(self.style.SUCCESS(f"✅ Perfil actualizado a saas_admin"))
            else:
                self.stdout.write(f"   Perfil ya es saas_admin")
        else:
            # Crear perfil si no existe
            profile = UserProfile.objects.create(
                user=user,
                user_type='saas_admin'
            )
            self.stdout.write(self.style.SUCCESS(f"✅ Perfil creado como saas_admin"))
        
        # Obtener o crear rol de Administrador para la institución
        admin_role, created = Role.objects.get_or_create(
            name='Administrador de Institución',
            institution=saas_institution,
            defaults={
                'description': 'Administrador con acceso completo',
                'is_active': True,
            }
        )
        
        if created:
            self.stdout.write(self.style.SUCCESS(f"✅ Rol creado: {admin_role.name}"))
            
            # Asignar todos los permisos al rol
            from api.models import Permission
            all_permissions = Permission.objects.filter(is_active=True)
            admin_role.permissions.set(all_permissions)
            self.stdout.write(f"   {all_permissions.count()} permisos asignados al rol")
        else:
            self.stdout.write(f"   Rol ya existe: {admin_role.name}")
        
        # Asignar rol al usuario
        user_role, created = UserRole.objects.get_or_create(
            user=user,
            role=admin_role,
            institution=saas_institution,
            defaults={'is_active': True}
        )
        
        if created:
            self.stdout.write(self.style.SUCCESS(f"✅ Rol asignado al usuario"))
        else:
            if not user_role.is_active:
                user_role.is_active = True
                user_role.save()
                self.stdout.write(f"   Rol reactivado")
            else:
                self.stdout.write(f"   Usuario ya tiene el rol asignado")
        
        self.stdout.write("")
        self.stdout.write("=" * 70)
        self.stdout.write(self.style.SUCCESS("✅ ADMINISTRADOR SAAS CREADO/ACTUALIZADO"))
        self.stdout.write("=" * 70)
        self.stdout.write("")
        self.stdout.write(f"Email: {email}")
        self.stdout.write(f"Contraseña: {password}")
        self.stdout.write(f"Tipo: SaaS Admin")
        self.stdout.write(f"Institución: {saas_institution.name}")
        self.stdout.write(f"Permisos: Todos ({admin_role.permissions.count()})")
        self.stdout.write("")
        self.stdout.write("Puedes iniciar sesión con estas credenciales.")
        self.stdout.write("")
