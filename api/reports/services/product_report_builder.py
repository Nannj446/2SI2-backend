"""
Constructor de reportes de productos crediticios.

Este servicio construye QuerySets especializados para reportes de productos
crediticios, incluyendo sus parámetros desde CreditProductParameter.
"""
import logging
from typing import Dict, List, Any
from django.db.models import F, Q, Value, CharField, DecimalField, IntegerField, BooleanField
from django.db.models.functions import Coalesce

logger = logging.getLogger(__name__)


class ProductReportBuilder:
    """
    Constructor especializado para reportes de productos crediticios.
    
    Maneja la complejidad de obtener parámetros desde CreditProductParameter
    a través de la relación con TenantRuleSet.
    """
    
    @staticmethod
    def annotate_product_parameters(queryset):
        """
        Anota el queryset de productos con sus parámetros desde CreditProductParameter.
        
        Los parámetros están en CreditProductParameter vinculados al rule_set del producto.
        
        Args:
            queryset: QuerySet de CreditProduct
        
        Returns:
            QuerySet anotado con campos de parámetros
        """
        # Obtener parámetros desde rule_set__product_parameters
        # Nota: CreditProductParameter tiene una relación ForeignKey con TenantRuleSet
        # usando related_name='product_parameters'
        
        queryset = queryset.annotate(
            # Parámetros de montos (DecimalField)
            min_amount=Coalesce(
                F('rule_set__product_parameters__min_amount'),
                Value(0),
                output_field=DecimalField()
            ),
            max_amount=Coalesce(
                F('rule_set__product_parameters__max_amount'),
                Value(0),
                output_field=DecimalField()
            ),
            
            # Parámetros de plazos (IntegerField)
            min_term_months=Coalesce(
                F('rule_set__product_parameters__min_term_months'),
                Value(0),
                output_field=IntegerField()
            ),
            max_term_months=Coalesce(
                F('rule_set__product_parameters__max_term_months'),
                Value(0),
                output_field=IntegerField()
            ),
            
            # Tasas de interés (DecimalField)
            min_interest_rate=Coalesce(
                F('rule_set__product_parameters__min_interest_rate'),
                Value(0.0),
                output_field=DecimalField()
            ),
            max_interest_rate=Coalesce(
                F('rule_set__product_parameters__max_interest_rate'),
                Value(0.0),
                output_field=DecimalField()
            ),
            interest_rate_type_value=Coalesce(
                F('rule_set__product_parameters__interest_type'),
                Value('FIXED'),
                output_field=CharField()
            ),
            
            # Comisiones (DecimalField)
            commission_rate_min=Coalesce(
                F('rule_set__product_parameters__commission_rate_min'),
                Value(0.0),
                output_field=DecimalField()
            ),
            commission_rate_max=Coalesce(
                F('rule_set__product_parameters__commission_rate_max'),
                Value(0.0),
                output_field=DecimalField()
            ),
            
            # Seguros (DecimalField)
            insurance_rate_min=Coalesce(
                F('rule_set__product_parameters__insurance_rate_min'),
                Value(0.0),
                output_field=DecimalField()
            ),
            insurance_rate_max=Coalesce(
                F('rule_set__product_parameters__insurance_rate_max'),
                Value(0.0),
                output_field=DecimalField()
            ),
            
            # Penalidad por pago anticipado (DecimalField)
            early_payment_penalty_min=Coalesce(
                F('rule_set__product_parameters__early_payment_penalty_min'),
                Value(0.0),
                output_field=DecimalField()
            ),
            early_payment_penalty_max=Coalesce(
                F('rule_set__product_parameters__early_payment_penalty_max'),
                Value(0.0),
                output_field=DecimalField()
            ),
            
            # Período de gracia (IntegerField)
            grace_period_months_min=Coalesce(
                F('rule_set__product_parameters__grace_period_months_min'),
                Value(0),
                output_field=IntegerField()
            ),
            grace_period_months_max=Coalesce(
                F('rule_set__product_parameters__grace_period_months_max'),
                Value(0),
                output_field=IntegerField()
            ),
            
            # Financiamiento (DecimalField)
            max_financing_percentage=Coalesce(
                F('rule_set__product_parameters__max_financing_percentage'),
                Value(100.0),
                output_field=DecimalField()
            ),
            
            # Garantías (BooleanField)
            requires_guarantor=Coalesce(
                F('rule_set__product_parameters__requires_guarantor'),
                Value(False),
                output_field=BooleanField()
            ),
            requires_collateral=Coalesce(
                F('rule_set__product_parameters__requires_collateral'),
                Value(False),
                output_field=BooleanField()
            ),
            
            # Información del conjunto de reglas (CharField)
            rule_set_name_value=Coalesce(
                F('rule_set__name'),
                Value('Sin conjunto de reglas'),
                output_field=CharField()
            ),
            rule_set_code_value=Coalesce(
                F('rule_set__version'),
                Value('N/A'),
                output_field=CharField()
            ),
        )
        
        return queryset
    
    @staticmethod
    def build_product_catalog_query(queryset, columns: List[str]):
        """
        Construye query específico para el reporte de catálogo de productos.
        
        Args:
            queryset: QuerySet base de CreditProduct
            columns: Columnas solicitadas
        
        Returns:
            QuerySet configurado con anotaciones necesarias
        """
        # Anotar con parámetros
        queryset = ProductReportBuilder.annotate_product_parameters(queryset)
        
        # Optimizar con select_related y prefetch_related
        queryset = queryset.select_related(
            'product_type',
            'rule_set'
        ).prefetch_related(
            'rule_set__product_parameters'
        )
        
        return queryset
    
    @staticmethod
    def map_column_to_field(column: str) -> str:
        """
        Mapea nombres de columnas del catálogo a campos anotados o reales.
        
        Args:
            column: Nombre de columna del catálogo
        
        Returns:
            Nombre del campo en el queryset
        """
        # Mapeo de columnas virtuales a campos reales o anotados
        column_mapping = {
            # Información básica (campos directos del modelo)
            'product_name': 'name',
            'product_code': 'code',
            'product_type': 'product_type__name',
            'description': 'description',
            'is_active': 'is_active',
            'display_order': 'display_order',
            
            # Parámetros de montos (campos anotados)
            'min_amount': 'min_amount',
            'max_amount': 'max_amount',
            
            # Parámetros de plazos (campos anotados)
            'min_term_months': 'min_term_months',
            'max_term_months': 'max_term_months',
            
            # Tasas de interés (campos anotados)
            'min_interest_rate': 'min_interest_rate',
            'max_interest_rate': 'max_interest_rate',
            'interest_rate_type': 'interest_rate_type_value',
            
            # Comisiones (campos anotados)
            'commission_rate_min': 'commission_rate_min',
            'commission_rate_max': 'commission_rate_max',
            
            # Seguros (campos anotados)
            'insurance_rate_min': 'insurance_rate_min',
            'insurance_rate_max': 'insurance_rate_max',
            
            # Penalidad por pago anticipado (campos anotados)
            'early_payment_penalty_min': 'early_payment_penalty_min',
            'early_payment_penalty_max': 'early_payment_penalty_max',
            
            # Período de gracia (campos anotados)
            'grace_period_months_min': 'grace_period_months_min',
            'grace_period_months_max': 'grace_period_months_max',
            
            # Financiamiento (campos anotados)
            'max_financing_percentage': 'max_financing_percentage',
            
            # Garantías (campos anotados)
            'requires_guarantor': 'requires_guarantor',
            'requires_collateral': 'requires_collateral',
            
            # Información de marketing (campos directos)
            'target_audience': 'target_audience',
            'benefits': 'benefits',
            
            # Conjunto de reglas (campos anotados)
            'rule_set_name': 'rule_set_name_value',
            'rule_set_code': 'rule_set_code_value',
            
            # Fechas (campos directos)
            'created_at': 'created_at',
            'updated_at': 'updated_at',
        }
        
        return column_mapping.get(column, column)
    
    @staticmethod
    def get_values_fields(columns: List[str]) -> List[str]:
        """
        Obtiene la lista de campos para values() basándose en las columnas solicitadas.
        
        Args:
            columns: Columnas solicitadas del catálogo
        
        Returns:
            Lista de campos para values()
        """
        fields = []
        for column in columns:
            field = ProductReportBuilder.map_column_to_field(column)
            fields.append(field)
        
        return fields
