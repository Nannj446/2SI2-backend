"""
Servicio de permisos para reportes.

Centraliza la lógica de autorización para:
- Acceso a scopes (TENANT/SAAS)
- Acceso a tipos de reportes específicos
- Gestión de plantillas
- Visualización de reportes generados
"""
from typing import Optional, List
from django.contrib.auth import get_user_model

from api.reports.models import ReportTemplate, GeneratedReport
from api.reports.services.report_catalog import ReportCatalogService

User = get_user_model()


class ReportPermissionService:
    """
    Servicio para validar permisos de reportes.
    
    Implementa lógica de autorización basada en:
    - Roles de usuario
    - Scope (TENANT/SAAS)
    - Aislamiento multi-tenant
    - Propiedad de recursos
    """
    
    def __init__(self, user: User, tenant=None):
        """
        Inicializa el servicio de permisos.
        
        Args:
            user: Usuario a validar
            tenant: Tenant del contexto (opcional)
        """
        self.user = user
        self.tenant = tenant
        self.catalog_service = ReportCatalogService()
    
    # === Permisos Generales ===
    
    def can_view_catalog(self) -> bool:
        """
        Verifica si el usuario puede ver el catálogo de reportes.
        
        Returns:
            True si puede ver el catálogo
        """
        if not self.user or not self.user.is_authenticated:
            return False
        
        # Todos los usuarios autenticados pueden ver el catálogo
        return True
    
    def can_generate_report(self, scope: str = None, category: str = None, 
                           report_type: str = None) -> bool:
        """
        Verifica si el usuario puede generar reportes.
        
        Args:
            scope: Scope del reporte (opcional)
            category: Categoría del reporte (opcional)
            report_type: Tipo de reporte (opcional)
        
        Returns:
            True si puede generar el reporte
        """
        if not self.user or not self.user.is_authenticated:
            return False
        
        # Validar acceso al scope
        if scope and not self.can_access_scope(scope):
            return False
        
        # Si se especifica tipo de reporte, validar acceso específico
        if scope and category and report_type:
            return self._can_access_report_type(scope, category, report_type)
        
        # Permiso general de generación
        return True
    
    def can_export_report(self) -> bool:
        """
        Verifica si el usuario puede exportar reportes.
        
        Returns:
            True si puede exportar
        """
        if not self.user or not self.user.is_authenticated:
            return False
        
        # Todos los usuarios autenticados pueden exportar
        return True
    
    def can_use_voice(self) -> bool:
        """
        Verifica si el usuario puede usar generación por voz.
        
        Returns:
            True si puede usar voz
        """
        if not self.user or not self.user.is_authenticated:
            return False
        
        # Por ahora, todos los usuarios autenticados pueden usar voz
        # En el futuro se puede restringir por plan o rol
        return True
    
    # === Permisos de Scope ===
    
    def can_access_scope(self, scope: str) -> bool:
        """
        Verifica si el usuario puede acceder a un scope específico.
        
        Args:
            scope: TENANT o SAAS
        
        Returns:
            True si puede acceder al scope
        """
        if not self.user or not self.user.is_authenticated:
            return False
        
        if scope == 'SAAS':
            # Solo superusuarios o admins SaaS
            if self.user.is_superuser:
                return True
            
            if hasattr(self.user, 'profile'):
                return self.user.profile.is_saas_admin()
            
            return False
        
        elif scope == 'TENANT':
            # Usuario debe tener tenant
            return self.tenant is not None
        
        return False
    
    def _can_access_report_type(self, scope: str, category: str, 
                                report_type: str) -> bool:
        """
        Verifica si el usuario puede acceder a un tipo de reporte específico.
        
        Args:
            scope: Scope del reporte
            category: Categoría del reporte
            report_type: Tipo de reporte
        
        Returns:
            True si puede acceder al tipo de reporte
        """
        # Obtener definición del reporte
        definition = self.catalog_service.get_report_definition(
            scope, category, report_type
        )
        
        if not definition:
            return False
        
        # Obtener roles requeridos
        required_roles = definition.get('roles', [])
        
        # Obtener roles del usuario
        user_roles = self._get_user_roles()
        
        # Verificar si el usuario tiene alguno de los roles requeridos
        return any(role in user_roles for role in required_roles)
    
    def _get_user_roles(self) -> List[str]:
        """
        Obtiene los roles del usuario.
        
        Returns:
            Lista de roles del usuario
        """
        roles = []
        
        # Superusuario tiene todos los roles
        if self.user.is_superuser:
            return ['admin', 'manager', 'analyst', 'officer']
        
        # Obtener rol del usuario
        if hasattr(self.user, 'role'):
            role = self.user.role.lower() if self.user.role else None
            if role:
                roles.append(role)
        
        # Roles por defecto según permisos
        if self.user.is_staff:
            roles.append('admin')
        
        # Si no tiene roles, asignar rol básico
        if not roles:
            roles.append('analyst')
        
        return roles
    
    # === Permisos de Plantillas ===
    
    def can_manage_templates(self) -> bool:
        """
        Verifica si el usuario puede gestionar plantillas.
        
        Returns:
            True si puede gestionar plantillas
        """
        if not self.user or not self.user.is_authenticated:
            return False
        
        # Todos los usuarios autenticados pueden crear plantillas
        return True
    
    def can_edit_template(self, template: ReportTemplate) -> bool:
        """
        Verifica si el usuario puede editar una plantilla.
        
        Args:
            template: Plantilla a editar
        
        Returns:
            True si puede editar la plantilla
        """
        if not self.user or not self.user.is_authenticated:
            return False
        
        # Superusuario puede editar cualquier plantilla
        if self.user.is_superuser:
            return True
        
        # Creador puede editar su plantilla
        if template.created_by == self.user:
            return True
        
        # Admin del tenant puede editar plantillas del tenant
        if template.scope == 'TENANT' and template.institution == self.tenant:
            if self.user.is_staff or 'admin' in self._get_user_roles():
                return True
        
        return False
    
    def can_delete_template(self, template: ReportTemplate) -> bool:
        """
        Verifica si el usuario puede eliminar una plantilla.
        
        Args:
            template: Plantilla a eliminar
        
        Returns:
            True si puede eliminar la plantilla
        """
        # Mismos permisos que editar
        return self.can_edit_template(template)
    
    # === Permisos de Reportes Generados ===
    
    def can_view_report(self, report: GeneratedReport) -> bool:
        """
        Verifica si el usuario puede ver un reporte generado.
        
        Args:
            report: Reporte generado
        
        Returns:
            True si puede ver el reporte
        """
        if not self.user or not self.user.is_authenticated:
            return False
        
        # Superusuario puede ver cualquier reporte
        if self.user.is_superuser:
            return True
        
        # Usuario que solicitó el reporte puede verlo
        if report.requested_by == self.user:
            return True
        
        # Admin del tenant puede ver reportes del tenant
        if report.scope == 'TENANT' and report.institution == self.tenant:
            if self.user.is_staff or 'admin' in self._get_user_roles():
                return True
        
        # Manager del tenant puede ver reportes del tenant
        if report.scope == 'TENANT' and report.institution == self.tenant:
            if 'manager' in self._get_user_roles():
                return True
        
        return False
    
    def can_download_report(self, report: GeneratedReport) -> bool:
        """
        Verifica si el usuario puede descargar un reporte.
        
        Args:
            report: Reporte generado
        
        Returns:
            True si puede descargar el reporte
        """
        # Mismos permisos que ver
        return self.can_view_report(report)
    
    def can_delete_report(self, report: GeneratedReport) -> bool:
        """
        Verifica si el usuario puede eliminar un reporte generado.
        
        Args:
            report: Reporte generado
        
        Returns:
            True si puede eliminar el reporte
        """
        if not self.user or not self.user.is_authenticated:
            return False
        
        # Superusuario puede eliminar cualquier reporte
        if self.user.is_superuser:
            return True
        
        # Usuario que solicitó el reporte puede eliminarlo
        if report.requested_by == self.user:
            return True
        
        # Admin del tenant puede eliminar reportes del tenant
        if report.scope == 'TENANT' and report.institution == self.tenant:
            if self.user.is_staff or 'admin' in self._get_user_roles():
                return True
        
        return False
    
    # === Validación de Aislamiento Multi-tenant ===
    
    def validate_tenant_isolation(self, resource_tenant, resource_scope: str) -> bool:
        """
        Valida que se respete el aislamiento multi-tenant.
        
        Args:
            resource_tenant: Tenant del recurso
            resource_scope: Scope del recurso (TENANT/SAAS)
        
        Returns:
            True si el aislamiento es válido
        
        Raises:
            PermissionError: Si se viola el aislamiento
        """
        # Reportes SAAS no deben tener tenant
        if resource_scope == 'SAAS':
            if resource_tenant is not None:
                raise PermissionError(
                    "Reportes SAAS no deben tener tenant asociado"
                )
            
            # Solo usuarios con acceso SAAS pueden acceder
            if not self.can_access_scope('SAAS'):
                raise PermissionError(
                    "No tiene acceso a reportes SAAS"
                )
        
        # Reportes TENANT deben tener tenant
        elif resource_scope == 'TENANT':
            if resource_tenant is None:
                raise PermissionError(
                    "Reportes TENANT deben tener tenant asociado"
                )
            
            # Usuario debe pertenecer al mismo tenant
            if resource_tenant != self.tenant:
                raise PermissionError(
                    "No puede acceder a reportes de otro tenant"
                )
        
        return True
