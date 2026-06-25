# Generated migration for adding rule_set and document relationships

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0002_refactor_credit_product'),
        ('loans', '0009_finalize_catalog_migration'),
        ('tenants', '__latest__'),
    ]

    operations = [
        # Agregar campo rule_set a CreditProduct
        migrations.AddField(
            model_name='creditproduct',
            name='rule_set',
            field=models.ForeignKey(
                blank=True,
                help_text='Conjunto de reglas asociado a este producto',
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='credit_products',
                to='loans.tenantruleset',
                verbose_name='Conjunto de Reglas'
            ),
        ),
        
        # Crear modelo ProductDocumentRequirement
        migrations.CreateModel(
            name='ProductDocumentRequirement',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Fecha de Creación')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Fecha de Actualización')),
                ('is_mandatory', models.BooleanField(default=True, help_text='Si el documento es obligatorio para este producto', verbose_name='Obligatorio')),
                ('display_order', models.IntegerField(default=0, verbose_name='Orden de Visualización')),
                ('max_validity_days', models.IntegerField(blank=True, help_text='Sobrescribe el valor por defecto del DocumentType', null=True, verbose_name='Vigencia Máxima (días)')),
                ('allowed_formats', models.JSONField(blank=True, default=list, help_text='Sobrescribe el valor por defecto del DocumentType', verbose_name='Formatos Permitidos')),
                ('max_file_size_mb', models.DecimalField(blank=True, decimal_places=2, help_text='Sobrescribe el valor por defecto del DocumentType', max_digits=5, null=True, verbose_name='Tamaño Máximo (MB)')),
                ('document_type', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='product_requirements_config', to='loans.documenttype', verbose_name='Tipo de Documento')),
                ('institution', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='%(class)s_set', to='tenants.financialinstitution', verbose_name='Institución')),
                ('product', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='document_requirements_config', to='products.creditproduct', verbose_name='Producto')),
            ],
            options={
                'verbose_name': 'Documento Requerido del Producto',
                'verbose_name_plural': 'Documentos Requeridos del Producto',
                'ordering': ['display_order', 'document_type__name'],
            },
        ),
        
        # Agregar relación M2M a CreditProduct
        migrations.AddField(
            model_name='creditproduct',
            name='required_documents',
            field=models.ManyToManyField(
                help_text='Documentos que serán requeridos para este producto',
                related_name='products_requiring',
                through='products.ProductDocumentRequirement',
                to='loans.documenttype',
                verbose_name='Documentos Requeridos'
            ),
        ),
        
        # Agregar constraint de unicidad
        migrations.AddConstraint(
            model_name='productdocumentrequirement',
            constraint=models.UniqueConstraint(
                fields=('product', 'document_type'),
                name='unique_document_per_product'
            ),
        ),
        
        # Agregar índice para rule_set
        migrations.AddIndex(
            model_name='creditproduct',
            index=models.Index(fields=['rule_set'], name='products_cr_rule_se_idx'),
        ),
    ]
