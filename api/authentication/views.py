from django_ratelimit.decorators import ratelimit
from django.utils.decorators import method_decorator
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema, OpenApiExample
from drf_spectacular.types import OpenApiTypes

from .serializers import LoginSerializer


@method_decorator(ratelimit(key='ip', rate='10/15m', method='POST'), name='dispatch')
class LoginAPIView(APIView):
    """Vista para login de usuario."""
    
    authentication_classes = []
    permission_classes = [AllowAny]

    @extend_schema(
        tags=['Autenticación'],
        summary='Iniciar sesión',
        description='''
        Autentica un usuario con email y contraseña, retornando tokens JWT.
        
        Si el usuario tiene 2FA habilitado, retorna un challenge_token que debe
        usarse en el endpoint de verificación 2FA.
        ''',
        request=LoginSerializer,
        responses={
            200: OpenApiTypes.OBJECT,
            400: OpenApiTypes.OBJECT,
            401: OpenApiTypes.OBJECT,
        },
        examples=[
            OpenApiExample(
                'Login exitoso sin 2FA',
                value={
                    'access': 'eyJ0eXAiOiJKV1QiLCJhbGc...',
                    'refresh': 'eyJ0eXAiOiJKV1QiLCJhbGc...',
                    'user': {
                        'id': 1,
                        'email': 'usuario@ejemplo.com',
                        'first_name': 'Juan',
                        'last_name': 'Pérez'
                    },
                    'institution': {
                        'id': 1,
                        'name': 'Banco Ejemplo',
                        'slug': 'banco-ejemplo'
                    },
                    'requires_2fa': False
                },
                response_only=True,
                status_codes=['200'],
            ),
            OpenApiExample(
                'Login requiere 2FA',
                value={
                    'requires_2fa': True,
                    'challenge_token': 'temp_token_123',
                    'expires_in': 300,
                    'method': 'app',
                    'message': 'Se requiere código de autenticación de dos factores.'
                },
                response_only=True,
                status_codes=['200'],
            ),
        ],
    )
    def post(self, request):
        """
        Autentica un usuario y retorna tokens JWT.

        Request body:
            {
                "email": "usuario@ejemplo.com",
                "password": "contraseña"
            }

        Response (200 OK):
            {
                "access": "token...",
                "refresh": "token...",
                "user": {
                    "id": 1,
                    "email": "usuario@ejemplo.com",
                    "first_name": "Juan",
                    "last_name": "Pérez"
                },
                "institution": {
                    "id": 1,
                    "name": "Banco Ejemplo",
                    "slug": "banco-ejemplo",
                    "institution_type": "banking"
                },
                "role": "admin",
                "requires_2fa": false
            }

        Response (400 Bad Request):
            {
                "email": ["mensaje de error"],
                "password": ["mensaje de error"]
            }

        Response (401 Unauthorized):
            {
                "detail": "Credenciales inválidas."
            }
        """
        serializer = LoginSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        result = serializer.save()

        # Si requiere 2FA, retornar respuesta especial
        if result.requires_2fa:
            return Response({
                'requires_2fa': True,
                'challenge_token': result.challenge_token,
                'expires_in': result.expires_in,
                'method': result.method,  # Incluir método de 2FA
                'message': 'Se requiere código de autenticación de dos factores.',
                'user': {
                    'id': result.user.id,
                    'email': result.user.email,
                },
            }, status=status.HTTP_200_OK)

        # Login normal sin 2FA
        response_payload = {
            'access': result.access_token,
            'refresh': result.refresh_token,
            'user': {
                'id': result.user.id,
                'email': result.user.email,
                'first_name': result.user.first_name,
                'last_name': result.user.last_name,
                'institution': {
                    'id': result.institution.id,
                    'name': result.institution.name,
                    'slug': result.institution.slug,
                    'institution_type': result.institution.institution_type,
                } if result.institution else None,
            },
            'institution': {
                'id': result.institution.id,
                'name': result.institution.name,
                'slug': result.institution.slug,
                'institution_type': result.institution.institution_type,
            } if result.institution else None,
            'role': result.role,
            'user_type': result.user_type,
            'roles': result.roles,
            'permissions': result.permissions,
            'requires_2fa': result.requires_2fa,
        }

        return Response(response_payload, status=status.HTTP_200_OK)



# ============================================================
# LOGOUT
# ============================================================

