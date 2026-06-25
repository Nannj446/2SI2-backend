"""
Servicios de negocio para gestión de clientes.
"""

from dataclasses import dataclass
from typing import Optional
from decimal import Decimal
from datetime import date

from django.db import transaction
from django.db.models import Q
from django.contrib.auth import get_user_model

from api.clients.models import Client, ClientDocument

User = get_user_model()


@dataclass
class CreateClientInput:
    """Input para crear un cliente."""
    # Datos básicos (requeridos)
    client_type: str
    first_name: str
    last_name: str
    document_type: str
    document_number: str
    birth_date: date
    phone: str
    address: str
    city: str
    department: str
    employment_status: str
    monthly_income: Decimal
    
    # Datos básicos (opcionales)
    document_extension: Optional[str] = None
    gender: Optional[str] = None
    
    # Contacto (opcionales)
    email: Optional[str] = None
    mobile_phone: Optional[str] = None
    country: str = 'Bolivia'
    postal_code: Optional[str] = None
    
    # Laboral y financiero (opcionales)
    employer_name: Optional[str] = None
    employer_nit: Optional[str] = None
    job_title: Optional[str] = None
    employment_start_date: Optional[date] = None
    additional_income: Decimal = Decimal('0')
    
    # Sistema
    notes: Optional[str] = None


@dataclass
class CreateClientResult:
    """Resultado de crear un cliente."""
    success: bool
    client: Optional[Client]
    message: str
    errors: Optional[dict] = None


@dataclass
class UpdateClientInput:
    """Input para actualizar un cliente."""
    # Todos los campos son opcionales para actualización parcial
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    mobile_phone: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    department: Optional[str] = None
    employment_status: Optional[str] = None
    employer_name: Optional[str] = None
    employer_nit: Optional[str] = None
    job_title: Optional[str] = None
    employment_start_date: Optional[date] = None
    monthly_income: Optional[Decimal] = None
    additional_income: Optional[Decimal] = None
    notes: Optional[str] = None
    is_active: Optional[bool] = None


