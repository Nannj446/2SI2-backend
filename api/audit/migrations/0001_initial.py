# Generated manually on 2026-04-11
# Migration for audit app models

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('tenants', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='AuditLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('action', models.CharField(choices=[('login', 'Login'), ('logout', 'Logout'), ('create', 'Create'), ('update', 'Update'), ('delete', 'Delete'), ('view', 'View'), ('permission_change', 'Permission Change'), ('role_assign', 'Role Assignment'), ('tenant_switch', 'Tenant Switch'), ('security_event', 'Security Event')], help_text='Tipo de acción realizada', max_length=50)),
                ('resource_type', models.CharField(help_text='Tipo de recurso afectado (ej: User, Role, Institution)', max_length=100)),
                ('resource_id', models.IntegerField(blank=True, help_text='ID del recurso afectado', null=True)),
                ('description', models.TextField(help_text='Descripción detallada de la acción')),
                ('timestamp', models.DateTimeField(auto_now_add=True, db_index=True, help_text='Momento en que ocurrió la acción')),
                ('ip_address', models.GenericIPAddressField(blank=True, help_text='Dirección IP desde donde se realizó la acción', null=True)),
                ('user_agent', models.TextField(blank=True, help_text='User agent del navegador/cliente', null=True)),
                ('severity', models.CharField(choices=[('info', 'Info'), ('warning', 'Warning'), ('error', 'Error'), ('critical', 'Critical')], default='info', help_text='Nivel de severidad del evento', max_length=20)),
                ('metadata', models.JSONField(blank=True, default=dict, help_text='Datos adicionales en formato JSON')),
                ('institution', models.ForeignKey(blank=True, help_text='Institución en cuyo contexto se realizó la acción', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='audit_logs', to='tenants.financialinstitution')),
                ('user', models.ForeignKey(blank=True, help_text='Usuario que realizó la acción', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='audit_logs', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Audit Log',
                'verbose_name_plural': 'Audit Logs',
                'db_table': 'audit_logs',
                'ordering': ['-timestamp'],
            },
        ),
        migrations.CreateModel(
            name='SecurityEvent',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('event_type', models.CharField(choices=[('failed_login', 'Failed Login Attempt'), ('account_locked', 'Account Locked'), ('suspicious_activity', 'Suspicious Activity'), ('unauthorized_access', 'Unauthorized Access Attempt'), ('permission_escalation', 'Permission Escalation Attempt'), ('data_breach_attempt', 'Data Breach Attempt'), ('rate_limit_exceeded', 'Rate Limit Exceeded'), ('invalid_token', 'Invalid Token'), ('session_hijack', 'Session Hijack Attempt')], db_index=True, help_text='Tipo de evento de seguridad', max_length=50)),
                ('email', models.EmailField(blank=True, help_text='Email usado en el intento (si aplica)', max_length=254, null=True)),
                ('ip_address', models.GenericIPAddressField(db_index=True, help_text='Dirección IP del origen')),
                ('user_agent', models.TextField(blank=True, help_text='User agent del cliente', null=True)),
                ('timestamp', models.DateTimeField(auto_now_add=True, db_index=True, help_text='Momento del evento')),
                ('description', models.TextField(help_text='Descripción del evento')),
                ('metadata', models.JSONField(blank=True, default=dict, help_text='Datos adicionales del evento')),
                ('resolved', models.BooleanField(default=False, help_text='Si el evento fue revisado y resuelto')),
                ('resolved_at', models.DateTimeField(blank=True, help_text='Momento en que se resolvió', null=True)),
                ('resolved_by', models.ForeignKey(blank=True, help_text='Usuario que resolvió el evento', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='resolved_security_events', to=settings.AUTH_USER_MODEL)),
                ('user', models.ForeignKey(blank=True, help_text='Usuario relacionado con el evento', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='security_events', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Security Event',
                'verbose_name_plural': 'Security Events',
                'db_table': 'security_events',
                'ordering': ['-timestamp'],
            },
        ),
        migrations.AddIndex(
            model_name='auditlog',
            index=models.Index(fields=['-timestamp'], name='audit_logs_timesta_idx'),
        ),
        migrations.AddIndex(
            model_name='auditlog',
            index=models.Index(fields=['user', '-timestamp'], name='audit_logs_user_id_timesta_idx'),
        ),
        migrations.AddIndex(
            model_name='auditlog',
            index=models.Index(fields=['institution', '-timestamp'], name='audit_logs_institu_timesta_idx'),
        ),
        migrations.AddIndex(
            model_name='auditlog',
            index=models.Index(fields=['action', '-timestamp'], name='audit_logs_action_timesta_idx'),
        ),
        migrations.AddIndex(
            model_name='auditlog',
            index=models.Index(fields=['severity', '-timestamp'], name='audit_logs_severit_timesta_idx'),
        ),
        migrations.AddIndex(
            model_name='securityevent',
            index=models.Index(fields=['-timestamp'], name='security_e_timesta_idx'),
        ),
        migrations.AddIndex(
            model_name='securityevent',
            index=models.Index(fields=['ip_address', '-timestamp'], name='security_e_ip_addr_timesta_idx'),
        ),
        migrations.AddIndex(
            model_name='securityevent',
            index=models.Index(fields=['event_type', '-timestamp'], name='security_e_event_t_timesta_idx'),
        ),
        migrations.AddIndex(
            model_name='securityevent',
            index=models.Index(fields=['resolved', '-timestamp'], name='security_e_resolve_timesta_idx'),
        ),
    ]