class LogoutAPIView(APIView):
    """Vista para logout de usuario."""
    
    permission_classes = [AllowAny]

    @extend_schema(
        tags=['Autenticación'],
        summary='Cerrar sesión',
        description='Cierra la sesión del usuario agregando el refresh token a la blacklist.',
        request={
            'application/json': {
                'type': 'object',
                'properties': {
                    'refresh': {
                        'type': 'string',
                        'description': 'Refresh token a invalidar'
                    }
                },
                'required': ['refresh']
            }
        },
        responses={
            200: OpenApiTypes.OBJECT,
            400: OpenApiTypes.OBJECT,
        },
        examples=[
            OpenApiExample(
                'Logout exitoso',
                value={'message': 'Sesión cerrada exitosamente.'},
                response_only=True,
                status_codes=['200'],
            ),
        ],
    )
    def post(self, request):
        """
        Cierra la sesión del usuario agregando el refresh token a la blacklist.

        Request body:
            {
                "refresh": "token..."
            }

        Response (200 OK):
            {
                "message": "Sesión cerrada exitosamente."
            }

        Response (400 Bad Request):
            {
                "detail": "Token inválido o ya ha sido revocado."
            }
        """
        from .serializers import LogoutSerializer
        
        serializer = LogoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = serializer.save()

        return Response(result, status=status.HTTP_200_OK)



# ============================================================
# PASSWORD RESET
# ============================================================

@method_decorator(ratelimit(key='ip', rate='5/1h', method='POST'), name='dispatch')
class PasswordResetRequestAPIView(APIView):
    """Vista para solicitar recuperación de contraseña."""
    
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        """
        Solicita recuperación de contraseña.

        Request body:
            {
                "email": "usuario@ejemplo.com"
            }

        Response (200 OK):
            {
                "message": "Si el correo existe, recibirás instrucciones para recuperar tu contraseña."
            }
        """
        from .serializers import PasswordResetRequestSerializer
        
        serializer = PasswordResetRequestSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        result = serializer.save()

        return Response({'message': result.message}, status=status.HTTP_200_OK)


class PasswordResetValidateAPIView(APIView):
    """Vista para validar token de recuperación."""
    
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        """
        Valida un token de recuperación.

        Request body:
            {
                "token": "token..."
            }

        Response (200 OK):
            {
                "valid": true,
                "message": "Token válido."
            }
        """
        from .serializers import PasswordResetValidateSerializer
        
        serializer = PasswordResetValidateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        return Response({
            'valid': serializer.validated_data['valid'],
            'message': serializer.validated_data['message']
        }, status=status.HTTP_200_OK)


class PasswordResetConfirmAPIView(APIView):
    """Vista para confirmar nueva contraseña."""
    
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        """
        Confirma el cambio de contraseña.

        Request body:
            {
                "token": "token...",
                "new_password": "NuevaPassword123!",
                "confirm_password": "NuevaPassword123!"
            }

        Response (200 OK):
            {
                "message": "Contraseña actualizada exitosamente."
            }
        """
        from .serializers import PasswordResetConfirmSerializer
        
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response({
            'message': 'Contraseña actualizada exitosamente.'
        }, status=status.HTTP_200_OK)



# ============================================================
# TWO-FACTOR AUTHENTICATION (2FA)
# ============================================================

from rest_framework.permissions import IsAuthenticated


class TwoFactorEnableAPIView(APIView):
    """Vista para iniciar habilitación de 2FA."""
    
    permission_classes = [IsAuthenticated]

    def post(self, request):
        """
        Inicia el proceso de habilitación de 2FA.

        Response (200 OK):
            {
                "secret": "JBSWY3DPEHPK3PXP",
                "qr_code": "data:image/png;base64,iVBORw0KGgo...",
                "backup_codes": ["ABCD-1234", "EFGH-5678", ...]
            }
        """
        from .serializers import TwoFactorEnableSerializer
        
        serializer = TwoFactorEnableSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        result = serializer.save()

        return Response({
            'secret': result.secret,
            'qr_code': f'data:image/png;base64,{result.qr_code_base64}',
            'provisioning_uri': result.provisioning_uri,  # URL otpauth para móvil
            'backup_codes': result.backup_codes,
        }, status=status.HTTP_200_OK)


