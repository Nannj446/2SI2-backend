"""
Modelos relacionados con autenticación y seguridad.
"""
from django.conf import settings
from django.db import models
from api.core.models import TimeStampedModel


class PasswordResetToken(TimeStampedModel):
	"""
	Modelo para almacenar tokens de recuperación de contraseña.
	
	Los tokens tienen una duración de 1 hora y solo pueden usarse una vez.
	"""
	user = models.ForeignKey(
		settings.AUTH_USER_MODEL,
		on_delete=models.CASCADE,
		related_name='password_reset_tokens',
	)
	token = models.CharField(max_length=64, unique=True, db_index=True)
	expires_at = models.DateTimeField()
	is_used = models.BooleanField(default=False)
	used_at = models.DateTimeField(null=True, blank=True)
	ip_address = models.GenericIPAddressField(null=True, blank=True)
	user_agent = models.TextField(blank=True)

	class Meta:
		db_table = 'password_reset_tokens'
		ordering = ['-created_at']
		indexes = [
			models.Index(fields=['token', 'is_used']),
			models.Index(fields=['user', 'is_used']),
			models.Index(fields=['expires_at']),
		]

	def __str__(self) -> str:
		return f'PasswordResetToken for {self.user.email} (used: {self.is_used})'

	def is_valid(self) -> bool:
		"""
		Verifica si el token es válido.
		
		Un token es válido si:
		- No ha sido usado
		- No ha expirado
		
		Returns:
			bool: True si el token es válido, False en caso contrario
		"""
		from django.utils import timezone
		
		if self.is_used:
			return False
		
		if timezone.now() > self.expires_at:
			return False
		
		return True

	def mark_as_used(self) -> None:
		"""
		Marca el token como usado.
		
		Actualiza is_used=True y used_at con la fecha/hora actual.
		"""
		from django.utils import timezone
		
		self.is_used = True
		self.used_at = timezone.now()
		self.save(update_fields=['is_used', 'used_at'])


class LoginAttempt(TimeStampedModel):
	"""
	Modelo para rastrear intentos de login (exitosos y fallidos).
	
	Se usa para implementar protección contra brute force attacks.
	"""
	user = models.ForeignKey(
		settings.AUTH_USER_MODEL,
		null=True,
		blank=True,
		on_delete=models.SET_NULL,
		related_name='login_attempts',
	)
	email_attempted = models.EmailField()
	ip_address = models.GenericIPAddressField()
	user_agent = models.TextField(blank=True)
	was_successful = models.BooleanField(default=False)
	failure_reason = models.CharField(max_length=50, blank=True)
	attempted_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		db_table = 'login_attempts'
		ordering = ['-attempted_at']
		indexes = [
			models.Index(fields=['email_attempted', 'attempted_at']),
			models.Index(fields=['ip_address', 'attempted_at']),
			models.Index(fields=['was_successful', 'attempted_at']),
		]

	def __str__(self) -> str:
		status = 'SUCCESS' if self.was_successful else 'FAILED'
		return f'{status}: {self.email_attempted} from {self.ip_address}'

	@staticmethod
	def get_recent_failures(email: str, minutes: int = 5) -> int:
		"""
		Obtiene el número de intentos fallidos recientes para un email.

		Args:
			email: Email del usuario
			minutes: Ventana de tiempo en minutos (default: 5)

		Returns:
			int: Número de intentos fallidos
		"""
		from django.utils import timezone

		time_threshold = timezone.now() - timezone.timedelta(minutes=minutes)
		
		return LoginAttempt.objects.filter(
			email_attempted__iexact=email,
			was_successful=False,
			attempted_at__gte=time_threshold,
		).count()

	@staticmethod
	def is_blocked(email: str, max_attempts: int = 5, window_minutes: int = 5) -> tuple[bool, int]:
		"""
		Verifica si un email está bloqueado por intentos fallidos.

		Args:
			email: Email del usuario
			max_attempts: Número máximo de intentos permitidos (default: 5)
			window_minutes: Ventana de tiempo en minutos (default: 5)

		Returns:
			tuple: (is_blocked: bool, remaining_minutes: int)
		"""
		from django.utils import timezone
		import math

		time_threshold = timezone.now() - timezone.timedelta(minutes=window_minutes)
		
		# Contar intentos fallidos en la ventana de tiempo
		failed_attempts = LoginAttempt.objects.filter(
			email_attempted__iexact=email,
			was_successful=False,
			attempted_at__gte=time_threshold,
		).count()

		if failed_attempts >= max_attempts:
			# Obtener el intento más antiguo en la ventana
			oldest_attempt = LoginAttempt.objects.filter(
				email_attempted__iexact=email,
				was_successful=False,
				attempted_at__gte=time_threshold,
			).order_by('attempted_at').first()

			if oldest_attempt:
				# Calcular minutos restantes hasta que expire el bloqueo
				unlock_time = oldest_attempt.attempted_at + timezone.timedelta(minutes=window_minutes)
				remaining = (unlock_time - timezone.now()).total_seconds() / 60
				remaining_minutes = max(1, math.ceil(remaining))  # Redondear hacia arriba
				return True, remaining_minutes

		return False, 0

	@staticmethod
	def clear_failed_attempts(email: str) -> None:
		"""
		Limpia los intentos fallidos de un email después de un login exitoso.

		Args:
			email: Email del usuario
		"""
		LoginAttempt.objects.filter(
			email_attempted__iexact=email,
			was_successful=False,
		).delete()


