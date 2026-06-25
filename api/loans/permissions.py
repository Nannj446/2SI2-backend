"""
Permisos personalizados para el módulo de créditos.

Define permisos específicos para:
- Administración de reglas (CU-09)
- Revisión de documentos (CU-12)
- Visualización de timeline (CU-07)
- Gestión de créditos activos (SP3)
- Gestión de pagos (SP3)
"""

from rest_framework.permissions import BasePermission


class CanManageRules(BasePermission):
    """
    Permiso para administrar reglas y parámetros.
    
    Requiere el permiso 'loans.manage_credit_rules'.
    
    Uso:
        class MyViewSet(viewsets.ModelViewSet):
            permission_classes = [IsAuthenticated, CanManageRules]
    """
    
    def has_permission(self, request, view):
        """
        Verifica si el usuario tiene permiso para gestionar reglas.
        """
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Verificar que tenga institución
        if not hasattr(request, 'tenant') or not request.tenant:
            return False
        
        # Verificar que tenga el permiso usando el sistema personalizado
        if not hasattr(request.user, 'profile'):
            return False
        
        return request.user.profile.has_permission('loans.manage_credit_rules', request.tenant)
    
    def has_object_permission(self, request, view, obj):
        """
        Verifica permiso a nivel de objeto.
        """
        # Verificar que el objeto pertenezca al tenant del usuario
        if hasattr(obj, 'institution'):
            return obj.institution == request.tenant
        
        return True


class CanReviewDocuments(BasePermission):
    """
    Permiso para revisar documentos.
    
    Requiere el permiso 'loans.review_loan_documents'.
    
    Uso:
        class DocumentViewSet(viewsets.ModelViewSet):
            permission_classes = [IsAuthenticated, CanReviewDocuments]
    """
    
    def has_permission(self, request, view):
        """
        Verifica si el usuario tiene permiso para revisar documentos.
        """
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Verificar que tenga institución
        if not hasattr(request, 'tenant') or not request.tenant:
            return False
        
        # Verificar que tenga el permiso usando el sistema personalizado
        if not hasattr(request.user, 'profile'):
            return False
        
        return request.user.profile.has_permission('loans.review_loan_documents', request.tenant)
    
    def has_object_permission(self, request, view, obj):
        """
        Verifica permiso a nivel de objeto.
        """
        # Verificar que el documento pertenezca al tenant del usuario
        if hasattr(obj, 'institution'):
            return obj.institution == request.tenant
        
        return True


class CanViewTimeline(BasePermission):
    """
    Permiso para ver timeline de solicitudes.
    
    Reglas:
    - Clientes: solo sus propias solicitudes
    - Staff con permiso: todas las solicitudes del tenant
    
    Uso:
        class TimelineViewSet(viewsets.ReadOnlyModelViewSet):
            permission_classes = [IsAuthenticated, CanViewTimeline]
    """
    
    def has_permission(self, request, view):
        """
        Verifica si el usuario está autenticado.
        """
        return request.user and request.user.is_authenticated
    
    def has_object_permission(self, request, view, obj):
        """
        Verifica si el usuario puede ver el timeline de una solicitud específica.
        
        Args:
            obj: LoanApplication instance
        """
        # Si es staff con permiso, puede ver todas las solicitudes del tenant
        if request.user.has_perm('loans.view_all_applications'):
            # Verificar que pertenezca al mismo tenant
            if hasattr(obj, 'institution'):
                return obj.institution == request.tenant
            return True
        
        # Obtener el cliente del usuario (puede ser client o client_profile)
        client = None
        if hasattr(request.user, 'client_profile'):
            client = request.user.client_profile
        elif hasattr(request.user, 'client'):
            client = request.user.client
        
        if not client:
            return False
        
        # Verificar que el cliente sea el dueño de la solicitud
        return obj.client == client


