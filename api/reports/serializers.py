"""
Serializers para el módulo de reportes.
"""
from rest_framework import serializers
from api.reports.models import ReportTemplate, GeneratedReport, VoiceReportRequest


class ReportTemplateSerializer(serializers.ModelSerializer):
    """
    Serializer para plantillas de reportes.
    """
    
    created_by_name = serializers.SerializerMethodField()
    created_by_email = serializers.SerializerMethodField()
    
    class Meta:
        model = ReportTemplate
        fields = [
            'id',
            'scope',
            'category',
            'report_type',
            'name',
            'description',
            'config_json',
            'created_by',
            'created_by_name',
            'created_by_email',
            'is_active',
            'created_at',
            'updated_at'
        ]
        read_only_fields = [
            'id',
            'created_by',
            'created_by_name',
            'created_by_email',
            'created_at',
            'updated_at'
        ]
    
    def get_created_by_name(self, obj):
        """Retorna nombre completo del creador."""
        if obj.created_by:
            return f"{obj.created_by.first_name} {obj.created_by.last_name}".strip()
        return None
    
    def get_created_by_email(self, obj):
        """Retorna email del creador."""
        return obj.created_by.email if obj.created_by else None
    
    def validate_config_json(self, value):
        """Valida que la configuración sea válida."""
        from api.reports.services.report_schema import ReportSchemaService
        
        schema_service = ReportSchemaService()
        is_valid, errors = schema_service.validate_report_config(value)
        
        if not is_valid:
            raise serializers.ValidationError(
                f"Configuración inválida: {', '.join(errors)}"
            )
        
        return value
    
    def validate(self, attrs):
        """Validación a nivel de objeto."""
        # Validar que scope coincida con tenant
        scope = attrs.get('scope')
        request = self.context.get('request')
        
        if scope == 'SAAS':
            # Solo Admin SaaS puede crear plantillas SAAS
            if not hasattr(request.user, 'profile') or not request.user.profile.is_saas_admin():
                raise serializers.ValidationError(
                    "Solo Admin SaaS puede crear plantillas globales"
                )
        elif scope == 'TENANT':
            # Usuario debe tener tenant
            if not hasattr(request, 'tenant') or not request.tenant:
                raise serializers.ValidationError(
                    "Usuario debe pertenecer a un tenant para crear plantillas TENANT"
                )
        
        return attrs
    
    def create(self, validated_data):
        """Crea plantilla asignando created_by."""
        request = self.context.get('request')
        validated_data['created_by'] = request.user
        
        # Asignar institution según scope
        if validated_data['scope'] == 'TENANT':
            validated_data['institution'] = request.tenant
        else:
            validated_data['institution'] = None
        
        return super().create(validated_data)


class ReportTemplateListSerializer(serializers.ModelSerializer):
    """
    Serializer simplificado para listado de plantillas.
    """
    
    created_by_name = serializers.SerializerMethodField()
    
    class Meta:
        model = ReportTemplate
        fields = [
            'id',
            'scope',
            'category',
            'report_type',
            'name',
            'description',
            'created_by_name',
            'is_active',
            'created_at'
        ]
    
    def get_created_by_name(self, obj):
        if obj.created_by:
            return f"{obj.created_by.first_name} {obj.created_by.last_name}".strip()
        return None


