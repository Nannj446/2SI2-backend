"""
Middleware para manejar rate limiting.
"""
from django.http import JsonResponse
from django_ratelimit.exceptions import Ratelimited


class RateLimitMiddleware:
	"""
	Middleware para manejar excepciones de rate limiting.
	
	Convierte las excepciones Ratelimited en respuestas JSON apropiadas.
	"""

	def __init__(self, get_response):
		self.get_response = get_response

	def __call__(self, request):
		response = self.get_response(request)
		return response

	def process_exception(self, request, exception):
		"""
		Procesa excepciones de rate limiting.

		Args:
			request: HttpRequest
			exception: Excepción lanzada

		Returns:
			JsonResponse si es una excepción de rate limiting, None en caso contrario
		"""
		if isinstance(exception, Ratelimited):
			return JsonResponse(
				{
					'detail': 'Has excedido el límite de peticiones. Por favor, intenta más tarde.',
					'code': 'rate_limit_exceeded'
				},
				status=429
			)
		return None
