"""
Clases de paginación personalizadas para la API.
"""

from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from collections import OrderedDict


class StandardResultsSetPagination(PageNumberPagination):
    """
    Paginación estándar para listados de la API.
    
    Parámetros:
    - page: Número de página (default: 1)
    - page_size: Tamaño de página (default: 20, max: 100)
    
    Ejemplo:
    GET /api/clients/?page=2&page_size=50
    """
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100
    page_query_param = 'page'
    
    def get_paginated_response(self, data):
        """
        Formato de respuesta paginada personalizado.
        
        Retorna:
        {
            "success": true,
            "count": 100,
            "total_pages": 5,
            "current_page": 2,
            "page_size": 20,
            "next": "http://api.example.com/api/clients/?page=3",
            "previous": "http://api.example.com/api/clients/?page=1",
            "results": [...]
        }
        """
        return Response(OrderedDict([
            ('success', True),
            ('count', self.page.paginator.count),
            ('total_pages', self.page.paginator.num_pages),
            ('current_page', self.page.number),
            ('page_size', self.get_page_size(self.request)),
            ('next', self.get_next_link()),
            ('previous', self.get_previous_link()),
            ('results', data)
        ]))


class LargeResultsSetPagination(PageNumberPagination):
    """
    Paginación para listados grandes (reportes, exportaciones).
    
    Parámetros:
    - page: Número de página (default: 1)
    - page_size: Tamaño de página (default: 100, max: 1000)
    """
    page_size = 100
    page_size_query_param = 'page_size'
    max_page_size = 1000
    page_query_param = 'page'
    
    def get_paginated_response(self, data):
        return Response(OrderedDict([
            ('success', True),
            ('count', self.page.paginator.count),
            ('total_pages', self.page.paginator.num_pages),
            ('current_page', self.page.number),
            ('page_size', self.get_page_size(self.request)),
            ('next', self.get_next_link()),
            ('previous', self.get_previous_link()),
            ('results', data)
        ]))


class SmallResultsSetPagination(PageNumberPagination):
    """
    Paginación para listados pequeños (dropdowns, selects).
    
    Parámetros:
    - page: Número de página (default: 1)
    - page_size: Tamaño de página (default: 10, max: 50)
    """
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 50
    page_query_param = 'page'
    
    def get_paginated_response(self, data):
        return Response(OrderedDict([
            ('success', True),
            ('count', self.page.paginator.count),
            ('total_pages', self.page.paginator.num_pages),
            ('current_page', self.page.number),
            ('page_size', self.get_page_size(self.request)),
            ('next', self.get_next_link()),
            ('previous', self.get_previous_link()),
            ('results', data)
        ]))