@method_decorator(ratelimit(key='user', rate='5/5m', method='POST'), name='dispatch')
class TwoFactorVerifyAPIView(APIView):
    """Vista para verificar y activar 2FA."""
    
    permission_classes = [IsAuthenticated]

    def post(self, request):
        """
        Verifica el código TOTP y activa 2FA.

        Request body:
            {
                "token": "123456"
            }

        Response (200 OK):
            {
                "message": "Autenticación de dos factores activada exitosamente."
            }
        """
        from .serializers import TwoFactorVerifySerializer
        
        serializer = TwoFactorVerifySerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        result = serializer.save()

        return Response({
            'message': result.message
        }, status=status.HTTP_200_OK)


class TwoFactorDisableAPIView(APIView):
    """Vista para deshabilitar 2FA."""
    
    permission_classes = [IsAuthenticated]

    def post(self, request):
        """
        Deshabilita 2FA después de verificar la contraseña.

        Request body:
            {
                "password": "contraseña"
            }

        Response (200 OK):
            {
                "message": "Autenticación de dos factores deshabilitada exitosamente."
            }
        """
        from .serializers import TwoFactorDisableSerializer
        
        serializer = TwoFactorDisableSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        result = serializer.save()

        return Response({
            'message': result.message
        }, status=status.HTTP_200_OK)


class TwoFactorStatusAPIView(APIView):
    """Vista para obtener el estado de 2FA del usuario."""
    
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """
        Obtiene el estado de 2FA del usuario.

        Response (200 OK):
            {
                "is_enabled": true,
                "enabled_at": "2026-03-28T10:30:00Z",
                "backup_codes_remaining": 8,
                "method": "totp" | "email"
            }
        """
        from api.models import TwoFactorAuth
        
        try:
            two_factor = TwoFactorAuth.objects.get(user=request.user)
            return Response({
                'is_enabled': two_factor.is_enabled,
                'enabled_at': two_factor.enabled_at,
                'backup_codes_remaining': len(two_factor.backup_codes) if two_factor.is_enabled else 0,
                'method': two_factor.method,
            }, status=status.HTTP_200_OK)
        except TwoFactorAuth.DoesNotExist:
            return Response({
                'is_enabled': False,
                'enabled_at': None,
                'backup_codes_remaining': 0,
                'method': 'totp',
            }, status=status.HTTP_200_OK)



@method_decorator(ratelimit(key='ip', rate='5/5m', method='POST'), name='dispatch')
class TwoFactorLoginVerifyAPIView(APIView):
    """Vista para verificar código 2FA durante login."""
    
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        """
        Verifica el código 2FA y completa el login.

        Request body:
            {
                "challenge_token": "token...",
                "totp_code": "123456",
                "is_backup_code": false
            }

        Response (200 OK):
            {
                "access": "token...",
                "refresh": "token...",
                "user": {...},
                "institution": {...},
                "role": "admin"
            }
        """
        from .serializers import TwoFactorLoginVerifySerializer
        
        serializer = TwoFactorLoginVerifySerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        result = serializer.save()

        response_payload = {
            'access': result.access_token,
            'refresh': result.refresh_token,
            'user': {
                'id': result.user.id,
                'email': result.user.email,
                'first_name': result.user.first_name,
                'last_name': result.user.last_name,
                'institution': {
                    'id': result.institution.id,
                    'name': result.institution.name,
                    'slug': result.institution.slug,
                    'institution_type': result.institution.institution_type,
                } if result.institution else None,
            },
            'institution': {
                'id': result.institution.id,
                'name': result.institution.name,
                'slug': result.institution.slug,
                'institution_type': result.institution.institution_type,
            } if result.institution else None,
            'role': result.role,
            'user_type': result.user_type,
            'roles': result.roles,
            'permissions': result.permissions,
        }

        return Response(response_payload, status=status.HTTP_200_OK)



class TwoFactorRegenerateBackupCodesAPIView(APIView):
    """Vista para regenerar códigos de respaldo."""
    
    permission_classes = [IsAuthenticated]

    def post(self, request):
        """
        Regenera los códigos de respaldo después de verificar la contraseña.

        Request body:
            {
                "password": "contraseña"
            }

        Response (200 OK):
            {
                "backup_codes": ["ABCD-1234", "EFGH-5678", ...],
                "message": "Códigos de respaldo regenerados exitosamente."
            }
        """
        from .serializers import TwoFactorRegenerateBackupCodesSerializer
        
        serializer = TwoFactorRegenerateBackupCodesSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        result = serializer.save()

        return Response({
            'backup_codes': result.backup_codes,
            'message': result.message
        }, status=status.HTTP_200_OK)


