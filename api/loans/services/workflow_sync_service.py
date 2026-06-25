"""
Servicio para sincronización de workflow de solicitudes de crédito.

FASE 3 - Endpoint de Sincronización:
Permite recalcular y corregir el estado de solicitudes "atascadas".
"""

from django.db import transaction
from django.core.exceptions import ValidationError
from typing import Optional, Dict, List
import logging

logger = logging.getLogger(__name__)


class WorkflowSyncService:
    """
    Servicio para sincronizar el estado del workflow de solicitudes.
    
    Detecta y corrige solicitudes que están en un estado inconsistente,
    donde el estado principal no refleja el progreso real basado en:
    - identity_verification_status
    - documents_status
    - Workflow configurado
    """
    
    @staticmethod
    @transaction.atomic
    def sync_application_workflow(application) -> Dict:
        """
        Sincroniza el estado del workflow de una solicitud.
        
        Determina el estado correcto basándose en:
        - identity_verification_status
        - documents_status
        - Estado actual
        - Workflow configurado
        
        Args:
            application: LoanApplication instance
            
        Returns:
            Dict con información de la sincronización:
            {
                'changed': bool,
                'previous_status': str,
                'new_status': str,
                'reason': str,
                'application': LoanApplication
            }
        """
        logger.info(f"[SYNC] Iniciando sincronización para solicitud {application.id}")
        
        current_status = application.status
        expected_status = WorkflowSyncService._calculate_expected_status(application)
        
        if current_status == expected_status:
            logger.info(
                f"[SYNC] Solicitud {application.id} ya está en el estado correcto: {current_status}"
            )
            return {
                'changed': False,
                'previous_status': current_status,
                'new_status': current_status,
                'reason': 'Estado ya es correcto',
                'application': application
            }
        
        logger.info(
            f"[SYNC] Solicitud {application.id} necesita sincronización: "
            f"{current_status} → {expected_status}"
        )
        
        # Transicionar al estado correcto
        from api.loans.services.workflow_service import WorkflowService
        
        try:
            WorkflowService.transition_state(
                loan_application_id=application.id,
                to_status=expected_status,
                changed_by=None,  # Sistema
                notes=f'Sincronización automática de workflow: {current_status} → {expected_status}',
                client_message='Tu solicitud ha sido actualizada.',
                send_notification=False  # No notificar en sincronización automática
            )
            
            # Recargar para obtener estado actualizado
            application.refresh_from_db()
            
            logger.info(
                f"[SYNC] Solicitud {application.id} sincronizada exitosamente a {expected_status}"
            )
            
            return {
                'changed': True,
                'previous_status': current_status,
                'new_status': expected_status,
                'reason': f'Sincronización automática basada en sub-estados',
                'application': application
            }
            
        except Exception as e:
            logger.error(
                f"[SYNC] Error sincronizando solicitud {application.id}: "
                f"{type(e).__name__}: {str(e)}",
                exc_info=True
            )
            raise
    
    @staticmethod
    def _calculate_expected_status(application) -> str:
        """
        Calcula el estado esperado basándose en los sub-estados.
        
        Lógica:
        1. Si está en estado final (APPROVED, REJECTED, etc.) → No cambiar
        2. Si está en DRAFT → No cambiar
        3. Si está en SUBMITTED:
           - KYC aprobado + Documentos completos → SCORING (o siguiente según workflow)
           - KYC aprobado + Documentos pendientes → IN_REVIEW (o DOCUMENTS según workflow)
           - KYC pendiente → SUBMITTED
        4. Para otros estados → Mantener actual
        
        Args:
            application: LoanApplication instance
            
        Returns:
            str: Código del estado esperado
        """
        from api.loans.models import LoanApplication
        
        current_status = application.status
        
        logger.debug(
            f"[SYNC] Calculando estado esperado para solicitud {application.id}. "
            f"Estado actual: {current_status}, "
            f"KYC: {application.identity_verification_status}, "
            f"Docs: {application.documents_status}"
        )
        
        # Si está en estado final, no cambiar
        if current_status in ['APPROVED', 'REJECTED', 'DISBURSED', 'CANCELLED']:
            logger.debug(f"[SYNC] Estado final detectado: {current_status}")
            return current_status
        
        # Si está en DRAFT, no cambiar
        if current_status == 'DRAFT':
            logger.debug(f"[SYNC] Estado DRAFT detectado")
            return current_status
        
        # Lógica de determinación de estado para SUBMITTED
        if current_status == 'SUBMITTED':
            kyc_status = application.identity_verification_status
            docs_status = application.documents_status
            
            # Si KYC está aprobado
            if kyc_status == LoanApplication.IdentityVerificationStatus.APPROVED:
                logger.debug(f"[SYNC] KYC aprobado detectado")
                
                # Si documentos están completos, avanzar a siguiente etapa
                if docs_status == LoanApplication.DocumentsStatus.COMPLETE:
                    logger.debug(f"[SYNC] Documentos completos detectados")
                    next_stage = WorkflowSyncService._get_stage_after_documents(application)
                    logger.info(
                        f"[SYNC] Estado esperado para solicitud {application.id}: {next_stage} "
                        f"(KYC aprobado + Documentos completos)"
                    )
                    return next_stage
                else:
                    # Documentos pendientes, ir a etapa de documentos
                    next_stage = WorkflowSyncService._get_stage_after_kyc(application)
                    logger.info(
                        f"[SYNC] Estado esperado para solicitud {application.id}: {next_stage} "
                        f"(KYC aprobado + Documentos pendientes)"
                    )
                    return next_stage
            else:
                # KYC aún pendiente, mantener en SUBMITTED
                logger.debug(f"[SYNC] KYC pendiente, mantener en SUBMITTED")
                return 'SUBMITTED'
        
        # Para otros estados, mantener el actual
        logger.debug(f"[SYNC] Mantener estado actual: {current_status}")
        return current_status
    
    @staticmethod
    def _get_stage_after_kyc(application) -> str:
        """
        Obtiene la etapa después de completar KYC.
        
        Busca en el workflow configurado la siguiente etapa después de SUBMITTED.
        Si no hay configuración, usa IN_REVIEW por defecto.
        
        Args:
            application: LoanApplication instance
            
        Returns:
            str: Código de la siguiente etapa
        """
        if not application.rule_set_snapshot:
            logger.debug(f"[SYNC] No hay rule_set_snapshot, usando IN_REVIEW por defecto")
            return 'IN_REVIEW'
        
        try:
            submitted_stage = application.rule_set_snapshot.workflow_stages.filter(
                stage_code='SUBMITTED'
            ).first()
            
            if submitted_stage and submitted_stage.next_stage_on_success:
                logger.debug(
                    f"[SYNC] Siguiente etapa después de KYC: {submitted_stage.next_stage_on_success}"
                )
                return submitted_stage.next_stage_on_success
            
            logger.debug(f"[SYNC] No hay next_stage_on_success, usando IN_REVIEW por defecto")
            return 'IN_REVIEW'
            
        except Exception as e:
            logger.warning(
                f"[SYNC] Error obteniendo etapa después de KYC: {str(e)}"
            )
            return 'IN_REVIEW'
    
    @staticmethod
    def _get_stage_after_documents(application) -> str:
        """
        Obtiene la etapa después de completar documentos.
        
        Busca en el workflow configurado la siguiente etapa después de DOCUMENTS.
        Si no hay configuración, usa SCORING por defecto.
        
        Args:
            application: LoanApplication instance
            
        Returns:
            str: Código de la siguiente etapa
        """
        if not application.rule_set_snapshot:
            logger.debug(f"[SYNC] No hay rule_set_snapshot, usando SCORING por defecto")
            return 'SCORING'
        
        try:
            # Primero intentar encontrar etapa DOCUMENTS
            documents_stage = application.rule_set_snapshot.workflow_stages.filter(
                stage_code='DOCUMENTS'
            ).first()
            
            if documents_stage and documents_stage.next_stage_on_success:
                logger.debug(
                    f"[SYNC] Siguiente etapa después de DOCUMENTS: "
                    f"{documents_stage.next_stage_on_success}"
                )
                return documents_stage.next_stage_on_success
            
            # Si no hay etapa DOCUMENTS, intentar con IN_REVIEW
            review_stage = application.rule_set_snapshot.workflow_stages.filter(
                stage_code='IN_REVIEW'
            ).first()
            
            if review_stage and review_stage.next_stage_on_success:
                logger.debug(
                    f"[SYNC] Siguiente etapa después de IN_REVIEW: "
                    f"{review_stage.next_stage_on_success}"
                )
                return review_stage.next_stage_on_success
            
            logger.debug(f"[SYNC] No hay configuración, usando SCORING por defecto")
            return 'SCORING'
            
        except Exception as e:
            logger.warning(
                f"[SYNC] Error obteniendo etapa después de documentos: {str(e)}"
            )
            return 'SCORING'
    
    @staticmethod
    def find_stuck_applications(institution_id: int, limit: int = 100) -> List:
        """
        Encuentra solicitudes que podrían estar "atascadas".
        
        Criterios:
        - Estado es SUBMITTED
        - KYC está aprobado
        - Última actualización hace más de 1 hora
        
        Args:
            institution_id: ID de la institución
            limit: Número máximo de solicitudes a retornar
            
        Returns:
            List[LoanApplication]: Lista de solicitudes atascadas
        """
        from api.loans.models import LoanApplication
        from django.utils import timezone
        from datetime import timedelta
        
        one_hour_ago = timezone.now() - timedelta(hours=1)
        
        stuck_applications = LoanApplication.objects.filter(
            institution_id=institution_id,
            status='SUBMITTED',
            identity_verification_status=LoanApplication.IdentityVerificationStatus.APPROVED,
            updated_at__lt=one_hour_ago
        ).order_by('updated_at')[:limit]
        
        logger.info(
            f"[SYNC] Encontradas {stuck_applications.count()} solicitudes atascadas "
            f"para institución {institution_id}"
        )
        
        return list(stuck_applications)
    
    @staticmethod
    @transaction.atomic
    def sync_stuck_applications(institution_id: int, limit: int = 100) -> Dict:
        """
        Sincroniza todas las solicitudes atascadas de una institución.
        
        Args:
            institution_id: ID de la institución
            limit: Número máximo de solicitudes a sincronizar
            
        Returns:
            Dict con estadísticas:
            {
                'total_found': int,
                'total_synced': int,
                'total_errors': int,
                'synced_applications': List[int],
                'errors': List[Dict]
            }
        """
        logger.info(
            f"[SYNC] Iniciando sincronización masiva para institución {institution_id}"
        )
        
        stuck_applications = WorkflowSyncService.find_stuck_applications(
            institution_id, limit
        )
        
        total_found = len(stuck_applications)
        total_synced = 0
        total_errors = 0
        synced_applications = []
        errors = []
        
        for application in stuck_applications:
            try:
                result = WorkflowSyncService.sync_application_workflow(application)
                
                if result['changed']:
                    total_synced += 1
                    synced_applications.append(application.id)
                    logger.info(
                        f"[SYNC] Solicitud {application.id} sincronizada: "
                        f"{result['previous_status']} → {result['new_status']}"
                    )
                    
            except Exception as e:
                total_errors += 1
                error_info = {
                    'application_id': application.id,
                    'error': str(e),
                    'error_type': type(e).__name__
                }
                errors.append(error_info)
                logger.error(
                    f"[SYNC] Error sincronizando solicitud {application.id}: {str(e)}",
                    exc_info=True
                )
        
        logger.info(
            f"[SYNC] Sincronización masiva completada: "
            f"{total_synced}/{total_found} sincronizadas, {total_errors} errores"
        )
        
        return {
            'total_found': total_found,
            'total_synced': total_synced,
            'total_errors': total_errors,
            'synced_applications': synced_applications,
            'errors': errors
        }
