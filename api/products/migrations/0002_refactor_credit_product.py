"""
Migración para refactorizar CreditProduct según arquitectura documentada.

Esta migración:
1. Crea ProductTypes desde los choices actuales
2. Crea un RuleSet completo con todas las configuraciones necesarias
3. Migra datos de CreditProduct a CreditProductParameter, DocumentRequirement, etc.
4. Simplifica CreditProduct eliminando campos duplicados
"""

from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings
from decimal import Decimal


def create_product_types(apps, schema_editor):
    """Crea ProductTypes desde los choices hardcodeados de CreditProduct."""
    ProductType = apps.get_model('loans', 'ProductType')
    FinancialInstitution = apps.get_model('tenants', 'FinancialInstitution')
    
    # Mapeo de choices actuales a catálogo
    product_type_mapping = {
        'PERSONAL': {
            'code': 'PERSONAL',
            'name': 'Crédito Personal/Consumo',
            'category': 'CONSUMER',
            'icon': 'user',
            'color': 'blue',
        },
        'VEHICULAR': {
            'code': 'VEHICULAR',
            'name': 'Crédito Vehicular',
            'category': 'CONSUMER',
            'icon': 'car',
            'color': 'green',
        },
        'HIPOTECARIO': {
            'code': 'HIPOTECARIO',
            'name': 'Crédito Hipotecario',
            'category': 'MORTGAGE',
            'icon': 'home',
            'color': 'purple',
        },
        'VIVIENDA_SOCIAL': {
            'code': 'VIVIENDA_SOCIAL',
            'name': 'Crédito Vivienda Social',
            'category': 'MORTGAGE',
            'icon': 'building',
            'color': 'orange',
        },
        'PYME': {
            'code': 'PYME',
            'name': 'Crédito PYME',
            'category': 'COMMERCIAL',
            'icon': 'briefcase',
            'color': 'indigo',
        },
        'EMPRESARIAL': {
            'code': 'EMPRESARIAL',
            'name': 'Crédito Empresarial',
            'category': 'COMMERCIAL',
            'icon': 'building-2',
            'color': 'cyan',
        },
        'AGROPECUARIO': {
            'code': 'AGROPECUARIO',
            'name': 'Crédito Agropecuario',
            'category': 'AGRICULTURAL',
            'icon': 'sprout',
            'color': 'green',
        },
        'MICROEMPRESA': {
            'code': 'MICROEMPRESA',
            'name': 'Microcrédito',
            'category': 'COMMERCIAL',
            'icon': 'store',
            'color': 'yellow',
        },
    }
    
    # Crear ProductTypes para cada institución
    for institution in FinancialInstitution.objects.all():
        for code, data in product_type_mapping.items():
            ProductType.objects.get_or_create(
                institution=institution,
                code=code,
                defaults={
                    'name': data['name'],
                    'category': data['category'],
                    'icon': data['icon'],
                    'color': data['color'],
                    'is_active': True,
                    'display_order': 0,
                }
            )


