"""
Middleware para auditoría automática de requests.
"""

import json
import time
from django.utils.deprecation import MiddlewareMixin
from api.audit.services import AuditService, SecurityEventService


class AuditMiddleware(MiddlewareMixin):
    """
    Middleware que registra automáticamente TODAS las acciones HTTP.
    """
    
    # Endpoints que NO deben ser auditados (para evitar spam)
    EXCLUDE_PATHS = [
        '/api/audit/',  # Evitar recursión
        '/static/',
        '/media/',
        '/favicon.ico',
        '/health/',
        '/metrics/',
    ]
    
    # Todos los métodos HTTP que queremos auditar
    AUDIT_METHODS = ['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'HEAD', 'OPTIONS']
    
    # Mapeo de endpoints a tipos de recursos más específicos
    RESOURCE_MAPPING = {
        '/api/auth/login/': 'Authentication',
        '/api/auth/logout/': 'Authentication',
        '/api/auth/register/': 'Registration',
        '/api/auth/password-reset/': 'PasswordReset',
        '/api/users/': 'User',
        '/api/roles/': 'Role',
        '/api/clients/': 'Client',
        '/api/products/': 'Product',
        '/api/loans/': 'Loan',
        '/api/saas/tenants/': 'Institution',
        '/api/saas/plans/': 'SubscriptionPlan',
        '/api/saas/subscriptions/': 'Subscription',
        '/api/saas/permissions/': 'Permission',
        '/api/profile/': 'UserProfile',
    }
    
    def process_request(self, request):
        """Marca el inicio del request."""
        request._audit_start_time = time.time()
        return None
    
    def process_response(self, request, response):
        """Registra el request si es necesario."""
        # Verificar si el path debe ser excluido
        should_exclude = any(
            request.path.startswith(path) for path in self.EXCLUDE_PATHS
        )
        
        if should_exclude:
            return response
        
        # Verificar si el método debe ser auditado
        if request.method not in self.AUDIT_METHODS:
            return response
        
        # Registrar la acción
        self._log_request(request, response)
        
        return response
    
    def _log_request(self, request, response):
        """Registra el request en el log de auditoría."""
        try:
            # Determinar el tipo de acción más específico
            action = self._get_detailed_action(request.method, request.path, response)
            
            # Determinar el tipo de recurso
            resource_type = self._get_resource_type(request.path)
            
            # Obtener el ID del recurso si está disponible
            resource_id = self._get_resource_id(request.path, response)
            
            # Crear descripción descriptiva
            description = self._get_descriptive_description(request, response, resource_type, resource_id)
            
            # Obtener metadata detallada
            metadata = self._get_detailed_metadata(request, response)
            
            # Determinar severidad basada en el código de respuesta y acción
            severity = self._get_severity(request.method, response.status_code, request.path)
            
            # Solo registrar si hay usuario autenticado o es una acción importante
            user = request.user if request.user.is_authenticated else None
            
            # Registrar acciones importantes incluso sin usuario (registro, login fallido, etc.)
            should_log = (
                user is not None or 
                '/auth/' in request.path or 
                response.status_code >= 400
            )
            
            if should_log:
                # Registrar en el log
                AuditService.log_action(
                    action=action,
                    resource_type=resource_type,
                    resource_id=resource_id,
                    description=description,
                    user=user,
                    institution=getattr(request, 'tenant', None),
                    request=request,
                    severity=severity,
                    metadata=metadata
                )
            
        except Exception as e:
            # No fallar el request si hay error en auditoría
            print(f"Error en auditoría: {e}")
    
    def _get_detailed_action(self, method: str, path: str, response) -> str:
        """Determina el tipo de acción más específico basado en el contexto."""
        # Acciones de autenticación
        if '/auth/login/' in path:
            return 'login_success' if response.status_code == 200 else 'login_failed'
        elif '/auth/logout/' in path:
            return 'logout'
        elif '/auth/register/' in path:
            return 'register'
        elif '/auth/password-reset/' in path:
            return 'password_reset_request'
        
        # Acciones CRUD estándar
        if method == 'GET':
            if path.endswith('/') and not any(char.isdigit() for char in path.split('/')[-2]):
                return 'list'  # Listar recursos
            else:
                return 'view'  # Ver recurso específico
        elif method == 'POST':
            return 'create'
        elif method == 'PUT':
            return 'update_full'
        elif method == 'PATCH':
            return 'update_partial'
        elif method == 'DELETE':
            return 'delete'
        elif method == 'HEAD':
            return 'check_exists'
        elif method == 'OPTIONS':
            return 'options_request'
        
        return method.lower()
    
    def _get_resource_type(self, path: str) -> str:
        """Extrae el tipo de recurso del path de manera más específica."""
        # Buscar coincidencia exacta primero
        for endpoint, resource_type in self.RESOURCE_MAPPING.items():
            if path.startswith(endpoint):
                return resource_type
        
        # Fallback a detección por segmentos
        if '/users/' in path:
            return 'User'
        elif '/roles/' in path:
            return 'Role'
        elif '/clients/' in path:
            return 'Client'
        elif '/products/' in path:
            return 'Product'
        elif '/loans/' in path:
            return 'Loan'
        elif '/saas/' in path:
            if '/tenants/' in path:
                return 'Institution'
            elif '/plans/' in path:
                return 'SubscriptionPlan'
            elif '/subscriptions/' in path:
                return 'Subscription'
            elif '/permissions/' in path:
                return 'Permission'
            return 'SaaS'
        elif '/profile/' in path:
            return 'UserProfile'
        elif '/auth/' in path:
            return 'Authentication'
        
        return 'Unknown'
    
    def _get_resource_id(self, path: str, response) -> int:
        """Intenta extraer el ID del recurso de manera más robusta."""
        # Intentar extraer del path (ej: /api/users/123/)
        parts = path.strip('/').split('/')
        for i, part in enumerate(parts):
            if part.isdigit():
                return int(part)
        
        # Intentar extraer de la respuesta para creaciones
        try:
            if hasattr(response, 'data') and isinstance(response.data, dict):
                return response.data.get('id')
            elif response.status_code == 201:  # Created
                # Intentar parsear JSON de la respuesta
                content = response.content.decode('utf-8')
                data = json.loads(content)
                if isinstance(data, dict) and 'id' in data:
                    return data['id']
        except:
            pass
        
        return None
    
    def _get_descriptive_description(self, request, response, resource_type, resource_id):
        """Genera una descripción más descriptiva de la acción."""
        method = request.method
        path = request.path
        status = response.status_code
        user_email = request.user.email if request.user.is_authenticated else 'Anónimo'
        
        # Descripciones específicas para autenticación
        if '/auth/login/' in path:
            if status == 200:
                return f"Inicio de sesión exitoso para {user_email}"
            else:
                return f"Intento de inicio de sesión fallido para {user_email}"
        elif '/auth/logout/' in path:
            return f"Cierre de sesión de {user_email}"
        elif '/auth/register/' in path:
            if status == 201:
                return f"Registro exitoso de nueva institución"
            else:
                return f"Intento de registro fallido"
        
        # Descripciones para operaciones CRUD
        resource_name = resource_type
        if resource_id:
            resource_identifier = f"{resource_name} #{resource_id}"
        else:
            resource_identifier = resource_name
        
        if method == 'GET':
            if resource_id:
                return f"Consulta de {resource_identifier} por {user_email}"
            else:
                return f"Listado de {resource_name}s por {user_email}"
        elif method == 'POST':
            if status == 201:
                return f"Creación exitosa de {resource_identifier} por {user_email}"
            else:
                return f"Intento fallido de crear {resource_name} por {user_email}"
        elif method == 'PUT':
            if status in [200, 204]:
                return f"Actualización completa de {resource_identifier} por {user_email}"
            else:
                return f"Intento fallido de actualizar {resource_identifier} por {user_email}"
        elif method == 'PATCH':
            if status in [200, 204]:
                return f"Actualización parcial de {resource_identifier} por {user_email}"
            else:
                return f"Intento fallido de actualizar parcialmente {resource_identifier} por {user_email}"
        elif method == 'DELETE':
            if status in [200, 204]:
                return f"Eliminación de {resource_identifier} por {user_email}"
            else:
                return f"Intento fallido de eliminar {resource_identifier} por {user_email}"
        
        # Descripción genérica
        return f"{method} {path} por {user_email} - Estado: {status}"
    
    def _get_detailed_metadata(self, request, response):
        """Obtiene metadata detallada del request."""
        metadata = {
            'method': request.method,
            'path': request.path,
            'status_code': response.status_code,
            'duration_ms': int((time.time() - getattr(request, '_audit_start_time', time.time())) * 1000),
            'query_params': dict(request.GET) if request.GET else {},
        }
        
        # Agregar información del body para métodos que lo permiten
        if request.method in ['POST', 'PUT', 'PATCH'] and hasattr(request, 'data'):
            try:
                # Filtrar información sensible
                body_data = dict(request.data) if hasattr(request.data, 'items') else {}
                # Remover campos sensibles
                sensitive_fields = ['password', 'confirm_password', 'token', 'secret']
                filtered_data = {
                    k: '***HIDDEN***' if k.lower() in sensitive_fields else v 
                    for k, v in body_data.items()
                }
                metadata['request_data'] = filtered_data
            except:
                pass
        
        # Agregar información de la respuesta para errores
        if response.status_code >= 400:
            try:
                content = response.content.decode('utf-8')[:500]  # Limitar tamaño
                metadata['response_content'] = content
            except:
                pass
        
        return metadata
    
    def _get_severity(self, method: str, status_code: int, path: str) -> str:
        """Determina la severidad basada en el método, código de estado y path."""
        # Errores críticos
        if status_code >= 500:
            return 'critical'
        
        # Errores de cliente y accesos no autorizados
        if status_code >= 400:
            if status_code == 401:  # No autorizado
                return 'warning'
            elif status_code == 403:  # Prohibido
                return 'warning'
            elif status_code == 404:  # No encontrado
                return 'info'
            else:
                return 'warning'
        
        # Operaciones de eliminación siempre son warning
        if method == 'DELETE' and status_code in [200, 204]:
            return 'warning'
        
        # Operaciones de autenticación
        if '/auth/' in path:
            return 'info'
        
        # Operaciones normales
        return 'info'


class SecurityEventMiddleware(MiddlewareMixin):
    """
    Middleware que detecta y registra eventos de seguridad.
    """
    
    def process_response(self, request, response):
        """Detecta eventos de seguridad basados en la respuesta."""
        # Registrar accesos no autorizados (403)
        if response.status_code == 403 and request.user.is_authenticated:
            self._log_unauthorized_access(request)
        
        # Registrar intentos de login fallidos (401 en /auth/login/)
        if response.status_code == 401 and '/auth/login/' in request.path:
            self._log_failed_login(request)
        
        # Registrar múltiples errores 404 (posible escaneo)
        if response.status_code == 404:
            self._check_suspicious_404(request)
        
        return response
    
    def _log_unauthorized_access(self, request):
        """Registra un intento de acceso no autorizado."""
        try:
            resource_type = self._get_resource_type(request.path)
            resource_id = self._get_resource_id_from_path(request.path)
            
            SecurityEventService.log_unauthorized_access(
                user=request.user,
                resource_type=resource_type,
                resource_id=resource_id,
                request=request,
                required_permission='unknown'
            )
        except Exception as e:
            print(f"Error registrando acceso no autorizado: {e}")
    
    def _log_failed_login(self, request):
        """Registra un intento de login fallido."""
        try:
            # Intentar obtener el email del body
            email = 'unknown'
            if hasattr(request, 'data') and isinstance(request.data, dict):
                email = request.data.get('email', 'unknown')
            elif request.method == 'POST':
                try:
                    body = json.loads(request.body.decode('utf-8'))
                    email = body.get('email', 'unknown')
                except:
                    pass
            
            SecurityEventService.log_failed_login(
                email=email,
                request=request,
                reason='Invalid credentials'
            )
        except Exception as e:
            print(f"Error registrando login fallido: {e}")
    
    def _check_suspicious_404(self, request):
        """Verifica si hay múltiples 404s que podrían indicar escaneo."""
        # Esta funcionalidad se podría implementar con un cache/contador
        # Por ahora solo registramos 404s en paths sospechosos
        suspicious_paths = ['/admin/', '/wp-admin/', '/.env', '/config/', '/api/v2/']
        if any(suspicious in request.path for suspicious in suspicious_paths):
            try:
                SecurityEventService.log_suspicious_activity(
                    user=request.user if request.user.is_authenticated else None,
                    request=request,
                    description=f"Acceso a path sospechoso: {request.path}",
                    metadata={'path': request.path, 'reason': 'suspicious_path_404'}
                )
            except Exception as e:
                print(f"Error registrando actividad sospechosa: {e}")
    
    def _get_resource_type(self, path: str) -> str:
        """Extrae el tipo de recurso del path."""
        if '/users/' in path:
            return 'User'
        elif '/roles/' in path:
            return 'Role'
        elif '/clients/' in path:
            return 'Client'
        elif '/products/' in path:
            return 'Product'
        elif '/loans/' in path:
            return 'Loan'
        elif '/saas/' in path:
            return 'Institution'
        return 'Unknown'
    
    def _get_resource_id_from_path(self, path: str) -> int:
        """Extrae el ID del recurso del path."""
        parts = path.strip('/').split('/')
        for part in parts:
            if part.isdigit():
                return int(part)
        return None
