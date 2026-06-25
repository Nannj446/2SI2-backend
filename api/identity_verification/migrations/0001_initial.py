# Generated migration for identity_verification app

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('tenants', '0001_initial'),  # Depends on FinancialInstitution
        ('loans', '0001_initial'),     # Depends on LoanApplication
        ('branches', '0001_initial'),  # Depends on Branch
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='IdentityVerification',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('provider', models.CharField(
                    choices=[('DIDIT', 'Didit')], 
                    db_index=True, 
                    default='DIDIT', 
                    help_text='Proveedor de verificación de identidad', 
                    max_length=50
                )),
                ('provider_session_id', models.CharField(
                    db_index=True, 
                    help_text='ID único de sesión en el proveedor (e.g., Didit session_id)', 
                    max_length=255, 
                    unique=True
                )),
                ('provider_session_token', models.CharField(
                    blank=True, 
                    help_text='Token de sesión del proveedor (si aplica y es necesario). SENSIBLE.', 
                    max_length=500
                )),
                ('verification_url', models.URLField(
                    help_text='URL del hosting Didit o similar donde el usuario completa la verificación'
                )),
                ('status', models.CharField(
                    choices=[
                        ('PENDING', 'Pendiente'),
                        ('IN_PROGRESS', 'En Progreso'),
                        ('APPROVED', 'Aprobada'),
                        ('DECLINED', 'Rechazada'),
                        ('MANUAL_REVIEW', 'Revisión Manual'),
                        ('EXPIRED', 'Expirada'),
                        ('ERROR', 'Error')
                    ],
                    db_index=True,
                    default='PENDING',
                    help_text='Estado actual de la verificación',
                    max_length=20
                )),
                ('decision', models.CharField(
                    choices=[
                        ('APPROVED', 'Aprobado'),
                        ('DECLINED', 'Rechazado'),
                        ('PENDING', 'Pendiente'),
                        ('MANUAL_REVIEW', 'Revisión Manual')
                    ],
                    db_index=True,
                    default='PENDING',
                    help_text='Decisión de aprobación/rechazo',
                    max_length=20
                )),
                ('document_type', models.CharField(
                    blank=True,
                    help_text='Tipo de documento (e.g., PASSPORT, NATIONAL_ID, DRIVER_LICENSE)',
                    max_length=50
                )),
                ('document_number', models.CharField(
                    blank=True,
                    db_index=True,
                    help_text='Número de documento identificado',
                    max_length=50
                )),
                ('full_name', models.CharField(
                    blank=True,
                    help_text='Nombre completo confirmado en la verificación',
                    max_length=255
                )),
                ('date_of_birth', models.DateField(
                    blank=True,
                    help_text='Fecha de nacimiento confirmada',
                    null=True
                )),
                ('country', models.CharField(
                    blank=True,
                    help_text='Código de país ISO 3166-1 alpha-2',
                    max_length=2
                )),
                ('error_message', models.TextField(
                    blank=True,
                    help_text='Mensaje de error si la verificación falló o tuvo problemas'
                )),
                ('raw_response', models.JSONField(
                    blank=True,
                    default=dict,
                    help_text='Respuesta del proveedor (solo campos no-sensibles y útiles para auditoría)'
                )),
                ('started_at', models.DateTimeField(
                    auto_now_add=True,
                    help_text='Cuando se creó la sesión de verificación'
                )),
                ('completed_at', models.DateTimeField(
                    blank=True,
                    db_index=True,
                    help_text='Cuando se completó/resolvió la verificación',
                    null=True
                )),
                ('expires_at', models.DateTimeField(
                    blank=True,
                    db_index=True,
                    help_text='Cuando expira la sesión (si aplica)',
                    null=True
                )),
                ('webhook_received_at', models.DateTimeField(
                    blank=True,
                    help_text='Último webhook recibido del proveedor',
                    null=True
                )),
                ('branch', models.ForeignKey(
                    blank=True,
                    help_text='Sucursal donde se origina la solicitud (opcional)',
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='identity_verifications',
                    to='branches.branch'
                )),
                ('credit_application', models.ForeignKey(
                    blank=True,
                    help_text='Solicitud de crédito asociada (opcional)',
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='identity_verifications',
                    to='loans.loanapplication'
                )),
                ('institution', models.ForeignKey(
                    help_text='Institución financiera a la que pertenece este registro',
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='identity_verification_set',
                    to='tenants.financialinstitution'
                )),
                ('user', models.ForeignKey(
                    help_text='Usuario prestatario siendo verificado',
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name='identity_verifications',
                    to=settings.AUTH_USER_MODEL
                )),
            ],
            options={
                'verbose_name': 'Verificación de Identidad',
                'verbose_name_plural': 'Verificaciones de Identidad',
                'db_table': 'identity_verifications',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='IdentityVerificationWebhook',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('provider', models.CharField(
                    db_index=True,
                    help_text='Proveedor que envió el webhook',
                    max_length=50
                )),
                ('provider_event_id', models.CharField(
                    db_index=True,
                    help_text='ID único del evento en el proveedor',
                    max_length=255,
                    unique=True
                )),
                ('provider_session_id', models.CharField(
                    db_index=True,
                    help_text='ID de sesión a la que corresponde el evento',
                    max_length=255
                )),
                ('payload', models.JSONField(
                    help_text='Payload completo del webhook recibido'
                )),
                ('status', models.CharField(
                    choices=[
                        ('PENDING', 'Pendiente'),
                        ('PROCESSED', 'Procesado'),
                        ('FAILED', 'Fallido'),
                        ('DUPLICATE', 'Duplicado')
                    ],
                    default='PENDING',
                    help_text='Estado del procesamiento del webhook',
                    max_length=20
                )),
                ('error_message', models.TextField(
                    blank=True,
                    help_text='Mensaje de error si el procesamiento falló'
                )),
                ('received_at', models.DateTimeField(
                    auto_now_add=True,
                    help_text='Cuándo se recibió el webhook'
                )),
                ('processed_at', models.DateTimeField(
                    blank=True,
                    help_text='Cuándo se procesó',
                    null=True
                )),
                ('identity_verification', models.ForeignKey(
                    blank=True,
                    help_text='Verificación de identidad asociada',
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='webhooks',
                    to='identity_verification.identityverification'
                )),
            ],
            options={
                'verbose_name': 'Webhook de Verificación de Identidad',
                'verbose_name_plural': 'Webhooks de Verificación de Identidad',
                'db_table': 'identity_verification_webhooks',
                'ordering': ['-received_at'],
            },
        ),
        migrations.AddIndex(
            model_name='identityverification',
            index=models.Index(fields=['institution', 'user'], name='identity_ve_instit_user_idx'),
        ),
        migrations.AddIndex(
            model_name='identityverification',
            index=models.Index(fields=['institution', 'status'], name='identity_ve_instit_status_idx'),
        ),
        migrations.AddIndex(
            model_name='identityverification',
            index=models.Index(fields=['user', '-created_at'], name='identity_ve_user_created_idx'),
        ),
        migrations.AddIndex(
            model_name='identityverification',
            index=models.Index(fields=['provider_session_id', 'provider'], name='identity_ve_session_provider_idx'),
        ),
        migrations.AddIndex(
            model_name='identityverification',
            index=models.Index(fields=['credit_application', 'status'], name='identity_ve_app_status_idx'),
        ),
        migrations.AddIndex(
            model_name='identityverificationwebhook',
            index=models.Index(fields=['provider', 'provider_event_id'], name='identity_ve_provider_event_idx'),
        ),
        migrations.AddIndex(
            model_name='identityverificationwebhook',
            index=models.Index(fields=['provider_session_id', 'status'], name='identity_ve_session_status_idx'),
        ),
        migrations.AddIndex(
            model_name='identityverificationwebhook',
            index=models.Index(fields=['-received_at'], name='identity_ve_received_idx'),
        ),
    ]
