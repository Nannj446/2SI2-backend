# Generated manually - Limpieza de campos de DocumentRequirement

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('loans', '0009_finalize_catalog_migration'),
    ]

    operations = [
        # PASO 1: Renombrar document_type (CharField) a document_type_old
        migrations.RenameField(
            model_name='documentrequirement',
            old_name='document_type',
            new_name='document_type_old',
        ),
        
        # PASO 2: Renombrar document_type_fk a document_type
        migrations.RenameField(
            model_name='documentrequirement',
            old_name='document_type_fk',
            new_name='document_type',
        ),
        
        # PASO 3: Hacer document_type NOT NULL (después de migrar datos)
        # Por ahora lo dejamos nullable hasta migrar todos los datos
        
        # PASO 4: Eliminar campos redundantes
        migrations.RemoveField(
            model_name='documentrequirement',
            name='document_name',
        ),
        
        migrations.RemoveField(
            model_name='documentrequirement',
            name='description',
        ),
        
        # PASO 5: Actualizar el ordering del modelo
        migrations.AlterModelOptions(
            name='documentrequirement',
            options={
                'ordering': ['display_order', 'document_type__name'],
                'verbose_name': 'Requisito Documental',
                'verbose_name_plural': 'Requisitos Documentales'
            },
        ),
    ]
