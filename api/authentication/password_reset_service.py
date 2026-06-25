"""
Servicios para recuperación de contraseña.
"""
import secrets
from dataclasses import dataclass
from typing import Optional

from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import serializers

from api.models import PasswordResetToken
from api.utils.email_service import EmailInput, EmailService


@dataclass(frozen=True)
class PasswordResetRequestInput:
    """Input para solicitud de recuperación de contraseña."""
    email: str
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    platform: Optional[str] = None  # 'web' o 'mobile'


@dataclass(frozen=True)
class PasswordResetRequestResult:
    """Resultado de solicitud de recuperación."""
    success: bool
    message: str


class PasswordResetRequestService:
    """Servicio para solicitar recuperación de contraseña."""

    def execute(self, payload: PasswordResetRequestInput) -> PasswordResetRequestResult:
        """
        Procesa una solicitud de recuperación de contraseña.

        Por seguridad, siempre retorna success=True incluso si el email no existe.
        Esto previene la enumeración de usuarios.

        Args:
            payload: PasswordResetRequestInput con email

        Returns:
            PasswordResetRequestResult con resultado
        """
        User = get_user_model()
        email = payload.email.strip().lower()

        # Buscar usuario por email (case-insensitive)
        try:
            user = User.objects.get(email__iexact=email)
        except User.DoesNotExist:
            # Por seguridad, retornar success=True aunque el usuario no exista
            return PasswordResetRequestResult(
                success=True,
                message='Si el correo existe, recibirás instrucciones para recuperar tu contraseña.'
            )

        # Verificar que el usuario esté activo
        if not user.is_active:
            # Por seguridad, retornar el mismo mensaje
            return PasswordResetRequestResult(
                success=True,
                message='Si el correo existe, recibirás instrucciones para recuperar tu contraseña.'
            )

        # Calcular fecha de expiración (1 hora)
        expires_at = timezone.now() + timezone.timedelta(hours=1)

        # Limpiar tokens anteriores del usuario para evitar duplicados
        PasswordResetToken.objects.filter(
            user=user, 
            is_used=False,
            expires_at__lt=timezone.now()  # Solo eliminar expirados
        ).delete()
        
        # Eliminar tokens no usados del mismo usuario (máximo 1 activo)
        PasswordResetToken.objects.filter(user=user, is_used=False).delete()

        # Determinar si el usuario es cliente (para móvil) o usuario del sistema (para web)
        from api.users.models import UserProfile
        
        is_client = False
        try:
            profile = UserProfile.objects.get(user=user)
            is_client = profile.user_type == 'client'
        except UserProfile.DoesNotExist:
            pass
        
        # Determinar plataforma: móvil si es cliente o si se especifica explícitamente
        is_mobile_request = payload.platform == 'mobile' or is_client
        
        if is_mobile_request:
            # FLUJO MÓVIL: Generar código de 6 dígitos único
            import random
            max_attempts = 5
            for attempt in range(max_attempts):
                verification_code = f"{random.randint(100000, 999999)}"
                try:
                    # Crear token con código de 6 dígitos
                    reset_token = PasswordResetToken.objects.create(
                        user=user,
                        token=verification_code,  # Código de 6 dígitos
                        expires_at=expires_at,
                        ip_address=payload.ip_address,
                        user_agent=payload.user_agent,
                    )
                    break  # Éxito, salir del bucle
                except Exception as e:
                    if attempt == max_attempts - 1:  # Último intento
                        raise serializers.ValidationError(
                            {'detail': 'Error al generar código de verificación. Intenta nuevamente.'},
                            code='token_generation_failed'
                        )
                    continue  # Intentar con otro código
            
            # Enviar email con código
            email_service = EmailService()
            email_input = EmailInput(
                to_email=user.email,
                subject='Código de verificación - Recuperación de contraseña',
                template_name='emails/password_reset_mobile.html',
                context={
                    'user_name': user.first_name or user.email,
                    'verification_code': verification_code,
                    'expires_in_minutes': 60,
                }
            )
        else:
            # FLUJO WEB: Generar token único
            max_attempts = 5
            for attempt in range(max_attempts):
                token = secrets.token_urlsafe(32)
                try:
                    # Crear registro de token
                    reset_token = PasswordResetToken.objects.create(
                        user=user,
                        token=token,
                        expires_at=expires_at,
                        ip_address=payload.ip_address,
                        user_agent=payload.user_agent,
                    )
                    break  # Éxito, salir del bucle
                except Exception as e:
                    if attempt == max_attempts - 1:  # Último intento
                        raise serializers.ValidationError(
                            {'detail': 'Error al generar token de recuperación. Intenta nuevamente.'},
                            code='token_generation_failed'
                        )
                    continue  # Intentar con otro token
            
            # Construir link de recuperación
            reset_link = f'{settings.FRONTEND_URL}/reset-password?token={token}'
            
            # Enviar email con enlace
            email_service = EmailService()
            email_input = EmailInput(
                to_email=user.email,
                subject='Recuperación de contraseña',
                template_name='emails/password_reset.html',
                context={
                    'user_name': user.first_name or user.email,
                    'reset_link': reset_link,
                    'expires_in_minutes': 60,
                }
            )

        email_result = email_service.execute(email_input)

        if not email_result.success:
            # Si falla el envío de email, eliminar el token
            reset_token.delete()
            raise serializers.ValidationError(
                {'detail': 'Error al enviar el correo. Intenta nuevamente.'},
                code='email_send_failed'
            )

        return PasswordResetRequestResult(
            success=True,
            message='Si el correo existe, recibirás instrucciones para recuperar tu contraseña.'
        )


