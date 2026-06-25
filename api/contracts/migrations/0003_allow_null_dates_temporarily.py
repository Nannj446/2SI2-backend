# Generated manually to fix null date issue

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('contracts', '0002_make_product_required'),
    ]

    operations = [
        migrations.AlterField(
            model_name='contract',
            name='contract_date',
            field=models.DateField(
                blank=True,
                null=True,
                help_text='Fecha de generación del contrato',
                verbose_name='Fecha del Contrato'
            ),
        ),
        migrations.AlterField(
            model_name='contract',
            name='start_date',
            field=models.DateField(
                blank=True,
                null=True,
                help_text='Fecha de inicio del crédito',
                verbose_name='Fecha de Inicio'
            ),
        ),
        migrations.AlterField(
            model_name='contract',
            name='end_date',
            field=models.DateField(
                blank=True,
                null=True,
                help_text='Fecha estimada de finalización del crédito',
                verbose_name='Fecha de Finalización'
            ),
        ),
        migrations.AlterField(
            model_name='contract',
            name='first_payment_date',
            field=models.DateField(
                blank=True,
                null=True,
                help_text='Fecha de vencimiento del primer pago',
                verbose_name='Fecha del Primer Pago'
            ),
        ),
    ]