class AuthChallenge(TimeStampedModel):
	"""
	Modelo para almacenar tokens temporales de autenticación.
	
	Se usa para vincular el paso de login inicial con la verificación 2FA,
	evitando que el usuario tenga que enviar email+password dos veces.
	"""
	user = models.ForeignKey(
		settings.AUTH_USER_MODEL,
		on_delete=models.CASCADE,
		related_name='auth_challenges',
	)
	challenge_token = models.CharField(max_length=64, unique=True, db_index=True)
	purpose = models.CharField(max_length=20, default='2fa_login')
	expires_at = models.DateTimeField()
	is_used = models.BooleanField(default=False)
	used_at = models.DateTimeField(null=True, blank=True)
	ip_address = models.GenericIPAddressField(null=True, blank=True)
	user_agent = models.TextField(blank=True)
	# Datos adicionales para completar el login después de 2FA
	institution_id = models.IntegerField(null=True, blank=True)
	role = models.CharField(max_length=100, blank=True)

	class Meta:
		db_table = 'auth_challenges'
		ordering = ['-created_at']
		indexes = [
			models.Index(fields=['challenge_token', 'is_used']),
			models.Index(fields=['user', 'is_used', 'expires_at']),
		]

	def __str__(self) -> str:
		return f'AuthChallenge for {self.user.email} (used: {self.is_used})'

	def is_valid(self) -> bool:
		"""
		Verifica si el challenge token es válido.
		
		Un token es válido si:
		- No ha sido usado
		- No ha expirado
		
		Returns:
			bool: True si el token es válido
		"""
		from django.utils import timezone
		
		if self.is_used:
			return False
		
		if timezone.now() > self.expires_at:
			return False
		
		return True

	def mark_as_used(self) -> None:
		"""
		Marca el challenge token como usado.
		"""
		from django.utils import timezone
		
		self.is_used = True
		self.used_at = timezone.now()
		self.save(update_fields=['is_used', 'used_at'])


class EmailTwoFactorCode(TimeStampedModel):
	"""
	Modelo para almacenar códigos OTP enviados por email para 2FA.
	
	Los códigos tienen una duración de 5 minutos y máximo 3 intentos.
	"""
	user = models.ForeignKey(
		settings.AUTH_USER_MODEL,
		on_delete=models.CASCADE,
		related_name='email_2fa_codes',
	)
	code_hash = models.CharField(max_length=128)  # SHA256 hash del código
	purpose = models.CharField(max_length=20, default='login')
	expires_at = models.DateTimeField()
	attempts = models.IntegerField(default=0)
	max_attempts = models.IntegerField(default=3)
	is_used = models.BooleanField(default=False)
	used_at = models.DateTimeField(null=True, blank=True)
	challenge_token = models.CharField(max_length=64, unique=True, db_index=True)
	ip_address = models.GenericIPAddressField(null=True, blank=True)
	user_agent = models.TextField(blank=True, default='')

	class Meta:
		db_table = 'email_two_factor_codes'
		ordering = ['-created_at']
		indexes = [
			models.Index(fields=['challenge_token', 'is_used']),
			models.Index(fields=['user', 'is_used', 'expires_at']),
		]

	def __str__(self) -> str:
		return f'EmailTwoFactorCode for {self.user.email} (used: {self.is_used})'

	def is_valid(self) -> bool:
		"""
		Verifica si el código es válido.
		
		Un código es válido si:
		- No ha sido usado
		- No ha expirado
		- No ha excedido el máximo de intentos
		
		Returns:
			bool: True si el código es válido
		"""
		from django.utils import timezone
		
		if self.is_used:
			return False
		
		if timezone.now() > self.expires_at:
			return False
		
		if self.attempts >= self.max_attempts:
			return False
		
		return True

	def mark_as_used(self) -> None:
		"""
		Marca el código como usado.
		"""
		from django.utils import timezone
		
		self.is_used = True
		self.used_at = timezone.now()
		self.save(update_fields=['is_used', 'used_at'])


