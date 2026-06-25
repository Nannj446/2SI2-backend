from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from .views import (
    ChangePasswordAPIView,
    EmailTwoFactorEnableAPIView,
    EmailTwoFactorResendAPIView,
    LoginAPIView,
    LogoutAPIView,
    PasswordResetConfirmAPIView,
    PasswordResetRequestAPIView,
    PasswordResetValidateAPIView,
    PasswordResetVerifyCodeAPIView,  # Nueva vista
    TwoFactorDisableAPIView,
    TwoFactorEnableAPIView,
    TwoFactorGetMethodAPIView,
    TwoFactorLoginVerifyAPIView,
    TwoFactorRegenerateBackupCodesAPIView,
    TwoFactorSetMethodAPIView,
    TwoFactorStatusAPIView,
    TwoFactorVerifyAPIView,
)
from .profile_views import ProfileAPIView, ProfileUpdateAPIView

urlpatterns = [
    # ============================================================
    # LOGIN
    # ============================================================
    path('auth/login/', LoginAPIView.as_view(), name='auth-login'),
    path('auth/login/2fa/', TwoFactorLoginVerifyAPIView.as_view(), name='auth-login-2fa'),
    
    # ============================================================
    # LOGOUT
    # ============================================================
    path('auth/logout/', LogoutAPIView.as_view(), name='auth-logout'),
    
    # ============================================================
    # REFRESH TOKEN
    # ============================================================
    path('auth/token/refresh/', TokenRefreshView.as_view(), name='token-refresh'),
    
    # ============================================================
    # PASSWORD RESET
    # ============================================================
    path('auth/password-reset/request/', PasswordResetRequestAPIView.as_view(), name='password-reset-request'),
    path('auth/password-reset/validate/', PasswordResetValidateAPIView.as_view(), name='password-reset-validate'),
    path('auth/password-reset/confirm/', PasswordResetConfirmAPIView.as_view(), name='password-reset-confirm'),
    
    # ============================================================
    # MOBILE PASSWORD RESET
    # ============================================================
    path('auth/password-reset/verify-code/', PasswordResetVerifyCodeAPIView.as_view(), name='password-reset-verify-code'),
    
    # ============================================================
    # TWO-FACTOR AUTHENTICATION (2FA)
    # ============================================================
    path('auth/2fa/enable/', TwoFactorEnableAPIView.as_view(), name='2fa-enable'),
    path('auth/2fa/verify/', TwoFactorVerifyAPIView.as_view(), name='2fa-verify'),
    path('auth/2fa/disable/', TwoFactorDisableAPIView.as_view(), name='2fa-disable'),
    path('auth/2fa/status/', TwoFactorStatusAPIView.as_view(), name='2fa-status'),
    path('auth/2fa/backup-codes/regenerate/', TwoFactorRegenerateBackupCodesAPIView.as_view(), name='2fa-regenerate-backup-codes'),
    
    # ============================================================
    # EMAIL TWO-FACTOR AUTHENTICATION
    # ============================================================
    path('auth/2fa/email/enable/', EmailTwoFactorEnableAPIView.as_view(), name='2fa-email-enable'),
    path('auth/2fa/email/resend/', EmailTwoFactorResendAPIView.as_view(), name='2fa-email-resend'),
    path('auth/2fa/method/set/', TwoFactorSetMethodAPIView.as_view(), name='2fa-set-method'),
    path('auth/2fa/method/', TwoFactorGetMethodAPIView.as_view(), name='2fa-get-method'),
    
    # ============================================================
    # CHANGE PASSWORD
    # ============================================================
    path('auth/change-password/', ChangePasswordAPIView.as_view(), name='change-password'),
    
    # ============================================================
    # PROFILE
    # ============================================================
    path('auth/profile/', ProfileAPIView.as_view(), name='profile'),
    path('auth/profile/update/', ProfileUpdateAPIView.as_view(), name='profile-update'),
]
