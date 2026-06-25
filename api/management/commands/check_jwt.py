from django.conf import settings
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Verifica la configuración de JWT'

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING('Verificando configuración de JWT...'))
        
        # Verificar SIMPLE_JWT
        jwt_config = settings.SIMPLE_JWT
        self.stdout.write(f'ACCESS_TOKEN_LIFETIME: {jwt_config["ACCESS_TOKEN_LIFETIME"]}')
        self.stdout.write(f'REFRESH_TOKEN_LIFETIME: {jwt_config["REFRESH_TOKEN_LIFETIME"]}')
        self.stdout.write(f'ROTATE_REFRESH_TOKENS: {jwt_config["ROTATE_REFRESH_TOKENS"]}')
        self.stdout.write(f'BLACKLIST_AFTER_ROTATION: {jwt_config["BLACKLIST_AFTER_ROTATION"]}')
        self.stdout.write(f'ALGORITHM: {jwt_config["ALGORITHM"]}')
        
        # Verificar signing key
        signing_key = jwt_config["SIGNING_KEY"]
        if signing_key == settings.SECRET_KEY:
            self.stdout.write(
                self.style.WARNING('⚠️  JWT_SECRET_KEY no está configurado, usando DJANGO_SECRET_KEY')
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(f'✅ JWT_SECRET_KEY configurado: {signing_key[:10]}...')
            )
        
        # Verificar REST_FRAMEWORK
        self.stdout.write('\nREST Framework Authentication:')
        auth_classes = settings.REST_FRAMEWORK.get('DEFAULT_AUTHENTICATION_CLASSES', [])
        for auth_class in auth_classes:
            self.stdout.write(f'  - {auth_class}')