def create_default_catalogs(apps, schema_editor):
    """Crea catálogos por defecto si no existen."""
    FinancialInstitution = apps.get_model('tenants', 'FinancialInstitution')
    Currency = apps.get_model('loans', 'Currency')
    PaymentFrequency = apps.get_model('loans', 'PaymentFrequency')
    AmortizationSystem = apps.get_model('loans', 'AmortizationSystem')
    DocumentType = apps.get_model('loans', 'DocumentType')
    
    for institution in FinancialInstitution.objects.all():
        # Monedas
        Currency.objects.get_or_create(
            institution=institution,
            code='BOB',
            defaults={
                'name': 'Boliviano',
                'symbol': 'Bs',
                'exchange_rate_to_base': Decimal('1.0000'),
                'is_base_currency': True,
                'is_active': True,
            }
        )
        Currency.objects.get_or_create(
            institution=institution,
            code='USD',
            defaults={
                'name': 'Dólar Estadounidense',
                'symbol': '$',
                'exchange_rate_to_base': Decimal('6.9600'),
                'is_base_currency': False,
                'is_active': True,
            }
        )
        
        # Frecuencias de pago
        PaymentFrequency.objects.get_or_create(
            institution=institution,
            code='MONTHLY',
            defaults={
                'name': 'Mensual',
                'days_between_payments': 30,
                'payments_per_year': 12,
                'is_active': True,
            }
        )
        PaymentFrequency.objects.get_or_create(
            institution=institution,
            code='BIWEEKLY',
            defaults={
                'name': 'Quincenal',
                'days_between_payments': 15,
                'payments_per_year': 24,
                'is_active': True,
            }
        )
        PaymentFrequency.objects.get_or_create(
            institution=institution,
            code='WEEKLY',
            defaults={
                'name': 'Semanal',
                'days_between_payments': 7,
                'payments_per_year': 52,
                'is_active': True,
            }
        )
        
        # Sistemas de amortización
        AmortizationSystem.objects.get_or_create(
            institution=institution,
            code='FRENCH',
            defaults={
                'name': 'Sistema Francés (Cuota Fija)',
                'description': 'Cuotas constantes con interés decreciente y capital creciente',
                'formula_type': 'FRENCH',
                'is_active': True,
            }
        )
        AmortizationSystem.objects.get_or_create(
            institution=institution,
            code='GERMAN',
            defaults={
                'name': 'Sistema Alemán (Cuota Decreciente)',
                'description': 'Capital constante con cuotas decrecientes',
                'formula_type': 'GERMAN',
                'is_active': True,
            }
        )
        AmortizationSystem.objects.get_or_create(
            institution=institution,
            code='AMERICAN',
            defaults={
                'name': 'Sistema Americano (Solo Intereses)',
                'description': 'Pago de intereses periódicos y capital al final',
                'formula_type': 'AMERICAN',
                'is_active': True,
            }
        )
        
        # Tipos de documento básicos
        doc_types = [
            {
                'code': 'ID_DOCUMENT',
                'name': 'Documento de Identidad',
                'category': 'IDENTITY',
                'formats': ['PDF', 'JPG', 'PNG'],
                'icon': 'id-card',
            },
            {
                'code': 'INCOME_PROOF',
                'name': 'Comprobante de Ingresos',
                'category': 'FINANCIAL',
                'formats': ['PDF'],
                'icon': 'file-text',
            },
            {
                'code': 'BANK_STATEMENT',
                'name': 'Extracto Bancario',
                'category': 'FINANCIAL',
                'formats': ['PDF'],
                'icon': 'file-spreadsheet',
            },
            {
                'code': 'EMPLOYMENT_LETTER',
                'name': 'Carta de Trabajo',
                'category': 'FINANCIAL',
                'formats': ['PDF'],
                'icon': 'briefcase',
            },
        ]
        
        for doc_data in doc_types:
            DocumentType.objects.get_or_create(
                institution=institution,
                code=doc_data['code'],
                defaults={
                    'name': doc_data['name'],
                    'category': doc_data['category'],
                    'default_formats': doc_data['formats'],
                    'default_max_size_mb': Decimal('5.00'),
                    'default_validity_days': 90,
                    'is_active': True,
                    'icon': doc_data['icon'],
                }
            )