class GeneratedReportSerializer(serializers.ModelSerializer):
    """
    Serializer para reportes generados.
    """
    
    requested_by_name = serializers.SerializerMethodField()
    requested_by_email = serializers.SerializerMethodField()
    download_url = serializers.SerializerMethodField()
    file_size_mb = serializers.SerializerMethodField()
    
    class Meta:
        model = GeneratedReport
        fields = [
            'id',
            'scope',
            'category',
            'report_type',
            'requested_by',
            'requested_by_name',
            'requested_by_email',
            'config_json',
            'generation_source',
            'voice_request',
            'status',
            'file_format',
            'file_size_mb',
            'row_count',
            'error_message',
            'download_url',
            'processing_time_seconds',
            'created_at',
            'completed_at'
        ]
        read_only_fields = [
            'id',
            'requested_by',
            'requested_by_name',
            'requested_by_email',
            'status',
            'file_size_mb',
            'row_count',
            'error_message',
            'download_url',
            'processing_time_seconds',
            'created_at',
            'completed_at'
        ]
    
    def get_requested_by_name(self, obj):
        """Retorna nombre completo del solicitante."""
        if obj.requested_by:
            return f"{obj.requested_by.first_name} {obj.requested_by.last_name}".strip()
        return None
    
    def get_requested_by_email(self, obj):
        """Retorna email del solicitante."""
        return obj.requested_by.email if obj.requested_by else None
    
    def get_download_url(self, obj):
        """Retorna URL firmada para descargar el reporte."""
        if obj.status == 'COMPLETED' and obj.file_resource:
            # Generar URL firmada con 1 hora de expiración
            return obj.file_resource.get_signed_url(expires_in=3600)
        return None
    
    def get_file_size_mb(self, obj):
        """Retorna tamaño del archivo en MB."""
        if obj.file_size_bytes:
            return round(obj.file_size_bytes / (1024 * 1024), 2)
        return None


class GeneratedReportListSerializer(serializers.ModelSerializer):
    """
    Serializer simplificado para listado de reportes generados.
    """
    
    requested_by_name = serializers.SerializerMethodField()
    file_size_mb = serializers.SerializerMethodField()
    
    class Meta:
        model = GeneratedReport
        fields = [
            'id',
            'scope',
            'category',
            'report_type',
            'requested_by_name',
            'generation_source',
            'status',
            'file_format',
            'file_size_mb',
            'row_count',
            'created_at',
            'completed_at'
        ]
    
    def get_requested_by_name(self, obj):
        if obj.requested_by:
            return f"{obj.requested_by.first_name} {obj.requested_by.last_name}".strip()
        return None
    
    def get_file_size_mb(self, obj):
        if obj.file_size_bytes:
            return round(obj.file_size_bytes / (1024 * 1024), 2)
        return None


class VoiceReportRequestSerializer(serializers.ModelSerializer):
    """
    Serializer para solicitudes de reporte por voz.
    """
    
    requested_by_name = serializers.SerializerMethodField()
    audio_duration_formatted = serializers.SerializerMethodField()
    
    class Meta:
        model = VoiceReportRequest
        fields = [
            'id',
            'scope',
            'requested_by',
            'requested_by_name',
            'audio_duration_seconds',
            'audio_duration_formatted',
            'transcription',
            'transcription_language',
            'parsed_intent_json',
            'validation_status',
            'missing_fields_json',
            'unsupported_terms_json',
            'groq_transcription_model',
            'groq_chat_model',
            'processing_time_seconds',
            'error_message',
            'created_at'
        ]
        read_only_fields = [
            'id',
            'requested_by',
            'requested_by_name',
            'transcription',
            'transcription_language',
            'parsed_intent_json',
            'validation_status',
            'missing_fields_json',
            'unsupported_terms_json',
            'groq_transcription_model',
            'groq_chat_model',
            'processing_time_seconds',
            'error_message',
            'created_at'
        ]
    
    def get_requested_by_name(self, obj):
        """Retorna nombre completo del solicitante."""
        if obj.requested_by:
            return f"{obj.requested_by.first_name} {obj.requested_by.last_name}".strip()
        return None
    
    def get_audio_duration_formatted(self, obj):
        """Retorna duración formateada (MM:SS)."""
        if obj.audio_duration_seconds:
            minutes = obj.audio_duration_seconds // 60
            seconds = obj.audio_duration_seconds % 60
            return f"{minutes:02d}:{seconds:02d}"
        return None


