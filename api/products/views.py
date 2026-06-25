"""
Views para gestión de productos crediticios (REFACTORIZADO).
"""

from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import action
from drf_spectacular.utils import extend_schema, OpenApiParameter
from drf_spectacular.types import OpenApiTypes

from api.products.models import CreditProduct
from api.products.serializers import (
    CreditProductSerializer,
    CreditProductWithParametersSerializer,
    CreateCreditProductSerializer,
    UpdateCreditProductSerializer,
    CreditProductListSerializer,
    CreditProductParameterSerializer,
    ProductCalculationRequestSerializer,
    ProductCalculationResponseSerializer,
)
from api.products.services import ProductCalculationService
from api.core.permissions import require_permission
from api.core.pagination import StandardResultsSetPagination


class CreditProductListCreateAPIView(APIView):
    """
    Vista para listar y crear productos crediticios.
    
    GET /api/products/ - Lista todos los productos de la institución
    POST /api/products/ - Crea un nuevo producto
    """
    permission_classes = [IsAuthenticated, require_permission('products.view')]
    
    @extend_schema(
        tags=['Productos'],
        summary='Listar productos crediticios',
        description='Obtiene la lista de productos crediticios de la institución con filtros y paginación',
        parameters=[
            OpenApiParameter(
                name='page',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description='Número de página (default: 1)',
                required=False,
            ),
            OpenApiParameter(
                name='page_size',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description='Tamaño de página (default: 20, max: 100)',
                required=False,
            ),
            OpenApiParameter(
                name='is_active',
                type=OpenApiTypes.BOOL,
                location=OpenApiParameter.QUERY,
                description='Filtrar por estado activo/inactivo',
                required=False,
            ),
            OpenApiParameter(
                name='product_type_id',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description='Filtrar por ID de tipo de producto',
                required=False,
            ),
            OpenApiParameter(
                name='rule_set_id',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description='Filtrar por ID de conjunto de reglas',
                required=False,
            ),
        ],
        responses={
            200: CreditProductListSerializer(many=True),
            401: OpenApiTypes.OBJECT,
            403: OpenApiTypes.OBJECT,
        },
    )
    def get(self, request):
        """Lista productos con filtros opcionales y paginación."""
        institution_id = request.user_institution_id
        
        # Parámetros de filtro
        is_active = request.query_params.get('is_active')
        product_type_id = request.query_params.get('product_type_id')
        rule_set_id = request.query_params.get('rule_set_id')
        
        # Construir queryset
        queryset = CreditProduct.objects.filter(institution_id=institution_id).select_related('product_type', 'rule_set')
        
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == 'true')
        
        if product_type_id:
            queryset = queryset.filter(product_type_id=product_type_id)
        
        if rule_set_id:
            queryset = queryset.filter(rule_set_id=rule_set_id)
        
        queryset = queryset.order_by('display_order', 'name')
        
        # Aplicar paginación
        paginator = StandardResultsSetPagination()
        paginated_queryset = paginator.paginate_queryset(queryset, request)
        
        # Serializar
        serializer = CreditProductListSerializer(paginated_queryset, many=True)
        
        # Retornar respuesta paginada
        return paginator.get_paginated_response(serializer.data)
    
    def post(self, request):
        """Crea un nuevo producto crediticio."""
        # Verificar permiso de creación
        if not (hasattr(request.user, 'profile') and 
                (request.user.profile.is_saas_admin() or 
                 request.user.profile.has_permission('products.create', request.tenant))):
            return Response({
                'success': False,
                'message': 'No tiene permiso para crear productos'
            }, status=status.HTTP_403_FORBIDDEN)
        
        serializer = CreateCreditProductSerializer(
            data=request.data,
            context={'request': request}
        )
        
        if not serializer.is_valid():
            return Response({
                'success': False,
                'message': 'Datos inválidos',
                'errors': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Crear producto con documentos requeridos
        product = serializer.save(institution_id=request.user_institution_id)
        
        # Serializar el producto creado
        product_serializer = CreditProductSerializer(product)
        
        return Response({
            'success': True,
            'message': 'Producto creado exitosamente',
            'product': product_serializer.data
        }, status=status.HTTP_201_CREATED)


class CreditProductDetailAPIView(APIView):
    """
    Vista para operaciones sobre un producto específico.
    
    GET /api/products/{id}/ - Obtiene detalle del producto
    PATCH /api/products/{id}/ - Actualiza el producto
    DELETE /api/products/{id}/ - Desactiva el producto
    """
    permission_classes = [IsAuthenticated, require_permission('products.view')]
    
    def get(self, request, product_id):
        """Obtiene el detalle de un producto."""
        try:
            product = CreditProduct.objects.get(
                id=product_id,
                institution_id=request.user_institution_id
            )
            serializer = CreditProductSerializer(product)
            
            return Response({
                'success': True,
                'product': serializer.data
            })
            
        except CreditProduct.DoesNotExist:
            return Response({
                'success': False,
                'message': 'Producto no encontrado'
            }, status=status.HTTP_404_NOT_FOUND)
    
    def patch(self, request, product_id):
        """Actualiza un producto."""
        import logging
        logger = logging.getLogger(__name__)
        
        # Verificar permiso de edición
        if not (hasattr(request.user, 'profile') and 
                (request.user.profile.is_saas_admin() or 
                 request.user.profile.has_permission('products.edit', request.tenant))):
            return Response({
                'success': False,
                'message': 'No tiene permiso para editar productos'
            }, status=status.HTTP_403_FORBIDDEN)
        
        try:
            product = CreditProduct.objects.get(
                id=product_id,
                institution_id=request.user_institution_id
            )
        except CreditProduct.DoesNotExist:
            return Response({
                'success': False,
                'message': 'Producto no encontrado'
            }, status=status.HTTP_404_NOT_FOUND)
        
        logger.error(f"PATCH /api/products/{product_id}/ - request.data: {request.data}")
        
        serializer = UpdateCreditProductSerializer(
            product,
            data=request.data,
            partial=True,
            context={'request': request}
        )
        
        if not serializer.is_valid():
            logger.error(f"PATCH /api/products/{product_id}/ - VALIDATION FAILED")
            logger.error(f"PATCH /api/products/{product_id}/ - serializer.errors: {serializer.errors}")
            return Response({
                'success': False,
                'message': 'Datos inválidos',
                'errors': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)
        
        serializer.save()
        
        # Retornar producto actualizado
        product_serializer = CreditProductSerializer(product)
        
        return Response({
            'success': True,
            'message': 'Producto actualizado exitosamente',
            'product': product_serializer.data
        })
    
    def delete(self, request, product_id):
        """Desactiva un producto (soft delete)."""
        # Verificar permiso de eliminación
        if not (hasattr(request.user, 'profile') and 
                (request.user.profile.is_saas_admin() or 
                 request.user.profile.has_permission('products.delete', request.tenant))):
            return Response({
                'success': False,
                'message': 'No tiene permiso para eliminar productos'
            }, status=status.HTTP_403_FORBIDDEN)
        
        try:
            product = CreditProduct.objects.get(
                id=product_id,
                institution_id=request.user_institution_id
            )
            product.is_active = False
            product.save()
            
            return Response({
                'success': True,
                'message': f'Producto {product.name} desactivado exitosamente'
            })
            
        except CreditProduct.DoesNotExist:
            return Response({
                'success': False,
                'message': 'Producto no encontrado'
            }, status=status.HTTP_404_NOT_FOUND)



class CreditProductParametersAPIView(APIView):
    """
    Vista para obtener los parámetros activos de un producto.
    
    GET /api/products/{id}/parameters/ - Obtiene parámetros del RuleSet activo
    """
    permission_classes = [IsAuthenticated, require_permission('products.view')]
    
    @extend_schema(
        tags=['Productos'],
        summary='Obtener parámetros del producto',
        description='Obtiene los parámetros activos del producto desde el RuleSet activo',
        responses={
            200: CreditProductParameterSerializer,
            404: OpenApiTypes.OBJECT,
        },
    )
    def get(self, request, product_id):
        """Obtiene los parámetros activos del producto."""
        try:
            product = CreditProduct.objects.get(
                id=product_id,
                institution_id=request.user_institution_id
            )
            
            parameters = product.get_active_parameters()
            
            if not parameters:
                return Response({
                    'success': False,
                    'message': 'No hay parámetros configurados para este producto'
                }, status=status.HTTP_404_NOT_FOUND)
            
            serializer = CreditProductParameterSerializer(parameters)
            
            return Response({
                'success': True,
                'parameters': serializer.data
            })
            
        except CreditProduct.DoesNotExist:
            return Response({
                'success': False,
                'message': 'Producto no encontrado'
            }, status=status.HTTP_404_NOT_FOUND)


class CreditProductCalculateAPIView(APIView):
    """
    Vista para calcular costos de un producto.
    
    POST /api/products/{id}/calculate/ - Calcula cuota y costos totales
    """
    permission_classes = [IsAuthenticated, require_permission('products.view')]
    
    @extend_schema(
        tags=['Productos'],
        summary='Calcular costos del producto',
        description='Calcula la cuota mensual y costos totales para un monto y plazo específicos',
        request=ProductCalculationRequestSerializer,
        responses={
            200: ProductCalculationResponseSerializer,
            400: OpenApiTypes.OBJECT,
            404: OpenApiTypes.OBJECT,
        },
    )
    def post(self, request, product_id):
        """Calcula costos del producto."""
        try:
            product = CreditProduct.objects.get(
                id=product_id,
                institution_id=request.user_institution_id
            )
            
            # Validar request
            request_serializer = ProductCalculationRequestSerializer(data=request.data)
            if not request_serializer.is_valid():
                return Response({
                    'success': False,
                    'message': 'Datos inválidos',
                    'errors': request_serializer.errors
                }, status=status.HTTP_400_BAD_REQUEST)
            
            data = request_serializer.validated_data
            
            # Validar que el producto tenga parámetros
            if not product.get_active_parameters():
                return Response({
                    'success': False,
                    'message': 'El producto no tiene parámetros configurados'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Validar monto y plazo
            validation = ProductCalculationService.validate_product_request(
                product=product,
                amount=data['amount'],
                term_months=data['term_months']
            )
            
            if not validation['valid']:
                return Response({
                    'success': False,
                    'message': 'Validación fallida',
                    'errors': validation['errors']
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Calcular
            calculation = ProductCalculationService.calculate_for_product(
                product=product,
                amount=data['amount'],
                term_months=data['term_months'],
                interest_rate=data.get('interest_rate'),
                commission_rate=data.get('commission_rate'),
                insurance_rate=data.get('insurance_rate'),
                amortization_system=data.get('amortization_system'),
            )
            
            if not calculation:
                return Response({
                    'success': False,
                    'message': 'No se pudo calcular'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            response_serializer = ProductCalculationResponseSerializer(calculation)
            
            return Response({
                'success': True,
                'calculation': response_serializer.data
            })
            
        except CreditProduct.DoesNotExist:
            return Response({
                'success': False,
                'message': 'Producto no encontrado'
            }, status=status.HTTP_404_NOT_FOUND)


class CreditProductRangesAPIView(APIView):
    """
    Vista para obtener los rangos configurados de un producto.
    
    GET /api/products/{id}/ranges/ - Obtiene rangos de montos, plazos, tasas, etc.
    """
    permission_classes = [IsAuthenticated, require_permission('products.view')]
    
    @extend_schema(
        tags=['Productos'],
        summary='Obtener rangos del producto',
        description='Obtiene los rangos configurados (montos, plazos, tasas, etc.) del producto',
        responses={
            200: OpenApiTypes.OBJECT,
            404: OpenApiTypes.OBJECT,
        },
    )
    def get(self, request, product_id):
        """Obtiene los rangos configurados del producto."""
        try:
            product = CreditProduct.objects.get(
                id=product_id,
                institution_id=request.user_institution_id
            )
            
            ranges = ProductCalculationService.get_product_ranges(product)
            
            if not ranges:
                return Response({
                    'success': False,
                    'message': 'No hay parámetros configurados para este producto'
                }, status=status.HTTP_404_NOT_FOUND)
            
            return Response({
                'success': True,
                'ranges': ranges
            })
            
        except CreditProduct.DoesNotExist:
            return Response({
                'success': False,
                'message': 'Producto no encontrado'
            }, status=status.HTTP_404_NOT_FOUND)


class CreditProductWithParametersAPIView(APIView):
    """
    Vista para obtener producto con sus parámetros.
    
    GET /api/products/{id}/full/ - Obtiene producto completo con parámetros
    """
    permission_classes = [IsAuthenticated, require_permission('products.view')]
    
    @extend_schema(
        tags=['Productos'],
        summary='Obtener producto completo',
        description='Obtiene el producto con todos sus parámetros activos incluidos',
        responses={
            200: CreditProductWithParametersSerializer,
            404: OpenApiTypes.OBJECT,
        },
    )
    def get(self, request, product_id):
        """Obtiene producto con parámetros."""
        try:
            product = CreditProduct.objects.select_related('product_type').get(
                id=product_id,
                institution_id=request.user_institution_id
            )
            
            serializer = CreditProductWithParametersSerializer(product)
            
            return Response({
                'success': True,
                'product': serializer.data
            })
            
        except CreditProduct.DoesNotExist:
            return Response({
                'success': False,
                'message': 'Producto no encontrado'
            }, status=status.HTTP_404_NOT_FOUND)