def create_rule_set_from_products(apps, schema_editor):
    """
    Crea un RuleSet completo con todas las configuraciones necesarias
    y migra los datos de CreditProduct.
    """
    FinancialInstitution = apps.get_model('tenants', 'FinancialInstitution')
    TenantRuleSet = apps.get_model('loans', 'TenantRuleSet')
    EligibilityRule = apps.get_model('loans', 'EligibilityRule')
    DecisionThreshold = apps.get_model('loans', 'DecisionThreshold')
    WorkflowStageDefinition = apps.get_model('loans', 'WorkflowStageDefinition')
    CreditProduct = apps.get_model('products', 'CreditProduct')
    CreditProductParameter = apps.get_model('loans', 'CreditProductParameter')
    DocumentRequirement = apps.get_model('loans', 'DocumentRequirement')
    DocumentType = apps.get_model('loans', 'DocumentType')
    Currency = apps.get_model('loans', 'Currency')
    PaymentFrequency = apps.get_model('loans', 'PaymentFrequency')
    AmortizationSystem = apps.get_model('loans', 'AmortizationSystem')
    
    for institution in FinancialInstitution.objects.all():
        # Verificar si ya existe un RuleSet activo
        active_rule_set = TenantRuleSet.objects.filter(
            institution=institution,
            status='ACTIVE'
        ).first()
        
        if not active_rule_set:
            # Crear RuleSet inicial
            rule_set = TenantRuleSet.objects.create(
                institution=institution,
                version='1.0.0',
                status='ACTIVE',
                name='Configuración Inicial (Migración)',
                description='RuleSet creado automáticamente durante la migración de datos',
            )
            
            # Crear EligibilityRule con valores por defecto
            EligibilityRule.objects.create(
                institution=institution,
                rule_set=rule_set,
                max_debt_to_income_ratio=Decimal('40.00'),
                min_income_required=Decimal('2000.00'),
                min_employment_months=6,
                max_arrears_allowed=Decimal('0.00'),
                allowed_cic_categories=['A', 'B', 'C'],
                min_collateral_coverage=Decimal('125.00'),
                min_age=18,
                max_age=70,
            )
            
            # Crear DecisionThreshold
            DecisionThreshold.objects.create(
                institution=institution,
                rule_set=rule_set,
                min_score_auto_approval=70,
                min_score_manual_review=50,
                max_score_auto_rejection=49,
                max_amount_auto_approval=Decimal('50000.00'),
                requires_manager_approval_amount=Decimal('200000.00'),
            )
            
            # Crear WorkflowStageDefinitions básicas
            # ORDEN CORRECTO: KYC primero, luego documentos
            workflow_stages = [
                {
                    'stage_code': 'DRAFT',
                    'stage_name': 'Borrador',
                    'stage_order': 1,
                    'is_automated': False,
                    'requires_manual_approval': False,
                    'next_stage_on_success': 'SUBMITTED',
                },
                {
                    'stage_code': 'SUBMITTED',
                    'stage_name': 'Enviada',
                    'stage_order': 2,
                    'is_automated': True,
                    'auto_advance_enabled': True,
                    'next_stage_on_success': 'KYC',
                },
                {
                    'stage_code': 'KYC',
                    'stage_name': 'Verificación de Identidad (KYC)',
                    'stage_order': 3,
                    'is_automated': True,
                    'auto_advance_enabled': True,
                    'time_limit_hours': 24,
                    'next_stage_on_success': 'DOCUMENTS',
                    'next_stage_on_failure': 'REJECTED',
                    'client_message_template': 'Por favor, complete la verificación de identidad mediante reconocimiento facial.',
                    'requires_client_action': True,
                    'client_action_description': 'Tomar selfie y fotografiar su documento de identidad',
                },
                {
                    'stage_code': 'DOCUMENTS',
                    'stage_name': 'Carga y Validación de Documentos',
                    'stage_order': 4,
                    'is_automated': False,
                    'requires_manual_approval': False,
                    'time_limit_hours': 48,
                    'next_stage_on_success': 'SCORING',
                    'next_stage_on_failure': 'REJECTED',
                    'client_message_template': 'Por favor, cargue los documentos requeridos para su solicitud.',
                    'requires_client_action': True,
                    'client_action_description': 'Cargar documentos de solvencia económica',
                },
                {
                    'stage_code': 'SCORING',
                    'stage_name': 'Evaluación Crediticia',
                    'stage_order': 5,
                    'is_automated': True,
                    'auto_advance_enabled': True,
                    'next_stage_on_success': 'REVIEW',
                    'next_stage_on_failure': 'REJECTED',
                },
                {
                    'stage_code': 'REVIEW',
                    'stage_name': 'Revisión Final',
                    'stage_order': 6,
                    'is_automated': False,
                    'requires_manual_approval': True,
                    'time_limit_hours': 72,
                    'next_stage_on_success': 'APPROVED',
                    'next_stage_on_failure': 'REJECTED',
                },
                {
                    'stage_code': 'APPROVED',
                    'stage_name': 'Aprobada',
                    'stage_order': 7,
                    'is_automated': False,
                    'is_final_stage': True,
                    'next_stage_on_success': 'DISBURSED',
                },
                {
                    'stage_code': 'REJECTED',
                    'stage_name': 'Rechazada',
                    'stage_order': 8,
                    'is_automated': False,
                    'is_final_stage': True,
                },
                {
                    'stage_code': 'DISBURSED',
                    'stage_name': 'Desembolsada',
                    'stage_order': 9,
                    'is_automated': False,
                    'is_final_stage': True,
                },
            ]
            
            for stage_data in workflow_stages:
                WorkflowStageDefinition.objects.create(
                    institution=institution,
                    rule_set=rule_set,
                    **stage_data
                )
        else:
            rule_set = active_rule_set
        
        # Migrar datos de cada CreditProduct
        products = CreditProduct.objects.filter(institution=institution)
        
        for product in products:
            # Crear CreditProductParameter con datos del producto
            param, created = CreditProductParameter.objects.get_or_create(
                institution=institution,
                rule_set=rule_set,
                product=product,
                defaults={
                    'min_amount': product.min_amount,
                    'max_amount': product.max_amount,
                    'min_term_months': product.min_term_months,
                    'max_term_months': product.max_term_months,
                    'min_interest_rate': product.interest_rate,
                    'max_interest_rate': product.interest_rate,
                    'interest_type': product.interest_type,
                    'commission_rate_min': product.commission_rate,
                    'commission_rate_max': product.commission_rate,
                    'insurance_rate_min': product.insurance_rate,
                    'insurance_rate_max': product.insurance_rate,
                    'additional_insurance_rate': product.additional_insurance_rate,
                    'grace_period_months_min': 0,
                    'grace_period_months_max': product.grace_period_months,
                    'allows_early_payment': product.allows_early_payment,
                    'early_payment_penalty_min': product.early_payment_penalty,
                    'early_payment_penalty_max': product.early_payment_penalty,
                    'max_financing_percentage': Decimal('100.00'),
                    'min_income_required': product.min_income_required,
                    'max_debt_to_income_ratio': product.max_debt_to_income_ratio,
                    'min_employment_months': product.min_employment_months,
                    'min_collateral_coverage': product.min_collateral_coverage,
                    'requires_guarantor': product.requires_guarantor,
                    'requires_collateral': product.requires_collateral,
                    'min_credit_score_required': product.min_credit_score,
                    'auto_approval_enabled': product.auto_approval_enabled,
                    'max_auto_approval_amount': product.max_auto_approval_amount,
                }
            )
            
            # Note: M2M relationships (allowed_currencies, allowed_payment_frequencies, allowed_amortization_systems)
            # will be empty after migration. They should be configured through the admin interface or
            # a separate data migration after the schema is fully migrated.
            
            # Migrar required_documents a DocumentRequirement
            if product.required_documents:
                for idx, doc_code in enumerate(product.required_documents):
                    # Intentar encontrar el DocumentType correspondiente
                    doc_type = DocumentType.objects.filter(
                        institution=institution,
                        code=doc_code
                    ).first()
                    
                    if not doc_type:
                        # Si no existe, crear uno genérico
                        doc_type = DocumentType.objects.create(
                            institution=institution,
                            code=doc_code,
                            name=doc_code.replace('_', ' ').title(),
                            category='OTHER',
                            default_formats=['PDF', 'JPG', 'PNG'],
                            default_max_size_mb=Decimal('5.00'),
                            is_active=True,
                        )
                    
                    DocumentRequirement.objects.get_or_create(
                        institution=institution,
                        rule_set=rule_set,
                        product=product,
                        document_type=doc_type,
                        defaults={
                            'is_mandatory': True,
                            'requires_manual_review': True,
                            'display_order': idx,
                        }
                    )