class CanManageApplications(BasePermission):
    """
    Permiso para gestionar solicitudes de crédito.
    
    Requiere el permiso 'loans.manage_applications'.
    
    Uso:
        class ApplicationViewSet(viewsets.ModelViewSet):
            permission_classes = [IsAuthenticated, CanManageApplications]
    """
    
    def has_permission(self, request, view):
        """
        Verifica si el usuario tiene permiso para gestionar solicitudes.
        """
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Para métodos de lectura, permitir si tiene permiso de ver
        if request.method in ['GET', 'HEAD', 'OPTIONS']:
            return (
                request.user.has_perm('loans.view_applications') or
                request.user.has_perm('loans.manage_applications')
            )
        
        # Para métodos de escritura, requiere permiso de gestión
        return request.user.has_perm('loans.manage_applications')
    
    def has_object_permission(self, request, view, obj):
        """
        Verifica permiso a nivel de objeto.
        """
        # Verificar que pertenezca al tenant del usuario
        if hasattr(obj, 'institution'):
            return obj.institution == request.tenant
        
        return True


class IsApplicationOwner(BasePermission):
    """
    Permiso para verificar que el usuario es el dueño de la solicitud.
    
    Solo permite acceso si:
    - El usuario es el cliente de la solicitud
    - O tiene permiso de staff para ver todas las solicitudes
    
    Uso:
        class MyApplicationViewSet(viewsets.ReadOnlyModelViewSet):
            permission_classes = [IsAuthenticated, IsApplicationOwner]
    """
    
    def has_permission(self, request, view):
        """
        Verifica si el usuario está autenticado.
        """
        return request.user and request.user.is_authenticated
    
    def has_object_permission(self, request, view, obj):
        """
        Verifica si el usuario es el dueño de la solicitud.
        
        Args:
            obj: LoanApplication instance
        """
        # Si es staff con permiso, puede acceder
        if request.user.has_perm('loans.view_all_applications'):
            if hasattr(obj, 'institution'):
                return obj.institution == request.tenant
            return True
        
        # Obtener el cliente del usuario (puede ser client o client_profile)
        client = None
        if hasattr(request.user, 'client_profile'):
            client = request.user.client_profile
        elif hasattr(request.user, 'client'):
            client = request.user.client
        
        if not client:
            return False
        
        # Verificar que el cliente sea el dueño de la solicitud
        return obj.client == client


class IsDocumentOwner(BasePermission):
    """
    Permiso para verificar que el usuario es el dueño del documento.
    
    Solo permite acceso si:
    - El usuario es el cliente de la solicitud del documento
    - O tiene permiso de staff para revisar documentos
    
    Uso:
        class MyDocumentViewSet(viewsets.ReadOnlyModelViewSet):
            permission_classes = [IsAuthenticated, IsDocumentOwner]
    """
    
    def has_permission(self, request, view):
        """
        Verifica si el usuario está autenticado.
        """
        return request.user and request.user.is_authenticated
    
    def has_object_permission(self, request, view, obj):
        """
        Verifica si el usuario es el dueño del documento.
        
        Args:
            obj: LoanApplicationDocumentRequirement instance
        """
        import logging
        logger = logging.getLogger(__name__)
        
        # Si es staff con permiso de revisar documentos
        if request.user.has_perm('loans.review_loan_documents'):
            if hasattr(obj, 'institution'):
                return obj.institution == request.tenant
            return True
        
        # Obtener el cliente del usuario (puede ser client o client_profile)
        client = None
        if hasattr(request.user, 'client_profile'):
            client = request.user.client_profile
        elif hasattr(request.user, 'client'):
            client = request.user.client
        
        if not client:
            logger.warning(
                f"[PERMISSIONS] Usuario {request.user.id} no tiene cliente asociado "
                f"para documento {obj.id}"
            )
            return False
        
        # Verificar que el cliente sea el dueño de la solicitud
        is_owner = obj.loan_application.client == client
        
        if not is_owner:
            logger.warning(
                f"[PERMISSIONS] Usuario {request.user.id} (Cliente {client.id}) "
                f"intentó acceder a documento de solicitud {obj.loan_application_id} "
                f"(Cliente {obj.loan_application.client_id})"
            )
        
        return is_owner


# ─── SP3: Permisos para Créditos Activos y Pagos ─────────────────

