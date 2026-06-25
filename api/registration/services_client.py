from dataclasses import dataclass
from datetime import date
from django.contrib.auth import get_user_model
from django.db import transaction

from api.models import FinancialInstitution
from api.clients.models import Client
from api.saas.services import UpdateUsageCountersService, UpdateUsageCountersInput


@dataclass(frozen=True)
class ClientRegisterInput:
    """Input para registro de cliente"""
    institution_id: int
    first_name: str
    last_name: str
    email: str
    phone: str
    document_type: str
    document_number: str
    date_of_birth: date
    address: str
    password: str


@dataclass(frozen=True)
class ClientRegisterResult:
    """Resultado del registro de cliente"""
    user: object
    client_profile: object
    institution: FinancialInstitution


class ClientRegisterService:
    """Servicio para registrar nuevos clientes"""

    @transaction.atomic
    def execute(self, payload: ClientRegisterInput) -> ClientRegisterResult:
        """
        Registra un nuevo cliente en una institución financiera.
        
        1. Obtiene la institución
        2. Crea el usuario
        3. Crea el perfil de cliente
        4. Retorna el resultado
        """
        # 1. Obtener institución
        institution = FinancialInstitution.objects.get(
            id=payload.institution_id,
            is_active=True
        )

        # 2. Crear usuario
        User = get_user_model()
        user = User.objects.create_user(
            username=payload.email,
            email=payload.email,
            first_name=payload.first_name,
            last_name=payload.last_name,
            password=payload.password,
            is_active=True
        )

        # 2.1 Crear o actualizar perfil de usuario con tipo 'client'
        from api.users.models import UserProfile
        profile, created = UserProfile.objects.get_or_create(
            user=user,
            defaults={
                'user_type': 'client',
                'phone': payload.phone
            }
        )
        
        # Si ya existía (creado por signal), actualizar tipo y teléfono
        if not created:
            profile.user_type = 'client'
            profile.phone = payload.phone
            profile.save(update_fields=['user_type', 'phone'])

        # 3. Mapear tipo de documento del frontend al backend
        document_type_map = {
            'ci': 'CI',
            'passport': 'PASSPORT',
            'nit': 'NIT',
        }
        document_type = document_type_map.get(
            payload.document_type.lower(), 
            'CI'
        )

        # 4. Crear perfil de cliente con los campos correctos del modelo
        client_profile = Client.objects.create(
            user=user,  # ← FK directa al usuario
            institution=institution,
            document_type=document_type,
            document_number=payload.document_number,
            birth_date=payload.date_of_birth,
            address=payload.address,
            # Campos obligatorios que necesitan valores
            city='La Paz',  # Valor por defecto, se puede actualizar después
            department='La Paz',  # Valor por defecto, se puede actualizar después
            employment_status='OTHER',  # Valor por defecto
            monthly_income=0.00,  # Valor por defecto, se puede actualizar después
            # Campos con valores por defecto del modelo
            is_active=True,
            kyc_status='PENDING'
        )

        # 5. Crear membresía en la institución financiera
        from api.models import FinancialInstitutionMembership
        FinancialInstitutionMembership.objects.create(
            user=user,
            institution=institution,
            is_active=True
        )

        # 5.1 Asignar rol "Cliente" al usuario
        from api.roles.models import Role, UserRole
        try:
            client_role = Role.objects.get(
                institution=institution,
                name='Cliente',
                is_active=True
            )
            UserRole.objects.create(
                user=user,
                role=client_role,
                institution=institution,
                is_active=True
            )
        except Role.DoesNotExist:
            # Si no existe el rol Cliente, continuar sin asignarlo
            # (se puede crear después con el comando create_client_roles)
            pass

        # 6. Actualizar contadores de suscripción (incrementar usuarios)
        usage_service = UpdateUsageCountersService()
        usage_service.execute(UpdateUsageCountersInput(
            institution=institution,
            users_delta=1  # Incrementar contador de usuarios
        ))

        return ClientRegisterResult(
            user=user,
            client_profile=client_profile,
            institution=institution
        )