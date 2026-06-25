"""
Servicio para generación de reportes mediante audio/voz.

Orquesta el flujo completo:
1. Recepción de audio
2. Transcripción con Groq
3. Interpretación de intención
4. Validación
5. Devolución de configuración editable
"""
import os
import time
import logging
from typing import Dict, Any, Optional, Tuple
from django.core.files.uploadedfile import UploadedFile
from django.core.files.base import ContentFile

from api.reports.models import VoiceReportRequest
from api.storage.services import StorageService
from .groq_client import GroqClient, GroqAPIError
from .report_schema import ReportSchemaService
from .report_catalog import ReportCatalogService

logger = logging.getLogger(__name__)


class VoiceReportService:
    """
    Servicio de reportes por voz.
    
    Maneja el proceso completo de interpretación de órdenes
    de voz para generar reportes.
    """
    
    # Formatos de audio permitidos
    ALLOWED_AUDIO_FORMATS = [
        'audio/mpeg',  # MP3
        'audio/wav',   # WAV
        'audio/x-m4a', # M4A
        'audio/ogg',   # OGG
        'audio/mp3',   # MP3 alternativo
        'audio/webm',  # WebM (usado por navegadores modernos)
        'audio/mp4',   # MP4/M4A alternativo
    ]
    
    MAX_AUDIO_SIZE_MB = 25
    
    def __init__(self, user, tenant=None):
        """
        Inicializa el servicio.
        
        Args:
            user: Usuario que solicita el reporte
            tenant: Tenant para reportes TENANT, None para SAAS
        """
        self.user = user
        self.tenant = tenant
        self.groq_client = GroqClient()
        self.schema_service = ReportSchemaService()
        self.catalog_service = ReportCatalogService()
        self.storage_service = StorageService()
    
    def process_voice_request(
        self,
        audio_file: UploadedFile,
        scope: str
    ) -> Tuple[VoiceReportRequest, Dict[str, Any]]:
        """
        Procesa solicitud de reporte por voz.
        
        Args:
            audio_file: Archivo de audio subido
            scope: TENANT o SAAS
        
        Returns:
            (VoiceReportRequest, proposed_config)
        
        Raises:
            ValueError: Si el audio es inválido
            GroqAPIError: Si falla la transcripción o interpretación
        """
        start_time = time.time()
        
        # 1. Validar audio
        self._validate_audio(audio_file)
        
        # 2. Guardar audio en Supabase Storage
        logger.info("Guardando audio en Supabase Storage")
        audio_resource = self._save_audio_to_storage(audio_file)
        
        # 3. Guardar audio temporalmente para procesamiento con Groq
        temp_audio_path = self._save_temp_audio(audio_file)
        
        # 4. Crear registro de solicitud
        voice_request = VoiceReportRequest.objects.create(
            institution=self.tenant,
            scope=scope,
            requested_by=self.user,
            audio_file_resource=audio_resource,
            audio_duration_seconds=0,
            groq_transcription_model=self.groq_client.transcription_model,
            groq_chat_model=self.groq_client.chat_model
        )
        
        # Actualizar entity_id del FileResource
        audio_resource.entity_id = voice_request.id
        audio_resource.save(update_fields=['entity_id'])
        
        try:
            # 5. Transcribir audio
            logger.info(f"Transcribiendo audio para solicitud {voice_request.id}")
            
            transcription_result = self.groq_client.transcribe_audio(
                audio_file_path=temp_audio_path,
                language='es'
            )
            
            voice_request.transcription = transcription_result['text']
            voice_request.transcription_language = transcription_result['language']
            voice_request.audio_duration_seconds = int(transcription_result['duration'])
            voice_request.save()
            
            # 6. Obtener categorías disponibles para el usuario
            available_categories = self._get_available_categories(scope)
            
            # 7. Interpretar intención
            logger.info(f"Interpretando intención para solicitud {voice_request.id}")
            
            intent = self.groq_client.interpret_intent(
                transcription=voice_request.transcription,
                user_scope=scope,
                available_categories=available_categories
            )
            
            voice_request.parsed_intent_json = intent
            
            # 8. Validar intención
            validation_status, missing_fields, unsupported_terms = self._validate_intent(intent)
            
            voice_request.validation_status = validation_status
            voice_request.missing_fields_json = missing_fields
            voice_request.unsupported_terms_json = unsupported_terms
            
            # 9. Calcular tiempo de procesamiento
            processing_time = int(time.time() - start_time)
            voice_request.processing_time_seconds = processing_time
            
            voice_request.save()
            
            # 10. Construir configuración propuesta
            proposed_config = self._build_proposed_config(intent)
            
            # 11. Limpiar archivo temporal
            self._cleanup_temp_file(temp_audio_path)
            
            logger.info(f"Solicitud de voz {voice_request.id} procesada exitosamente")
            
            return voice_request, proposed_config
        
        except GroqAPIError as e:
            logger.error(f"Error de Groq API: {e}")
            voice_request.error_message = str(e)
            voice_request.validation_status = 'INVALID'
            voice_request.save()
            self._cleanup_temp_file(temp_audio_path)
            raise
        
        except Exception as e:
            logger.error(f"Error inesperado: {e}")
            voice_request.error_message = str(e)
            voice_request.validation_status = 'INVALID'
            voice_request.save()
            self._cleanup_temp_file(temp_audio_path)
            raise
    
    def _validate_audio(self, audio_file: UploadedFile):
        """Valida archivo de audio."""
        # Validar tipo MIME
        if audio_file.content_type not in self.ALLOWED_AUDIO_FORMATS:
            raise ValueError(
                f"Formato de audio no soportado: {audio_file.content_type}. "
                f"Formatos permitidos: MP3, WAV, M4A, OGG, WebM"
            )
        
        # Validar tamaño
        size_mb = audio_file.size / (1024 * 1024)
        if size_mb > self.MAX_AUDIO_SIZE_MB:
            raise ValueError(
                f"Archivo de audio muy grande: {size_mb:.2f}MB. "
                f"Máximo permitido: {self.MAX_AUDIO_SIZE_MB}MB"
            )
    
    def _save_audio_to_storage(self, audio_file: UploadedFile) -> 'FileResource':
        """
        Guarda audio en Supabase Storage y crea FileResource.
        
        Returns:
            FileResource creado
        """
        from api.storage.models import FileResource
        import mimetypes
        
        # Leer contenido del archivo
        audio_content = audio_file.read()
        audio_file.seek(0)  # Reset para uso posterior
        
        # Obtener extensión y tipo MIME
        ext = os.path.splitext(audio_file.name)[1].lstrip('.') or 'mp3'
        mime_type = audio_file.content_type or mimetypes.guess_type(audio_file.name)[0] or 'audio/mpeg'
        
        # Construir ruta en storage
        from uuid import uuid4
        file_uuid = uuid4()
        
        if self.tenant:
            # Reportes TENANT: tenants/{tenant_id}/reports/voice/{uuid}.{ext}
            storage_path = f"tenants/{self.tenant.id}/reports/voice/{file_uuid}.{ext}"
        else:
            # Reportes SAAS: saas/reports/voice/{uuid}.{ext}
            storage_path = f"saas/reports/voice/{file_uuid}.{ext}"
        
        # Subir a Supabase Storage
        try:
            self.storage_service.upload_to_storage(
                file_path=storage_path,
                file_content=audio_content,
                content_type=mime_type
            )
        except Exception as e:
            logger.error(f"Error subiendo audio a storage: {e}")
            raise ValueError(f"No se pudo guardar el audio: {str(e)}")
        
        # Calcular checksum
        checksum = self.storage_service.calculate_checksum(audio_content)
        
        # Crear FileResource
        file_resource = FileResource.objects.create(
            tenant=self.tenant,
            resource_type=FileResource.ResourceType.REPORT,
            entity_type='voice_report_request',
            entity_id=None,  # Se actualizará después
            original_name=audio_file.name,
            stored_name=f"{file_uuid}.{ext}",
            file_path=storage_path,
            bucket='uploads',
            mime_type=mime_type,
            extension=ext,
            size=audio_file.size,
            category='voice_audio',
            visibility=FileResource.Visibility.PRIVATE,
            uploaded_by=self.user,
            status=FileResource.Status.ACTIVE,
            checksum=checksum
        )
        
        return file_resource
    
    def _save_temp_audio(self, audio_file: UploadedFile) -> str:
        """
        Guarda audio temporalmente para procesamiento.
        
        Returns:
            Ruta al archivo temporal
        """
        import tempfile
        
        # Obtener extensión del archivo
        ext = os.path.splitext(audio_file.name)[1] or '.mp3'
        
        # Crear archivo temporal
        temp_file = tempfile.NamedTemporaryFile(
            delete=False,
            suffix=ext
        )
        
        # Escribir contenido
        for chunk in audio_file.chunks():
            temp_file.write(chunk)
        
        temp_file.close()
        
        return temp_file.name
    
    def _cleanup_temp_file(self, file_path: str):
        """Elimina archivo temporal."""
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
        except Exception as e:
            logger.warning(f"No se pudo eliminar archivo temporal {file_path}: {e}")
    
    def _get_available_categories(self, scope: str) -> list:
        """Obtiene categorías disponibles para el usuario."""
        # TODO: Obtener roles reales del usuario
        user_roles = ['admin', 'manager', 'analyst']
        
        available_reports = self.catalog_service.get_available_reports(scope, user_roles)
        return list(available_reports.keys())
    
    def _validate_intent(
        self,
        intent: Dict[str, Any]
    ) -> Tuple[str, list, list]:
        """
        Valida intención parseada.
        
        Returns:
            (validation_status, missing_fields, unsupported_terms)
        """
        missing_fields = intent.get('missing_fields', [])
        unsupported_terms = intent.get('unsupported_terms', [])
        
        # Intentar mapear nombre de reporte a código si es necesario
        if intent.get('report_type') and intent.get('category') and intent.get('scope'):
            report_type = self._map_report_name_to_code(
                intent['scope'],
                intent['category'],
                intent['report_type']
            )
            if report_type:
                intent['report_type'] = report_type
            
            # Mapear nombres de columnas en español a inglés
            intent = self._map_column_names(intent)
        
        # Determinar estado de validación
        if unsupported_terms:
            return 'INVALID', missing_fields, unsupported_terms
        
        if missing_fields:
            return 'NEEDS_REVIEW', missing_fields, unsupported_terms
        
        # Validar configuración completa
        config = self._build_proposed_config(intent)
        is_valid, errors = self.schema_service.validate_report_config(config)
        
        if is_valid:
            return 'VALID', missing_fields, unsupported_terms
        else:
            # Agregar errores a missing_fields
            missing_fields.extend(errors)
            return 'NEEDS_REVIEW', missing_fields, unsupported_terms
    
    def _map_report_name_to_code(
        self,
        scope: str,
        category: str,
        report_name_or_code: str
    ) -> str:
        """
        Mapea nombre de reporte a código interno.
        
        Args:
            scope: TENANT o SAAS
            category: Categoría del reporte
            report_name_or_code: Nombre legible o código del reporte
        
        Returns:
            Código del reporte o el valor original si ya es un código válido
        """
        # Diccionario de alias comunes para mapear a códigos correctos
        REPORT_ALIASES = {
            'TENANT': {
                'PRODUCTS': {
                    'credit_products': 'credit_products_catalog',
                    'catalog_of_products': 'credit_products_catalog',
                    'product_catalog': 'credit_products_catalog',
                    'productos_crediticios': 'credit_products_catalog',
                    'productos': 'credit_products_catalog',
                    'catalogo_productos': 'credit_products_catalog',
                    'catalogo_de_productos': 'credit_products_catalog',
                },
                'CREDITS': {
                    'creditos': 'loans_by_status',
                    'solicitudes': 'loans_by_status',
                    'prestamos': 'loans_by_status',
                },
                'CUSTOMERS': {
                    'clientes': 'customers_by_status',
                },
            }
        }
        
        # Obtener todos los reportes de la categoría
        catalog = self.catalog_service.CATALOG.get(scope, {}).get(category, {})
        
        # Si el valor ya es un código válido, devolverlo
        if report_name_or_code in catalog:
            return report_name_or_code
        
        # Buscar en alias
        aliases = REPORT_ALIASES.get(scope, {}).get(category, {})
        if report_name_or_code in aliases:
            mapped_code = aliases[report_name_or_code]
            logger.info(f"Mapeando alias '{report_name_or_code}' a código '{mapped_code}'")
            return mapped_code
        
        # Buscar por nombre
        for report_code, report_def in catalog.items():
            if report_def.get('name', '').lower() == report_name_or_code.lower():
                logger.info(f"Mapeando nombre '{report_name_or_code}' a código '{report_code}'")
                return report_code
        
        # Si no se encuentra, devolver el valor original
        logger.warning(f"No se pudo mapear '{report_name_or_code}' a un código de reporte")
        return report_name_or_code
    
    def _map_column_names(
        self,
        intent: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Mapea nombres de columnas en español a nombres en inglés del catálogo.
        
        Args:
            intent: Intención parseada con posibles nombres en español
        
        Returns:
            Intención con nombres de columnas mapeados
        """
        if not intent.get('scope') or not intent.get('category') or not intent.get('report_type'):
            return intent
        
        # Obtener definición del reporte
        report_def = self.catalog_service.get_report_definition(
            intent['scope'],
            intent['category'],
            intent['report_type']
        )
        
        if not report_def:
            return intent
        
        available_columns = report_def.get('available_columns', [])
        available_groupings = report_def.get('available_groupings', [])
        available_sort_fields = report_def.get('available_sort_fields', [])
        
        # Si las columnas ya están en el catálogo, no hacer nada
        columns = intent.get('columns', [])
        if columns and all(col in available_columns for col in columns):
            return intent
        
        # Mapeo común español -> inglés para reportes
        column_mapping = {
            # === PRODUCTO ===
            'producto': 'product_name',
            'nombre_producto': 'product_name',
            'codigo_producto': 'product_code',
            'tipo_producto': 'product_type',
            
            # === SOLICITUD ===
            'numero_solicitud': 'application_number',
            'solicitud': 'application_number',
            'estado': 'status',
            'status': 'status',
            'nivel_riesgo': 'risk_level',
            'riesgo': 'risk_level',
            'puntaje': 'credit_score',
            'score': 'credit_score',
            'proposito': 'purpose',
            'notas': 'notes',
            'motivo_observacion': 'observation_reason',
            'motivo_rechazo': 'rejection_reason',
            'activo': 'is_active',
            
            # === CLIENTE ===
            'nombre': 'full_name',
            'nombre_completo': 'full_name',
            'nombre_cliente': 'client_name',
            'primer_nombre': 'first_name',
            'apellido': 'last_name',
            'correo': 'email',
            'email': 'email',
            'correo_cliente': 'client_email',
            'telefono': 'phone',
            'phone': 'phone',
            'telefono_cliente': 'client_phone',
            'celular': 'mobile_phone',
            'movil': 'mobile_phone',
            'documento': 'document_number',
            'numero_documento': 'document_number',
            'documento_cliente': 'client_document',
            'tipo_documento': 'document_type',
            'extension': 'document_extension',
            'extension_ci': 'document_extension',
            'fecha_nacimiento': 'birth_date',
            'genero': 'gender',
            'tipo_cliente': 'client_type',
            'direccion': 'address',
            'ciudad': 'city',
            'departamento': 'department',
            'pais': 'country',
            'codigo_postal': 'postal_code',
            
            # === INFORMACIÓN LABORAL ===
            'estado_laboral': 'employment_status',
            'empleo': 'employment_status',
            'tipo_empleo': 'employment_type',
            'empleador': 'employer_name',
            'nombre_empleador': 'employer_name',
            'nit_empleador': 'employer_nit',
            'cargo': 'job_title',
            'puesto': 'job_title',
            'fecha_inicio_laboral': 'employment_start_date',
            'ingreso_mensual': 'monthly_income',
            'ingreso': 'monthly_income',
            'ingresos_adicionales': 'additional_income',
            'ratio_deuda': 'debt_to_income_ratio',
            'deuda_ingreso': 'debt_to_income_ratio',
            
            # === ESTADOS ===
            'estado_kyc': 'kyc_status',
            'kyc': 'kyc_status',
            'estado_verificacion': 'identity_verification_status',
            'verificacion_identidad': 'identity_verification_status',
            'estado_documentos': 'documents_status',
            'documentos': 'documents_status',
            
            # === MONTOS ===
            'monto': 'total_approved_amount',
            'monto_total': 'total_approved_amount',
            'monto_solicitado': 'requested_amount',
            'monto_aprobado': 'approved_amount',
            'monto_desembolsado': 'disbursed_amount',
            'total_solicitado': 'total_requested_amount',
            'total_aprobado': 'total_approved_amount',
            'promedio_monto': 'avg_approved_amount',
            'monto_promedio': 'avg_approved_amount',
            'promedio_solicitado': 'avg_requested_amount',
            'promedio_aprobado': 'avg_approved_amount',
            
            # === PLAZOS Y TASAS ===
            'plazo': 'term_months',
            'plazo_meses': 'term_months',
            'plazo_aprobado': 'approved_term_months',
            'plazo_promedio': 'avg_term_months',
            'tasa': 'approved_interest_rate',
            'tasa_interes': 'approved_interest_rate',
            'tasa_aprobada': 'approved_interest_rate',
            'cuota_mensual': 'monthly_payment',
            'cuota': 'monthly_payment',
            'tasa_aprobacion': 'approval_rate',
            
            # === SUCURSAL ===
            'sucursal': 'branch_name',
            'nombre_sucursal': 'branch_name',
            'ciudad_sucursal': 'branch_city',
            'cantidad_sucursales': 'branch_count',
            
            # === USUARIOS ===
            'asignado_a': 'assigned_to_name',
            'asignado': 'assigned_to_name',
            'revisado_por': 'reviewed_by_name',
            'aprobado_por': 'approved_by_name',
            'creado_por': 'created_by_name',
            'actualizado_por': 'updated_by_name',
            'verificado_por': 'verified_by_name',
            
            # === FECHAS ===
            'fecha_creacion': 'created_at',
            'created_at': 'created_at',
            'fecha_registro': 'created_at',
            'fecha_envio': 'submitted_at',
            'fecha_revision': 'reviewed_at',
            'fecha_aprobacion': 'approved_at',
            'fecha_rechazo': 'rejected_at',
            'fecha_desembolso': 'disbursed_at',
            'fecha_actualizacion': 'updated_at',
            'fecha_verificacion': 'verified_at',
            'ultima_actividad': 'last_activity_at',
            'ultimo_acceso': 'last_login',
            'last_login': 'last_login',
            
            # === ACTIVIDAD ===
            'tiempo_activo': 'active_time',
            'active_time': 'active_time',
            'dispositivo': 'device_type',
            'device_type': 'device_type',
            'tipo_dispositivo': 'device_type',
            
            # === CONTADORES ===
            'cantidad': 'total_applications',
            'total_solicitudes': 'total_applications',
            'solicitudes': 'total_applications',
            'aprobados': 'approved_count',
            'cantidad_aprobados': 'approved_count',
            'rechazados': 'rejected_count',
            'cantidad_rechazados': 'rejected_count',
            'pendientes': 'pending_count',
            'cantidad_pendientes': 'pending_count',
            'creditos_activos': 'total_active_loans',
            'score_promedio': 'avg_credit_score',
            'puntaje_promedio': 'avg_credit_score',
            'ultima_fecha_credito': 'latest_loan_date',
            
            # === TENANT/INSTITUCIÓN ===
            'institucion': 'tenant_name',
            'nombre_institucion': 'tenant_name',
            'codigo_institucion': 'tenant_slug',
            'slug': 'tenant_slug',
            'tipo_institucion': 'institution_type',
            'estado_suscripcion': 'subscription_status',
            'cantidad_usuarios': 'user_count',
            'usuarios': 'user_count',
            'total_clientes': 'total_clients',
            'clientes': 'total_clients',
            'cantidad_creditos_activos': 'active_loans_count',
            'total_usuarios': 'total_users',
            'usuarios_activos': 'active_users',
            'usuarios_inactivos': 'inactive_users',
            'administradores': 'admin_count',
            'gerentes': 'manager_count',
            'analistas': 'analyst_count',
            'oficiales': 'officer_count',
            'cantidad_clientes': 'client_count',
            'ultimo_usuario_creado': 'last_user_created_at',
            
            # === PLAN Y SUSCRIPCIÓN ===
            'plan': 'plan_name',
            'nombre_plan': 'plan_name',
            'estado_pago': 'payment_status',
            'pago': 'payment_status',
            'fecha_inicio': 'start_date',
            'fecha_fin': 'end_date',
            'fin_prueba': 'trial_end_date',
            'fecha_prueba': 'trial_end_date',
            'proxima_facturacion': 'next_billing_date',
            'fecha_facturacion': 'next_billing_date',
            'monto_pagar': 'amount_due',
            'monto_debido': 'amount_due',
            'total_pagado': 'total_paid',
            'pagado': 'total_paid',
            'usuarios_actuales': 'current_users',
            'sucursales_actuales': 'current_branches',
            'dias_activo': 'days_active',
            
            # === DOCUMENTOS ===
            'tipo_documento_requerido': 'document_type',
            'estado_documento': 'document_status',
            'total_documentos': 'total_documents_required',
            'documentos_pendientes': 'pending_documents_count',
            'tipos_pendientes': 'pending_document_types',
            'porcentaje_completitud': 'completion_percentage',
            'completitud': 'completion_percentage',
            'estado_solicitud': 'application_status',
            'dias_desde_envio': 'days_since_submission',
            
            # === VERIFICACIÓN ===
            'estado_verificacion': 'verification_status',
            'metodo_verificacion': 'verification_method',
            'decision': 'decision',
            'proveedor': 'provider',
            'fecha_inicio_verificacion': 'started_at',
            'fecha_finalizacion': 'completed_at',
            'tiempo_procesamiento': 'processing_time_minutes',
        }
        
        # Mapear columnas
        if columns:
            mapped_columns = []
            for col in columns:
                mapped_col = column_mapping.get(col.lower(), col)
                # Verificar si la columna mapeada existe en el catálogo
                if mapped_col in available_columns:
                    # Evitar duplicados
                    if mapped_col not in mapped_columns:
                        mapped_columns.append(mapped_col)
                    if col != mapped_col:
                        logger.info(f"Mapeando columna '{col}' a '{mapped_col}'")
                else:
                    # Si no existe, buscar una columna similar o usar una por defecto
                    logger.warning(f"Columna '{col}' (mapeada a '{mapped_col}') no encontrada en catálogo, omitiendo")
            
            # Si no quedaron columnas válidas, usar columnas por defecto
            if not mapped_columns and available_columns:
                logger.info("No hay columnas válidas, usando columnas por defecto")
                # Usar las primeras 5 columnas disponibles
                mapped_columns = available_columns[:5]
            
            intent['columns'] = mapped_columns
        
        # Mapear agrupaciones
        if intent.get('group_by'):
            mapped_groupings = []
            for group in intent['group_by']:
                mapped_group = column_mapping.get(group.lower(), group)
                if mapped_group in available_groupings:
                    mapped_groupings.append(mapped_group)
                    if group != mapped_group:
                        logger.info(f"Mapeando agrupación '{group}' a '{mapped_group}'")
                else:
                    mapped_groupings.append(group)
            
            intent['group_by'] = mapped_groupings
        
        # Mapear ordenamiento
        if intent.get('sort'):
            mapped_sort = []
            for sort_item in intent['sort']:
                field = sort_item.get('field', '')
                mapped_field = column_mapping.get(field.lower(), field)
                
                # Si el campo mapeado no está en available_sort_fields, usar un campo por defecto
                if mapped_field not in available_sort_fields:
                    # Usar el primer campo disponible como fallback
                    if available_sort_fields:
                        logger.warning(f"Campo de ordenamiento '{field}' no válido, usando '{available_sort_fields[0]}' como fallback")
                        mapped_field = available_sort_fields[0]
                    else:
                        logger.warning(f"No hay campos de ordenamiento disponibles")
                        continue
                
                mapped_sort.append({
                    'field': mapped_field,
                    'direction': sort_item.get('direction', 'asc')
                })
                
                if field != mapped_field:
                    logger.info(f"Mapeando campo de ordenamiento '{field}' a '{mapped_field}'")
            
            intent['sort'] = mapped_sort if mapped_sort else []
        
        return intent
    
    def _build_proposed_config(self, intent: Dict[str, Any]) -> Dict[str, Any]:
        """Construye configuración propuesta desde intención."""
        return {
            'scope': intent.get('scope'),
            'category': intent.get('category'),
            'report_type': intent.get('report_type'),
            'date_range': intent.get('date_range', {}),
            'filters': intent.get('filters', []),
            'columns': intent.get('columns', []),
            'group_by': intent.get('group_by', []),
            'sort': intent.get('sort', []),
            'format': intent.get('format', 'xlsx')
        }