class ClientManagementService:
    """
    Servicio para gestión de clientes/prestatarios.
    """
    
    @transaction.atomic
    def create_client(
        self,
        institution_id: int,
        input_data: CreateClientInput,
        created_by: Optional[User] = None
    ) -> CreateClientResult:
        """
        Crea un nuevo cliente en el sistema.
        
        IMPORTANTE: Este método crea tanto el usuario como el cliente.
        Sigue el mismo patrón que ClientRegisterService.
        
        Args:
            institution_id: ID de la institución financiera
            input_data: Datos del cliente
            created_by: Usuario que crea el cliente
            
        Returns:
            CreateClientResult con el resultado de la operación
        """
        try:
            # Verificar si ya existe un cliente con ese documento en la institución
            existing = Client.objects.filter(
                institution_id=institution_id,
                document_number=input_data.document_number
            ).first()
            
            if existing:
                return CreateClientResult(
                    success=False,
                    client=None,
                    message='Ya existe un cliente con ese número de documento en esta institución',
                    errors={'document_number': 'Documento duplicado'}
                )
            
            # Verificar si ya existe un usuario con ese email
            if input_data.email:
                existing_user = User.objects.filter(email=input_data.email).first()
                if existing_user:
                    return CreateClientResult(
                        success=False,
                        client=None,
                        message='Ya existe un usuario con ese email',
                        errors={'email': 'Email duplicado'}
                    )
            
            # 1. Crear usuario
            user = User.objects.create_user(
                username=input_data.email or f"client_{input_data.document_number}",
                email=input_data.email or f"{input_data.document_number}@temp.local",
                first_name=input_data.first_name,
                last_name=input_data.last_name,
                password=User.objects.make_random_password(),  # Password temporal
                is_active=True
            )
            
            # 2. Crear perfil de usuario
            from api.users.models import UserProfile
            profile = UserProfile.objects.create(
                user=user,
                user_type='client',
                phone=input_data.phone
            )
            
            # 3. Crear cliente (SIN duplicar datos)
            client = Client.objects.create(
                user=user,  # ← FK directa
                institution_id=institution_id,
                client_type=input_data.client_type,
                document_type=input_data.document_type,
                document_number=input_data.document_number,
                document_extension=input_data.document_extension,
                birth_date=input_data.birth_date,
                gender=input_data.gender,
                mobile_phone=input_data.mobile_phone,
                address=input_data.address,
                city=input_data.city,
                department=input_data.department,
                country=input_data.country,
                postal_code=input_data.postal_code,
                employment_status=input_data.employment_status,
                employer_name=input_data.employer_name,
                employer_nit=input_data.employer_nit,
                job_title=input_data.job_title,
                employment_start_date=input_data.employment_start_date,
                monthly_income=input_data.monthly_income,
                additional_income=input_data.additional_income,
                notes=input_data.notes,
            )
            
            # 4. Crear membresía en la institución
            from api.models import FinancialInstitutionMembership
            FinancialInstitutionMembership.objects.create(
                user=user,
                institution_id=institution_id,
                is_active=True
            )
            
            # 5. Asignar rol "Cliente"
            from api.roles.models import Role, UserRole
            try:
                client_role = Role.objects.get(
                    institution_id=institution_id,
                    name='Cliente',
                    is_active=True
                )
                UserRole.objects.create(
                    user=user,
                    role=client_role,
                    institution_id=institution_id,
                    is_active=True
                )
            except Role.DoesNotExist:
                pass  # Continuar sin asignar rol si no existe
            
            # 6. Actualizar contadores de suscripción
            from api.saas.services import UpdateUsageCountersService, UpdateUsageCountersInput
            usage_service = UpdateUsageCountersService()
            usage_service.execute(UpdateUsageCountersInput(
                institution_id=institution_id,
                users_delta=1
            ))
            
            return CreateClientResult(
                success=True,
                client=client,
                message=f'Cliente {client.get_full_name()} creado exitosamente'
            )
            
        except Exception as e:
            return CreateClientResult(
                success=False,
                client=None,
                message=f'Error al crear cliente: {str(e)}',
                errors={'general': str(e)}
            )
    
    @transaction.atomic
    def update_client(
        self,
        client_id: int,
        institution_id: int,
        input_data: UpdateClientInput,
        updated_by: Optional[User] = None
    ) -> CreateClientResult:
        """
        Actualiza un cliente existente.
        
        IMPORTANTE: Los campos first_name, last_name, email, phone están en el usuario.
        Este método actualiza tanto el cliente como el usuario asociado.
        
        Args:
            client_id: ID del cliente
            institution_id: ID de la institución
            input_data: Datos a actualizar
            updated_by: Usuario que actualiza
            
        Returns:
            CreateClientResult con el resultado
        """
        try:
            client = Client.objects.select_related('user', 'user__profile').get(
                id=client_id,
                institution_id=institution_id
            )
            
            # Actualizar datos del usuario si se proporcionan
            user_updated = False
            if input_data.first_name is not None:
                client.user.first_name = input_data.first_name
                user_updated = True
            if input_data.last_name is not None:
                client.user.last_name = input_data.last_name
                user_updated = True
            if input_data.email is not None:
                client.user.email = input_data.email
                client.user.username = input_data.email  # Mantener sincronizado
                user_updated = True
            
            if user_updated:
                client.user.save()
            
            # Actualizar teléfono en el perfil si se proporciona
            if input_data.phone is not None and hasattr(client.user, 'profile'):
                client.user.profile.phone = input_data.phone
                client.user.profile.save()
            
            # Actualizar campos específicos del cliente
            if input_data.mobile_phone is not None:
                client.mobile_phone = input_data.mobile_phone
            if input_data.address is not None:
                client.address = input_data.address
            if input_data.city is not None:
                client.city = input_data.city
            if input_data.department is not None:
                client.department = input_data.department
            if input_data.employment_status is not None:
                client.employment_status = input_data.employment_status
            if input_data.employer_name is not None:
                client.employer_name = input_data.employer_name
            if input_data.employer_nit is not None:
                client.employer_nit = input_data.employer_nit
            if input_data.job_title is not None:
                client.job_title = input_data.job_title
            if input_data.employment_start_date is not None:
                client.employment_start_date = input_data.employment_start_date
            if input_data.monthly_income is not None:
                client.monthly_income = input_data.monthly_income
            if input_data.additional_income is not None:
                client.additional_income = input_data.additional_income
            if input_data.notes is not None:
                client.notes = input_data.notes
            if input_data.is_active is not None:
                client.is_active = input_data.is_active
            
            client.save()
            
            return CreateClientResult(
                success=True,
                client=client,
                message=f'Cliente {client.get_full_name()} actualizado exitosamente'
            )
            
        except Client.DoesNotExist:
            return CreateClientResult(
                success=False,
                client=None,
                message='Cliente no encontrado',
                errors={'client_id': 'No existe'}
            )
        except Exception as e:
            return CreateClientResult(
                success=False,
                client=None,
                message=f'Error al actualizar cliente: {str(e)}',
                errors={'general': str(e)}
            )
    
    def get_client(self, client_id: int, institution_id: int) -> Optional[Client]:
        """Obtiene un cliente por ID con datos relacionados."""
        try:
            return Client.objects.select_related('user', 'user__profile').get(
                id=client_id,
                institution_id=institution_id
            )
        except Client.DoesNotExist:
            return None
    
    def list_clients(
        self,
        institution_id: int,
        is_active: Optional[bool] = None,
        kyc_status: Optional[str] = None,
        search: Optional[str] = None
    ):
        """
        Lista clientes con filtros opcionales.
        
        Args:
            institution_id: ID de la institución
            is_active: Filtrar por estado activo
            kyc_status: Filtrar por estado KYC
            search: Búsqueda por nombre o documento
            
        Returns:
            QuerySet de clientes
        """
        queryset = Client.objects.filter(
            institution_id=institution_id
        ).select_related('user', 'user__profile')
        
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active)
        
        if kyc_status:
            queryset = queryset.filter(kyc_status=kyc_status)
        
        if search:
            queryset = queryset.filter(
                Q(user__first_name__icontains=search) |
                Q(user__last_name__icontains=search) |
                Q(document_number__icontains=search) |
                Q(user__email__icontains=search)
            )
        
        return queryset.order_by('-created_at')
    
    @transaction.atomic
    def deactivate_client(
        self,
        client_id: int,
        institution_id: int,
        reason: Optional[str] = None
    ) -> CreateClientResult:
        """Desactiva un cliente (soft delete)."""
        try:
            client = Client.objects.select_related('user').get(
                id=client_id,
                institution_id=institution_id
            )
            
            client.is_active = False
            if reason:
                client.notes = f"{client.notes or ''}\n[DESACTIVADO] {reason}"
            client.save()
            
            return CreateClientResult(
                success=True,
                client=client,
                message=f'Cliente {client.get_full_name()} desactivado'
            )
            
        except Client.DoesNotExist:
            return CreateClientResult(
                success=False,
                client=None,
                message='Cliente no encontrado',
                errors={'client_id': 'No existe'}
            )
