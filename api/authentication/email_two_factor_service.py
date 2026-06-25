"""
Servicios para autenticación de dos factores por email.
"""
import hashlib
import secrets
from dataclasses import dataclass
from datetime import timedelta
from typing import Optional

from django.utils import timezone
from rest_framework import serializers

from api.models import EmailTwoFactorCode


@dataclass(frozen=True)
class EmailTwoFactorSendInput:
    """Input para enviar código 2FA por email."""
    user: object
    challenge_token: str
    purpose: str = 'login'
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None


@dataclass(frozen=True)
class EmailTwoFactorSendResult:
    """Resultado de envío de código 2FA."""
    challenge_token: str
    expires_in_minutes: int
    message: str


class EmailTwoFactorSendService:
    """Servicio para generar y enviar código 2FA por email."""
    
    CODE_LENGTH = 6
    EXPIRATION_MINUTES = 5
    MAX_ATTEMPTS = 3
    
    def execute(self, payload: EmailTwoFactorSendInput) -> EmailTwoFactorSendResult:
        """
        Genera un código OTP, lo hashea, lo guarda y lo envía por email.
        
        Args:
            payload: EmailTwoFactorSendInput con datos del usuario
            
        Returns:
            EmailTwoFactorSendResult con challenge token y tiempo de expiración
            
        Raises:
            serializers.ValidationError: Si hay error al enviar el email
        """
        # 1. Invalidar códigos anteriores no usados del mismo usuario
        EmailTwoFactorCode.objects.filter(
            user=payload.user,
            is_used=False,
            purpose=payload.purpose
        ).update(is_used=True)
        
        # 2. Generar código de 6 dígitos
        code = ''.join(secrets.choice('0123456789') for _ in range(self.CODE_LENGTH))
        
        # 3. Hashear código con SHA256
        code_hash = hashlib.sha256(code.encode()).hexdigest()
        
        # 4. Calcular expiración
        expires_at = timezone.now() + timedelta(minutes=self.EXPIRATION_MINUTES)
        
        # 5. Guardar en BD
        email_code = EmailTwoFactorCode.objects.create(
            user=payload.user,
            code_hash=code_hash,
            purpose=payload.purpose,
            expires_at=expires_at,
            challenge_token=payload.challenge_token,
            ip_address=payload.ip_address,
            user_agent=payload.user_agent or '',
            max_attempts=self.MAX_ATTEMPTS,
        )
        
        # 6. Enviar email
        from api.utils.email_service import EmailInput, EmailService
        
        email_service = EmailService()
        email_input = EmailInput(
            to_email=payload.user.email,
            subject='Código de verificación - Sistema Bancario',
            template_name='emails/2fa_code.html',
            context={
                'user_name': payload.user.first_name or payload.user.email,
                'code': code,
                'expires_in': self.EXPIRATION_MINUTES,
            }
        )
        
        try:
            email_result = email_service.execute(email_input)

            if not email_result.success:
                raise serializers.ValidationError(
                    {'detail': 'Error al enviar el código por email. Intenta nuevamente.'},
                    code='email_send_failed'
                )
        except Exception as e:
            # Si falla el envío, marcar código como usado para que no quede activo
            email_code.is_used = True
            email_code.save(update_fields=['is_used'])
            raise serializers.ValidationError(
                {'detail': 'Error al enviar el código por email. Intenta nuevamente.'},
                code='email_send_failed'
            )
        
        return EmailTwoFactorSendResult(
            challenge_token=payload.challenge_token,
            expires_in_minutes=self.EXPIRATION_MINUTES,
            message=f'Código enviado a {payload.user.email}'
        )


@dataclass(frozen=True)
class EmailTwoFactorVerifyInput:
    """Input para verificar código 2FA por email."""
    challenge_token: str
    code: str


@dataclass(frozen=True)
class EmailTwoFactorVerifyResult:
    """Resultado de verificación de código 2FA."""
    success: bool
    user: object
    message: str


