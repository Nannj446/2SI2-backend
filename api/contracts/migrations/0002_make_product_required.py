# Generated manually

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0001_initial'),
        ('contracts', '0001_initial'),
    ]

    operations = [
        # Primero, asignar un producto por defecto a las plantillas existentes que no tienen uno
        # NOTA: Esta migración asume que existe al menos un producto en la base de datos
        # Si no existe, deberás crear uno antes de ejecutar esta migración
        migrations.RunSQL(
            """
            UPDATE contracts_contracttemplate 
            SET product_id = (SELECT id FROM products_creditproduct LIMIT 1)
            WHERE product_id IS NULL;
            """,
            reverse_sql=migrations.RunSQL.noop,
        ),
        
        # Ahora hacer el campo obligatorio
        migrations.AlterField(
            model_name='contracttemplate',
            name='product',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name='contract_templates',
                to='products.creditproduct',
                verbose_name='Producto Crediticio',
                help_text='Producto crediticio al que pertenece esta plantilla de contrato'
            ),
        ),
    ]