# ============================================================
# EMAIL TWO-FACTOR AUTHENTICATION
# ============================================================

@method_decorator(ratelimit(key='user_or_ip', rate='3/5m', method='POST'), name='dispatch')
class EmailTwoFactorResendAPIView(APIView):
    """Vista para reenviar código 2FA por email."""
    
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        """
        Reenvía código de verificación por email.
        
        Request body:
            {
                "challenge_token": "token..."
            }
        
        Response (200 OK):
            {
                "challenge_token": "new_token...",
                "message": "Código reenviado exitosamente.",
                "expires_in": 5
            }
        """
        from .serializers import EmailTwoFactorResendSerializer
        
        serializer = EmailTwoFactorResendSerializer(
            data=request.data,
            context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        result = serializer.save()
        
        return Response({
            'challenge_token': result.challenge_token,
            'message': result.message,
            'expires_in': result.expires_in_minutes
        }, status=status.HTTP_200_OK)


class TwoFactorSetMethodAPIView(APIView):
    """Vista para cambiar el método de 2FA."""
    
    permission_classes = [IsAuthenticated]

    def post(self, request):
        """
        Cambia el método de 2FA entre TOTP y Email.
        
        Request body:
            {
                "method": "totp" | "email",
                "password": "contraseña"
            }
        
        Response (200 OK):
            {
                "method": "email",
                "message": "Método de 2FA cambiado a: Código por Email"
            }
        """
        from .serializers import TwoFactorSetMethodSerializer
        
        serializer = TwoFactorSetMethodSerializer(
            data=request.data,
            context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        result = serializer.save()
        
        return Response({
            'method': result['method'],
            'message': result['message']
        }, status=status.HTTP_200_OK)


class TwoFactorGetMethodAPIView(APIView):
    """Vista para obtener el método de 2FA actual."""
    
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """
        Obtiene el método de 2FA actual del usuario.
        
        Response (200 OK):
            {
                "method": "totp" | "email",
                "is_enabled": true
            }
        """
        from api.models import TwoFactorAuth
        
        try:
            two_factor = TwoFactorAuth.objects.get(user=request.user)
            return Response({
                'method': two_factor.method,
                'is_enabled': two_factor.is_enabled,
            }, status=status.HTTP_200_OK)
        except TwoFactorAuth.DoesNotExist:
            return Response({
                'method': 'totp',
                'is_enabled': False,
            }, status=status.HTTP_200_OK)



class EmailTwoFactorEnableAPIView(APIView):
    """Vista para habilitar 2FA directamente con email."""
    
    permission_classes = [IsAuthenticated]

    def post(self, request):
        """
        Habilita 2FA con método email directamente.
        
        Request body:
            {
                "password": "contraseña"
            }
        
        Response (200 OK):
            {
                "method": "email",
                "message": "Autenticación de dos factores habilitada con método email."
            }
        """
        from .serializers import EmailTwoFactorEnableSerializer
        
        serializer = EmailTwoFactorEnableSerializer(
            data=request.data,
            context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        result = serializer.save()
        
        return Response(result, status=status.HTTP_200_OK)

# ============================================================
# MOBILE PASSWORD RESET
# ============================================================

@method_decorator(ratelimit(key='ip', rate='5/5m', method='POST'), name='dispatch')
class PasswordResetVerifyCodeAPIView(APIView):
    """Vista para verificar código de recuperación móvil."""
    
    authentication_classes = []
    permission_classes = [AllowAny]

    @extend_schema(
        tags=['Autenticación'],
        summary='Verificar código de recuperación móvil',
        description='''
        Verifica un código de 6 dígitos enviado por email para recuperación de contraseña en móvil.
        
        Si el código es válido, retorna un token temporal que debe usarse para confirmar la nueva contraseña.
        ''',
        request={
            'application/json': {
                'type': 'object',
                'properties': {
                    'email': {
                        'type': 'string',
                        'format': 'email',
                        'description': 'Email del usuario'
                    },
                    'code': {
                        'type': 'string',
                        'minLength': 6,
                        'maxLength': 6,
                        'description': 'Código de 6 dígitos recibido por email'
                    }
                },
                'required': ['email', 'code']
            }
        },
        responses={
            200: OpenApiTypes.OBJECT,
            400: OpenApiTypes.OBJECT,
        },
        examples=[
            OpenApiExample(
                'Código válido',
                value={
                    'valid': True,
                    'message': 'Código verificado correctamente.',
                    'reset_token': 'temp_token_for_password_reset'
                },
                response_only=True,
                status_codes=['200'],
            ),
            OpenApiExample(
                'Código inválido',
                value={
                    'valid': False,
                    'message': 'Código inválido o expirado.'
                },
                response_only=True,
                status_codes=['200'],
            ),
        ],
    )
    def post(self, request):
        """
        Verifica código de recuperación móvil.

        Request body:
            {
                "email": "usuario@ejemplo.com",
                "code": "123456"
            }

        Response (200 OK):
            {
                "valid": true,
                "message": "Código verificado correctamente.",
                "reset_token": "temp_token_for_password_reset"
            }

        Response (400 Bad Request):
            {
                "email": ["mensaje de error"],
                "code": ["mensaje de error"]
            }
        """
        from .serializers import PasswordResetVerifyCodeSerializer
        
        serializer = PasswordResetVerifyCodeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = serializer.save()

        response_data = {
            'valid': result.valid,
            'message': result.message,
        }
        
        if result.reset_token:
            response_data['reset_token'] = result.reset_token

        return Response(response_data, status=status.HTTP_200_OK)



# ============================================================
# CHANGE PASSWORD
# ============================================================

from rest_framework.permissions import IsAuthenticated

@method_decorator(ratelimit(key='user', rate='5/15m', method='POST'), name='dispatch')
class ChangePasswordAPIView(APIView):
    """Vista para cambiar contraseña de usuario autenticado."""
    
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=['Autenticación'],
        summary='Cambiar contraseña',
        description='''
        Permite a un usuario autenticado cambiar su contraseña.
        
        Requiere la contraseña actual para verificar la identidad del usuario.
        ''',
        request={
            'application/json': {
                'type': 'object',
                'properties': {
                    'current_password': {
                        'type': 'string',
                        'description': 'Contraseña actual del usuario'
                    },
                    'new_password': {
                        'type': 'string',
                        'minLength': 8,
                        'description': 'Nueva contraseña (mínimo 8 caracteres)'
                    },
                    'confirm_password': {
                        'type': 'string',
                        'description': 'Confirmación de la nueva contraseña'
                    }
                },
                'required': ['current_password', 'new_password', 'confirm_password']
            }
        },
        responses={
            200: OpenApiTypes.OBJECT,
            400: OpenApiTypes.OBJECT,
            401: OpenApiTypes.OBJECT,
        },
        examples=[
            OpenApiExample(
                'Cambio exitoso',
                value={
                    'message': 'Contraseña actualizada exitosamente.',
                    'detail': 'Tu contraseña ha sido cambiada. Por seguridad, te recomendamos cerrar sesión en todos tus dispositivos.'
                },
                response_only=True,
                status_codes=['200'],
            ),
            OpenApiExample(
                'Contraseña actual incorrecta',
                value={
                    'current_password': ['La contraseña actual es incorrecta.']
                },
                response_only=True,
                status_codes=['400'],
            ),
            OpenApiExample(
                'Contraseñas no coinciden',
                value={
                    'confirm_password': ['Las contraseñas no coinciden.']
                },
                response_only=True,
                status_codes=['400'],
            ),
        ],
    )
    def post(self, request):
        """
        Cambia la contraseña del usuario autenticado.

        Request body:
            {
                "current_password": "contraseña_actual",
                "new_password": "nueva_contraseña",
                "confirm_password": "nueva_contraseña"
            }

        Response (200 OK):
            {
                "message": "Contraseña actualizada exitosamente.",
                "detail": "Tu contraseña ha sido cambiada. Por seguridad, te recomendamos cerrar sesión en todos tus dispositivos."
            }

        Response (400 Bad Request):
            {
                "current_password": ["La contraseña actual es incorrecta."]
            }
        """
        from .serializers import ChangePasswordSerializer
        
        serializer = ChangePasswordSerializer(data=request.data, context={'request': request})
        
        if not serializer.is_valid():
            # Retornar errores de validación de forma más clara
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        result = serializer.save()

        return Response(result, status=status.HTTP_200_OK)