class ReportConfigSerializer(serializers.Serializer):
    """
    Serializer para configuración de reporte.
    
    Valida la estructura completa de configuración.
    """
    
    scope = serializers.ChoiceField(choices=['TENANT', 'SAAS'])
    category = serializers.CharField(max_length=50)
    report_type = serializers.CharField(max_length=100)
    
    date_range = serializers.JSONField(required=False, allow_null=True)
    filters = serializers.ListField(
        child=serializers.JSONField(),
        required=False,
        default=list
    )
    columns = serializers.ListField(
        child=serializers.CharField(),
        min_length=1
    )
    group_by = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        default=list
    )
    sort = serializers.ListField(
        child=serializers.JSONField(),
        required=False,
        default=list
    )
    format = serializers.ChoiceField(choices=['csv', 'xlsx', 'pdf'], required=True)
    visualization = serializers.JSONField(required=False, allow_null=True)
    
    def validate(self, attrs):
        """Validación completa de configuración."""
        import logging
        logger = logging.getLogger(__name__)
        
        logger.info(f"Validando configuración de reporte: {attrs}")
        
        # Normalizar report_type usando alias comunes
        attrs = self._normalize_report_type(attrs)
        
        from api.reports.services.report_schema import ReportSchemaService
        
        schema_service = ReportSchemaService()
        is_valid, errors = schema_service.validate_report_config(attrs)
        
        if not is_valid:
            logger.error(f"Errores de validación de schema: {errors}")
            raise serializers.ValidationError({
                'config': errors
            })
        
        return attrs
    
    def _normalize_report_type(self, attrs):
        """
        Normaliza el report_type usando alias comunes.
        
        Mapea nombres alternativos al código correcto del reporte.
        """
        import logging
        logger = logging.getLogger(__name__)
        
        # Diccionario de alias comunes
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
        
        scope = attrs.get('scope')
        category = attrs.get('category')
        report_type = attrs.get('report_type')
        
        if scope and category and report_type:
            aliases = REPORT_ALIASES.get(scope, {}).get(category, {})
            if report_type in aliases:
                original = report_type
                attrs['report_type'] = aliases[report_type]
                logger.info(f"Normalizando report_type: '{original}' → '{attrs['report_type']}'")
        
        return attrs


class ReportPreviewRequestSerializer(serializers.Serializer):
    """
    Serializer para solicitud de vista previa.
    """
    
    config = ReportConfigSerializer()
    page = serializers.IntegerField(default=1, min_value=1)
    page_size = serializers.IntegerField(default=50, min_value=1, max_value=100)


class ReportGenerationRequestSerializer(serializers.Serializer):
    """
    Serializer para solicitud de generación de reporte.
    """
    
    config = ReportConfigSerializer()
    save_as_template = serializers.BooleanField(default=False)
    template_name = serializers.CharField(
        max_length=200,
        required=False,
        allow_blank=True
    )
    template_description = serializers.CharField(
        required=False,
        allow_blank=True
    )
    
    def validate(self, attrs):
        """Valida que si save_as_template=True, template_name sea requerido."""
        if attrs.get('save_as_template') and not attrs.get('template_name'):
            raise serializers.ValidationError({
                'template_name': 'Requerido cuando save_as_template=True'
            })
        return attrs


class VisualizationConfigSerializer(serializers.Serializer):
    """
    Serializer para configuración de visualización (gráficos).
    """
    
    requested = serializers.BooleanField(
        help_text="Si el usuario solicitó explícitamente un gráfico"
    )
    recommended = serializers.BooleanField(
        help_text="Si se recomienda incluir un gráfico"
    )
    chart_type = serializers.ChoiceField(
        choices=['BAR', 'HORIZONTAL_BAR', 'LINE', 'PIE', 'DONUT', 'STACKED_BAR', 'NONE'],
        help_text="Tipo de gráfico a generar"
    )
    title = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text="Título del gráfico"
    )
    reason = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text="Razón por la que se recomienda este gráfico"
    )
    
    # Campos opcionales específicos por tipo de gráfico
    x_field = serializers.CharField(required=False, allow_null=True)
    y_field = serializers.CharField(required=False, allow_null=True)
    x_axis = serializers.CharField(required=False, allow_null=True)
    y_axis = serializers.CharField(required=False, allow_null=True)
    label_field = serializers.CharField(required=False, allow_null=True)
    value_field = serializers.CharField(required=False, allow_null=True)
    series_fields = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        default=list
    )
    series_labels = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        default=list
    )


