"""
Servicio para gestión de documentos crediticios (CU-12).

Maneja la lógica de negocio para:
- Creación de checklist de documentos
- Carga de documentos
- Validación de archivos
- Revisión de documentos
- Verificación de completitud
"""

from django.db import transaction
from django.utils import timezone
import os
import logging
from api.loans.models import LoanApplication
from api.loans.models_documents import (
    LoanApplicationDocumentRequirement,
    DocumentReviewHistory
)
from api.storage.models import FileResource

logger = logging.getLogger(__name__)


class DocumentService:
    """
    Servicio para gestión de documentos crediticios.
    """
    
    @staticmethod
    @transaction.atomic
    def create_document_checklist(loan_application):
        """
        Crea el checklist de documentos para una solicitud.
        
        Se ejecuta automáticamente al crear la solicitud.
        
        Args:
            loan_application: LoanApplication
        
        Returns:
            list: Lista de LoanApplicationDocumentRequirement creados
        """
        import logging
        logger = logging.getLogger(__name__)
        
        # Obtener requisitos del producto directamente
        from api.products.models import ProductDocumentRequirement
        
        requirements = ProductDocumentRequirement.objects.filter(
            product=loan_application.product,
            institution=loan_application.institution
        ).select_related('document_type').order_by('display_order')
        
        logger.info(
            f"[DOCUMENT_CHECKLIST] Creando checklist para solicitud {loan_application.id} "
            f"(Producto: {loan_application.product.name}, ID: {loan_application.product_id}). "
            f"Documentos configurados: {requirements.count()}"
        )
        
        checklist = []
        
        for req in requirements:
            doc_req = LoanApplicationDocumentRequirement.objects.create(
                institution=loan_application.institution,
                loan_application=loan_application,
                product_document_requirement=req,
                status=LoanApplicationDocumentRequirement.Status.PENDING
            )
            checklist.append(doc_req)
            logger.info(
                f"[DOCUMENT_CHECKLIST] Creado documento requerido: {req.document_type.name} "
                f"(Obligatorio: {req.is_mandatory})"
            )
        
        logger.info(f"[DOCUMENT_CHECKLIST] Checklist creado con {len(checklist)} documentos")
        
        return checklist
    
    @staticmethod
    @transaction.atomic
    def upload_document(
        document_requirement_id,
        file,
        uploaded_by,
        notes='',
        storage_service=None
    ):
        """
        Carga un documento para una solicitud.
        
        Proceso:
        1. Validar archivo (MIME type, extensión, tamaño, magic bytes)
        2. Subir a Supabase Storage
        3. Crear FileResource
        4. Actualizar LoanApplicationDocumentRequirement
        5. Crear evento en timeline
        
        Args:
            document_requirement_id: ID del LoanApplicationDocumentRequirement
            file: Archivo Django UploadedFile
            uploaded_by: Usuario que carga
            notes: Notas adicionales
            storage_service: Servicio de storage (opcional, para testing)
        
        Returns:
            LoanApplicationDocumentRequirement: Documento actualizado
        
        Raises:
            ValueError: Si la validación falla
        """
        # Obtener el requisito
        doc_req = LoanApplicationDocumentRequirement.objects.select_for_update().get(
            id=document_requirement_id
        )
        
        app_id = doc_req.loan_application_id
        logger.info(
            f"[DOCUMENT_UPLOAD] ===== INICIO upload_document ====="
        )
        logger.info(
            f"[DOCUMENT_UPLOAD] doc_req_id={document_requirement_id}, "
            f"loan_application_id={app_id}, "
            f"institution_id={doc_req.institution_id}, "
            f"uploaded_by={uploaded_by.id if uploaded_by else 'system'}, "
            f"document_type={doc_req.product_document_requirement.document_type.name if doc_req.product_document_requirement else 'unknown'}"
        )
        
        # Validar archivo
        DocumentService.validate_file(file, doc_req.product_document_requirement)
        logger.info(f"[DOCUMENT_UPLOAD] Archivo validado OK: {file.name}")

        
        # Generar nombre único
        timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
        ext = os.path.splitext(file.name)[1]
        unique_filename = f"{doc_req.loan_application.id}_{doc_req.product_document_requirement.document_type.code}_{timestamp}{ext}"

        
        # Subir a Supabase
        storage_path = f"loan_documents/{doc_req.loan_application.institution.id}/{doc_req.loan_application.id}/{unique_filename}"
        
        # Si no se proporciona storage_service, usar el real
        if storage_service is None:
            from api.storage.services import StorageService
            storage_service = StorageService()
        
        # Subir archivo
        file.seek(0)
        file_content = file.read()
        storage_service.upload_to_storage(
            file_path=storage_path,
            file_content=file_content,
            content_type=file.content_type or 'application/octet-stream',
        )
        
        # Crear FileResource
        file_resource = FileResource.objects.create(
            tenant=doc_req.institution,
            resource_type=FileResource.ResourceType.LOAN_APPLICATION,
            entity_type='loan_application_document',
            entity_id=doc_req.loan_application.id,
            original_name=file.name,
            stored_name=unique_filename,
            file_path=storage_path,
            mime_type=file.content_type,
            extension=ext.lstrip('.'),
            size=file.size,
            category=doc_req.product_document_requirement.document_type.code,
            visibility=FileResource.Visibility.PRIVATE,

            uploaded_by=uploaded_by,
            status=FileResource.Status.ACTIVE
        )
        
        # Actualizar documento requirement
        doc_req.file_resource = file_resource
        doc_req.status = LoanApplicationDocumentRequirement.Status.UPLOADED
        doc_req.uploaded_at = timezone.now()
        doc_req.uploaded_by = uploaded_by
        doc_req.notes = notes
        doc_req.save(update_fields=[
            'file_resource', 'status', 'uploaded_at', 'uploaded_by', 'notes'
        ])
        
        # Actualizar estado de documentos de la solicitud
        doc_req.loan_application.update_documents_status()
        
        # Crear evento en timeline
        logger.info(
            f"[DOCUMENT_UPLOAD] Creando timeline event para app_id={app_id}, "
            f"status_actual={doc_req.loan_application.status}"
        )
        doc_req.loan_application.add_timeline_event(
            to_status=doc_req.loan_application.status,  # Mantener estado
            changed_by=uploaded_by,
            notes=f"Documento cargado: {doc_req.product_document_requirement.document_type.name}",
            is_visible_to_client=True,
            client_message=f"Documento '{doc_req.product_document_requirement.document_type.name}' cargado exitosamente",
            send_notification=False
        )
        logger.info(f"[DOCUMENT_UPLOAD] Timeline event creado para app_id={app_id}")

        
        # Si todos los documentos obligatorios están aprobados, notificar
        docs_status = doc_req.loan_application.documents_status
        logger.info(
            f"[DOCUMENT_UPLOAD] documents_status={docs_status} para app_id={app_id}"
        )
        if docs_status == 'COMPLETE':
            logger.info(
                f"[DOCUMENT_UPLOAD] Documentos COMPLETOS para app_id={app_id}. "
                f"Creando evento y verificando avance automatico."
            )
            doc_req.loan_application.add_timeline_event(
                to_status=doc_req.loan_application.status,  # Mantener estado
                changed_by=uploaded_by,
                notes="Todos los documentos obligatorios completados",
                is_visible_to_client=True,
                client_message="¡Documentación completa! Tu solicitud está lista para continuar.",
                send_notification=True
            )
            # Disparar avance automatico del workflow
            from api.loans.services.workflow_service import WorkflowService
            try:
                logger.info(
                    f"[DOCUMENT_UPLOAD] Llamando check_and_advance_if_ready "
                    f"para app_id={app_id}, trigger='documents_completed'"
                )
                WorkflowService.check_and_advance_if_ready(
                    doc_req.loan_application,
                    changed_by=uploaded_by,
                    trigger='documents_completed'
                )
            except Exception as e:
                logger.warning(
                    f"[DOCUMENT_UPLOAD] Error avanzando workflow: {e}",
                    exc_info=True
                )
        else:
            logger.info(
                f"[DOCUMENT_UPLOAD] Documentos aun NO completos (status={docs_status}) "
                f"para app_id={app_id}. No se verifica avance automatico."
            )
        
        logger.info(
            f"[DOCUMENT_UPLOAD] ===== FIN upload_document =====: "
            f"doc_req_id={document_requirement_id}, app_id={app_id}"
        )
        
        return doc_req
    
    @staticmethod
    def validate_file(file, document_requirement):
        """
        Valida un archivo antes de subirlo.
        
        Validaciones:
        1. Tamaño máximo
        2. MIME type
        3. Extensión
        4. Magic bytes (contenido real del archivo)
        
        Args:
            file: Archivo Django UploadedFile
            document_requirement: DocumentRequirement
        
        Raises:
            ValueError: Si alguna validación falla
        """
        import logging
        logger = logging.getLogger(__name__)
        
        # 1. Validar tamaño
        max_size_bytes = float(document_requirement.get_max_file_size_mb()) * 1024 * 1024
        if file.size > max_size_bytes:
            raise ValueError(
                f"El archivo excede el tamaño máximo de {document_requirement.get_max_file_size_mb()} MB"
            )
        
        # Mapeo de formatos legibles a MIME types
        format_to_mime = {
            'PDF': ['application/pdf'],
            'JPG': ['image/jpeg'],
            'JPEG': ['image/jpeg'],
            'PNG': ['image/png'],
            'DOC': ['application/msword'],
            'DOCX': ['application/vnd.openxmlformats-officedocument.wordprocessingml.document'],
        }
        
        # Mapeo de MIME types a extensiones
        mime_to_ext = {
            'application/pdf': ['.pdf'],
            'image/jpeg': ['.jpg', '.jpeg'],
            'image/png': ['.png'],
            'application/msword': ['.doc'],
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx'],
        }
        
        # Obtener formatos permitidos y convertir a MIME types
        allowed_formats = document_requirement.get_allowed_formats()
        logger.info(f"[VALIDATE] Formatos permitidos configurados: {allowed_formats}")
        logger.info(f"[VALIDATE] Tipo de allowed_formats: {type(allowed_formats)}")
        
        allowed_mimes = []
        for fmt in allowed_formats:
            fmt_upper = str(fmt).upper()  # Asegurar que sea string
            if fmt_upper in format_to_mime:
                allowed_mimes.extend(format_to_mime[fmt_upper])
        
        logger.info(f"[VALIDATE] MIME types permitidos: {allowed_mimes}")
        logger.info(f"[VALIDATE] Archivo recibido - MIME: {file.content_type}, Nombre: {file.name}, Tamaño: {file.size}")
        
        # 2. Validar MIME type
        if file.content_type not in allowed_mimes:
            raise ValueError(
                f"Formato no permitido. Formatos válidos: {', '.join(allowed_formats)}"
            )
        
        # 3. Validar extensión
        ext = os.path.splitext(file.name)[1].lower()
        
        valid_extensions = []
        for mime in allowed_mimes:
            valid_extensions.extend(mime_to_ext.get(mime, []))
        
        if ext not in valid_extensions:
            raise ValueError(
                f"Extensión no permitida. Extensiones válidas: {', '.join(valid_extensions)}"
            )
        
        logger.info(f"[VALIDATE] Validación exitosa para {file.name}")
    
    @staticmethod
    @transaction.atomic
    def review_document(
        document_requirement_id,
        action,
        reviewed_by,
        comments=''
    ):
        """
        Revisa un documento (aprobar/rechazar/solicitar re-carga).
        
        Args:
            document_requirement_id: ID del LoanApplicationDocumentRequirement
            action: 'APPROVED', 'REJECTED', 'REQUESTED_REUPLOAD'
            reviewed_by: Usuario que revisa
            comments: Comentarios de la revisión
        
        Returns:
            LoanApplicationDocumentRequirement: Documento actualizado
        
        Raises:
            ValueError: Si el documento no está en estado válido para revisión
        """
        doc_req = LoanApplicationDocumentRequirement.objects.select_for_update().get(
            id=document_requirement_id
        )
        
        app_id = doc_req.loan_application_id
        logger.info(
            f"[DOCUMENT_REVIEW] ===== INICIO review_document ====="
        )
        logger.info(
            f"[DOCUMENT_REVIEW] doc_req_id={document_requirement_id}, "
            f"loan_application_id={app_id}, "
            f"institution_id={doc_req.institution_id}, "
            f"action={action}, "
            f"reviewed_by={reviewed_by.id if reviewed_by else 'system'}"
        )
        
        # Validar que esté en estado válido para revisión
        valid_statuses = [
            LoanApplicationDocumentRequirement.Status.UPLOADED,
            LoanApplicationDocumentRequirement.Status.UNDER_REVIEW
        ]
        
        if doc_req.status not in valid_statuses:
            logger.error(
                f"[DOCUMENT_REVIEW] Estado invalido para revision: "
                f"doc_req_id={document_requirement_id}, status={doc_req.status}"
            )
            raise ValueError(
                f"El documento no puede ser revisado en el estado actual: {doc_req.status}"
            )
        
        logger.info(f"[DOCUMENT_REVIEW] Estado OK: {doc_req.status} para app_id={app_id}")
        
        # Crear historial de revisión
        DocumentReviewHistory.objects.create(
            institution=doc_req.institution,
            document_requirement=doc_req,
            action=action,
            reviewed_by=reviewed_by,
            comments=comments,
            file_resource_at_review=doc_req.file_resource
        )
        logger.info(f"[DOCUMENT_REVIEW] Historial de revision creado para doc_req_id={document_requirement_id}")
        
        # Actualizar estado según la acción
        if action == 'APPROVED':
            doc_req.status = LoanApplicationDocumentRequirement.Status.APPROVED
            client_message = f"Documento '{doc_req.product_document_requirement.document_type.name}' aprobado"
        elif action == 'REJECTED':
            doc_req.status = LoanApplicationDocumentRequirement.Status.REJECTED
            doc_req.rejection_reason = comments
            client_message = f"Documento '{doc_req.product_document_requirement.document_type.name}' rechazado. {comments}"
        elif action == 'REQUESTED_REUPLOAD':
            doc_req.status = LoanApplicationDocumentRequirement.Status.PENDING
            client_message = f"Se requiere volver a cargar '{doc_req.product_document_requirement.document_type.name}'. {comments}"

        
        doc_req.reviewed_at = timezone.now()
        doc_req.reviewed_by = reviewed_by
        doc_req.save(update_fields=[
            'status', 'reviewed_at', 'reviewed_by', 'rejection_reason'
        ])
        
        # Actualizar estado de documentos de la solicitud
        doc_req.loan_application.update_documents_status()
        
        # Crear evento en timeline
        logger.info(
            f"[DOCUMENT_REVIEW] Creando timeline event para app_id={app_id}, "
            f"status_actual={doc_req.loan_application.status}"
        )
        doc_req.loan_application.add_timeline_event(
            to_status=doc_req.loan_application.status,
            changed_by=reviewed_by,
            notes=f"Documento revisado: {doc_req.product_document_requirement.document_type.name} - {action}",
            is_visible_to_client=True,
            client_message=client_message,
            requires_client_action=(action == 'REQUESTED_REUPLOAD'),
            action_description=comments if action == 'REQUESTED_REUPLOAD' else '',
            send_notification=True
        )
        logger.info(f"[DOCUMENT_REVIEW] Timeline event creado para app_id={app_id}")
        
        # Si los documentos quedaron completos, disparar avance automatico
        docs_status = doc_req.loan_application.documents_status
        logger.info(
            f"[DOCUMENT_REVIEW] documents_status={docs_status} para app_id={app_id}"
        )
        if docs_status == 'COMPLETE':
            logger.info(
                f"[DOCUMENT_REVIEW] Documentos COMPLETOS. Verificando avance automatico "
                f"para app_id={app_id}"
            )
            from api.loans.services.workflow_service import WorkflowService
            try:
                WorkflowService.check_and_advance_if_ready(
                    doc_req.loan_application,
                    changed_by=reviewed_by,
                    trigger='documents_completed'
                )
            except Exception as e:
                logger.warning(
                    f"[DOCUMENT_REVIEW] Error avanzando workflow: {e}",
                    exc_info=True
                )
        else:
            logger.info(
                f"[DOCUMENT_REVIEW] Documentos aun NO completos (status={docs_status}) "
                f"para app_id={app_id}"
            )
        
        logger.info(
            f"[DOCUMENT_REVIEW] ===== FIN review_document =====: "
            f"doc_req_id={document_requirement_id}, app_id={app_id}"
        )
        
        return doc_req
    
    @staticmethod
    def check_completion(loan_application):
        """
        Verifica si todos los documentos obligatorios están aprobados.
        
        Args:
            loan_application: LoanApplication
        
        Returns:
            dict: Información de completitud
        """
        checklist = loan_application.document_checklist.all()
        
        total = checklist.count()
        mandatory = checklist.filter(product_document_requirement__is_mandatory=True).count()
        uploaded = checklist.exclude(status='PENDING').count()
        approved = checklist.filter(status='APPROVED').count()
        rejected = checklist.filter(status='REJECTED').count()
        pending = checklist.filter(status='PENDING').count()
        
        mandatory_approved = checklist.filter(
            product_document_requirement__is_mandatory=True,
            status='APPROVED'
        ).count()

        
        is_complete = (mandatory_approved == mandatory)
        completion_percentage = (mandatory_approved / mandatory * 100) if mandatory > 0 else 0
        
        return {
            'total_documents': total,
            'mandatory_documents': mandatory,
            'uploaded_documents': uploaded,
            'approved_documents': approved,
            'rejected_documents': rejected,
            'pending_documents': pending,
            'is_complete': is_complete,
            'completion_percentage': round(completion_percentage, 2)
        }
