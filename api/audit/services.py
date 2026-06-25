"""
Servicio para gestionar auditoría y logs de seguridad.
"""

from typing import Optional, Dict, Any
from django.contrib.auth import get_user_model
from django.http import HttpRequest
from api.audit.models import AuditLog, SecurityEvent
from api.tenants.models import FinancialInstitution

User = get_user_model()


class AuditService:
    """
    Servicio centralizado para registrar eventos de auditoría.
    """
    
    @staticmethod
    def log_action(
        action: str,
        resource_type: str,
        description: str,
        user: Optional[User] = None,
        resource_id: Optional[int] = None,
        institution: Optional[FinancialInstitution] = None,
        request: Optional[HttpRequest] = None,
        severity: str = 'info',
        metadata: Optional[Dict[str, Any]] = None
    ) -> AuditLog:
        """
        Registra una acción en el log de auditoría.
        
        Args:
            action: Tipo de acción (login, create, update, delete, etc.)
            resource_type: Tipo de recurso afectado
            description: Descripción de la acción
            user: Usuario que realizó la acción
            resource_id: ID del recurso afectado
            institution: Institución en cuyo contexto se realizó
            request: Request HTTP para extraer IP y user agent
            severity: Nivel de severidad (info, warning, error, critical)
            metadata: Datos adicionales
        
        Returns:
            AuditLog creado
        """
        ip_address = None
        user_agent = None
        
        if request:
            ip_address = AuditService._get_client_ip(request)
            user_agent = request.META.get('HTTP_USER_AGENT', '')
        
        audit_log = AuditLog.objects.create(
            user=user,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            description=description,
            ip_address=ip_address,
            user_agent=user_agent,
            institution=institution,
            severity=severity,
            metadata=metadata or {}
        )
        
        return audit_log
    
    @staticmethod
    def log_login(user: User, request: HttpRequest, success: bool = True):
        """Registra un intento de login."""
        severity = 'info' if success else 'warning'
        action = 'login_success' if success else 'login_failed'
        description = f"Login {'exitoso' if success else 'fallido'} para {user.email}"
        
        return AuditService.log_action(
            action=action,
            resource_type='Authentication',
            resource_id=user.id,
            description=description,
            user=user if success else None,
            request=request,
            severity=severity
        )
    
    @staticmethod
    def log_logout(user: User, request: HttpRequest):
        """Registra un logout."""
        return AuditService.log_action(
            action='logout',
            resource_type='Authentication',
            resource_id=user.id,
            description=f"Logout de {user.email}",
            user=user,
            request=request
        )
    
    @staticmethod
    def log_register(user: User, request: HttpRequest, institution_name: str):
        """Registra un registro exitoso."""
        return AuditService.log_action(
            action='register',
            resource_type='Registration',
            resource_id=user.id,
            description=f"Registro exitoso de {user.email} para institución {institution_name}",
            user=user,
            request=request,
            metadata={'institution_name': institution_name}
        )
    
    @staticmethod
    def log_create(
        user: User,
        resource_type: str,
        resource_id: int,
        description: str,
        request: Optional[HttpRequest] = None,
        institution: Optional[FinancialInstitution] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Registra la creación de un recurso."""
        return AuditService.log_action(
            action='create',
            resource_type=resource_type,
            resource_id=resource_id,
            description=description,
            user=user,
            institution=institution,
            request=request,
            metadata=metadata
        )
    
    @staticmethod
    def log_update(
        user: User,
        resource_type: str,
        resource_id: int,
        description: str,
        request: Optional[HttpRequest] = None,
        institution: Optional[FinancialInstitution] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Registra la actualización de un recurso."""
        return AuditService.log_action(
            action='update',
            resource_type=resource_type,
            resource_id=resource_id,
            description=description,
            user=user,
            institution=institution,
            request=request,
            metadata=metadata
        )
    
    @staticmethod
    def log_delete(
        user: User,
        resource_type: str,
        resource_id: int,
        description: str,
        request: Optional[HttpRequest] = None,
        institution: Optional[FinancialInstitution] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Registra la eliminación de un recurso."""
        return AuditService.log_action(
            action='delete',
            resource_type=resource_type,
            resource_id=resource_id,
            description=description,
            user=user,
            institution=institution,
            request=request,
            severity='warning',
            metadata=metadata
        )
    
    @staticmethod
    def log_permission_change(
        user: User,
        target_user: User,
        description: str,
        request: Optional[HttpRequest] = None,
        institution: Optional[FinancialInstitution] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Registra un cambio de permisos."""
        return AuditService.log_action(
            action='permission_change',
            resource_type='User',
            resource_id=target_user.id,
            description=description,
            user=user,
            institution=institution,
            request=request,
            severity='warning',
            metadata=metadata
        )
    
    @staticmethod
    def _get_client_ip(request: HttpRequest) -> str:
        """Obtiene la IP real del cliente, considerando proxies."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR', '')
        return ip


class SecurityEventService:
    """
    Servicio para gestionar eventos de seguridad.
    """
    
    @staticmethod
    def log_failed_login(
        email: str,
        request: HttpRequest,
        reason: str = 'Invalid credentials'
    ) -> SecurityEvent:
        """Registra un intento de login fallido."""
        ip_address = AuditService._get_client_ip(request)
        user_agent = request.META.get('HTTP_USER_AGENT', '')
        
        return SecurityEvent.objects.create(
            event_type='failed_login',
            email=email,
            ip_address=ip_address,
            user_agent=user_agent,
            description=f"Intento de login fallido para {email}: {reason}",
            metadata={'reason': reason}
        )
    
    @staticmethod
    def log_unauthorized_access(
        user: User,
        resource_type: str,
        resource_id: Optional[int],
        request: HttpRequest,
        required_permission: str
    ) -> SecurityEvent:
        """Registra un intento de acceso no autorizado."""
        ip_address = AuditService._get_client_ip(request)
        user_agent = request.META.get('HTTP_USER_AGENT', '')
        
        return SecurityEvent.objects.create(
            event_type='unauthorized_access',
            user=user,
            email=user.email,
            ip_address=ip_address,
            user_agent=user_agent,
            description=f"Intento de acceso no autorizado a {resource_type}#{resource_id} por {user.email}",
            metadata={
                'resource_type': resource_type,
                'resource_id': resource_id,
                'required_permission': required_permission
            }
        )
    
    @staticmethod
    def log_rate_limit_exceeded(
        request: HttpRequest,
        endpoint: str,
        user: Optional[User] = None
    ) -> SecurityEvent:
        """Registra cuando se excede el rate limit."""
        ip_address = AuditService._get_client_ip(request)
        user_agent = request.META.get('HTTP_USER_AGENT', '')
        
        return SecurityEvent.objects.create(
            event_type='rate_limit_exceeded',
            user=user,
            email=user.email if user else None,
            ip_address=ip_address,
            user_agent=user_agent,
            description=f"Rate limit excedido en {endpoint}",
            metadata={'endpoint': endpoint}
        )
    
    @staticmethod
    def log_suspicious_activity(
        user: User,
        request: HttpRequest,
        description: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> SecurityEvent:
        """Registra actividad sospechosa."""
        ip_address = AuditService._get_client_ip(request)
        user_agent = request.META.get('HTTP_USER_AGENT', '')
        
        return SecurityEvent.objects.create(
            event_type='suspicious_activity',
            user=user,
            email=user.email,
            ip_address=ip_address,
            user_agent=user_agent,
            description=description,
            metadata=metadata or {}
        )
    
    @staticmethod
    def get_unresolved_events():
        """Obtiene eventos de seguridad no resueltos."""
        return SecurityEvent.objects.filter(resolved=False).order_by('-timestamp')
    
    @staticmethod
    def resolve_event(event_id: int, resolved_by: User):
        """Marca un evento como resuelto."""
        from django.utils import timezone
        
        event = SecurityEvent.objects.get(id=event_id)
        event.resolved = True
        event.resolved_at = timezone.now()
        event.resolved_by = resolved_by
        event.save()
        
        return event