class TwoFactorAuth(TimeStampedModel):
	"""
	Modelo para almacenar configuración de autenticación de dos factores (2FA).
	
	Cada usuario puede tener una configuración 2FA con:
	- Secret key para TOTP
	- Códigos de respaldo
	- Estado de habilitación
	"""
	user = models.OneToOneField(
		settings.AUTH_USER_MODEL,
		on_delete=models.CASCADE,
		related_name='two_factor',
	)
	secret_key = models.CharField(max_length=32)
	is_enabled = models.BooleanField(default=False)
	backup_codes = models.JSONField(default=list)
	enabled_at = models.DateTimeField(null=True, blank=True)
	last_used_at = models.DateTimeField(null=True, blank=True)
	# Método de 2FA: 'totp' (app autenticadora) o 'email' (código por correo)
	method = models.CharField(
		max_length=20,
		choices=[
			('totp', 'App Autenticadora'),
			('email', 'Código por Email'),
		],
		default='totp'
	)

	class Meta:
		db_table = 'two_factor_auth'
		ordering = ['-created_at']

	def __str__(self) -> str:
		status = 'ENABLED' if self.is_enabled else 'DISABLED'
		return f'2FA for {self.user.email}: {status}'

	def generate_secret(self) -> str:
		"""
		Genera una nueva secret key para TOTP.

		Returns:
			str: Secret key en formato base32
		"""
		import pyotp
		self.secret_key = pyotp.random_base32()
		return self.secret_key

	def verify_token(self, token: str) -> bool:
		"""
		Verifica un código TOTP.

		Args:
			token: Código de 6 dígitos

		Returns:
			bool: True si el token es válido
		"""
		import pyotp
		totp = pyotp.TOTP(self.secret_key)
		return totp.verify(token, valid_window=1)

	def generate_backup_codes(self, count: int = 10) -> list[str]:
		"""
		Genera códigos de respaldo.

		Args:
			count: Número de códigos a generar (default: 10)

		Returns:
			list[str]: Lista de códigos de respaldo
		"""
		import secrets
		codes = []
		for _ in range(count):
			# Generar código de 8 caracteres alfanuméricos
			code = ''.join(secrets.choice('ABCDEFGHJKLMNPQRSTUVWXYZ23456789') for _ in range(8))
			# Formatear como XXXX-XXXX
			formatted_code = f'{code[:4]}-{code[4:]}'
			codes.append(formatted_code)
		
		self.backup_codes = codes
		return codes

	def verify_backup_code(self, code: str) -> bool:
		"""
		Verifica y consume un código de respaldo.

		Args:
			code: Código de respaldo

		Returns:
			bool: True si el código es válido
		"""
		# Normalizar código (remover espacios y guiones)
		normalized_code = code.replace(' ', '').replace('-', '').upper()
		
		for backup_code in self.backup_codes:
			normalized_backup = backup_code.replace(' ', '').replace('-', '').upper()
			if normalized_code == normalized_backup:
				# Remover el código usado
				self.backup_codes.remove(backup_code)
				self.save(update_fields=['backup_codes'])
				return True
		
		return False

	def get_provisioning_uri(self, user_email: str, issuer_name: str = 'Sistema Bancario') -> str:
		"""
		Genera la URI de provisioning para QR code.

		Args:
			user_email: Email del usuario
			issuer_name: Nombre de la aplicación (default: 'Sistema Bancario')

		Returns:
			str: URI de provisioning
		"""
		import pyotp
		totp = pyotp.TOTP(self.secret_key)
		return totp.provisioning_uri(name=user_email, issuer_name=issuer_name)