class CanViewActiveCredits(BasePermission):
    """
    Permiso para ver créditos activos.

    Requiere el permiso 'active_credits.view'.

    Staff puede ver créditos de su tenant.
    Clientes solo ven sus propios créditos (vía MyActiveCreditsViewSet).
    """

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        # Verificar que tenga institución
        if not hasattr(request, 'tenant') or not request.tenant:
            return False

        # Superadmin SaaS ve todo
        if hasattr(request.user, 'profile') and request.user.profile.is_saas_admin():
            return True

        # Verificar permiso
        if not hasattr(request.user, 'profile'):
            return False

        return request.user.profile.has_permission('active_credits.view', request.tenant)

    def has_object_permission(self, request, view, obj):
        if hasattr(obj, 'institution'):
            return obj.institution == request.tenant
        return True


class CanManageActiveCredits(BasePermission):
    """
    Permiso para gestionar créditos activos (CREAR, EDITAR).

    Requiere el permiso 'active_credits.manage'.
    """

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        if not hasattr(request, 'tenant') or not request.tenant:
            return False

        # Superadmin SaaS
        if hasattr(request.user, 'profile') and request.user.profile.is_saas_admin():
            return True

        if not hasattr(request.user, 'profile'):
            return False

        return request.user.profile.has_permission('active_credits.manage', request.tenant)

    def has_object_permission(self, request, view, obj):
        if hasattr(obj, 'institution'):
            return obj.institution == request.tenant
        return True


class CanManagePayments(BasePermission):
    """
    Permiso para gestionar pagos.

    - GET: payments.view
    - POST: payments.create
    - Confirmar: payments.confirm
    - Reversar: payments.reverse
    """

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        if not hasattr(request, 'tenant') or not request.tenant:
            return False

        if hasattr(request.user, 'profile') and request.user.profile.is_saas_admin():
            return True

        if not hasattr(request.user, 'profile'):
            return False

        if request.method in ['GET', 'HEAD', 'OPTIONS']:
            return request.user.profile.has_permission('payments.view', request.tenant)

        if request.method == 'POST' and request.path.endswith('/confirm/'):
            return request.user.profile.has_permission('payments.confirm', request.tenant)

        if request.method == 'POST' and request.path.endswith('/reverse/'):
            return request.user.profile.has_permission('payments.reverse', request.tenant)

        return request.user.profile.has_permission('payments.create', request.tenant)

    def has_object_permission(self, request, view, obj):
        if hasattr(obj, 'institution'):
            return obj.institution == request.tenant
        return True


class CanApplyGracePeriod(BasePermission):
    """
    Permiso para aplicar períodos de gracia.

    Requiere el permiso 'active_credits.apply_grace_period'.
    """

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        if not hasattr(request, 'tenant') or not request.tenant:
            return False

        if hasattr(request.user, 'profile') and request.user.profile.is_saas_admin():
            return True

        if not hasattr(request.user, 'profile'):
            return False

        return request.user.profile.has_permission('active_credits.apply_grace_period', request.tenant)

    def has_object_permission(self, request, view, obj):
        if hasattr(obj, 'institution'):
            return obj.institution == request.tenant
        return True


class CanRestructure(BasePermission):
    """
    Permiso para reestructurar créditos.

    Requiere el permiso 'active_credits.restructure'.
    """

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        if not hasattr(request, 'tenant') or not request.tenant:
            return False

        if hasattr(request.user, 'profile') and request.user.profile.is_saas_admin():
            return True

        if not hasattr(request.user, 'profile'):
            return False

        return request.user.profile.has_permission('active_credits.restructure', request.tenant)

    def has_object_permission(self, request, view, obj):
        if hasattr(obj, 'institution'):
            return obj.institution == request.tenant
        return True


class CanManageSupportRequests(BasePermission):
    """
    Permiso para gestionar solicitudes de apoyo de pago.

    Requiere el permiso 'active_credits.manage'.
    Staff puede ver, revisar, aprobar y rechazar solicitudes.
    """

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        if not hasattr(request, 'tenant') or not request.tenant:
            return False

        if hasattr(request.user, 'profile') and request.user.profile.is_saas_admin():
            return True

        if not hasattr(request.user, 'profile'):
            return False

        return request.user.profile.has_permission('active_credits.manage', request.tenant)

    def has_object_permission(self, request, view, obj):
        if hasattr(obj, 'institution'):
            return obj.institution == request.tenant
        return True
