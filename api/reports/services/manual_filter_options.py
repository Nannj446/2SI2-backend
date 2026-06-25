"""
Servicio para obtener opciones de filtros dinámicos.

Proporciona listas de opciones para selectores en filtros de reportes manuales.

Autor: Sistema FinCore
Fecha: 2026-05-11
"""

from django.db.models import Q
from django.contrib.auth import get_user_model
from api.clients.models import Client
from api.products.models import CreditProduct
from api.loans.models import LoanApplication
from api.loans.models_catalogs import ProductType
from api.branches.models import Branch

User = get_user_model()


class ManualFilterOptionsService:
    """
    Servicio para obtener opciones de filtros.
    """
    
    def __init__(self, institution=None):
        """
        Inicializa el servicio.
        
        Args:
            institution: Institución para filtrar datos (None para superusuarios)
        """
        self.institution = institution
    
    def get_all_options(self):
        """
        Obtiene todas las opciones de filtros disponibles.
        
        Returns:
            dict: Diccionario con todas las opciones
        """
        return {
            'users': self.get_users(),
            'products': self.get_products(),
            'clients': self.get_clients(),
            'branches': self.get_branches(),
            'product_types': self.get_product_types(),
        }
    
    def get_users(self):
        """
        Obtiene lista de usuarios para filtros.
        
        Returns:
            list: Lista de usuarios con id, nombre y email
        """
        queryset = User.objects.filter(is_active=True)
        
        if self.institution:
            # Filtrar por membresía activa en la institución
            queryset = queryset.filter(
                institution_memberships__institution=self.institution,
                institution_memberships__is_active=True
            ).distinct()
        
        users = queryset.values('id', 'first_name', 'last_name', 'email').order_by('first_name', 'last_name')[:100]
        
        return [
            {
                'id': user['id'],
                'name': f"{user['first_name']} {user['last_name']}".strip() or user['email'],
                'email': user['email']
            }
            for user in users
        ]
    
    def get_products(self):
        """
        Obtiene lista de productos crediticios para filtros.
        
        Returns:
            list: Lista de productos con id, nombre y código
        """
        queryset = CreditProduct.objects.filter(is_active=True)
        
        if self.institution:
            queryset = queryset.filter(institution=self.institution)
        
        products = queryset.values('id', 'name', 'code').order_by('name')[:100]
        
        return [
            {
                'id': product['id'],
                'name': product['name'],
                'code': product['code']
            }
            for product in products
        ]
    
    def get_clients(self):
        """
        Obtiene lista de clientes para filtros.
        
        Returns:
            list: Lista de clientes con id, nombre y documento
        """
        queryset = Client.objects.filter(is_active=True).select_related('user')
        
        if self.institution:
            queryset = queryset.filter(institution=self.institution)
        
        clients = queryset.values(
            'id', 
            'user__first_name', 
            'user__last_name', 
            'document_number'
        ).order_by('user__first_name', 'user__last_name')[:100]
        
        return [
            {
                'id': client['id'],
                'name': f"{client['user__first_name']} {client['user__last_name']}".strip(),
                'document': client['document_number']
            }
            for client in clients
        ]
    
    def get_branches(self):
        """
        Obtiene lista de sucursales para filtros.
        
        Returns:
            list: Lista de sucursales con id, nombre y ciudad
        """
        queryset = Branch.objects.filter(is_active=True)
        
        if self.institution:
            queryset = queryset.filter(institution=self.institution)
        
        branches = queryset.values('id', 'name', 'city').order_by('name')[:100]
        
        return [
            {
                'id': branch['id'],
                'name': branch['name'],
                'city': branch['city'] or ''
            }
            for branch in branches
        ]
    
    def get_product_types(self):
        """
        Obtiene lista de tipos de productos para filtros.
        
        Returns:
            list: Lista de tipos de productos
        """
        queryset = ProductType.objects.filter(is_active=True)
        
        if self.institution:
            queryset = queryset.filter(institution=self.institution)
        
        types = queryset.values('id', 'name', 'code').order_by('name')
        
        return [
            {
                'id': ptype['id'],
                'name': ptype['name'],
                'code': ptype['code']
            }
            for ptype in types
        ]
