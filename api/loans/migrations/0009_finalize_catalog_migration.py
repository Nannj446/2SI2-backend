# Generated manually for Fase 2: Finalizar Migración a Catálogos

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('loans', '0008_migrate_data_to_catalogs'),
    ]

    operations = [
        # La migración de datos se hará manualmente después
        # Por ahora, solo marcamos como aplicada
        migrations.RunPython(
            migrations.RunPython.noop,
            migrations.RunPython.noop
        ),
    ]
