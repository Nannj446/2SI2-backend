"""
Managers personalizados para aislamiento multi-tenant.

Este módulo implementa el patrón de thread-local storage para mantener
el contexto del tenant actual y proporciona un manager que filtra
automáticamente los queries por tenant.
"""

import threading
from django.db import models


# Thread-local storage para el tenant actual
_thread_locals = threading.local()


def set_current_tenant(tenant):
    """
    Establece el tenant actual en el thread-local storage.
    
    Args:
        tenant: Instancia de FinancialInstitution o None para superadmin
    """
    _thread_locals.tenant = tenant


def get_current_tenant():
    """
    Obtiene el tenant actual del thread-local storage.
    
    Returns:
        Instancia de FinancialInstitution o None
    """
    return getattr(_thread_locals, 'tenant', None)


def clear_current_tenant():
    """Limpia el tenant actual del thread-local storage."""
    if hasattr(_thread_locals, 'tenant'):
        delattr(_thread_locals, 'tenant')


class TenantManager(models.Manager):
    """
    Manager que filtra automáticamente los queries por tenant.
    
    Este manager utiliza el tenant almacenado en thread-local storage
    para filtrar automáticamente todos los queries. Si no hay tenant
    establecido (caso de superadmin SaaS), retorna todos los objetos.
    
    Uso:
        class MyModel(TenantModel):
            # ... campos ...
            
            objects = TenantManager()  # Filtra por tenant
            all_objects = models.Manager()  # Sin filtrar
    """
    
    def get_queryset(self):
        """
        Retorna el queryset filtrado por tenant actual.
        
        Si hay un tenant establecido, filtra por ese tenant.
        Si no hay tenant (superadmin SaaS), retorna todos los objetos.
        """
        qs = super().get_queryset()
        tenant = get_current_tenant()
        
        if tenant is not None:
            # Filtrar por tenant actual
            return qs.filter(institution=tenant)
        
        # Sin tenant (superadmin) - retornar todo
        return qs
    
    def create(self, **kwargs):
        """
        Crea un objeto asignando automáticamente el tenant actual.
        
        Si hay un tenant establecido y no se proporciona 'institution',
        se asigna automáticamente el tenant actual.
        """
        tenant = get_current_tenant()
        
        if tenant is not None and 'institution' not in kwargs:
            kwargs['institution'] = tenant
        
        return super().create(**kwargs)


class TenantQuerySet(models.QuerySet):
    """
    QuerySet personalizado para modelos multi-tenant.
    
    Proporciona métodos adicionales para trabajar con tenants.
    """
    
    def for_tenant(self, tenant):
        """
        Filtra explícitamente por un tenant específico.
        
        Args:
            tenant: Instancia de FinancialInstitution
            
        Returns:
            QuerySet filtrado por el tenant especificado
        """
        return self.filter(institution=tenant)
    
    def all_tenants(self):
        """
        Retorna objetos de todos los tenants.
        
        Útil cuando se necesita acceso explícito a todos los tenants,
        ignorando el filtrado automático.
        
        Returns:
            QuerySet sin filtrar por tenant
        """
        return self.all()


class TenantManagerWithQuerySet(TenantManager):
    """
    Manager que combina TenantManager con TenantQuerySet.
    
    Proporciona tanto el filtrado automático como los métodos
    adicionales del QuerySet personalizado.
    """
    
    def get_queryset(self):
        """Retorna el queryset personalizado filtrado por tenant."""
        qs = TenantQuerySet(self.model, using=self._db)
        tenant = get_current_tenant()
        
        if tenant is not None:
            return qs.filter(institution=tenant)
        
        return qs
