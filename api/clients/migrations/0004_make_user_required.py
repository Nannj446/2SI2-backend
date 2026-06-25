# Generated migration to make user FK required and unique

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('clients', '0003_populate_user_fk'),
    ]

    operations = [
        migrations.AlterField(
            model_name='client',
            name='user',
            field=models.OneToOneField(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='client_profile',
                to=settings.AUTH_USER_MODEL,
                verbose_name='Usuario',
                help_text='Usuario asociado a este cliente'
            ),
        ),
    ]