class EmailTwoFactorVerifyService:
    """Servicio para verificar código 2FA por email."""
    
    def execute(self, payload: EmailTwoFactorVerifyInput) -> EmailTwoFactorVerifyResult:
        """
        Verifica un código OTP enviado por email.
        
        Args:
            payload: EmailTwoFactorVerifyInput con challenge token y código
            
        Returns:
            EmailTwoFactorVerifyResult con resultado de la verificación
            
        Raises:
            serializers.ValidationError: Si el código es inválido o expiró
        """
        # 1. Buscar código por challenge_token
        try:
            email_code = EmailTwoFactorCode.objects.select_related('user').get(
                challenge_token=payload.challenge_token,
                is_used=False
            )
        except EmailTwoFactorCode.DoesNotExist:
            raise serializers.ValidationError(
                {'detail': 'Código inválido o ya usado.'},
                code='invalid_code'
            )
        
        # 2. Verificar expiración
        if timezone.now() > email_code.expires_at:
            raise serializers.ValidationError(
                {'detail': 'Código expirado. Solicita uno nuevo.'},
                code='code_expired'
            )
        
        # 3. Verificar intentos
        if email_code.attempts >= email_code.max_attempts:
            raise serializers.ValidationError(
                {'detail': 'Demasiados intentos. Solicita un nuevo código.'},
                code='too_many_attempts'
            )
        
        # 4. Incrementar intentos
        email_code.attempts += 1
        email_code.save(update_fields=['attempts'])
        
        # 5. Verificar código (comparar hashes)
        code_hash = hashlib.sha256(payload.code.encode()).hexdigest()
        
        if code_hash != email_code.code_hash:
            remaining_attempts = email_code.max_attempts - email_code.attempts
            raise serializers.ValidationError(
                {'detail': f'Código incorrecto. Te quedan {remaining_attempts} intento(s).'},
                code='incorrect_code'
            )
        
        # 6. Marcar como usado
        email_code.mark_as_used()
        
        return EmailTwoFactorVerifyResult(
            success=True,
            user=email_code.user,
            message='Código verificado exitosamente.'
        )


@dataclass(frozen=True)
class EmailTwoFactorResendInput:
    """Input para reenviar código 2FA por email."""
    challenge_token: str
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None


@dataclass(frozen=True)
class EmailTwoFactorResendResult:
    """Resultado de reenvío de código 2FA."""
    challenge_token: str
    expires_in_minutes: int
    message: str


class EmailTwoFactorResendService:
    """Servicio para reenviar código 2FA por email."""
    
    EXPIRATION_MINUTES = 5  # Mismo tiempo que EmailTwoFactorSendService
    
    def execute(self, payload: EmailTwoFactorResendInput) -> EmailTwoFactorResendResult:
        """
        Reenvía un código OTP por email.
        
        Args:
            payload: EmailTwoFactorResendInput con challenge token
            
        Returns:
            EmailTwoFactorResendResult con nuevo challenge token
            
        Raises:
            serializers.ValidationError: Si el challenge token es inválido
        """
        from api.models import AuthChallenge
        from django.utils import timezone
        
        # 1. Buscar código anterior por challenge_token
        try:
            old_code = EmailTwoFactorCode.objects.select_related('user').get(
                challenge_token=payload.challenge_token,
                is_used=False
            )
        except EmailTwoFactorCode.DoesNotExist:
            raise serializers.ValidationError(
                {'detail': 'Token de autenticación inválido.'},
                code='invalid_challenge'
            )
        
        # 2. Buscar y actualizar AuthChallenge asociado
        try:
            auth_challenge = AuthChallenge.objects.get(
                challenge_token=payload.challenge_token,
                is_used=False,
                purpose='2fa_login'
            )
        except AuthChallenge.DoesNotExist:
            # Si no existe AuthChallenge, solo invalidar el código anterior
            old_code.is_used = True
            old_code.save(update_fields=['is_used'])
            raise serializers.ValidationError(
                {'detail': 'Token de autenticación inválido.'},
                code='invalid_challenge'
            )
        
        # 3. Invalidar código anterior
        old_code.is_used = True
        old_code.save(update_fields=['is_used'])
        
        # 4. Generar nuevo challenge token único
        new_challenge_token = secrets.token_urlsafe(32)
        
        # 5. Actualizar AuthChallenge con el nuevo token y extender expiración
        auth_challenge.challenge_token = new_challenge_token
        auth_challenge.expires_at = timezone.now() + timedelta(minutes=self.EXPIRATION_MINUTES)
        auth_challenge.save(update_fields=['challenge_token', 'expires_at'])
        
        # 6. Generar nuevo código usando el servicio de envío
        send_service = EmailTwoFactorSendService()
        send_result = send_service.execute(
            EmailTwoFactorSendInput(
                user=old_code.user,
                challenge_token=new_challenge_token,  # Nuevo token único
                purpose=old_code.purpose,
                ip_address=payload.ip_address,
                user_agent=payload.user_agent or '',
            )
        )
        
        return EmailTwoFactorResendResult(
            challenge_token=send_result.challenge_token,
            expires_in_minutes=send_result.expires_in_minutes,
            message='Código reenviado exitosamente.'
        )
