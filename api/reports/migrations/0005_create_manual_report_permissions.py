"""
Migración para crear permisos de reportes manuales.
"""

from django.db import migrations


def create_permissions(apps, schema_editor):
    """Crear permisos personalizados."""
    from api.reports.permissions_manual import create_manual_report_permissions
    create_manual_report_permissions()


def reverse_permissions(apps, schema_editor):
    """Eliminar permisos creados."""
    Permission = apps.get_model('auth', 'Permission')
    ContentType = apps.get_model('contenttypes', 'ContentType')
    
    try:
        content_type = ContentType.objects.get(
            app_label='reports',
            model='manualreport'
        )
        Permission.objects.filter(content_type=content_type).delete()
    except ContentType.DoesNotExist:
        pass


class Migration(migrations.Migration):
    
    dependencies = [
        ('reports', '0004_generatedreport_file_size_bytes'),
    ]
    
    operations = [
        migrations.RunPython(create_permissions, reverse_permissions),
    ]
