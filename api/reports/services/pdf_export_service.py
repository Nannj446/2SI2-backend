"""
Servicio de exportación de reportes a PDF.

Genera PDFs profesionales con:
- Encabezado con metadatos
- Resumen ejecutivo
- Gráficos (cuando aplique)
- Tablas de datos
- Pie de página
"""
import io
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, date
from decimal import Decimal

try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter, A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
    from reportlab.platypus import (
        SimpleDocTemplate, Table, TableStyle, Paragraph, 
        Spacer, PageBreak, Image, KeepTogether
    )
    from reportlab.pdfgen import canvas
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False

try:
    import matplotlib
    matplotlib.use('Agg')  # Backend sin GUI
    import matplotlib.pyplot as plt
    from matplotlib.figure import Figure
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False

logger = logging.getLogger(__name__)


class PDFExportService:
    """
    Servicio de exportación de reportes a PDF.
    
    Genera PDFs profesionales con formato corporativo,
    tablas, gráficos y metadatos completos en español.
    """
    
    # Mapeo de nombres técnicos a nombres en español (reutilizado de ExportService)
    COLUMN_LABELS = {
        # Información de solicitud
        'application_number': 'Número de Solicitud',
        'status': 'Estado',
        'risk_level': 'Nivel de Riesgo',
        'credit_score': 'Puntaje de Crédito',
        'purpose': 'Propósito del Crédito',
        'notes': 'Notas',
        'observation_reason': 'Motivo de Observación',
        'rejection_reason': 'Motivo de Rechazo',
        'is_active': 'Activo',
        
        # Cliente
        'client_name': 'Nombre del Cliente',
        'client_document': 'Documento del Cliente',
        'client_email': 'Correo Electrónico',
        'client_phone': 'Teléfono',
        'client_type': 'Tipo de Cliente',
        'full_name': 'Nombre Completo',
        'first_name': 'Nombre',
        'last_name': 'Apellido',
        'document_number': 'Número de Documento',
        'document_type': 'Tipo de Documento',
        'document_extension': 'Extensión CI',
        'birth_date': 'Fecha de Nacimiento',
        'gender': 'Género',
        'email': 'Correo Electrónico',
        'phone': 'Teléfono',
        'mobile_phone': 'Teléfono Móvil',
        'address': 'Dirección',
        'city': 'Ciudad',
        'department': 'Departamento',
        'country': 'País',
        'postal_code': 'Código Postal',
        'kyc_status': 'Estado KYC',
        'employment_status': 'Estado Laboral',
        'employer_name': 'Nombre del Empleador',
        'employer_nit': 'NIT del Empleador',
        'job_title': 'Cargo',
        'employment_start_date': 'Fecha de Inicio Laboral',
        'monthly_income': 'Ingreso Mensual',
        'additional_income': 'Ingresos Adicionales',
        'verified_at': 'Fecha de Verificación',
        'verified_by_name': 'Verificado Por',
        
        # Producto
        'product_name': 'Producto',
        'product_code': 'Código de Producto',
        'product_type': 'Tipo de Producto',
        
        # Montos
        'requested_amount': 'Monto Solicitado',
        'approved_amount': 'Monto Aprobado',
        'disbursed_amount': 'Monto Desembolsado',
        'total_requested_amount': 'Total Solicitado',
        'total_approved_amount': 'Total Aprobado',
        'avg_requested_amount': 'Promedio Solicitado',
        'avg_approved_amount': 'Promedio Aprobado',
        
        # Plazos y tasas
        'term_months': 'Plazo (Meses)',
        'approved_term_months': 'Plazo Aprobado (Meses)',
        'interest_rate': 'Tasa de Interés',
        'approved_interest_rate': 'Tasa de Interés Aprobada',
        'monthly_payment': 'Cuota Mensual',
        'debt_to_income_ratio': 'Ratio Deuda/Ingreso',
        'avg_term_months': 'Promedio Plazo (Meses)',
        
        # Sucursal
        'branch_name': 'Sucursal',
        'branch_city': 'Ciudad',
        'branch_count': 'Cantidad de Sucursales',
        
        # Usuario asignado
        'assigned_to_name': 'Asignado a',
        'reviewed_by_name': 'Revisado Por',
        'approved_by_name': 'Aprobado Por',
        'created_by_name': 'Creado Por',
        'updated_by_name': 'Actualizado Por',
        
        # Estados de verificación
        'identity_verification_status': 'Estado de Verificación de Identidad',
        'documents_status': 'Estado de Documentos',
        'employment_type': 'Tipo de Empleo',
        
        # Fechas
        'created_at': 'Fecha de Creación',
        'submitted_at': 'Fecha de Envío',
        'reviewed_at': 'Fecha de Revisión',
        'approved_at': 'Fecha de Aprobación',
        'rejected_at': 'Fecha de Rechazo',
        'disbursed_at': 'Fecha de Desembolso',
        'updated_at': 'Fecha de Actualización',
        
        # Contadores
        'total_applications': 'Total de Solicitudes',
        'approved_count': 'Aprobadas',
        'rejected_count': 'Rechazadas',
        'pending_count': 'Pendientes',
        'approval_rate': 'Tasa de Aprobación (%)',
        'total_active_loans': 'Total de Créditos Activos',
        'avg_credit_score': 'Puntaje de Crédito Promedio',
        'latest_loan_date': 'Fecha del Último Crédito',
        
        # Tenant
        'tenant_name': 'Institución',
        'tenant_slug': 'Código de Institución',
        'institution_type': 'Tipo de Institución',
        'subscription_status': 'Estado de Suscripción',
        'user_count': 'Cantidad de Usuarios',
        'total_clients': 'Total de Clientes',
        'active_loans_count': 'Créditos Activos',
        'total_users': 'Total de Usuarios',
        'active_users': 'Usuarios Activos',
        'inactive_users': 'Usuarios Inactivos',
        'admin_count': 'Administradores',
        'manager_count': 'Gerentes',
        'analyst_count': 'Analistas',
        'officer_count': 'Oficiales',
        'client_count': 'Clientes',
        
        # Plan y suscripción
        'plan_name': 'Plan',
        'payment_status': 'Estado de Pago',
        'start_date': 'Fecha de Inicio',
        'end_date': 'Fecha de Fin',
        'amount_due': 'Monto a Pagar',
        'total_paid': 'Total Pagado',
        'current_users': 'Usuarios Actuales',
        'current_branches': 'Sucursales Actuales',
        'days_active': 'Días Activo',
        
        # Documentos
        'document_status': 'Estado del Documento',
        'total_documents_required': 'Total de Documentos Requeridos',
        'pending_documents_count': 'Documentos Pendientes',
        'pending_document_types': 'Tipos de Documentos Pendientes',
        'completion_percentage': 'Porcentaje de Completitud (%)',
        'application_status': 'Estado de Solicitud',
        'days_since_submission': 'Días desde Envío',
        
        # Verificación
        'decision': 'Decisión',
        'provider': 'Proveedor',
        'started_at': 'Fecha de Inicio',
        'completed_at': 'Fecha de Finalización',
        'processing_time_minutes': 'Tiempo de Procesamiento (min)',
    }
    
    # Títulos de reportes en español
    REPORT_TITLES = {
        'loans_by_product': 'Reporte de Créditos por Producto',
        'loans_by_branch': 'Reporte de Créditos por Sucursal',
        'loans_by_status': 'Reporte de Créditos por Estado',
        'loans_by_date_range': 'Reporte de Créditos por Rango de Fechas',
        'active_loans': 'Reporte de Créditos Activos',
        'customers_registered': 'Reporte de Clientes Registrados',
        'customers_by_status': 'Reporte de Clientes por Estado',
        'customers_with_active_loans': 'Reporte de Clientes con Créditos Activos',
        'applications_with_pending_documents': 'Reporte de Solicitudes con Documentos Pendientes',
        'verifications_by_status': 'Reporte de Verificaciones por Estado',
        'tenants_by_status': 'Reporte de Tenants por Estado',
        'users_by_tenant': 'Reporte de Usuarios por Tenant',
        'subscriptions_by_status': 'Reporte de Suscripciones por Estado',
    }
    
    # Colores corporativos
    COLOR_PRIMARY = colors.HexColor('#1F4E78')  # Azul corporativo
    COLOR_SECONDARY = colors.HexColor('#4472C4')  # Azul claro
    COLOR_ACCENT = colors.HexColor('#ED7D31')  # Naranja
    COLOR_GRAY_LIGHT = colors.HexColor('#F8F9FA')  # Gris muy claro
    COLOR_GRAY = colors.HexColor('#666666')  # Gris medio
    COLOR_GRAY_DARK = colors.HexColor('#333333')  # Gris oscuro
    
    def __init__(self):
        """Inicializa el servicio de exportación PDF."""
        if not PDF_AVAILABLE:
            raise ImportError(
                "reportlab no está instalado. "
                "Instalar con: pip install reportlab"
            )
        
        self.styles = getSampleStyleSheet()
        self._setup_custom_styles()
    
    def _setup_custom_styles(self):
        """Configura estilos personalizados para el PDF."""
        # Estilo para título principal
        self.styles.add(ParagraphStyle(
            name='ReportTitle',
            parent=self.styles['Heading1'],
            fontSize=18,
            textColor=self.COLOR_PRIMARY,
            spaceAfter=12,
            alignment=TA_LEFT,
            fontName='Helvetica-Bold'
        ))
        
        # Estilo para subtítulos
        self.styles.add(ParagraphStyle(
            name='ReportSubtitle',
            parent=self.styles['Heading2'],
            fontSize=14,
            textColor=self.COLOR_SECONDARY,
            spaceAfter=10,
            spaceBefore=10,
            fontName='Helvetica-Bold'
        ))
        
        # Estilo para metadatos
        self.styles.add(ParagraphStyle(
            name='Metadata',
            parent=self.styles['Normal'],
            fontSize=9,
            textColor=self.COLOR_GRAY,
            spaceAfter=4
        ))
        
        # Estilo para metadatos en negrita
        self.styles.add(ParagraphStyle(
            name='MetadataLabel',
            parent=self.styles['Normal'],
            fontSize=9,
            textColor=self.COLOR_GRAY_DARK,
            fontName='Helvetica-Bold',
            spaceAfter=4
        ))
    
    def export(
        self,
        data: List[Dict[str, Any]],
        columns: List[str],
        report_metadata: Optional[Dict[str, Any]] = None,
        chart_config: Optional[Dict[str, Any]] = None
    ) -> bytes:
        """
        Exporta datos a PDF profesional.
        
        Args:
            data: Lista de diccionarios con datos
            columns: Lista de columnas a incluir
            report_metadata: Metadatos del reporte (título, usuario, filtros, etc.)
            chart_config: Configuración del gráfico a generar
        
        Returns:
            Contenido PDF en bytes
        """
        logger.info(f"Generando PDF con {len(data)} filas y {len(columns)} columnas")
        
        # Generar imagen del gráfico si hay configuración
        chart_image = None
        if chart_config and MATPLOTLIB_AVAILABLE and data:
            try:
                chart_image = self._generate_chart_image(data, chart_config)
            except Exception as e:
                logger.error(f"Error generando gráfico para PDF: {e}", exc_info=True)
        
        # Crear buffer en memoria
        buffer = io.BytesIO()
        
        # Crear documento PDF
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            rightMargin=0.75*inch,
            leftMargin=0.75*inch,
            topMargin=0.75*inch,
            bottomMargin=0.75*inch,
            title=self._get_report_title(report_metadata)
        )
        
        # Construir elementos del PDF
        elements = []
        
        # 1. Encabezado con metadatos
        elements.extend(self._build_header(report_metadata, len(data)))
        elements.append(Spacer(1, 0.3*inch))
        
        # 2. Resumen ejecutivo (si hay datos agregados)
        if self._should_include_summary(data, columns):
            elements.extend(self._build_summary(data, columns))
            elements.append(Spacer(1, 0.2*inch))
        
        # 3. Gráfico (si se generó)
        if chart_image:
            elements.extend(self._build_chart_section(chart_image, report_metadata))
            elements.append(Spacer(1, 0.2*inch))
        
        # 4. Tabla de datos
        elements.extend(self._build_data_table(data, columns))
        
        # Construir PDF
        doc.build(
            elements,
            onFirstPage=self._add_page_number,
            onLaterPages=self._add_page_number
        )
        
        # Obtener contenido
        pdf_content = buffer.getvalue()
        buffer.close()
        
        logger.info(f"PDF generado exitosamente. Tamaño: {len(pdf_content)} bytes")
        return pdf_content
    
    def _build_header(
        self,
        report_metadata: Optional[Dict[str, Any]],
        total_rows: int
    ) -> List:
        """
        Construye el encabezado del PDF con metadatos.
        
        Args:
            report_metadata: Metadatos del reporte
            total_rows: Total de filas de datos
        
        Returns:
            Lista de elementos de ReportLab
        """
        elements = []
        
        if not report_metadata:
            return elements
        
        # Título del reporte
        report_type = report_metadata.get('report_type', '')
        title = self.REPORT_TITLES.get(report_type, 'Reporte de Datos')
        elements.append(Paragraph(title, self.styles['ReportTitle']))
        
        # Línea separadora
        elements.append(Spacer(1, 0.1*inch))
        
        # Metadatos en tabla de 2 columnas
        metadata_data = []
        
        # Fecha de generación
        metadata_data.append([
            Paragraph('<b>Fecha de Generación:</b>', self.styles['MetadataLabel']),
            Paragraph(datetime.now().strftime('%d/%m/%Y %H:%M:%S'), self.styles['Metadata'])
        ])
        
        # Usuario
        if report_metadata.get('user_name'):
            metadata_data.append([
                Paragraph('<b>Generado por:</b>', self.styles['MetadataLabel']),
                Paragraph(report_metadata['user_name'], self.styles['Metadata'])
            ])
        
        # Institución
        if report_metadata.get('tenant_name'):
            metadata_data.append([
                Paragraph('<b>Institución:</b>', self.styles['MetadataLabel']),
                Paragraph(report_metadata['tenant_name'], self.styles['Metadata'])
            ])
        
        # Total de registros
        metadata_data.append([
            Paragraph('<b>Total de Registros:</b>', self.styles['MetadataLabel']),
            Paragraph(str(total_rows), self.styles['Metadata'])
        ])
        
        # Filtros aplicados
        if report_metadata.get('filters'):
            filters_text = self._format_filters(report_metadata['filters'])
            if filters_text:
                metadata_data.append([
                    Paragraph('<b>Filtros Aplicados:</b>', self.styles['MetadataLabel']),
                    Paragraph(filters_text, self.styles['Metadata'])
                ])
        
        # Crear tabla de metadatos
        metadata_table = Table(metadata_data, colWidths=[2*inch, 4.5*inch])
        metadata_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 0),
            ('TOPPADDING', (0, 0), (-1, -1), 2),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ]))
        
        elements.append(metadata_table)
        
        return elements
    
    def _build_summary(
        self,
        data: List[Dict[str, Any]],
        columns: List[str]
    ) -> List:
        """
        Construye sección de resumen ejecutivo.
        
        Args:
            data: Datos del reporte
            columns: Columnas del reporte
        
        Returns:
            Lista de elementos de ReportLab
        """
        elements = []
        
        elements.append(Paragraph('Resumen Ejecutivo', self.styles['ReportSubtitle']))
        
        summary_data = []
        
        # Detectar métricas agregadas en las columnas
        aggregated_metrics = [
            col for col in columns 
            if any(keyword in col for keyword in [
                'total_', 'avg_', 'count', 'rate', 'percentage'
            ])
        ]
        
        if aggregated_metrics and data:
            # Mostrar primeras métricas agregadas
            first_row = data[0]
            for metric in aggregated_metrics[:5]:  # Máximo 5 métricas
                label = self._get_column_label(metric)
                value = first_row.get(metric)
                formatted_value = self._format_value_for_display(value, metric)
                
                summary_data.append([
                    Paragraph(f'<b>{label}:</b>', self.styles['MetadataLabel']),
                    Paragraph(formatted_value, self.styles['Metadata'])
                ])
        
        if summary_data:
            summary_table = Table(summary_data, colWidths=[3*inch, 3.5*inch])
            summary_table.setStyle(TableStyle([
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('LEFTPADDING', (0, 0), (-1, -1), 0),
                ('RIGHTPADDING', (0, 0), (-1, -1), 0),
                ('TOPPADDING', (0, 0), (-1, -1), 2),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
            ]))
            elements.append(summary_table)
        
        return elements
    
    def _build_chart_section(
        self,
        chart_image: bytes,
        report_metadata: Optional[Dict[str, Any]]
    ) -> List:
        """
        Construye sección con gráfico.
        
        Args:
            chart_image: Imagen del gráfico en bytes
            report_metadata: Metadatos del reporte
        
        Returns:
            Lista de elementos de ReportLab
        """
        elements = []
        
        # Título de la sección
        chart_title = 'Visualización de Datos'
        if report_metadata and report_metadata.get('visualization'):
            viz_config = report_metadata['visualization']
            if viz_config.get('title'):
                chart_title = viz_config['title']
        
        elements.append(Paragraph(chart_title, self.styles['ReportSubtitle']))
        elements.append(Spacer(1, 0.1*inch))
        
        # Agregar imagen del gráfico
        try:
            img_buffer = io.BytesIO(chart_image)
            img = Image(img_buffer, width=6*inch, height=4*inch)
            elements.append(img)
        except Exception as e:
            logger.error(f"Error al agregar gráfico al PDF: {e}")
            elements.append(Paragraph(
                '<i>Error al cargar gráfico</i>',
                self.styles['Metadata']
            ))
        
        return elements
    
    def _build_data_table(
        self,
        data: List[Dict[str, Any]],
        columns: List[str]
    ) -> List:
        """
        Construye tabla de datos con formato profesional y texto ajustado.
        
        Args:
            data: Datos del reporte
            columns: Columnas a incluir
        
        Returns:
            Lista de elementos de ReportLab
        """
        elements = []
        
        if not data:
            elements.append(Paragraph(
                '<i>No hay datos para mostrar</i>',
                self.styles['Metadata']
            ))
            return elements
        
        # Título de la sección
        elements.append(Paragraph('Datos Detallados', self.styles['ReportSubtitle']))
        elements.append(Spacer(1, 0.1*inch))
        
        # Preparar datos de la tabla
        table_data = []
        
        # Encabezados con Paragraph para word wrap
        headers = []
        for col in columns:
            label = self._get_column_label(col)
            # Usar Paragraph para permitir word wrap en encabezados
            header_para = Paragraph(
                f'<b>{label}</b>',
                ParagraphStyle(
                    'HeaderCell',
                    parent=self.styles['Normal'],
                    fontSize=8,
                    textColor=colors.white,
                    alignment=TA_CENTER,
                    fontName='Helvetica-Bold',
                    leading=10
                )
            )
            headers.append(header_para)
        table_data.append(headers)
        
        # Filas de datos con Paragraph para word wrap
        cell_style = ParagraphStyle(
            'DataCell',
            parent=self.styles['Normal'],
            fontSize=7,
            textColor=self.COLOR_GRAY_DARK,
            alignment=TA_LEFT,
            leading=9,
            wordWrap='CJK'  # Permite word wrap
        )
        
        for row in data:
            table_row = []
            for col in columns:
                value = row.get(col)
                formatted_value = self._format_value_for_table(value, col)
                # Usar Paragraph para permitir word wrap
                cell_para = Paragraph(formatted_value, cell_style)
                table_row.append(cell_para)
            table_data.append(table_row)
        
        # Calcular anchos de columna de forma inteligente
        col_widths = self._calculate_column_widths(columns, data)
        
        # Crear tabla con word wrap habilitado
        table = Table(
            table_data,
            colWidths=col_widths,
            repeatRows=1,
            splitByRow=True  # Permite dividir tabla entre páginas
        )
        
        # Aplicar estilos mejorados
        table.setStyle(TableStyle([
            # Encabezados
            ('BACKGROUND', (0, 0), (-1, 0), self.COLOR_SECONDARY),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('VALIGN', (0, 0), (-1, 0), 'MIDDLE'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 8),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
            ('TOPPADDING', (0, 0), (-1, 0), 6),
            ('LEFTPADDING', (0, 0), (-1, 0), 4),
            ('RIGHTPADDING', (0, 0), (-1, 0), 4),
            
            # Datos
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 7),
            ('ALIGN', (0, 1), (-1, -1), 'LEFT'),
            ('VALIGN', (0, 1), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 1), (-1, -1), 4),
            ('RIGHTPADDING', (0, 1), (-1, -1), 4),
            ('TOPPADDING', (0, 1), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 4),
            
            # Bordes
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('LINEBELOW', (0, 0), (-1, 0), 1.5, self.COLOR_PRIMARY),
            
            # Filas alternadas
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, self.COLOR_GRAY_LIGHT]),
        ]))
        
        elements.append(table)
        
        return elements
    
    def _calculate_column_widths(
        self,
        columns: List[str],
        data: List[Dict[str, Any]]
    ) -> List[float]:
        """
        Calcula anchos de columna de forma inteligente basándose en el contenido.
        
        Args:
            columns: Lista de columnas
            data: Datos del reporte
        
        Returns:
            Lista de anchos en inches
        """
        available_width = 6.5 * inch
        num_columns = len(columns)
        
        # Anchos mínimos y máximos
        min_width = 0.8 * inch
        max_width = 2.5 * inch
        
        # Calcular peso de cada columna basándose en el tipo de dato
        column_weights = []
        for col in columns:
            # Determinar peso basándose en el tipo de columna
            if any(keyword in col for keyword in ['name', 'description', 'notes', 'reason', 'address']):
                weight = 3  # Columnas de texto largo
            elif any(keyword in col for keyword in ['email', 'document', 'phone']):
                weight = 2  # Columnas de texto medio
            elif any(keyword in col for keyword in ['amount', 'income', 'payment']):
                weight = 1.5  # Columnas numéricas con formato
            elif any(keyword in col for keyword in ['date', 'at']):
                weight = 1.5  # Columnas de fecha
            elif any(keyword in col for keyword in ['status', 'type', 'code']):
                weight = 1  # Columnas cortas
            else:
                weight = 1.2  # Peso por defecto
            
            column_weights.append(weight)
        
        # Calcular anchos proporcionales
        total_weight = sum(column_weights)
        col_widths = []
        
        for weight in column_weights:
            width = (weight / total_weight) * available_width
            # Aplicar límites
            width = max(min_width, min(width, max_width))
            col_widths.append(width)
        
        # Ajustar si la suma excede el ancho disponible
        total_width = sum(col_widths)
        if total_width > available_width:
            scale_factor = available_width / total_width
            col_widths = [w * scale_factor for w in col_widths]
        
        return col_widths
    
    def _format_value_for_table(self, value: Any, column: str) -> str:
        """
        Formatea un valor para mostrar en tabla del PDF con truncamiento inteligente.
        
        Args:
            value: Valor a formatear
            column: Nombre de la columna (para contexto)
        
        Returns:
            String formateado y truncado si es necesario
        """
        if value is None:
            return ''
        
        if isinstance(value, bool):
            return 'Sí' if value else 'No'
        
        if isinstance(value, (datetime, date)):
            if isinstance(value, datetime):
                return value.strftime('%d/%m/%Y %H:%M')
            return value.strftime('%d/%m/%Y')
        
        if isinstance(value, (int, float, Decimal)):
            # Formatear montos
            if 'amount' in column or 'income' in column or 'payment' in column:
                return f"${value:,.2f}"
            
            # Formatear porcentajes
            if 'rate' in column or 'percentage' in column:
                return f"{value:.2f}%"
            
            # Formatear números con separadores de miles
            if isinstance(value, int):
                return f"{value:,}"
            
            return f"{value:,.2f}"
        
        # Convertir a string y aplicar truncamiento inteligente
        str_value = str(value)
        
        # Límites de longitud según tipo de columna
        if any(keyword in column for keyword in ['description', 'notes', 'reason', 'address']):
            max_length = 100  # Columnas de texto largo
        elif any(keyword in column for keyword in ['name', 'email']):
            max_length = 50  # Columnas de texto medio
        else:
            max_length = 40  # Columnas cortas
        
        if len(str_value) > max_length:
            return str_value[:max_length-3] + '...'
        
        return str_value
    
    def _add_page_number(self, canvas, doc):
        """
        Agrega número de página al pie.
        
        Args:
            canvas: Canvas de ReportLab
            doc: Documento de ReportLab
        """
        page_num = canvas.getPageNumber()
        text = f"Página {page_num}"
        canvas.saveState()
        canvas.setFont('Helvetica', 8)
        canvas.setFillColor(self.COLOR_GRAY)
        canvas.drawRightString(
            doc.pagesize[0] - 0.75*inch,
            0.5*inch,
            text
        )
        canvas.drawString(
            0.75*inch,
            0.5*inch,
            "Generado por FinCore"
        )
        canvas.restoreState()
    
    def _get_report_title(self, report_metadata: Optional[Dict[str, Any]]) -> str:
        """Obtiene el título del reporte."""
        if not report_metadata:
            return 'Reporte de Datos'
        
        report_type = report_metadata.get('report_type', '')
        return self.REPORT_TITLES.get(report_type, 'Reporte de Datos')
    
    def _get_column_label(self, column: str) -> str:
        """Obtiene la etiqueta en español para una columna."""
        return self.COLUMN_LABELS.get(column, self._format_column_header(column))
    
    def _format_column_header(self, column: str) -> str:
        """Formatea nombre de columna para encabezado."""
        return column.replace('_', ' ').title()
    
    def _format_value_for_display(self, value: Any, column: str) -> str:
        """
        Formatea un valor para mostrar en el PDF.
        
        Args:
            value: Valor a formatear
            column: Nombre de la columna (para contexto)
        
        Returns:
            String formateado
        """
        if value is None:
            return ''
        
        if isinstance(value, bool):
            return 'Sí' if value else 'No'
        
        if isinstance(value, (datetime, date)):
            if isinstance(value, datetime):
                return value.strftime('%d/%m/%Y %H:%M')
            return value.strftime('%d/%m/%Y')
        
        if isinstance(value, (int, float, Decimal)):
            # Formatear montos
            if 'amount' in column or 'income' in column or 'payment' in column:
                return f"${value:,.2f}"
            
            # Formatear porcentajes
            if 'rate' in column or 'percentage' in column:
                return f"{value:.2f}%"
            
            # Formatear números con separadores de miles
            if isinstance(value, int):
                return f"{value:,}"
            
            return f"{value:,.2f}"
        
        # Limitar longitud de strings
        str_value = str(value)
        if len(str_value) > 50:
            return str_value[:47] + '...'
        
        return str_value
    
    def _format_filters(self, filters: Dict[str, Any]) -> str:
        """
        Formatea filtros para mostrar.
        
        Args:
            filters: Diccionario de filtros
        
        Returns:
            String formateado con filtros
        """
        if not filters:
            return ''
        
        filter_parts = []
        if isinstance(filters, list):
            for f in filters:
                if isinstance(f, dict):
                    label = self._get_column_label(f.get('field', ''))
                    value = f.get('value', '')
                    if isinstance(value, list):
                        value_str = ', '.join(str(v) for v in value)
                    else:
                        value_str = str(value)
                    filter_parts.append(f"{label}: {value_str}")
        else:
            for key, value in filters.items():
                label = self._get_column_label(key)
                if isinstance(value, list):
                    value_str = ', '.join(str(v) for v in value)
                else:
                    value_str = str(value)
                filter_parts.append(f"{label}: {value_str}")
        
        return ' | '.join(filter_parts)
    
    def _should_include_summary(
        self,
        data: List[Dict[str, Any]],
        columns: List[str]
    ) -> bool:
        """
        Determina si se debe incluir resumen ejecutivo.
        
        Args:
            data: Datos del reporte
            columns: Columnas del reporte
        
        Returns:
            True si se debe incluir resumen
        """
        if not data:
            return False
        
        # Incluir resumen si hay métricas agregadas
        aggregated_metrics = [
            col for col in columns 
            if any(keyword in col for keyword in [
                'total_', 'avg_', 'count', 'rate', 'percentage'
            ])
        ]
        
        return len(aggregated_metrics) > 0

    def _generate_chart_image(
        self,
        data: List[Dict[str, Any]],
        chart_config: Dict[str, Any]
    ) -> bytes:
        """
        Genera imagen del gráfico usando matplotlib.
        
        Args:
            data: Datos del reporte
            chart_config: Configuración del gráfico
        
        Returns:
            Imagen PNG en bytes
        """
        if not MATPLOTLIB_AVAILABLE:
            logger.warning("matplotlib no está disponible, no se puede generar gráfico")
            return None
        
        chart_type = chart_config.get('type', 'bar').lower()
        
        # Crear figura
        fig = Figure(figsize=(8, 5), dpi=100)
        ax = fig.add_subplot(111)
        
        try:
            if chart_type in ['bar', 'horizontal_bar']:
                self._render_matplotlib_bar(ax, data, chart_config, chart_type == 'horizontal_bar')
            elif chart_type == 'line':
                self._render_matplotlib_line(ax, data, chart_config)
            elif chart_type in ['pie', 'donut']:
                self._render_matplotlib_pie(ax, data, chart_config, chart_type == 'donut')
            else:
                # Tipo no soportado, usar gráfico de barras por defecto
                logger.warning(f"Tipo de gráfico '{chart_type}' no soportado en PDF, usando 'bar'")
                self._render_matplotlib_bar(ax, data, chart_config, False)
            
            # Ajustar layout
            fig.tight_layout()
            
            # Guardar en buffer
            buffer = io.BytesIO()
            fig.savefig(buffer, format='png', bbox_inches='tight', dpi=100)
            buffer.seek(0)
            image_bytes = buffer.getvalue()
            buffer.close()
            
            # Limpiar figura
            plt.close(fig)
            
            return image_bytes
            
        except Exception as e:
            logger.error(f"Error generando gráfico matplotlib: {e}", exc_info=True)
            plt.close(fig)
            return None
    
    def _render_matplotlib_bar(
        self,
        ax,
        data: List[Dict[str, Any]],
        chart_config: Dict[str, Any],
        horizontal: bool
    ):
        """Renderiza gráfico de barras con matplotlib."""
        x_axis = chart_config.get('x_axis', 'name')
        y_axes = chart_config.get('y_axes', [])
        
        # Si no hay y_axes, usar y_axis o data_key
        if not y_axes:
            y_key = chart_config.get('y_axis') or chart_config.get('data_key', 'value')
            y_axes = [{'key': y_key, 'color': '#3b82f6', 'label': y_key}]
        
        # Extraer datos
        labels = [str(row.get(x_axis, '')) for row in data]
        
        # Renderizar cada serie
        bar_width = 0.8 / len(y_axes)
        for i, y_axis_config in enumerate(y_axes):
            y_key = y_axis_config['key']
            values = [float(row.get(y_key, 0)) for row in data]
            color = y_axis_config.get('color', '#3b82f6')
            label = y_axis_config.get('label', y_key)
            
            if horizontal:
                positions = [j + i * bar_width for j in range(len(labels))]
                ax.barh(positions, values, bar_width, label=label, color=color)
            else:
                positions = [j + i * bar_width for j in range(len(labels))]
                ax.bar(positions, values, bar_width, label=label, color=color)
        
        # Configurar ejes
        if horizontal:
            ax.set_yticks([j + bar_width * (len(y_axes) - 1) / 2 for j in range(len(labels))])
            ax.set_yticklabels(labels)
            ax.set_xlabel('Valor')
        else:
            ax.set_xticks([j + bar_width * (len(y_axes) - 1) / 2 for j in range(len(labels))])
            ax.set_xticklabels(labels, rotation=45, ha='right')
            ax.set_ylabel('Valor')
        
        if len(y_axes) > 1:
            ax.legend()
        
        ax.grid(axis='y' if not horizontal else 'x', alpha=0.3)
    
    def _render_matplotlib_line(
        self,
        ax,
        data: List[Dict[str, Any]],
        chart_config: Dict[str, Any]
    ):
        """Renderiza gráfico de líneas con matplotlib."""
        x_axis = chart_config.get('x_axis', 'name')
        y_axes = chart_config.get('y_axes', [])
        
        # Si no hay y_axes, usar y_axis o data_key
        if not y_axes:
            y_key = chart_config.get('y_axis') or chart_config.get('data_key', 'value')
            y_axes = [{'key': y_key, 'color': '#10b981', 'label': y_key}]
        
        # Extraer datos
        labels = [str(row.get(x_axis, '')) for row in data]
        x_positions = range(len(labels))
        
        # Renderizar cada serie
        for y_axis_config in y_axes:
            y_key = y_axis_config['key']
            values = [float(row.get(y_key, 0)) for row in data]
            color = y_axis_config.get('color', '#10b981')
            label = y_axis_config.get('label', y_key)
            
            ax.plot(x_positions, values, marker='o', label=label, color=color, linewidth=2)
        
        # Configurar ejes
        ax.set_xticks(x_positions)
        ax.set_xticklabels(labels, rotation=45, ha='right')
        ax.set_ylabel('Valor')
        
        if len(y_axes) > 1:
            ax.legend()
        
        ax.grid(alpha=0.3)
    
    def _render_matplotlib_pie(
        self,
        ax,
        data: List[Dict[str, Any]],
        chart_config: Dict[str, Any],
        is_donut: bool
    ):
        """Renderiza gráfico circular con matplotlib."""
        data_key = chart_config.get('data_key', 'value')
        name_key = chart_config.get('name_key', 'name')
        colors = chart_config.get('colors', ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899'])
        
        # Extraer datos
        labels = [str(row.get(name_key, '')) for row in data]
        values = [float(row.get(data_key, 0)) for row in data]
        
        # Renderizar
        wedgeprops = {'width': 0.4} if is_donut else {}
        ax.pie(
            values,
            labels=labels,
            colors=colors[:len(values)],
            autopct='%1.1f%%',
            startangle=90,
            wedgeprops=wedgeprops
        )
        ax.axis('equal')
