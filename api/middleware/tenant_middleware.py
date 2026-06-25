"""
Middleware para inyectar contexto de tenant en cada request.

Este middleware identifica el tenant (institución financiera) del usuario autenticado
y lo inyecta en request.tenant para uso en vistas y servicios.

También establece el tenant en thread-local storage para el TenantManager.

Comportamiento:
- Superadmin SaaS: request.tenant = None, request.user_type = 'saas_admin'
- Cliente: request.tenant = Institution (desde Client), request.user_type = 'client'
- Usuario de tenant: request.tenant = Institution, request.user_type = 'tenant_user'
- Usuario no autenticado: request.tenant = None, request.user_type = None
"""

from api.core.managers import set_current_tenant, clear_current_tenant
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.exceptions import AuthenticationFailed


class TenantMiddleware:
	"""
	Middleware que inyecta el tenant actual en el request.
	
	Atributos inyectados:
	- request.tenant: Instancia de FinancialInstitution o None
	- request.user_type: 'saas_admin', 'client', 'tenant_user', o None
	- request.user_institution_id: ID de la institución o None
	"""
	
	def __init__(self, get_response):
		"""
		Inicializa el middleware.
		
		Args:
			get_response: Callable para obtener la respuesta
		"""
		self.get_response = get_response
		self.jwt_authenticator = JWTAuthentication()
	
	def __call__(self, request):
		"""
		Procesa el request e inyecta el tenant.
		
		Args:
			request: HttpRequest
		
		Returns:
			HttpResponse
		"""
		# Inicializar valores por defecto
		request.tenant = None
		request.user_type = None
		request.user_institution_id = None
		
		# Limpiar tenant anterior del thread-local
		clear_current_tenant()
		
		# Intentar autenticar con JWT si hay token
		if 'Authorization' in request.headers or 'HTTP_AUTHORIZATION' in request.META:
			try:
				# Intentar autenticar con JWT
				auth_result = self.jwt_authenticator.authenticate(request)
				if auth_result is not None:
					user, token = auth_result
					request.user = user
			except AuthenticationFailed:
				pass
			except Exception:
				pass
		
		# Solo procesar si el usuario está autenticado
		if request.user.is_authenticated:
			# Verificar si el usuario tiene perfil
			if hasattr(request.user, 'profile'):
				# Verificar si es superadmin SaaS
				if request.user.profile.is_saas_admin():
					request.tenant = None
					request.user_type = 'saas_admin'
					request.user_institution_id = None
					# Superadmin no tiene tenant - puede ver todo
					set_current_tenant(None)
				elif request.user.profile.is_client():
					# Usuario es cliente - obtener institución desde Client
					if hasattr(request.user, 'client_profile'):
						client = request.user.client_profile
						request.tenant = client.institution
						request.user_type = 'client'
						request.user_institution_id = client.institution.id
						# Establecer tenant en thread-local para TenantManager
						set_current_tenant(client.institution)
					else:
						# Cliente sin perfil de cliente (caso edge)
						request.tenant = None
						request.user_type = 'client'
						request.user_institution_id = None
						set_current_tenant(None)
				else:
					# Usuario de tenant - obtener su institución activa
					membership = request.user.institution_memberships.filter(
						is_active=True
					).first()
					
					if membership:
						request.tenant = membership.institution
						request.user_type = 'tenant_user'
						request.user_institution_id = membership.institution.id
						# Establecer tenant en thread-local para TenantManager
						set_current_tenant(membership.institution)
					else:
						# Usuario sin membership activa
						request.tenant = None
						request.user_type = 'tenant_user'
						request.user_institution_id = None
						set_current_tenant(None)
			else:
				# Usuario sin perfil (caso edge - no debería ocurrir con signals)
				request.tenant = None
				request.user_type = None
				request.user_institution_id = None
				set_current_tenant(None)
		
		try:
			# Procesar request
			response = self.get_response(request)
		finally:
			# Limpiar tenant del thread-local después del request
			clear_current_tenant()
		
		return response
