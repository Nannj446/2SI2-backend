"""
Servicio para importar datos desde un backup JSON.
"""
import logging
from typing import Dict, List, Any, Optional
from django.apps import apps
from django.db import transaction
from django.core.exceptions import ValidationError as DjangoValidationError

logger = logging.getLogger(__name__)


class ImportService:
    """
    Servicio para importar datos desde un backup JSON.
    
    Maneja la deserialización e inserción de datos en la base de datos,
    respetando dependencias entre modelos y manejando conflictos.
    """
    
    # Orden de importación (respetando dependencias FK)
    # IMPORTANTE: User debe importarse ANTES de cualquier modelo que tenga FK a User
    IMPORT_ORDER = [
        # 1. Institution base (sin dependencias)
        'tenants.FinancialInstitution',
        
        # 2. Usuarios PRIMERO (antes de cualquier cosa que dependa de ellos)
        'auth.User',  # Django auth User model
        
        # 3. Tenant config y suscripciones (tienen FK a Institution y User)
        'tenants.TenantBranding',
        'saas.Subscription',
        
        # 4. Perfiles de usuario (FK a User)
        'users.UserProfile',
        
        # 5. Membresías y roles
        'tenants.FinancialInstitutionMembership',
        'roles.Role',
        'roles.UserRole',
        
        # 6. Autenticación (FK a User)
        'authentication.TwoFactorAuth',
        'authentication.EmailTwoFactorCode',
        'authentication.PasswordResetToken',
        'authentication.LoginAttempt',
        'authentication.AuthChallenge',
        
        # 7. Sucursales
        'branches.Branch',
        
        # 8. Productos
        'products.CreditProduct',
        'products.ProductRequirement',
        
        # 9. Clientes (FK a User)
        'clients.Client',
        'clients.ClientDocument',
        
        # 10. Verificación de identidad
        'identity_verification.IdentityVerification',
        'identity_verification.IdentityVerificationWebhook',
        
        # 11. Préstamos
        'loans.LoanApplication',
        'loans.LoanApplicationDocument',
        'loans.LoanApplicationComment',
        'loans.LoanApplicationStatusHistory',
        
        # 12. Storage
        'storage.FileResource',
        
        # 13. Auditoría (último)
        'audit.AuditLog',
        'audit.SecurityEvent',
    ]
    
    def __init__(
        self, 
        tenant_id: int,
        conflict_strategy: str = 'skip',
        dry_run: bool = False
    ):
        """
        Inicializa el servicio.
        
        Args:
            tenant_id: ID del tenant donde se importarán los datos
            conflict_strategy: Estrategia para conflictos ('skip', 'overwrite', 'fail')
            dry_run: Si True, simula la importación sin escribir en BD
        """
        self.tenant_id = tenant_id
        self.conflict_strategy = conflict_strategy
        self.dry_run = dry_run
        self.stats = {
            'created': {},
            'updated': {},
            'skipped': {},
            'errors': {}
        }
        logger.info(
            f"ImportService inicializado para tenant {tenant_id}, "
            f"estrategia: {conflict_strategy}, dry_run: {dry_run}"
        )
    
    def import_data(self, backup_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Importa datos desde un backup.
        
        Args:
            backup_data: Diccionario con datos del backup
        
        Returns:
            Estadísticas de importación
        """
        logger.info("Iniciando importación de datos")
        
        # Validar estructura del backup
        self._validate_backup_structure(backup_data)
        
        data = backup_data.get('data', {})
        
        # Importar modelos en orden de dependencias
        for model_path in self.IMPORT_ORDER:
            if model_path in data:
                records = data[model_path]
                if records:
                    logger.info(f"Importando {model_path}: {len(records)} registros")
                    self._import_model(model_path, records)
        
        # Resumen
        total_created = sum(self.stats['created'].values())
        total_updated = sum(self.stats['updated'].values())
        total_skipped = sum(self.stats['skipped'].values())
        total_errors = sum(self.stats['errors'].values())
        
        logger.info(
            f"Importación completada: "
            f"{total_created} creados, {total_updated} actualizados, "
            f"{total_skipped} omitidos, {total_errors} errores"
        )
        
        return {
            'created': self.stats['created'],
            'updated': self.stats['updated'],
            'skipped': self.stats['skipped'],
            'errors': self.stats['errors'],
            'total_created': total_created,
            'total_updated': total_updated,
            'total_skipped': total_skipped,
            'total_errors': total_errors,
            'dry_run': self.dry_run
        }
    
    def _validate_backup_structure(self, backup_data: Dict[str, Any]):
        """
        Valida que el backup tenga la estructura correcta.
        
        Raises:
            ValueError: Si la estructura es inválida
        """
        required_fields = ['tenant_id', 'tenant_name', 'export_timestamp', 'data']
        
        for field in required_fields:
            if field not in backup_data:
                raise ValueError(f"Backup inválido: falta campo '{field}'")
        
        if not isinstance(backup_data['data'], dict):
            raise ValueError("Backup inválido: 'data' debe ser un diccionario")
        
        logger.debug("Estructura del backup validada correctamente")
    
    def _import_model(self, model_path: str, records: List[Dict]):
        """
        Importa registros de un modelo específico.
        
        Args:
            model_path: Ruta del modelo (ej: 'clients.Client')
            records: Lista de registros serializados
        """
        try:
            app_label, model_name = model_path.split('.')
            Model = apps.get_model(app_label, model_name)
        except (ValueError, LookupError) as e:
            logger.error(f"Modelo no encontrado: {model_path} - {str(e)}")
            self.stats['errors'][model_path] = len(records)
            return
        
        created_count = 0
        updated_count = 0
        skipped_count = 0
        error_count = 0
        
        for record in records:
            try:
                result = self._import_record(Model, model_path, record)
                
                if result == 'created':
                    created_count += 1
                elif result == 'updated':
                    updated_count += 1
                elif result == 'skipped':
                    skipped_count += 1
                
            except Exception as e:
                error_count += 1
                logger.error(
                    f"Error importando registro de {model_path}: {str(e)}"
                )
        
        # Guardar estadísticas
        if created_count > 0:
            self.stats['created'][model_path] = created_count
        if updated_count > 0:
            self.stats['updated'][model_path] = updated_count
        if skipped_count > 0:
            self.stats['skipped'][model_path] = skipped_count
        if error_count > 0:
            self.stats['errors'][model_path] = error_count
        
        logger.info(
            f"✓ {model_path}: {created_count} creados, {updated_count} actualizados, "
            f"{skipped_count} omitidos, {error_count} errores"
        )
    
    def _import_record(
        self, 
        Model, 
        model_path: str, 
        record: Dict
    ) -> str:
        """
        Importa un registro individual.
        
        Args:
            Model: Clase del modelo Django
            model_path: Ruta del modelo
            record: Registro serializado
        
        Returns:
            'created', 'updated', o 'skipped'
        """
        pk = record.get('pk')
        fields = record.get('fields', {})
        
        # Resolver ForeignKeys (convertir IDs en instancias)
        resolved_fields = self._resolve_foreign_keys(Model, fields)
        
        # Verificar si el registro ya existe
        existing = None
        if pk:
            try:
                existing = Model.objects.get(pk=pk)
            except Model.DoesNotExist:
                pass
        
        # Manejar conflicto según estrategia
        if existing:
            if self.conflict_strategy == 'skip':
                logger.debug(f"Omitiendo {model_path} pk={pk} (ya existe)")
                return 'skipped'
            
            elif self.conflict_strategy == 'overwrite':
                if not self.dry_run:
                    try:
                        # Actualizar campos
                        for field_name, value in resolved_fields.items():
                            setattr(existing, field_name, value)
                        existing.save()
                        
                        # Establecer relaciones ManyToMany
                        self._set_many_to_many(existing, Model, fields)
                    except Exception as e:
                        error_msg = str(e)
                        logger.error(f"Error actualizando {model_path} pk={pk}: {error_msg}")
                        raise
                
                logger.debug(f"Actualizado {model_path} pk={pk}")
                return 'updated'
            
            elif self.conflict_strategy == 'fail':
                raise ValueError(
                    f"Registro duplicado: {model_path} pk={pk}"
                )
        
        # Crear nuevo registro
        if not self.dry_run:
            # Preparar datos para creación
            create_data = resolved_fields.copy()
            if pk:
                create_data['id'] = pk
            
            try:
                instance = Model.objects.create(**create_data)
                
                # Establecer relaciones ManyToMany después de crear
                self._set_many_to_many(instance, Model, fields)
            except Exception as e:
                # Capturar el error y mostrar qué campo causó el problema
                error_msg = str(e)
                logger.error(f"Error creando {model_path} pk={pk}: {error_msg}")
                logger.error(f"Datos que se intentaron crear: {create_data}")
                raise
        
        logger.debug(f"Creado {model_path} pk={pk}")
        return 'created'
    
    def _resolve_foreign_keys(self, Model, fields: Dict) -> Dict:
        """
        Resuelve ForeignKeys convirtiendo IDs en instancias de objetos.
        Separa ManyToMany fields para manejo especial.
        
        Args:
            Model: Clase del modelo Django
            fields: Diccionario de campos con valores
        
        Returns:
            Diccionario con ForeignKeys resueltas (sin M2M)
        """
        resolved = {}
        
        for field_name, value in fields.items():
            # Obtener el campo del modelo
            try:
                # Intentar obtener el campo directamente
                field = None
                actual_field_name = field_name
                
                try:
                    field = Model._meta.get_field(field_name)
                except Exception as e1:
                    # Si el campo termina en _id, intentar sin el _id
                    if field_name.endswith('_id'):
                        base_name = field_name[:-3]
                        try:
                            field = Model._meta.get_field(base_name)
                            actual_field_name = base_name
                        except Exception as e2:
                            # No se pudo encontrar, usar valor directo para campos no-FK
                            resolved[field_name] = value
                            continue
                    else:
                        # No se pudo encontrar, usar valor directo para campos no-FK
                        resolved[field_name] = value
                        continue
                
                # Si es ManyToMany, omitir (se manejará después de crear el objeto)
                if field.many_to_many:
                    continue
                
                # Verificar si es ForeignKey usando diferentes métodos
                # Django tiene varias formas de identificar FKs
                is_fk = (
                    field.many_to_one or  # ForeignKey estándar
                    hasattr(field, 'related_model') and field.related_model is not None or  # Tiene modelo relacionado
                    field.__class__.__name__ == 'ForeignKey'  # Es instancia de ForeignKey
                )
                
                # Si es ForeignKey y el valor es un ID
                if is_fk and value is not None:
                    # Obtener el modelo relacionado
                    related_model = field.related_model
                    
                    # Convertir valor a int si es string numérico
                    fk_value = value
                    if isinstance(value, str) and value.isdigit():
                        fk_value = int(value)
                    
                    try:
                        # Buscar la instancia por ID
                        instance = related_model.objects.get(pk=fk_value)
                        resolved[actual_field_name] = instance
                    except related_model.DoesNotExist:
                        # Si no existe, omitir este campo
                        logger.warning(
                            f"FK no encontrada: {Model.__name__}.{field_name}={fk_value} "
                            f"-> {related_model.__name__} no existe"
                        )
                        continue
                else:
                    # No es FK ni M2M, usar valor directo
                    resolved[actual_field_name] = value
                    
            except Exception as e:
                # Si hay error, loguear con detalles
                logger.error(f"Error procesando {Model.__name__}.{field_name}: {str(e)}")
                import traceback
                logger.error(traceback.format_exc())
                # Usar valor directo si no es FK
                resolved[field_name] = value
                continue
        
        return resolved
    
    def _set_many_to_many(self, instance, Model, fields: Dict):
        """
        Establece relaciones ManyToMany después de crear el objeto.
        
        Args:
            instance: Instancia del modelo creada/actualizada
            Model: Clase del modelo Django
            fields: Diccionario de campos originales
        """
        for field_name, value in fields.items():
            try:
                field = Model._meta.get_field(field_name)
                
                # Solo procesar ManyToMany
                if field.many_to_many and value is not None:
                    related_model = field.related_model
                    
                    # value debería ser una lista de IDs
                    if isinstance(value, list):
                        # Buscar instancias que existan
                        instances = []
                        for pk in value:
                            try:
                                obj = related_model.objects.get(pk=pk)
                                instances.append(obj)
                            except related_model.DoesNotExist:
                                logger.warning(
                                    f"M2M objeto no encontrado: {related_model.__name__} pk={pk}"
                                )
                        
                        # Usar .set() para asignar la relación M2M
                        if instances:
                            getattr(instance, field_name).set(instances)
                            logger.debug(
                                f"M2M {field_name}: {len(instances)} objetos asignados"
                            )
                    
            except Exception as e:
                logger.warning(f"Error estableciendo M2M {field_name}: {str(e)}")
    
    def get_import_preview(self, backup_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Genera preview de lo que se importaría sin ejecutar la importación.
        
        Args:
            backup_data: Diccionario con datos del backup
        
        Returns:
            Preview con conteos y conflictos potenciales
        """
        logger.info("Generando preview de importación")
        
        self._validate_backup_structure(backup_data)
        
        data = backup_data.get('data', {})
        preview = {
            'models': {},
            'total_records': 0,
            'potential_conflicts': 0
        }
        
        for model_path in self.IMPORT_ORDER:
            if model_path in data:
                records = data[model_path]
                if records:
                    try:
                        app_label, model_name = model_path.split('.')
                        Model = apps.get_model(app_label, model_name)
                        
                        # Contar conflictos potenciales
                        conflicts = 0
                        for record in records:
                            pk = record.get('pk')
                            if pk and Model.objects.filter(pk=pk).exists():
                                conflicts += 1
                        
                        preview['models'][model_path] = {
                            'total': len(records),
                            'conflicts': conflicts,
                            'new': len(records) - conflicts
                        }
                        
                        preview['total_records'] += len(records)
                        preview['potential_conflicts'] += conflicts
                    
                    except Exception as e:
                        logger.error(f"Error en preview de {model_path}: {str(e)}")
        
        logger.info(
            f"Preview generado: {preview['total_records']} registros, "
            f"{preview['potential_conflicts']} conflictos potenciales"
        )
        
        return preview
