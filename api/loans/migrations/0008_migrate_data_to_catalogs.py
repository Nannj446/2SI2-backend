# Generated manually for Fase 2: Migración de Datos a Catálogos

from django.db import migrations


def migrate_currencies_to_m2m(apps, schema_editor):
    """
    Migra allowed_currencies de JSONField a ManyToMany.
    
    Mapeo:
    - "BOB" → Currency con code="BOB"
    - "USD" → Currency con code="USD"
    """
    # Por ahora, skip - los datos se migrarán manualmente después
    print("⚠ Migración de currencies: Se debe hacer manualmente después de aplicar todas las migraciones")
    print("  Razón: Los campos M2M no están disponibles en el estado de migración")


def migrate_payment_frequencies_to_m2m(apps, schema_editor):
    """
    Migra payment_frequencies de JSONField a ManyToMany.
    
    Mapeo:
    - "MONTHLY" → PaymentFrequency con code="MONTHLY"
    - "BIWEEKLY" → PaymentFrequency con code="BIWEEKLY"
    - "WEEKLY" → PaymentFrequency con code="WEEKLY"
    """
    # Por ahora, skip - los datos se migrarán manualmente después
    print("⚠ Migración de payment frequencies: Se debe hacer manualmente después de aplicar todas las migraciones")
    print("  Razón: Los campos M2M no están disponibles en el estado de migración")


def migrate_document_types_to_fk(apps, schema_editor):
    """
    Migra document_type de CharField a ForeignKey.
    
    Mapeo:
    - "ID_DOCUMENT" → DocumentType con code="ID_DOCUMENT"
    - "INCOME_PROOF" → DocumentType con code="INCOME_PROOF"
    - etc.
    """
    # Por ahora, skip - los datos se migrarán manualmente después
    print("⚠ Migración de document types: Se debe hacer manualmente después de aplicar todas las migraciones")
    print("  Razón: El ordering del modelo causa conflictos en el estado de migración")


def reverse_migration(apps, schema_editor):
    """
    Revierte la migración (opcional, para rollback).
    """
    print("⚠ Reversión de migración de datos no implementada")
    print("⚠ Los datos en M2M y FK permanecerán, pero los JSONFields no se restaurarán")


class Migration(migrations.Migration):

    dependencies = [
        ('loans', '0007_extend_product_parameters_and_document_requirements'),
    ]

    operations = [
        migrations.RunPython(
            migrate_currencies_to_m2m,
            reverse_migration
        ),
        migrations.RunPython(
            migrate_payment_frequencies_to_m2m,
            reverse_migration
        ),
        migrations.RunPython(
            migrate_document_types_to_fk,
            reverse_migration
        ),
    ]
