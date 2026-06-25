"""
Servicios para autenticación de dos factores (2FA).
"""
import base64
import io
from dataclasses import dataclass
from typing import Optional

from django.contrib.auth import get_user_model
from rest_framework import serializers

from api.models import TwoFactorAuth


@dataclass(frozen=True)
class TwoFactorEnableInput:
    """Input para habilitar 2FA."""
    user: object


@dataclass(frozen=True)
class TwoFactorEnableResult:
    """Resultado de habilitar 2FA."""
    secret: str
    qr_code_base64: str
    provisioning_uri: str  # URL otpauth para móvil
    backup_codes: list[str]


class TwoFactorEnableService:
    """Servicio para habilitar 2FA."""

    def execute(self, payload: TwoFactorEnableInput) -> TwoFactorEnableResult:
        """
        Inicia el proceso de habilitación de 2FA.

        Genera secret key, QR code y códigos de respaldo.
        El 2FA no se activa hasta que el usuario verifique el código.

        Args:
            payload: TwoFactorEnableInput con usuario

        Returns:
            TwoFactorEnableResult con secret, QR y códigos
        """
        user = payload.user

        # Crear o actualizar configuración 2FA
        two_factor, created = TwoFactorAuth.objects.get_or_create(
            user=user,
            defaults={'secret_key': '', 'method': 'totp'}
        )

        # Guardar estado previo de habilitación
        was_enabled = two_factor.is_enabled
        previous_enabled_at = two_factor.enabled_at

        # Si ya existía, asegurar que el método sea TOTP
        if not created and two_factor.method != 'totp':
            two_factor.method = 'totp'

        # Generar nueva secret key
        secret = two_factor.generate_secret()

        # Generar códigos de respaldo
        backup_codes = two_factor.generate_backup_codes(count=10)

        # Si ya estaba habilitado, mantenerlo habilitado (cambio de método)
        # Si no estaba habilitado, marcarlo como NO habilitado (primera vez)
        if not was_enabled:
            two_factor.is_enabled = False
            two_factor.enabled_at = None
        else:
            # Mantener el estado habilitado y la fecha
            two_factor.is_enabled = True
            two_factor.enabled_at = previous_enabled_at
        
        two_factor.save()

        # Generar QR code
        provisioning_uri = two_factor.get_provisioning_uri(
            user_email=user.email,
            issuer_name='Sistema Bancario'
        )

        qr_code_base64 = self._generate_qr_code(provisioning_uri)

        return TwoFactorEnableResult(
            secret=secret,
            qr_code_base64=qr_code_base64,
            provisioning_uri=provisioning_uri,  # Agregar URL otpauth
            backup_codes=backup_codes,
        )

    def _generate_qr_code(self, data: str) -> str:
        """
        Genera un QR code y lo convierte a base64.

        Args:
            data: Datos a codificar en el QR

        Returns:
            str: QR code en formato base64
        """
        import qrcode

        # Crear QR code
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(data)
        qr.make(fit=True)

        # Generar imagen
        img = qr.make_image(fill_color="black", back_color="white")

        # Convertir a base64
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        img_base64 = base64.b64encode(buffer.getvalue()).decode()

        return img_base64


@dataclass(frozen=True)
class TwoFactorVerifyInput:
    """Input para verificar 2FA inicial."""
    user: object
    token: str


@dataclass(frozen=True)
class TwoFactorVerifyResult:
    """Resultado de verificar 2FA."""
    success: bool
    message: str


class TwoFactorVerifyService:
    """Servicio para verificar y activar 2FA."""

    def execute(self, payload: TwoFactorVerifyInput) -> TwoFactorVerifyResult:
        """
        Verifica el código TOTP y activa 2FA.

        Args:
            payload: TwoFactorVerifyInput con usuario y token

        Returns:
            TwoFactorVerifyResult con resultado

        Raises:
            serializers.ValidationError: Si no hay configuración 2FA o el token es inválido
        """
        from django.utils import timezone

        user = payload.user

        # Obtener configuración 2FA
        try:
            two_factor = TwoFactorAuth.objects.get(user=user)
        except TwoFactorAuth.DoesNotExist:
            raise serializers.ValidationError(
                {'detail': 'No se ha iniciado la configuración de 2FA.'},
                code='2fa_not_configured'
            )

        # Verificar token
        if not two_factor.verify_token(payload.token):
            raise serializers.ValidationError(
                {'detail': 'Código inválido. Verifica e intenta nuevamente.'},
                code='invalid_token'
            )

        # Activar 2FA con método TOTP
        two_factor.is_enabled = True
        two_factor.enabled_at = timezone.now()
        two_factor.method = 'totp'
        two_factor.save(update_fields=['is_enabled', 'enabled_at', 'method'])

        return TwoFactorVerifyResult(
            success=True,
            message='Autenticación de dos factores activada exitosamente.'
        )


@dataclass(frozen=True)
class TwoFactorDisableInput:
    """Input para deshabilitar 2FA."""
    user: object
    password: str


@dataclass(frozen=True)
class TwoFactorDisableResult:
    """Resultado de deshabilitar 2FA."""
    success: bool
    message: str


