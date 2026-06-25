"""
Archivo de compatibilidad para imports de servicios.

Los servicios han sido movidos a sus módulos correspondientes:
- Servicios de autenticación: api.authentication.*
- Servicios de usuarios: api.users.services
- Servicios de roles: api.roles.services
- Servicios de auditoría: api.audit.services
- Servicios de registro: api.registration.services

Este archivo mantiene la compatibilidad con código existente.
Para código nuevo, importar directamente desde los módulos específicos.
"""

# ============================================================
# SERVICIOS DE AUTENTICACIÓN
# ============================================================
from api.authentication.services import (
    # Login principal
    LoginService,
    LoginInput,
    LoginResult,
    TwoFactorLoginService,
    TwoFactorLoginInput,
    TwoFactorLoginResult,
)

from api.authentication.email_two_factor_service import (
    # 2FA por email
    EmailTwoFactorSendService,
    EmailTwoFactorSendInput,
    EmailTwoFactorSendResult,
    EmailTwoFactorVerifyService,
    EmailTwoFactorVerifyInput,
    EmailTwoFactorVerifyResult,
    EmailTwoFactorResendService,
    EmailTwoFactorResendInput,
    EmailTwoFactorResendResult,
)

from api.authentication.password_reset_service import (
    # Recuperación de contraseña
    PasswordResetRequestService,
    PasswordResetRequestInput,
    PasswordResetRequestResult,
    PasswordResetValidateService,
    PasswordResetValidateInput,
    PasswordResetValidateResult,
    PasswordResetConfirmService,
    PasswordResetConfirmInput,
    PasswordResetConfirmResult,
)

from api.authentication.two_factor_service import (
    # 2FA TOTP
    TwoFactorEnableService,
    TwoFactorEnableInput,
    TwoFactorEnableResult,
    TwoFactorVerifyService,
    TwoFactorVerifyInput,
    TwoFactorVerifyResult,
    TwoFactorDisableService,
    TwoFactorDisableInput,
    TwoFactorDisableResult,
    TwoFactorLoginService as TwoFactorAuthService,
    TwoFactorLoginInput as TwoFactorAuthInput,
    TwoFactorLoginResult as TwoFactorAuthResult,
    TwoFactorRegenerateBackupCodesService,
    TwoFactorRegenerateBackupCodesInput,
    TwoFactorRegenerateBackupCodesResult,
)

# ============================================================
# SERVICIOS DE OTROS MÓDULOS
# ============================================================
# Servicios de usuarios
from api.users.services import (
    UserManagementService,
    CreateUserInput,
    UpdateUserInput,
)

# Servicios de roles y permisos
from api.roles.services import (
    PermissionService,
)

# Servicios de registro
from api.registration.services import (
    RegisterUserService,
    RegisterUserInput,
    RegisterUserResult,
)

# ============================================================
# EXPORTAR TODOS LOS SERVICIOS
# ============================================================
__all__ = [
    # Login principal
    'LoginService',
    'LoginInput',
    'LoginResult',
    'TwoFactorLoginService',
    'TwoFactorLoginInput',
    'TwoFactorLoginResult',
    
    # 2FA por email
    'EmailTwoFactorSendService',
    'EmailTwoFactorSendInput',
    'EmailTwoFactorSendResult',
    'EmailTwoFactorVerifyService',
    'EmailTwoFactorVerifyInput',
    'EmailTwoFactorVerifyResult',
    'EmailTwoFactorResendService',
    'EmailTwoFactorResendInput',
    'EmailTwoFactorResendResult',
    
    # Recuperación de contraseña
    'PasswordResetRequestService',
    'PasswordResetRequestInput',
    'PasswordResetRequestResult',
    'PasswordResetValidateService',
    'PasswordResetValidateInput',
    'PasswordResetValidateResult',
    'PasswordResetConfirmService',
    'PasswordResetConfirmInput',
    'PasswordResetConfirmResult',
    
    # 2FA TOTP
    'TwoFactorEnableService',
    'TwoFactorEnableInput',
    'TwoFactorEnableResult',
    'TwoFactorVerifyService',
    'TwoFactorVerifyInput',
    'TwoFactorVerifyResult',
    'TwoFactorDisableService',
    'TwoFactorDisableInput',
    'TwoFactorDisableResult',
    'TwoFactorAuthService',
    'TwoFactorAuthInput',
    'TwoFactorAuthResult',
    'TwoFactorRegenerateBackupCodesService',
    'TwoFactorRegenerateBackupCodesInput',
    'TwoFactorRegenerateBackupCodesResult',
    
    # Servicios de usuarios
    'UserManagementService',
    'CreateUserInput',
    'UpdateUserInput',
    
    # Servicios de roles y permisos
    'PermissionService',
    
    # Servicios de registro
    'RegisterUserService',
    'RegisterUserInput',
    'RegisterUserResult',
]