class VoiceReportInterpretRequestSerializer(serializers.Serializer):
    """
    Serializer para solicitud de interpretación de audio.
    """
    
    audio_file = serializers.FileField()
    scope = serializers.ChoiceField(choices=['TENANT', 'SAAS'])
    
    def validate_audio_file(self, value):
        """Valida archivo de audio."""
        # Validar tipo MIME
        allowed_types = [
            'audio/mpeg',
            'audio/wav',
            'audio/x-m4a',
            'audio/ogg',
            'audio/mp3',
            'audio/webm',  # Formato usado por navegadores modernos
            'audio/mp4'    # Formato alternativo para M4A
        ]
        
        if value.content_type not in allowed_types:
            raise serializers.ValidationError(
                f"Formato no soportado: {value.content_type}. "
                f"Formatos permitidos: MP3, WAV, M4A, OGG, WebM"
            )
        
        # Validar tamaño (25 MB)
        max_size = 25 * 1024 * 1024
        if value.size > max_size:
            size_mb = value.size / (1024 * 1024)
            raise serializers.ValidationError(
                f"Archivo muy grande: {size_mb:.2f}MB. Máximo: 25MB"
            )
        
        return value


class VoiceReportInterpretResponseSerializer(serializers.Serializer):
    """
    Serializer para respuesta de interpretación de audio.
    """
    
    voice_request_id = serializers.IntegerField()
    transcription = serializers.CharField()
    language = serializers.CharField(required=False, allow_blank=True)
    proposed_config = ReportConfigSerializer()
    validation_status = serializers.ChoiceField(
        choices=['VALID', 'NEEDS_REVIEW', 'INVALID']
    )
    missing_fields = serializers.ListField(
        child=serializers.CharField(),
        default=list
    )
    unsupported_terms = serializers.ListField(
        child=serializers.JSONField(),
        default=list
    )
    interpretation_notes = serializers.CharField(allow_blank=True)
    confidence = serializers.FloatField(min_value=0, max_value=1)
    visualization = VisualizationConfigSerializer(required=False, allow_null=True)


class ReportCatalogSerializer(serializers.Serializer):
    """
    Serializer para catálogo de reportes disponibles.
    """
    
    scope = serializers.CharField()
    categories = serializers.DictField(
        child=serializers.ListField(
            child=serializers.DictField()
        )
    )


class ReportDefinitionSerializer(serializers.Serializer):
    """
    Serializer para definición de un reporte específico.
    """
    
    name = serializers.CharField()
    description = serializers.CharField()
    datasource = serializers.CharField()
    roles = serializers.ListField(child=serializers.CharField())
    available_columns = serializers.ListField(child=serializers.CharField())
    available_filters = serializers.DictField()
    available_groupings = serializers.ListField(child=serializers.CharField())
    available_sort_fields = serializers.ListField(child=serializers.CharField())
    supported_formats = serializers.ListField(child=serializers.CharField())


class ReportPreviewResponseSerializer(serializers.Serializer):
    """
    Serializer para respuesta de vista previa.
    """
    
    data = serializers.ListField(child=serializers.DictField())
    pagination = serializers.DictField()
    columns = serializers.ListField(child=serializers.CharField())


class ErrorResponseSerializer(serializers.Serializer):
    """
    Serializer para respuestas de error.
    """
    
    error = serializers.CharField()
    details = serializers.DictField(required=False)
    code = serializers.CharField(required=False)
