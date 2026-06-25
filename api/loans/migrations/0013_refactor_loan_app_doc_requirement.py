from django.db import migrations, models
import django.db.models.deletion


def migrate_document_requirements(apps, schema_editor):
    LoanApplicationDocumentRequirement = apps.get_model('loans', 'LoanApplicationDocumentRequirement')
    orphaned_count = LoanApplicationDocumentRequirement.objects.filter(
        product_document_requirement__isnull=True
    ).count()
    if orphaned_count > 0:
        print(f"Eliminando {orphaned_count} registros huérfanos")
        LoanApplicationDocumentRequirement.objects.filter(
            product_document_requirement__isnull=True
        ).delete()


def remove_old_field(apps, schema_editor):
    with schema_editor.connection.cursor() as cursor:
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name='loan_application_document_requirements' 
            AND column_name='document_requirement_id'
        """)
        if cursor.fetchone():
            print("Eliminando columna document_requirement_id...")
            cursor.execute("""
                ALTER TABLE loan_application_document_requirements 
                DROP COLUMN IF EXISTS document_requirement_id CASCADE
            """)


class Migration(migrations.Migration):

    dependencies = [
        ('loans', '0012_remove_document_requirement_model'),
        ('products', '0002_refactor_credit_product'),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
                DO $$
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1 FROM information_schema.columns 
                        WHERE table_name='loan_application_document_requirements' 
                        AND column_name='product_document_requirement_id'
                    ) THEN
                        ALTER TABLE loan_application_document_requirements 
                        ADD COLUMN product_document_requirement_id INTEGER NULL;
                        
                        ALTER TABLE loan_application_document_requirements 
                        ADD CONSTRAINT loan_application_document_requirements_product_document_requirement_id_fkey 
                        FOREIGN KEY (product_document_requirement_id) 
                        REFERENCES product_document_requirements(id) 
                        ON DELETE RESTRICT 
                        DEFERRABLE INITIALLY DEFERRED;
                    END IF;
                END $$;
            """,
            reverse_sql=migrations.RunSQL.noop
        ),
        migrations.RunPython(migrate_document_requirements, reverse_code=migrations.RunPython.noop),
        migrations.RunPython(remove_old_field, reverse_code=migrations.RunPython.noop),
        migrations.RunSQL(
            sql="ALTER TABLE loan_application_document_requirements DROP CONSTRAINT IF EXISTS unique_doc_per_application",
            reverse_sql=migrations.RunSQL.noop
        ),
        migrations.RunSQL(
            sql="""
                DO $$
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1 FROM pg_constraint 
                        WHERE conname = 'unique_product_doc_per_application'
                    ) THEN
                        ALTER TABLE loan_application_document_requirements 
                        ADD CONSTRAINT unique_product_doc_per_application 
                        UNIQUE (loan_application_id, product_document_requirement_id);
                    END IF;
                END $$;
            """,
            reverse_sql=migrations.RunSQL.noop
        ),
        migrations.AlterModelOptions(
            name='loanapplicationdocumentrequirement',
            options={
                'ordering': ['product_document_requirement__display_order'],
                'verbose_name': 'Documento Requerido de Solicitud',
                'verbose_name_plural': 'Documentos Requeridos de Solicitudes'
            },
        ),
    ]
