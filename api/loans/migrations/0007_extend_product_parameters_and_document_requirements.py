# Generated manually for Fase 2: Extender Modelos Existentes

from django.db import migrations, models
import django.core.validators
from decimal import Decimal


class Migration(migrations.Migration):

    dependencies = [
        ('loans', '0006_create_catalog_models'),
    ]

    operations = [
        # ============================================================
        # PASO 1: Agregar nuevos campos a CreditProductParameter
        # ============================================================
        
        # Tipo de tasa
        migrations.AddField(
            model_name='creditproductparameter',
            name='interest_type',
            field=models.CharField(
                choices=[
                    ('FIXED', 'Tasa Fija'),
                    ('VARIABLE', 'Tasa Variable'),
                    ('MIXED', 'Tasa Mixta')
                ],
                default='FIXED',
                max_length=20,
                verbose_name='Tipo de Tasa'
            ),
        ),
        
        # Comisiones
        migrations.AddField(
            model_name='creditproductparameter',
            name='commission_rate_min',
            field=models.DecimalField(
                decimal_places=2,
                default=Decimal('0.00'),
                max_digits=5,
                validators=[django.core.validators.MinValueValidator(0)],
                verbose_name='Comisión Mínima (%)'
            ),
        ),
        migrations.AddField(
            model_name='creditproductparameter',
            name='commission_rate_max',
            field=models.DecimalField(
                decimal_places=2,
                default=Decimal('0.00'),
                max_digits=5,
                validators=[django.core.validators.MinValueValidator(0)],
                verbose_name='Comisión Máxima (%)'
            ),
        ),
        
        # Seguros
        migrations.AddField(
            model_name='creditproductparameter',
            name='insurance_rate_min',
            field=models.DecimalField(
                decimal_places=2,
                default=Decimal('0.00'),
                max_digits=5,
                validators=[django.core.validators.MinValueValidator(0)],
                verbose_name='Seguro Mínimo (%)'
            ),
        ),
        migrations.AddField(
            model_name='creditproductparameter',
            name='insurance_rate_max',
            field=models.DecimalField(
                decimal_places=2,
                default=Decimal('0.00'),
                max_digits=5,
                validators=[django.core.validators.MinValueValidator(0)],
                verbose_name='Seguro Máximo (%)'
            ),
        ),
        migrations.AddField(
            model_name='creditproductparameter',
            name='additional_insurance_rate',
            field=models.DecimalField(
                decimal_places=2,
                default=Decimal('0.00'),
                max_digits=5,
                validators=[django.core.validators.MinValueValidator(0)],
                verbose_name='Seguro Adicional (%)'
            ),
        ),
        
        # Sistema de Pago
        migrations.AddField(
            model_name='creditproductparameter',
            name='grace_period_months_min',
            field=models.IntegerField(
                default=0,
                validators=[django.core.validators.MinValueValidator(0)],
                verbose_name='Período de Gracia Mínimo (meses)'
            ),
        ),
        migrations.AddField(
            model_name='creditproductparameter',
            name='grace_period_months_max',
            field=models.IntegerField(
                default=6,
                validators=[django.core.validators.MinValueValidator(0)],
                verbose_name='Período de Gracia Máximo (meses)'
            ),
        ),
        migrations.AddField(
            model_name='creditproductparameter',
            name='allows_early_payment',
            field=models.BooleanField(
                default=True,
                verbose_name='Permite Pago Anticipado'
            ),
        ),
        migrations.AddField(
            model_name='creditproductparameter',
            name='early_payment_penalty_min',
            field=models.DecimalField(
                decimal_places=2,
                default=Decimal('0.00'),
                max_digits=5,
                validators=[django.core.validators.MinValueValidator(0)],
                verbose_name='Penalidad Pago Anticipado Mínima (%)'
            ),
        ),
        migrations.AddField(
            model_name='creditproductparameter',
            name='early_payment_penalty_max',
            field=models.DecimalField(
                decimal_places=2,
                default=Decimal('5.00'),
                max_digits=5,
                validators=[django.core.validators.MinValueValidator(0)],
                verbose_name='Penalidad Pago Anticipado Máxima (%)'
            ),
        ),
        
        # Elegibilidad
        migrations.AddField(
            model_name='creditproductparameter',
            name='min_income_required',
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                help_text='Si es NULL, usa el valor de EligibilityRule',
                max_digits=12,
                null=True,
                validators=[django.core.validators.MinValueValidator(0)],
                verbose_name='Ingreso Mínimo Requerido (Bs)'
            ),
        ),
        migrations.AddField(
            model_name='creditproductparameter',
            name='max_debt_to_income_ratio',
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                help_text='Si es NULL, usa el valor de EligibilityRule',
                max_digits=5,
                null=True,
                validators=[django.core.validators.MinValueValidator(0)],
                verbose_name='RCI Máximo (%)'
            ),
        ),
        migrations.AddField(
            model_name='creditproductparameter',
            name='min_employment_months',
            field=models.IntegerField(
                blank=True,
                help_text='Si es NULL, usa el valor de EligibilityRule',
                null=True,
                validators=[django.core.validators.MinValueValidator(0)],
                verbose_name='Antigüedad Laboral Mínima (meses)'
            ),
        ),
        migrations.AddField(
            model_name='creditproductparameter',
            name='min_collateral_coverage',
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                help_text='Si es NULL, usa el valor de EligibilityRule',
                max_digits=5,
                null=True,
                validators=[django.core.validators.MinValueValidator(0)],
                verbose_name='Cobertura Mínima de Garantía (%)'
            ),
        ),
        
        # Scoring
        migrations.AddField(
            model_name='creditproductparameter',
            name='min_credit_score_required',
            field=models.IntegerField(
                blank=True,
                help_text='Si es NULL, usa el valor de DecisionThreshold',
                null=True,
                validators=[django.core.validators.MinValueValidator(0)],
                verbose_name='Score Mínimo Requerido'
            ),
        ),
        migrations.AddField(
            model_name='creditproductparameter',
            name='auto_approval_enabled',
            field=models.BooleanField(
                default=False,
                verbose_name='Aprobación Automática Habilitada'
            ),
        ),
        migrations.AddField(
            model_name='creditproductparameter',
            name='max_auto_approval_amount',
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                help_text='Si es NULL, usa el valor de DecisionThreshold',
                max_digits=12,
                null=True,
                validators=[django.core.validators.MinValueValidator(0)],
                verbose_name='Monto Máximo para Aprobación Automática (Bs)'
            ),
        ),
        
        # ============================================================
        # PASO 2: Crear tablas M2M para catálogos
        # ============================================================
        
        migrations.CreateModel(
            name='CreditProductParameter_allowed_currencies',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('creditproductparameter', models.ForeignKey(on_delete=models.CASCADE, to='loans.creditproductparameter')),
                ('currency', models.ForeignKey(on_delete=models.CASCADE, to='loans.currency')),
            ],
            options={
                'db_table': 'credit_product_parameters_allowed_currencies',
                'unique_together': {('creditproductparameter', 'currency')},
            },
        ),
        
        migrations.CreateModel(
            name='CreditProductParameter_allowed_payment_frequencies',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('creditproductparameter', models.ForeignKey(on_delete=models.CASCADE, to='loans.creditproductparameter')),
                ('paymentfrequency', models.ForeignKey(on_delete=models.CASCADE, to='loans.paymentfrequency')),
            ],
            options={
                'db_table': 'credit_product_parameters_allowed_payment_frequencies',
                'unique_together': {('creditproductparameter', 'paymentfrequency')},
            },
        ),
        
        migrations.CreateModel(
            name='CreditProductParameter_allowed_amortization_systems',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('creditproductparameter', models.ForeignKey(on_delete=models.CASCADE, to='loans.creditproductparameter')),
                ('amortizationsystem', models.ForeignKey(on_delete=models.CASCADE, to='loans.amortizationsystem')),
            ],
            options={
                'db_table': 'credit_product_parameters_allowed_amortization_systems',
                'unique_together': {('creditproductparameter', 'amortizationsystem')},
            },
        ),
        
        # ============================================================
        # PASO 3: Modificar DocumentRequirement
        # ============================================================
        
        # Agregar nuevo campo FK a DocumentType (nullable temporalmente)
        migrations.AddField(
            model_name='documentrequirement',
            name='document_type_fk',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=models.PROTECT,
                related_name='requirements',
                to='loans.documenttype',
                verbose_name='Tipo de Documento'
            ),
        ),
        
        # Agregar campo auto_validation_rules
        migrations.AddField(
            model_name='documentrequirement',
            name='auto_validation_rules',
            field=models.JSONField(
                blank=True,
                default=dict,
                verbose_name='Reglas de Validación Automática'
            ),
        ),
        
        # Modificar campos existentes para permitir NULL/blank
        migrations.AlterField(
            model_name='documentrequirement',
            name='max_file_size_mb',
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                help_text='Sobrescribe el valor por defecto del DocumentType. NULL = usar valor del catálogo',
                max_digits=5,
                null=True,
                validators=[django.core.validators.MinValueValidator(0.01)],
                verbose_name='Tamaño Máximo (MB)'
            ),
        ),
        migrations.AlterField(
            model_name='documentrequirement',
            name='allowed_formats',
            field=models.JSONField(
                blank=True,
                default=list,
                help_text='Sobrescribe el valor por defecto del DocumentType. [] = usar valor del catálogo',
                verbose_name='Formatos Permitidos'
            ),
        ),
        migrations.AlterField(
            model_name='documentrequirement',
            name='max_validity_days',
            field=models.IntegerField(
                blank=True,
                help_text='Sobrescribe el valor por defecto del DocumentType. NULL = usar valor del catálogo',
                null=True,
                validators=[django.core.validators.MinValueValidator(1)],
                verbose_name='Vigencia Máxima (días)'
            ),
        ),
        
        # ============================================================
        # PASO 4: Actualizar Meta de CreditProductParameter
        # ============================================================
        
        migrations.AlterModelOptions(
            name='creditproductparameter',
            options={
                'ordering': ['product__name'],
                'verbose_name': 'Parámetro de Producto',
                'verbose_name_plural': 'Parámetros de Productos'
            },
        ),
        
        migrations.AddIndex(
            model_name='creditproductparameter',
            index=models.Index(fields=['rule_set', 'product'], name='credit_prod_rule_se_idx'),
        ),
        
        # ============================================================
        # PASO 5: Actualizar Meta de DocumentRequirement
        # ============================================================
        
        migrations.AlterModelOptions(
            name='documentrequirement',
            options={
                'ordering': ['display_order', 'document_type__name'],
                'verbose_name': 'Requisito Documental',
                'verbose_name_plural': 'Requisitos Documentales'
            },
        ),
        
        # Agregar constraint único para document_type_fk
        migrations.AddConstraint(
            model_name='documentrequirement',
            constraint=models.UniqueConstraint(
                fields=['rule_set', 'product', 'document_type_fk'],
                name='unique_document_per_product_rule_set'
            ),
        ),
    ]
