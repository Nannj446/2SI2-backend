# Generated migration to populate user FK based on email

from django.db import migrations


def populate_user_fk(apps, schema_editor):
    """
    Poblar user_id basado en email coincidente.
    Vincula cada cliente con su usuario correspondiente.
    """
    Client = apps.get_model('clients', 'Client')
    User = apps.get_model('auth', 'User')
    
    updated_count = 0
    not_found_count = 0
    
    for client in Client.objects.all():
        if not client.email:
            print(f"[-] Cliente {client.id} sin email, saltando...")
            continue
            
        try:
            user = User.objects.get(email=client.email)
            client.user = user
            client.save(update_fields=['user'])
            updated_count += 1
            print(f"[OK] Cliente {client.id} ({client.email}) vinculado a User {user.id}")
        except User.DoesNotExist:
            not_found_count += 1
            print(f"[X] No se encontró usuario para cliente {client.id} con email: {client.email}")
        except User.MultipleObjectsReturned:
            # Si hay múltiples usuarios, tomar el primero
            user = User.objects.filter(email=client.email).first()
            client.user = user
            client.save(update_fields=['user'])
            updated_count += 1
            print(f"[-] Múltiples usuarios con email {client.email}, usando User {user.id}")
    
    print(f"\nResumen:")
    print(f"   Clientes vinculados: {updated_count}")
    print(f"   Clientes sin usuario: {not_found_count}")


def reverse_populate_user_fk(apps, schema_editor):
    """Reversa: limpiar user_id"""
    Client = apps.get_model('clients', 'Client')
    Client.objects.update(user=None)
    print("campo user_id limpiado en todos los clientes")


class Migration(migrations.Migration):

    dependencies = [
        ('clients', '0002_add_user_fk'),
    ]

    operations = [
        migrations.RunPython(
            populate_user_fk,
            reverse_populate_user_fk
        ),
    ]