def link_products_to_product_types(apps, schema_editor):
    """Vincula productos existentes con ProductTypes del catálogo."""
    CreditProduct = apps.get_model('products', 'CreditProduct')
    ProductType = apps.get_model('loans', 'ProductType')
    
    for product in CreditProduct.objects.all():
        # Buscar el ProductType correspondiente
        product_type = ProductType.objects.filter(
            institution=product.institution,
            code=product.product_type  # product_type es CharField actualmente
        ).first()
        
        if product_type:
            # Guardar el ID del ProductType en un campo temporal
            # (se usará después de cambiar el campo a FK)
            product.product_type_temp_id = product_type.id
            product.save(update_fields=['product_type_temp_id'])


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0001_initial'),
        ('loans', '0009_finalize_catalog_migration'),
        ('tenants', '0001_initial'),
    ]

    operations = [
        # Paso 1: Crear ProductTypes desde choices
        migrations.RunPython(
            create_product_types,
            reverse_code=migrations.RunPython.noop,
        ),
        
        # Paso 2: Crear catálogos por defecto
        migrations.RunPython(
            create_default_catalogs,
            reverse_code=migrations.RunPython.noop,
        ),
        
        # Paso 3: Agregar campo temporal para guardar el ID del ProductType
        migrations.AddField(
            model_name='creditproduct',
            name='product_type_temp_id',
            field=models.IntegerField(null=True, blank=True),
        ),
        
        # Paso 4: Crear RuleSets y migrar datos
        migrations.RunPython(
            create_rule_set_from_products,
            reverse_code=migrations.RunPython.noop,
        ),
        
        # Paso 5: Vincular productos con ProductTypes
        migrations.RunPython(
            link_products_to_product_types,
            reverse_code=migrations.RunPython.noop,
        ),
        
        # Eliminar primero el índice antes de remover el campo (requerido para compatibilidad con SQLite)
        migrations.RemoveIndex(
            model_name='creditproduct',
            name='products_cr_product_5aa762_idx',
        ),
        # Paso 6: Eliminar el campo product_type viejo (CharField)
        migrations.RemoveField(
            model_name='creditproduct',
            name='product_type',
        ),
        
        # Paso 7: Crear nuevo campo product_type como FK usando el ID temporal
        migrations.AddField(
            model_name='creditproduct',
            name='product_type',
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='products',
                to='loans.producttype',
                verbose_name='Tipo de Producto'
            ),
        ),
        
        # Paso 8: Copiar IDs del campo temporal al nuevo FK
        migrations.RunSQL(
            sql="""
                UPDATE products_creditproduct 
                SET product_type_id = product_type_temp_id 
                WHERE product_type_temp_id IS NOT NULL;
            """,
            reverse_sql=migrations.RunSQL.noop,
        ),
        
        # Paso 9: Hacer el FK no nullable
        migrations.AlterField(
            model_name='creditproduct',
            name='product_type',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name='products',
                to='loans.producttype',
                verbose_name='Tipo de Producto'
            ),
        ),
        
        # Paso 10: Eliminar campo temporal
        migrations.RemoveField(
            model_name='creditproduct',
            name='product_type_temp_id',
        ),
        
        # Paso 11: Eliminar campos duplicados que ahora están en CreditProductParameter
        migrations.RemoveField(model_name='creditproduct', name='min_amount'),
        migrations.RemoveField(model_name='creditproduct', name='max_amount'),
        migrations.RemoveField(model_name='creditproduct', name='min_term_months'),
        migrations.RemoveField(model_name='creditproduct', name='max_term_months'),
        migrations.RemoveField(model_name='creditproduct', name='interest_rate'),
        migrations.RemoveField(model_name='creditproduct', name='interest_type'),
        migrations.RemoveField(model_name='creditproduct', name='effective_annual_rate'),
        migrations.RemoveField(model_name='creditproduct', name='commission_rate'),
        migrations.RemoveField(model_name='creditproduct', name='insurance_rate'),
        migrations.RemoveField(model_name='creditproduct', name='additional_insurance_rate'),
        migrations.RemoveField(model_name='creditproduct', name='payment_frequency'),
        migrations.RemoveField(model_name='creditproduct', name='amortization_system'),
        migrations.RemoveField(model_name='creditproduct', name='grace_period_months'),
        migrations.RemoveField(model_name='creditproduct', name='allows_early_payment'),
        migrations.RemoveField(model_name='creditproduct', name='early_payment_penalty'),
        migrations.RemoveField(model_name='creditproduct', name='min_income_required'),
        migrations.RemoveField(model_name='creditproduct', name='max_debt_to_income_ratio'),
        migrations.RemoveField(model_name='creditproduct', name='min_employment_months'),
        migrations.RemoveField(model_name='creditproduct', name='requires_guarantor'),
        migrations.RemoveField(model_name='creditproduct', name='requires_collateral'),
        migrations.RemoveField(model_name='creditproduct', name='min_collateral_coverage'),
        migrations.RemoveField(model_name='creditproduct', name='required_documents'),
        migrations.RemoveField(model_name='creditproduct', name='min_credit_score'),
        migrations.RemoveField(model_name='creditproduct', name='auto_approval_enabled'),
        migrations.RemoveField(model_name='creditproduct', name='max_auto_approval_amount'),
        
        # Paso 12: Agregar índice para el nuevo FK
        migrations.AddIndex(
            model_name='creditproduct',
            index=models.Index(fields=['product_type'], name='products_cr_product_idx'),
        ),
    ]
