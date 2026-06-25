# Generated migration to remove DocumentRequirement model

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('loans', '0011_remove_product_from_parameters'),
    ]

    operations = [
        # Primero eliminar el campo document_requirement de LoanApplicationDocumentRequirement
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.RemoveField(
                    model_name='loanapplicationdocumentrequirement',
                    name='document_requirement',
                ),
            ],
            database_operations=[
                # No hacer nada en la base de datos, el campo se eliminará manualmente después
                migrations.RunSQL(sql=migrations.RunSQL.noop, reverse_sql=migrations.RunSQL.noop),
            ],
        ),
        # Luego eliminar el modelo DocumentRequirement completamente
        migrations.DeleteModel(
            name='DocumentRequirement',
        ),
    ]