@dataclass(frozen=True)
class PasswordResetValidateInput:
    """Input para validar token de recuperación."""
    token: str


@dataclass(frozen=True)
class PasswordResetValidateResult:
    """Resultado de validación de token."""
    valid: bool
    message: str


class PasswordResetValidateService:
    """Servicio para validar token de recuperación."""

    def execute(self, payload: PasswordResetValidateInput) -> PasswordResetValidateResult:
        """
        Valida un token de recuperación de contraseña.

        Args:
            payload: PasswordResetValidateInput con token

        Returns:
            PasswordResetValidateResult con resultado
        """
        token = payload.token.strip()

        try:
            reset_token = PasswordResetToken.objects.get(token=token)
        except PasswordResetToken.DoesNotExist:
            return PasswordResetValidateResult(
                valid=False,
                message='Token inválido o expirado.'
            )

        if not reset_token.is_valid():
            return PasswordResetValidateResult(
                valid=False,
                message='Token inválido o expirado.'
            )

        return PasswordResetValidateResult(
            valid=True,
            message='Token válido.'
        )


@dataclass(frozen=True)
class PasswordResetVerifyCodeInput:
    """Input para verificar código de recuperación móvil."""
    email: str
    code: str


@dataclass(frozen=True)
class PasswordResetVerifyCodeResult:
    """Resultado de verificación de código móvil."""
    valid: bool
    message: str
    reset_token: Optional[str] = None  # Token para usar en confirmación


class PasswordResetVerifyCodeService:
    """Servicio para verificar código de recuperación móvil."""

    def execute(self, payload: PasswordResetVerifyCodeInput) -> PasswordResetVerifyCodeResult:
        """
        Verifica un código de recuperación de contraseña para móvil.

        Args:
            payload: PasswordResetVerifyCodeInput con email y código

        Returns:
            PasswordResetVerifyCodeResult con resultado
        """
        User = get_user_model()
        email = payload.email.strip().lower()
        code = payload.code.strip()

        # Buscar usuario por email
        try:
            user = User.objects.get(email__iexact=email, is_active=True)
        except User.DoesNotExist:
            return PasswordResetVerifyCodeResult(
                valid=False,
                message='Código inválido o expirado.'
            )

        # Buscar token con el código
        try:
            reset_token = PasswordResetToken.objects.get(
                user=user,
                token=code,  # El código está en el campo token
                is_used=False
            )
        except PasswordResetToken.DoesNotExist:
            return PasswordResetVerifyCodeResult(
                valid=False,
                message='Código inválido o expirado.'
            )

        # Verificar que no haya expirado
        if not reset_token.is_valid():
            return PasswordResetVerifyCodeResult(
                valid=False,
                message='Código inválido o expirado.'
            )

        # Generar token temporal para la confirmación de contraseña
        import secrets
        temp_token = secrets.token_urlsafe(32)
        
        # Actualizar el registro con el nuevo token temporal
        reset_token.token = temp_token
        reset_token.save(update_fields=['token'])

        return PasswordResetVerifyCodeResult(
            valid=True,
            message='Código verificado correctamente.',
            reset_token=temp_token
        )


@dataclass(frozen=True)
class PasswordResetConfirmInput:
    """Input para confirmar nueva contraseña."""
    token: str
    new_password: str
    platform: Optional[str] = None  # 'web' o 'mobile'


@dataclass(frozen=True)
class PasswordResetConfirmResult:
    """Resultado de confirmación de nueva contraseña."""
    success: bool
    user: object


class PasswordResetConfirmService:
    """Servicio para confirmar nueva contraseña."""

    def execute(self, payload: PasswordResetConfirmInput) -> PasswordResetConfirmResult:
        """
        Confirma el cambio de contraseña.

        Args:
            payload: PasswordResetConfirmInput con token y nueva contraseña

        Returns:
            PasswordResetConfirmResult con resultado

        Raises:
            serializers.ValidationError: Si el token es inválido o la contraseña no cumple requisitos
        """
        from django.contrib.auth.password_validation import validate_password

        token = payload.token.strip()

        # Buscar token
        try:
            reset_token = PasswordResetToken.objects.select_related('user').get(token=token)
        except PasswordResetToken.DoesNotExist:
            raise serializers.ValidationError(
                {'detail': 'Token inválido o expirado.'},
                code='invalid_token'
            )

        # Validar token
        if not reset_token.is_valid():
            raise serializers.ValidationError(
                {'detail': 'Token inválido o expirado.'},
                code='invalid_token'
            )

        user = reset_token.user

        # Validar nueva contraseña con validadores de Django
        try:
            validate_password(payload.new_password, user=user)
        except Exception as e:
            raise serializers.ValidationError(
                {'new_password': list(e.messages)},
                code='invalid_password'
            )

        # Actualizar contraseña
        user.set_password(payload.new_password)
        user.save(update_fields=['password'])

        # Marcar token como usado
        reset_token.mark_as_used()

        # Enviar email de confirmación
        email_service = EmailService()
        email_input = EmailInput(
            to_email=user.email,
            subject='Contraseña actualizada',
            template_name='emails/password_changed.html',
            context={
                'user_name': user.first_name or user.email,
            }
        )
        email_service.execute(email_input)

        return PasswordResetConfirmResult(
            success=True,
            user=user
        )
