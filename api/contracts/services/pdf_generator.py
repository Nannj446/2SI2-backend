"""
Servicio para generación de PDFs de contratos

Este servicio maneja la generación de documentos PDF a partir de
plantillas HTML con datos del contrato.
"""

import logging
import io
from django.template import Template, Context
from django.conf import settings
from api.contracts.models import Contract
from api.contracts.services.contract_generator import ContractGeneratorService

logger = logging.getLogger(__name__)


class PDFGeneratorService:
    """
    Servicio para generar PDFs de contratos.
    
    Utiliza WeasyPrint para convertir HTML a PDF.
    """
    
    @staticmethod
    def generate_contract_pdf(contract: Contract) -> bytes:
        """
        Genera el PDF de un contrato.
        
        Args:
            contract: Contrato para el cual generar el PDF
        
        Returns:
            bytes: Contenido del PDF generado
        
        Raises:
            Exception: Si hay error en la generación del PDF
        """
        try:
            # Obtener variables del contrato
            variables = ContractGeneratorService.get_contract_variables(contract)
            
            # Obtener plantilla HTML
            template_content = contract.template.template_content
            
            # Renderizar plantilla con variables
            html_content = PDFGeneratorService._render_template(
                template_content,
                variables
            )
            
            # Generar PDF desde HTML
            pdf_bytes = PDFGeneratorService._html_to_pdf(html_content)
            
            logger.info(
                f"PDF generado exitosamente para contrato {contract.contract_number}"
            )
            
            return pdf_bytes
            
        except Exception as e:
            logger.error(
                f"Error generando PDF para contrato {contract.contract_number}: {str(e)}"
            )
            raise
    
    @staticmethod
    def _render_template(template_content: str, variables: dict) -> str:
        """
        Renderiza una plantilla HTML con variables.
        
        Args:
            template_content: Contenido HTML de la plantilla
            variables: Diccionario con variables a reemplazar
        
        Returns:
            str: HTML renderizado
        """
        # Usar el motor de plantillas de Django
        template = Template(template_content)
        context = Context(variables)
        return template.render(context)
    
    @staticmethod
    def _html_to_pdf(html_content: str) -> bytes:
        """
        Convierte HTML a PDF usando WeasyPrint.
        
        Args:
            html_content: Contenido HTML
        
        Returns:
            bytes: Contenido del PDF
        
        Raises:
            ImportError: Si WeasyPrint no está instalado
            Exception: Si hay error en la conversión
        """
        try:
            from weasyprint import HTML, CSS
            from weasyprint.text.fonts import FontConfiguration
        except ImportError:
            logger.error(
                "WeasyPrint no está instalado. "
                "Instale con: pip install weasyprint"
            )
            raise ImportError(
                "WeasyPrint es requerido para generar PDFs. "
                "Instale con: pip install weasyprint"
            )
        
        try:
            # Configuración de fuentes
            font_config = FontConfiguration()
            
            # CSS personalizado para el PDF
            css_content = PDFGeneratorService._get_default_css()
            css = CSS(string=css_content, font_config=font_config)
            
            # Generar PDF
            html = HTML(string=html_content)
            pdf_bytes = html.write_pdf(
                stylesheets=[css],
                font_config=font_config
            )
            
            return pdf_bytes
            
        except Exception as e:
            logger.error(f"Error convirtiendo HTML a PDF: {str(e)}")
            raise
    
    @staticmethod
    def _get_default_css() -> str:
        """
        Retorna el CSS por defecto para los PDFs de contratos.
        
        Returns:
            str: Contenido CSS
        """
        return """
        @page {
            size: Letter;
            margin: 2cm;
            @bottom-center {
                content: "Página " counter(page) " de " counter(pages);
                font-size: 9pt;
                color: #666;
            }
        }
        
        body {
            font-family: 'Arial', 'Helvetica', sans-serif;
            font-size: 11pt;
            line-height: 1.6;
            color: #333;
        }
        
        h1 {
            font-size: 18pt;
            font-weight: bold;
            text-align: center;
            margin-bottom: 20pt;
            color: #000;
        }
        
        h2 {
            font-size: 14pt;
            font-weight: bold;
            margin-top: 15pt;
            margin-bottom: 10pt;
            color: #000;
        }
        
        h3 {
            font-size: 12pt;
            font-weight: bold;
            margin-top: 10pt;
            margin-bottom: 8pt;
            color: #000;
        }
        
        p {
            margin-bottom: 10pt;
            text-align: justify;
        }
        
        .header {
            text-align: center;
            margin-bottom: 30pt;
        }
        
        .contract-number {
            font-size: 12pt;
            font-weight: bold;
            text-align: center;
            margin-bottom: 20pt;
        }
        
        .parties {
            margin: 20pt 0;
        }
        
        .party {
            margin-bottom: 15pt;
        }
        
        .party-label {
            font-weight: bold;
            text-transform: uppercase;
        }
        
        .terms {
            margin: 20pt 0;
        }
        
        .term-item {
            margin-bottom: 10pt;
        }
        
        .term-label {
            font-weight: bold;
        }
        
        .clauses {
            margin: 20pt 0;
        }
        
        .clause {
            margin-bottom: 15pt;
        }
        
        .clause-number {
            font-weight: bold;
        }
        
        .signatures {
            margin-top: 50pt;
            page-break-inside: avoid;
        }
        
        .signature-block {
            margin-top: 40pt;
            text-align: center;
        }
        
        .signature-line {
            border-top: 1px solid #000;
            width: 200pt;
            margin: 0 auto 5pt auto;
        }
        
        .signature-label {
            font-size: 10pt;
        }
        
        table {
            width: 100%;
            border-collapse: collapse;
            margin: 15pt 0;
        }
        
        th, td {
            border: 1px solid #ddd;
            padding: 8pt;
            text-align: left;
        }
        
        th {
            background-color: #f5f5f5;
            font-weight: bold;
        }
        
        .amount {
            font-weight: bold;
            color: #000;
        }
        
        .footer {
            margin-top: 30pt;
            font-size: 9pt;
            color: #666;
            text-align: center;
        }
        """
    
    @staticmethod
    def save_contract_pdf(contract: Contract, pdf_bytes: bytes) -> 'FileResource':
        """
        Guarda el PDF del contrato en el sistema de almacenamiento.
        
        Args:
            contract: Contrato
            pdf_bytes: Contenido del PDF
        
        Returns:
            FileResource: Recurso de archivo creado
        """
        from api.storage.models import FileResource
        from django.core.files.base import ContentFile
        
        # Nombre del archivo
        file_name = f"contrato_{contract.contract_number}.pdf"
        
        # Crear FileResource
        file_resource = FileResource.objects.create(
            institution=contract.institution,
            file_name=file_name,
            file_size=len(pdf_bytes),
            mime_type='application/pdf',
            storage_path=f"contracts/{contract.id}/",
            uploaded_by=contract.generated_by,
            is_public=False,
            metadata={
                'contract_id': contract.id,
                'contract_number': contract.contract_number,
                'generated_at': contract.created_at.isoformat(),
            }
        )
        
        # Guardar archivo
        file_resource.file.save(
            file_name,
            ContentFile(pdf_bytes),
            save=True
        )
        
        logger.info(
            f"PDF guardado para contrato {contract.contract_number}: {file_name}"
        )
        
        return file_resource
    
    @staticmethod
    def generate_and_save_contract_pdf(contract: Contract) -> 'FileResource':
        """
        Genera y guarda el PDF de un contrato.
        
        Método de conveniencia que combina generación y guardado.
        
        Args:
            contract: Contrato
        
        Returns:
            FileResource: Recurso de archivo creado
        """
        # Generar PDF
        pdf_bytes = PDFGeneratorService.generate_contract_pdf(contract)
        
        # Guardar PDF
        file_resource = PDFGeneratorService.save_contract_pdf(contract, pdf_bytes)
        
        # Actualizar contrato con referencia al PDF
        contract.pdf_file = file_resource
        contract.save(update_fields=['pdf_file', 'updated_at'])
        
        return file_resource
    
    @staticmethod
    def preview_contract_html(contract: Contract) -> str:
        """
        Genera una vista previa HTML del contrato (sin convertir a PDF).
        
        Útil para debugging y vista previa en navegador.
        
        Args:
            contract: Contrato
        
        Returns:
            str: HTML renderizado
        """
        variables = ContractGeneratorService.get_contract_variables(contract)
        template_content = contract.template.template_content
        return PDFGeneratorService._render_template(template_content, variables)
    
    @staticmethod
    def preview_template_html(template: 'ContractTemplate', sample_data: dict = None) -> str:
        """
        Genera una vista previa HTML de una plantilla con datos de ejemplo.
        
        Args:
            template: Plantilla de contrato
            sample_data: Datos de ejemplo (si es None, usa datos por defecto)
        
        Returns:
            str: HTML renderizado con estilos CSS
        """
        if sample_data is None:
            sample_data = PDFGeneratorService._get_sample_data()
        
        # Renderizar el contenido de la plantilla
        rendered_content = PDFGeneratorService._render_template(
            template.template_content,
            sample_data
        )
        
        # Envolver con estilos CSS profesionales
        css_styles = PDFGeneratorService._get_default_css()
        
        full_html = f"""
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Vista Previa - {template.name}</title>
    <style>
        {css_styles}
    </style>
</head>
<body>
    {rendered_content}
</body>
</html>
        """
        
        return full_html
    
    @staticmethod
    def _get_sample_data() -> dict:
        """
        Retorna datos de ejemplo para vista previa de plantillas.
        
        Returns:
            dict: Datos de ejemplo
        """
        return {
            'institution_name': 'Institución Financiera Ejemplo S.A.',
            'institution_address': 'Av. Principal #123, Ciudad',
            'institution_nit': '1234567890',
            'institution_phone': '+591 2 1234567',
            'institution_email': 'info@institucion.com',
            'borrower_name': 'Juan Pérez García',
            'borrower_document': '1234567 LP',
            'borrower_address': 'Calle Secundaria #456, Ciudad',
            'borrower_email': 'juan.perez@email.com',
            'borrower_phone': '+591 70123456',
            'contract_number': 'CONT-1-2026-0001-1234',
            'contract_date': '30/05/2026',
            'start_date': '05/06/2026',
            'end_date': '05/06/2028',
            'principal_amount': 'Bs. 50,000.00',
            'principal_amount_raw': '50000.00',
            'interest_rate': '12.5%',
            'interest_rate_raw': '12.5',
            'term_months': '24',
            'monthly_payment': 'Bs. 2,356.78',
            'monthly_payment_raw': '2356.78',
            'total_amount': 'Bs. 56,562.72',
            'total_amount_raw': '56562.72',
            'first_payment_date': '05/07/2026',
            'last_payment_date': '05/06/2028',
            'product_name': 'Crédito Personal',
            'product_description': 'Crédito personal para libre disponibilidad',
        }
