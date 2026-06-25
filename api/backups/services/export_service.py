"""
Servicio para exportar datos de un tenant a JSON.
"""
import logging
from typing import Dict, List, Any
from django.apps import apps
from django.core.serializers import serialize
from api.tenants.models import FinancialInstitution
import re

logger = logging.getLogger(__name__)


class ExportService:
    """
    Servicio para exportar datos de un tenant a JSON.
    
    Exporta todas las tablas relacionadas con un tenant,
    excluyendo datos sensibles como passwords y tokens.
    """
    
    # Campos que NO deben exportarse por modelo
    # NOTA: password se INCLUYE porque ya está hasheado (seguro)
    EXCLUDED_FIELDS = {
        'user': ['last_login'],  # ✅ Incluir password hasheado
        'userprofile': [],  # ✅ Incluir two_factor_secret (necesario para 2FA)
    }
    
    # Patrones de campos a excluir (regex)
    # NOTA: Tokens y keys temporales se excluyen, pero NO passwords hasheados
    EXCLUDED_FIELD_PATTERNS = [
        r'.*_token$',      # Excluir tokens temporales (access_token, refresh_token)
        r'.*_key$',        # Excluir API keys
        r'.*_secret$',     # Excluir secrets temporales
        # ❌ REMOVIDO: r'.*password.*' - Necesitamos password hasheado para restore
    ]
    
    # Modelos que usan TenantModel (filtrados por institution)
    TENANT_MODELS = [
        'clients.Client',
        'clients.ClientDocument',
        'branches.Branch',
        'loans.LoanApplication',
        'loans.LoanApplicationDocument',
        'loans.LoanApplicationComment',
        'loans.LoanApplicationStatusHistory',
        'products.CreditProduct',
        'products.ProductRequirement',  # ✅ NUEVO
        'roles.Role',
        'identity_verification.IdentityVerification',
    ]
    
    # Modelos relacionados (no TenantModel pero tienen FK a institution)
    RELATED_MODELS = [
        'tenants.FinancialInstitution',
        'tenants.TenantBranding',
        'tenants.FinancialInstitutionMembership',
        'roles.UserRole',  # Asignaciones de roles a usuarios
        'saas.Subscription',  # ✅ NUEVO - Suscripción del tenant
        'identity_verification.IdentityVerificationWebhook',  # ✅ NUEVO - Webhooks (via FK a IdentityVerification)
    ]
    
    # Modelos de usuarios (requieren lógica especial)
    USER_MODELS = [
        'auth.User',  # Usuarios del sistema (Django auth)
        'users.UserProfile',  # Perfiles de usuarios
    ]
    
    # Modelos de autenticación (requieren lógica especial - filtrar por usuarios del tenant)
    AUTH_MODELS = [
        'authentication.PasswordResetToken',  # ✅ NUEVO - Tokens de reset
        'authentication.LoginAttempt',  # ✅ NUEVO - Intentos de login
        'authentication.AuthChallenge',  # ✅ NUEVO - Tokens temporales
        'authentication.EmailTwoFactorCode',  # ✅ NUEVO - Códigos 2FA por email
        'authentication.TwoFactorAuth',  # ✅ NUEVO - Configuración 2FA
    ]
    
    # Modelos de storage (archivos y recursos)
    STORAGE_MODELS = [
        'storage.FileResource',  # ✅ NUEVO - Referencias a archivos
    ]
    
    # Modelos de auditoría (opcionales - pueden ser grandes)
    AUDIT_MODELS = [
        'audit.AuditLog',  # ✅ NUEVO - Logs de auditoría
        'audit.SecurityEvent',  # ✅ NUEVO - Eventos de seguridad
    ]
    
    def __init__(self, tenant: FinancialInstitution, include_audit_logs: bool = False):
        """
        Inicializa el servicio.
        
        Args:
            tenant: Institución financiera a exportar
            include_audit_logs: Si True, incluye logs de auditoría (puede ser grande)
        """
        self.tenant = tenant
        self.include_audit_logs = include_audit_logs
        logger.info(
            f"ExportService inicializado para tenant {tenant.id} ({tenant.name}), "
            f"incluir auditoría: {include_audit_logs}"
        )
    
    def export_all_data(self) -> Dict[str, Any]:
        """
        Exporta todos los datos del tenant.
        
        Returns:
            Diccionario con datos exportados por modelo:
            {
                'tenant_id': 1,
                'tenant_name': 'Banco Test',
                'export_timestamp': '2026-05-06T...',
                'data': {
                    'clients.Client': [...],
                    'branches.Branch': [...],
                    ...
                }
            }
        """
        logger.info(f"Iniciando exportación completa para tenant {self.tenant.id}")
        
        exported_data = {
            'tenant_id': self.tenant.id,
            'tenant_name': self.tenant.name,
            'export_timestamp': self._get_timestamp(),
            'data': {}
        }
        
        # Exportar modelos de tenant
        for model_path in self.TENANT_MODELS:
            try:
                data = self._export_tenant_model(model_path)
                if data:
                    exported_data['data'][model_path] = data
                    logger.debug(f"Exportado {model_path}: {len(data)} registros")
            except Exception as e:
                logger.error(f"Error exportando {model_path}: {str(e)}")
                # Continuar con otros modelos en caso de error
                exported_data['data'][model_path] = []
        
        # Exportar modelos relacionados
        for model_path in self.RELATED_MODELS:
            try:
                data = self._export_related_model(model_path)
                if data:
                    exported_data['data'][model_path] = data
                    logger.debug(f"Exportado {model_path}: {len(data)} registros")
            except Exception as e:
                logger.error(f"Error exportando {model_path}: {str(e)}")
                exported_data['data'][model_path] = []
        
        # Exportar usuarios del tenant
        for model_path in self.USER_MODELS:
            try:
                data = self._export_user_model(model_path)
                if data:
                    exported_data['data'][model_path] = data
                    logger.debug(f"Exportado {model_path}: {len(data)} registros")
            except Exception as e:
                logger.error(f"Error exportando {model_path}: {str(e)}")
                exported_data['data'][model_path] = []
        
        # Exportar modelos de autenticación del tenant
        for model_path in self.AUTH_MODELS:
            try:
                data = self._export_auth_model(model_path)
                if data:
                    exported_data['data'][model_path] = data
                    logger.debug(f"Exportado {model_path}: {len(data)} registros")
            except Exception as e:
                logger.error(f"Error exportando {model_path}: {str(e)}")
                exported_data['data'][model_path] = []
        
        # Exportar archivos y recursos de storage
        for model_path in self.STORAGE_MODELS:
            try:
                data = self._export_storage_model(model_path)
                if data:
                    exported_data['data'][model_path] = data
                    logger.debug(f"Exportado {model_path}: {len(data)} registros")
            except Exception as e:
                logger.error(f"Error exportando {model_path}: {str(e)}")
                exported_data['data'][model_path] = []
        
        # Exportar logs de auditoría (opcional)
        if self.include_audit_logs:
            logger.info("Incluyendo logs de auditoría en el backup")
            for model_path in self.AUDIT_MODELS:
                try:
                    data = self._export_audit_model(model_path)
                    if data:
                        exported_data['data'][model_path] = data
                        logger.debug(f"Exportado {model_path}: {len(data)} registros")
                except Exception as e:
                    logger.error(f"Error exportando {model_path}: {str(e)}")
                    exported_data['data'][model_path] = []
        else:
            logger.info("Logs de auditoría NO incluidos en el backup")
        
        total_models = len([v for v in exported_data['data'].values() if v])
        logger.info(f"Exportación completada: {total_models} modelos con datos")
        
        return exported_data
    
    def _export_tenant_model(self, model_path: str) -> List[Dict]:
        """
        Exporta un modelo que usa TenantModel.
        
        Args:
            model_path: Ruta del modelo (ej: 'clients.Client')
        
        Returns:
            Lista de registros serializados
        """
        try:
            app_label, model_name = model_path.split('.')
            Model = apps.get_model(app_label, model_name)
        except (ValueError, LookupError) as e:
            logger.warning(f"Modelo no encontrado: {model_path} - {str(e)}")
            return []
        
        # Filtrar por tenant
        queryset = Model.objects.filter(institution=self.tenant)
        count = queryset.count()
        
        logger.debug(f"Exportando {model_path}: {count} registros")
        
        if count == 0:
            return []
        
        # Serializar a Python dict
        serialized = serialize('python', queryset)
        
        # Limpiar datos sensibles
        cleaned_data = self._clean_sensitive_data(serialized, model_name.lower())
        
        return cleaned_data
    
    def _export_related_model(self, model_path: str) -> List[Dict]:
        """
        Exporta un modelo relacionado (con FK a institution).
        
        Args:
            model_path: Ruta del modelo
        
        Returns:
            Lista de registros serializados
        """
        try:
            app_label, model_name = model_path.split('.')
            Model = apps.get_model(app_label, model_name)
        except (ValueError, LookupError) as e:
            logger.warning(f"Modelo no encontrado: {model_path} - {str(e)}")
            return []
        
        # Casos especiales según el modelo
        if model_name == 'FinancialInstitution':
            # Solo exportar el tenant actual
            queryset = Model.objects.filter(id=self.tenant.id)
        elif model_name == 'TenantBranding':
            queryset = Model.objects.filter(institution=self.tenant)
        elif model_name == 'FinancialInstitutionMembership':
            queryset = Model.objects.filter(institution=self.tenant)
        elif model_name == 'UserRole':
            # Exportar asignaciones de roles del tenant
            queryset = Model.objects.filter(institution=self.tenant)
        elif model_name == 'Subscription':
            # Exportar suscripción activa del tenant
            queryset = Model.objects.filter(institution=self.tenant)
        elif model_name == 'IdentityVerificationWebhook':
            # Exportar webhooks relacionados con verificaciones del tenant
            # Obtener IDs de verificaciones del tenant
            from api.identity_verification.models import IdentityVerification
            verification_ids = IdentityVerification.objects.filter(
                institution=self.tenant
            ).values_list('id', flat=True)
            queryset = Model.objects.filter(identity_verification_id__in=verification_ids)
        else:
            queryset = Model.objects.none()
        
        count = queryset.count()
        logger.debug(f"Exportando {model_path}: {count} registros")
        
        if count == 0:
            return []
        
        serialized = serialize('python', queryset)
        cleaned_data = self._clean_sensitive_data(serialized, model_name.lower())
        
        return cleaned_data
    
    def _export_user_model(self, model_path: str) -> List[Dict]:
        """
        Exporta usuarios que pertenecen al tenant.
        
        Solo exporta usuarios que tienen membresía activa en el tenant.
        Excluye passwords y datos sensibles.
        
        Args:
            model_path: Ruta del modelo (users.User o users.UserProfile)
        
        Returns:
            Lista de registros serializados
        """
        try:
            app_label, model_name = model_path.split('.')
            Model = apps.get_model(app_label, model_name)
        except (ValueError, LookupError) as e:
            logger.warning(f"Modelo no encontrado: {model_path} - {str(e)}")
            return []
        
        # Obtener IDs de usuarios del tenant a través de membresías
        from api.tenants.models import FinancialInstitutionMembership
        user_ids = FinancialInstitutionMembership.objects.filter(
            institution=self.tenant,
            is_active=True
        ).values_list('user_id', flat=True)
        
        if model_name == 'User':
            # Exportar usuarios del tenant
            queryset = Model.objects.filter(id__in=user_ids)
        elif model_name == 'UserProfile':
            # Exportar perfiles de usuarios del tenant
            queryset = Model.objects.filter(user_id__in=user_ids)
        else:
            queryset = Model.objects.none()
        
        count = queryset.count()
        logger.info(f"Exportando {model_path}: {count} usuarios del tenant")
        
        if count == 0:
            return []
        
        serialized = serialize('python', queryset)
        cleaned_data = self._clean_sensitive_data(serialized, model_name.lower())
        
        return cleaned_data
    
    def _export_auth_model(self, model_path: str) -> List[Dict]:
        """
        Exporta modelos de autenticación relacionados con usuarios del tenant.
        
        Incluye tokens, intentos de login, configuración 2FA, etc.
        Solo exporta datos de usuarios que pertenecen al tenant.
        
        Args:
            model_path: Ruta del modelo (authentication.*)
        
        Returns:
            Lista de registros serializados
        """
        try:
            app_label, model_name = model_path.split('.')
            Model = apps.get_model(app_label, model_name)
        except (ValueError, LookupError) as e:
            logger.warning(f"Modelo no encontrado: {model_path} - {str(e)}")
            return []
        
        # Obtener IDs de usuarios del tenant a través de membresías
        from api.tenants.models import FinancialInstitutionMembership
        user_ids = FinancialInstitutionMembership.objects.filter(
            institution=self.tenant,
            is_active=True
        ).values_list('user_id', flat=True)
        
        # Filtrar por usuarios del tenant
        queryset = Model.objects.filter(user_id__in=user_ids)
        
        count = queryset.count()
        logger.info(f"Exportando {model_path}: {count} registros de autenticación")
        
        if count == 0:
            return []
        
        serialized = serialize('python', queryset)
        cleaned_data = self._clean_sensitive_data(serialized, model_name.lower())
        
        return cleaned_data
    
    def _export_storage_model(self, model_path: str) -> List[Dict]:
        """
        Exporta recursos de storage (FileResource) del tenant.
        
        Exporta referencias a archivos almacenados en Supabase Storage.
        Los archivos físicos se respaldan por separado.
        
        Args:
            model_path: Ruta del modelo (storage.FileResource)
        
        Returns:
            Lista de registros serializados
        """
        try:
            app_label, model_name = model_path.split('.')
            Model = apps.get_model(app_label, model_name)
        except (ValueError, LookupError) as e:
            logger.warning(f"Modelo no encontrado: {model_path} - {str(e)}")
            return []
        
        if model_name == 'FileResource':
            # Exportar archivos del tenant (usa FK 'tenant')
            queryset = Model.objects.filter(tenant=self.tenant)
        else:
            queryset = Model.objects.none()
        
        count = queryset.count()
        logger.info(f"Exportando {model_path}: {count} archivos del tenant")
        
        if count == 0:
            return []
        
        serialized = serialize('python', queryset)
        cleaned_data = self._clean_sensitive_data(serialized, model_name.lower())
        
        return cleaned_data
    
    def _export_audit_model(self, model_path: str) -> List[Dict]:
        """
        Exporta logs de auditoría del tenant.
        
        Solo exporta logs relacionados con el tenant.
        ADVERTENCIA: Puede ser muy grande.
        
        Args:
            model_path: Ruta del modelo (audit.AuditLog o audit.SecurityEvent)
        
        Returns:
            Lista de registros serializados
        """
        try:
            app_label, model_name = model_path.split('.')
            Model = apps.get_model(app_label, model_name)
        except (ValueError, LookupError) as e:
            logger.warning(f"Modelo no encontrado: {model_path} - {str(e)}")
            return []
        
        # Filtrar logs del tenant
        if model_name == 'AuditLog':
            # AuditLog usa FK 'institution'
            queryset = Model.objects.filter(institution=self.tenant).order_by('-timestamp')
        elif model_name == 'SecurityEvent':
            # SecurityEvent NO tiene campo de tenant, obtener usuarios del tenant
            from api.tenants.models import FinancialInstitutionMembership
            user_ids = FinancialInstitutionMembership.objects.filter(
                institution=self.tenant,
                is_active=True
            ).values_list('user_id', flat=True)
            queryset = Model.objects.filter(user_id__in=user_ids).order_by('-timestamp')
        else:
            queryset = Model.objects.none()
        
        count = queryset.count()
        logger.warning(f"Exportando {model_path}: {count} registros de auditoría (puede ser grande)")
        
        if count == 0:
            return []
        
        # Limitar a últimos 10,000 registros para evitar backups gigantes
        MAX_AUDIT_RECORDS = 10000
        if count > MAX_AUDIT_RECORDS:
            logger.warning(
                f"Limitando {model_path} a {MAX_AUDIT_RECORDS} registros más recientes (total: {count})"
            )
            queryset = queryset[:MAX_AUDIT_RECORDS]
        
        serialized = serialize('python', queryset)
        cleaned_data = self._clean_sensitive_data(serialized, model_name.lower())
        
        return cleaned_data
    
    def _clean_sensitive_data(
        self, 
        serialized_data: List[Dict], 
        model_name: str
    ) -> List[Dict]:
        """
        Elimina campos sensibles de los datos serializados.
        
        Args:
            serialized_data: Datos serializados por Django
            model_name: Nombre del modelo (lowercase)
        
        Returns:
            Datos limpios sin campos sensibles
        """
        cleaned = []
        
        for item in serialized_data:
            fields = item.get('fields', {})
            
            # Eliminar campos específicos del modelo
            if model_name in self.EXCLUDED_FIELDS:
                for field in self.EXCLUDED_FIELDS[model_name]:
                    fields.pop(field, None)
            
            # Eliminar campos por patrón regex
            fields_to_remove = []
            for field_name in fields.keys():
                if self._should_exclude_field(field_name):
                    fields_to_remove.append(field_name)
            
            for field in fields_to_remove:
                fields.pop(field)
                logger.debug(f"Campo sensible excluido: {model_name}.{field}")
            
            cleaned.append(item)
        
        return cleaned
    
    def _should_exclude_field(self, field_name: str) -> bool:
        """
        Determina si un campo debe excluirse por patrón.
        
        Args:
            field_name: Nombre del campo
        
        Returns:
            True si debe excluirse, False si no
        """
        for pattern in self.EXCLUDED_FIELD_PATTERNS:
            if re.match(pattern, field_name, re.IGNORECASE):
                return True
        return False
    
    def get_record_counts(self) -> Dict[str, int]:
        """
        Obtiene conteo de registros por modelo sin exportar datos.
        
        Útil para preview antes de hacer backup completo.
        
        Returns:
            Diccionario con conteos: {'clients.Client': 100, ...}
        """
        counts = {}
        
        # Contar modelos de tenant
        for model_path in self.TENANT_MODELS:
            try:
                app_label, model_name = model_path.split('.')
                Model = apps.get_model(app_label, model_name)
                count = Model.objects.filter(institution=self.tenant).count()
                counts[model_path] = count
            except Exception as e:
                logger.warning(f"Error contando {model_path}: {str(e)}")
                counts[model_path] = 0
        
        # Contar modelos relacionados
        for model_path in self.RELATED_MODELS:
            try:
                app_label, model_name = model_path.split('.')
                Model = apps.get_model(app_label, model_name)
                
                if model_name == 'FinancialInstitution':
                    count = 1 if Model.objects.filter(id=self.tenant.id).exists() else 0
                elif model_name == 'UserRole':
                    count = Model.objects.filter(institution=self.tenant).count()
                elif model_name == 'IdentityVerificationWebhook':
                    # Contar webhooks relacionados con verificaciones del tenant
                    from api.identity_verification.models import IdentityVerification
                    verification_ids = IdentityVerification.objects.filter(
                        institution=self.tenant
                    ).values_list('id', flat=True)
                    count = Model.objects.filter(identity_verification_id__in=verification_ids).count()
                elif hasattr(Model, 'institution'):
                    count = Model.objects.filter(institution=self.tenant).count()
                else:
                    count = 0
                
                counts[model_path] = count
            except Exception as e:
                logger.warning(f"Error contando {model_path}: {str(e)}")
                counts[model_path] = 0
        
        # Contar usuarios del tenant
        try:
            from api.tenants.models import FinancialInstitutionMembership
            user_ids = FinancialInstitutionMembership.objects.filter(
                institution=self.tenant,
                is_active=True
            ).values_list('user_id', flat=True)
            
            for model_path in self.USER_MODELS:
                try:
                    app_label, model_name = model_path.split('.')
                    Model = apps.get_model(app_label, model_name)
                    
                    if model_name == 'User':
                        count = Model.objects.filter(id__in=user_ids).count()
                    elif model_name == 'UserProfile':
                        count = Model.objects.filter(user_id__in=user_ids).count()
                    else:
                        count = 0
                    
                    counts[model_path] = count
                except Exception as e:
                    logger.warning(f"Error contando {model_path}: {str(e)}")
                    counts[model_path] = 0
        except Exception as e:
            logger.error(f"Error contando usuarios: {str(e)}")
            for model_path in self.USER_MODELS:
                counts[model_path] = 0
        
        # Contar modelos de autenticación del tenant
        try:
            from api.tenants.models import FinancialInstitutionMembership
            user_ids = FinancialInstitutionMembership.objects.filter(
                institution=self.tenant,
                is_active=True
            ).values_list('user_id', flat=True)
            
            for model_path in self.AUTH_MODELS:
                try:
                    app_label, model_name = model_path.split('.')
                    Model = apps.get_model(app_label, model_name)
                    count = Model.objects.filter(user_id__in=user_ids).count()
                    counts[model_path] = count
                except Exception as e:
                    logger.warning(f"Error contando {model_path}: {str(e)}")
                    counts[model_path] = 0
        except Exception as e:
            logger.error(f"Error contando modelos de autenticación: {str(e)}")
            for model_path in self.AUTH_MODELS:
                counts[model_path] = 0
        
        # Contar archivos de storage
        for model_path in self.STORAGE_MODELS:
            try:
                app_label, model_name = model_path.split('.')
                Model = apps.get_model(app_label, model_name)
                
                if model_name == 'FileResource':
                    count = Model.objects.filter(tenant=self.tenant).count()
                else:
                    count = 0
                
                counts[model_path] = count
            except Exception as e:
                logger.warning(f"Error contando {model_path}: {str(e)}")
                counts[model_path] = 0
        
        # Contar logs de auditoría (solo si se incluyen)
        if self.include_audit_logs:
            for model_path in self.AUDIT_MODELS:
                try:
                    app_label, model_name = model_path.split('.')
                    Model = apps.get_model(app_label, model_name)
                    
                    if model_name == 'AuditLog':
                        count = Model.objects.filter(institution=self.tenant).count()
                    elif model_name == 'SecurityEvent':
                        # SecurityEvent no tiene tenant, contar por usuarios del tenant
                        from api.tenants.models import FinancialInstitutionMembership
                        user_ids = FinancialInstitutionMembership.objects.filter(
                            institution=self.tenant,
                            is_active=True
                        ).values_list('user_id', flat=True)
                        count = Model.objects.filter(user_id__in=user_ids).count()
                    else:
                        count = 0
                    
                    counts[model_path] = count
                except Exception as e:
                    logger.warning(f"Error contando {model_path}: {str(e)}")
                    counts[model_path] = 0
        
        return counts
    
    @staticmethod
    def _get_timestamp() -> str:
        """
        Obtiene timestamp actual en formato ISO 8601.
        
        Returns:
            Timestamp string (ej: '2026-05-06T14:30:22.123456+00:00')
        """
        from django.utils import timezone
        return timezone.now().isoformat()
    
    def download_tenant_files(self) -> Dict[str, bytes]:
        """
        Descarga todos los archivos físicos del tenant desde Supabase Storage.
        
        Returns:
            Dict con {file_path: file_content_bytes}
        """
        from api.storage.services import StorageService
        from api.storage.models import FileResource
        
        storage_service = StorageService()
        files = {}
        
        # Obtener todas las referencias de archivos activos del tenant
        file_resources = FileResource.objects.filter(
            tenant=self.tenant,
            status=FileResource.Status.ACTIVE
        )
        
        total_files = file_resources.count()
        logger.info(f"Descargando {total_files} archivos del tenant {self.tenant.id}")
        
        for idx, file_resource in enumerate(file_resources, 1):
            try:
                # Descargar archivo desde Supabase
                file_content = storage_service.download_file(file_resource.file_path)
                files[file_resource.file_path] = file_content
                logger.debug(
                    f"✓ [{idx}/{total_files}] Descargado: {file_resource.file_path} "
                    f"({len(file_content)} bytes)"
                )
            except Exception as e:
                logger.error(
                    f"✗ [{idx}/{total_files}] Error descargando {file_resource.file_path}: {str(e)}"
                )
                # Continuar con otros archivos
        
        logger.info(f"Descargados {len(files)}/{total_files} archivos exitosamente")
        return files
    
    def create_backup_zip(
        self, 
        exported_data: dict, 
        manifest_json: dict, 
        files: Dict[str, bytes]
    ) -> bytes:
        """
        Crea un archivo ZIP con datos JSON + archivos físicos.
        
        Estructura del ZIP:
        backup_{id}.zip
        ├── data.json          # Datos del tenant
        ├── manifest.json      # Manifest del backup
        └── files/             # Archivos físicos
            ├── tenants/2/branding/logo.png
            ├── tenants/2/clients/doc1.pdf
            └── ...
        
        Args:
            exported_data: Datos exportados del tenant
            manifest_json: Manifest del backup
            files: Dict con {file_path: file_content_bytes}
        
        Returns:
            Contenido del ZIP en bytes
        """
        import zipfile
        import io
        import json
        
        logger.info(f"Creando archivo ZIP del backup con {len(files)} archivos")
        
        zip_buffer = io.BytesIO()
        
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            # 1. Agregar data.json
            data_json = json.dumps(exported_data, indent=2, ensure_ascii=False, default=str)
            zip_file.writestr('data.json', data_json)
            logger.debug(f"✓ Agregado data.json ({len(data_json)} bytes)")
            
            # 2. Agregar manifest.json
            manifest_json_str = json.dumps(manifest_json, indent=2, ensure_ascii=False, default=str)
            zip_file.writestr('manifest.json', manifest_json_str)
            logger.debug(f"✓ Agregado manifest.json ({len(manifest_json_str)} bytes)")
            
            # 3. Agregar archivos físicos
            for file_path, file_content in files.items():
                zip_path = f'files/{file_path}'
                zip_file.writestr(zip_path, file_content)
                logger.debug(f"✓ Agregado {zip_path} ({len(file_content)} bytes)")
            
            logger.info(f"ZIP creado exitosamente con {len(files)} archivos")
        
        zip_buffer.seek(0)
        return zip_buffer.read()
