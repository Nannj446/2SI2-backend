# Generated migration to remove product field from CreditProductParameter and DocumentRequirement

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('loans', '0010_cleanup_document_requirement_fields'),
    ]

    operations = [
        # ============================================================
        # CREDIT PRODUCT PARAMETER
        # ============================================================
        
        # Eliminar la constraint única que incluye product
        migrations.RemoveConstraint(
            model_name='creditproductparameter',
            name='unique_product_per_rule_set',
        ),
        
        # Eliminar el índice que incluye product (si existe)
        migrations.RunSQL(
            sql="DROP INDEX IF EXISTS credit_product_parameters_rule_set_id_product_id_idx;",
            reverse_sql="",
        ),
        
        # Eliminar el campo product
        migrations.RemoveField(
            model_name='creditproductparameter',
            name='product',
        ),
        
        # Agregar nueva constraint única solo con rule_set
        migrations.AddConstraint(
            model_name='creditproductparameter',
            constraint=models.UniqueConstraint(
                fields=['rule_set'],
                name='unique_rule_set_parameter'
            ),
        ),
        
        # Agregar nuevo índice solo con rule_set
        migrations.AddIndex(
            model_name='creditproductparameter',
            index=models.Index(fields=['rule_set'], name='credit_product_parameters_rule_set_idx'),
        ),
        
        # ============================================================
        # DOCUMENT REQUIREMENT
        # ============================================================
        
        # Eliminar la constraint única que incluye product
        migrations.RemoveConstraint(
            model_name='documentrequirement',
            name='unique_document_per_product_rule_set',
        ),
        
        # Eliminar el índice que incluye product (si existe)
        migrations.RunSQL(
            sql="DROP INDEX IF EXISTS document_requirements_rule_set_id_product_id_idx;",
            reverse_sql="",
        ),
        
        # Eliminar el campo product
        migrations.RemoveField(
            model_name='documentrequirement',
            name='product',
        ),
        
        # Agregar nueva constraint única sin product
        migrations.AddConstraint(
            model_name='documentrequirement',
            constraint=models.UniqueConstraint(
                fields=['rule_set', 'document_type'],
                name='unique_document_per_rule_set'
            ),
        ),
        
        # Agregar nuevo índice sin product
        migrations.AddIndex(
            model_name='documentrequirement',
            index=models.Index(fields=['rule_set'], name='document_requirements_rule_set_idx'),
        ),
    ]
