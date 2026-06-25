# Generated manually

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('loans', '0004_add_custom_permissions'),
    ]

    operations = [
        migrations.AddField(
            model_name='workflowstagedefinition',
            name='auto_advance_enabled',
            field=models.BooleanField(default=False, help_text='Si la etapa puede avanzar automáticamente al cumplir condiciones', verbose_name='Avance Automático Habilitado'),
        ),
        migrations.AddField(
            model_name='workflowstagedefinition',
            name='auto_advance_conditions',
            field=models.JSONField(blank=True, default=dict, help_text='Condiciones que deben cumplirse para avanzar automáticamente. Ej: {"documents_complete": true, "kyc_approved": true}', verbose_name='Condiciones de Avance Automático'),
        ),
        migrations.AddField(
            model_name='workflowstagedefinition',
            name='next_stage_on_success',
            field=models.CharField(blank=True, help_text='Código de la etapa siguiente si se completa exitosamente', max_length=50, null=True, verbose_name='Siguiente Etapa (Éxito)'),
        ),
        migrations.AddField(
            model_name='workflowstagedefinition',
            name='next_stage_on_failure',
            field=models.CharField(blank=True, help_text='Código de la etapa siguiente si falla (ej: REJECTED)', max_length=50, null=True, verbose_name='Siguiente Etapa (Fallo)'),
        ),
        migrations.AddField(
            model_name='workflowstagedefinition',
            name='requires_manual_approval',
            field=models.BooleanField(default=True, help_text='Si requiere que un usuario apruebe manualmente para avanzar', verbose_name='Requiere Aprobación Manual'),
        ),
        migrations.AddField(
            model_name='workflowstagedefinition',
            name='escalation_enabled',
            field=models.BooleanField(default=False, help_text='Si se debe escalar cuando se excede el tiempo límite', verbose_name='Escalamiento Habilitado'),
        ),
        migrations.AddField(
            model_name='workflowstagedefinition',
            name='notification_template',
            field=models.CharField(blank=True, help_text='Nombre de la plantilla de notificación a usar al entrar en esta etapa', max_length=100, null=True, verbose_name='Plantilla de Notificación'),
        ),
        migrations.AddField(
            model_name='workflowstagedefinition',
            name='client_message_template',
            field=models.TextField(blank=True, help_text='Mensaje que se mostrará al cliente al entrar en esta etapa', null=True, verbose_name='Mensaje para el Cliente'),
        ),
        migrations.AddField(
            model_name='workflowstagedefinition',
            name='requires_client_action',
            field=models.BooleanField(default=False, help_text='Si el cliente debe realizar alguna acción en esta etapa', verbose_name='Requiere Acción del Cliente'),
        ),
        migrations.AddField(
            model_name='workflowstagedefinition',
            name='client_action_description',
            field=models.TextField(blank=True, help_text='Descripción de la acción que debe realizar el cliente', null=True, verbose_name='Descripción de Acción del Cliente'),
        ),
        migrations.AddField(
            model_name='workflowstagedefinition',
            name='client_action_url',
            field=models.CharField(blank=True, help_text='URL relativa donde el cliente puede realizar la acción', max_length=255, null=True, verbose_name='URL de Acción del Cliente'),
        ),
        migrations.AddField(
            model_name='workflowstagedefinition',
            name='is_final_stage',
            field=models.BooleanField(default=False, help_text='Si esta es una etapa final del workflow (APPROVED, REJECTED, DISBURSED)', verbose_name='Etapa Final'),
        ),
    ]