class TwoFactorDisableService:
    """Servicio para deshabilitar 2FA."""

    def execute(self, payload: TwoFactorDisableInput) -> TwoFactorDisableResult:
        """
        Deshabilita 2FA después de verificar la contraseña.

        Args:
            payload: TwoFactorDisableInput con usuario y contraseña

        Returns:
            TwoFactorDisableResult con resultado

        Raises:
            serializers.ValidationError: Si la contraseña es incorrecta o no hay 2FA
        """
        from django.contrib.auth import authenticate

        user = payload.user

        # Verificar contraseña
        authenticated_user = authenticate(
            username=user.username,
            password=payload.password
        )

        if authenticated_user is None:
            raise serializers.ValidationError(
                {'detail': 'Contraseña incorrecta.'},
                code='invalid_password'
            )

        # Obtener configuración 2FA
        try:
            two_factor = TwoFactorAuth.objects.get(user=user)
        except TwoFactorAuth.DoesNotExist:
            raise serializers.ValidationError(
                {'detail': '2FA no está habilitado.'},
                code='2fa_not_enabled'
            )

        # Deshabilitar 2FA
        two_factor.is_enabled = False
        two_factor.enabled_at = None
        two_factor.backup_codes = []
        two_factor.save(update_fields=['is_enabled', 'enabled_at', 'backup_codes'])

        # Enviar email de notificación
        from api.utils.email_service import EmailInput, EmailService

        email_service = EmailService()
        email_input = EmailInput(
            to_email=user.email,
            subject='Autenticación de dos factores deshabilitada',
            template_name='emails/2fa_disabled.html',
            context={
                'user_name': user.first_name or user.email,
            }
        )
        # No fallar si el email no se envía
        try:
            email_service.execute(email_input)
        except Exception:
            pass

        return TwoFactorDisableResult(
            success=True,
            message='Autenticación de dos factores deshabilitada exitosamente.'
        )


@dataclass(frozen=True)
class TwoFactorLoginInput:
    """Input para login con 2FA."""
    user: object
    token: str
    is_backup_code: bool = False


@dataclass(frozen=True)
class TwoFactorLoginResult:
    """Resultado de login con 2FA."""
    success: bool
    message: str


class TwoFactorLoginService:
    """Servicio para verificar código 2FA en login."""

    def execute(self, payload: TwoFactorLoginInput) -> TwoFactorLoginResult:
        """
        Verifica el código 2FA durante el login.

        Args:
            payload: TwoFactorLoginInput con usuario y token

        Returns:
            TwoFactorLoginResult con resultado

        Raises:
            serializers.ValidationError: Si el código es inválido
        """
        from django.utils import timezone

        user = payload.user

        # Obtener configuración 2FA
        try:
            two_factor = TwoFactorAuth.objects.get(user=user, is_enabled=True)
        except TwoFactorAuth.DoesNotExist:
            raise serializers.ValidationError(
                {'detail': '2FA no está habilitado para este usuario.'},
                code='2fa_not_enabled'
            )

        # Verificar código
        if payload.is_backup_code:
            # Verificar código de respaldo
            if not two_factor.verify_backup_code(payload.token):
                raise serializers.ValidationError(
                    {'detail': 'Código de respaldo inválido.'},
                    code='invalid_backup_code'
                )
        else:
            # Verificar código TOTP
            if not two_factor.verify_token(payload.token):
                raise serializers.ValidationError(
                    {'detail': 'Código inválido. Verifica e intenta nuevamente.'},
                    code='invalid_token'
                )

        # Actualizar último uso
        two_factor.last_used_at = timezone.now()
        two_factor.save(update_fields=['last_used_at'])

        return TwoFactorLoginResult(
            success=True,
            message='Código verificado exitosamente.'
        )



@dataclass(frozen=True)
class TwoFactorRegenerateBackupCodesInput:
    """Input para regenerar códigos de respaldo."""
    user: object
    password: str


@dataclass(frozen=True)
class TwoFactorRegenerateBackupCodesResult:
    """Resultado de regenerar códigos de respaldo."""
    backup_codes: list[str]
    message: str


class TwoFactorRegenerateBackupCodesService:
    """Servicio para regenerar códigos de respaldo."""

    def execute(self, payload: TwoFactorRegenerateBackupCodesInput) -> TwoFactorRegenerateBackupCodesResult:
        """
        Regenera los códigos de respaldo después de verificar la contraseña.

        Args:
            payload: TwoFactorRegenerateBackupCodesInput con usuario y contraseña

        Returns:
            TwoFactorRegenerateBackupCodesResult con nuevos códigos

        Raises:
            serializers.ValidationError: Si la contraseña es incorrecta o 2FA no está habilitado
        """
        from django.contrib.auth import authenticate

        user = payload.user

        # Verificar contraseña
        authenticated_user = authenticate(
            username=user.username,
            password=payload.password
        )

        if authenticated_user is None:
            raise serializers.ValidationError(
                {'detail': 'Contraseña incorrecta.'},
                code='invalid_password'
            )

        # Obtener configuración 2FA
        try:
            two_factor = TwoFactorAuth.objects.get(user=user, is_enabled=True)
        except TwoFactorAuth.DoesNotExist:
            raise serializers.ValidationError(
                {'detail': '2FA no está habilitado.'},
                code='2fa_not_enabled'
            )

        # Generar nuevos códigos de respaldo
        backup_codes = two_factor.generate_backup_codes(count=10)
        two_factor.save(update_fields=['backup_codes'])

        # Enviar email de notificación
        from api.utils.email_service import EmailInput, EmailService

        email_service = EmailService()
        email_input = EmailInput(
            to_email=user.email,
            subject='Códigos de respaldo regenerados',
            template_name='emails/backup_codes_regenerated.html',
            context={
                'user_name': user.first_name or user.email,
                'backup_codes': backup_codes,
            }
        )
        # No fallar si el email no se envía
        try:
            email_service.execute(email_input)
        except Exception:
            pass

        return TwoFactorRegenerateBackupCodesResult(
            backup_codes=backup_codes,
            message='Códigos de respaldo regenerados exitosamente.'
        )
