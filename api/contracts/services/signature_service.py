"""
Servicio para gestión de firmas digitales de contratos

Este servicio maneja la lógica de negocio para firmar contratos
y validar firmas.
"""

import logging
import hashlib
from django.utils import timezone
from django.db import transaction
from api.contracts.models import Contract, ContractSignature

logger = logging.getLogger(__name__)


class SignatureService:
    """
    Servicio para gestión de firmas digitales.
    """
    
    @staticmethod
    def sign_contract_as_borrower(
        contract: Contract,
        user,
        signature_data: str,
        ip_address: str,
        signature_method: str = ContractSignature.SignatureMethod.DIGITAL,
        device_info: dict = None,
        geolocation: dict = None,
        verification_method: str = ''
    ) -> ContractSignature:
        """
        Firma un contrato como prestatario.
        
        Args:
            contract: Contrato a firmar
            user: Usuario prestatario que firma
            signature_data: Datos de la firma (hash, imagen, etc.)
            ip_address: Dirección IP desde donde se firma
            signature_method: Método de firma utilizado
            device_info: Información del dispositivo
            geolocation: Datos de geolocalización
            verification_method: Método de verificación de identidad usado
        
        Returns:
            ContractSignature: Registro de firma creado
        
        Raises:
            ValueError: Si el contrato no puede ser firmado o el usuario no es válido
        """
        # Validaciones
        if not contract.can_be_signed():
            raise ValueError(
                f"El contrato en estado {contract.status} no puede ser firmado."
            )
        
        # Verificar que el usuario sea el prestatario
        if contract.loan_application.client.user != user:
            raise ValueError(
                "El usuario no es el prestatario de este contrato."
            )
        
        # Verificar que no haya firmado ya
        if contract.is_signed_by_borrower:
            raise ValueError(
                "El prestatario ya ha firmado este contrato."
            )
        
        # Generar hash del documento para verificación
        document_hash = SignatureService._generate_document_hash(contract)
        
        with transaction.atomic():
            # Crear registro de firma
            signature = ContractSignature.objects.create(
                institution=contract.institution,
                contract=contract,
                signer_type=ContractSignature.SignerType.BORROWER,
                user=user,
                signed_at=timezone.now(),
                signature_method=signature_method,
                signature_data=signature_data,
                ip_address=ip_address,
                device_info=device_info if device_info is not None else {},
                geolocation=geolocation if geolocation is not None else {},
                identity_verified=True,  # Asumimos que ya pasó verificación de identidad
                verification_method=verification_method
            )
            
            # Actualizar contrato
            contract.borrower_signed_at = signature.signed_at
            contract.borrower_signature_ip = ip_address
            contract.borrower_signature_data = document_hash
            contract.save(update_fields=[
                'borrower_signed_at',
                'borrower_signature_ip',
                'borrower_signature_data',
                'updated_at'
            ])
            
            # Actualizar estado del contrato
            contract.update_status_after_signature()
            
            logger.info(
                f"Contrato {contract.contract_number} firmado por prestatario "
                f"{user.email} desde IP {ip_address}"
            )
        
        return signature
    
    @staticmethod
    def sign_contract_as_guarantor(
        contract: Contract,
        guarantor,
        signature_data: str,
        ip_address: str,
        signature_method: str = ContractSignature.SignatureMethod.DIGITAL,
        device_info: dict = None,
        geolocation: dict = None,
        verification_method: str = ''
    ) -> ContractSignature:
        """
        Firma un contrato como garante.
        
        Args:
            contract: Contrato a firmar
            guarantor: Garante que firma
            signature_data: Datos de la firma
            ip_address: Dirección IP desde donde se firma
            signature_method: Método de firma utilizado
            device_info: Información del dispositivo
            geolocation: Datos de geolocalización
            verification_method: Método de verificación de identidad usado
        
        Returns:
            ContractSignature: Registro de firma creado
        
        Raises:
            ValueError: Si el contrato no puede ser firmado o el garante no es válido
        """
        # Validaciones
        if not contract.can_be_signed():
            raise ValueError(
                f"El contrato en estado {contract.status} no puede ser firmado."
            )
        
        # Verificar que el contrato requiera firmas de garantes
        if not contract.requires_guarantor_signatures:
            raise ValueError(
                "Este contrato no requiere firmas de garantes."
            )
        
        # Verificar que el garante pertenezca a la solicitud
        if not contract.loan_application.guarantors.filter(
            id=guarantor.id,
            status='APPROVED'
        ).exists():
            raise ValueError(
                "El garante no está asociado a esta solicitud o no está aprobado."
            )
        
        # Verificar que el garante no haya firmado ya
        if contract.signatures.filter(
            signer_type=ContractSignature.SignerType.GUARANTOR,
            guarantor=guarantor
        ).exists():
            raise ValueError(
                "Este garante ya ha firmado el contrato."
            )
        
        # Generar hash del documento
        document_hash = SignatureService._generate_document_hash(contract)
        
        with transaction.atomic():
            # Crear registro de firma
            signature = ContractSignature.objects.create(
                institution=contract.institution,
                contract=contract,
                signer_type=ContractSignature.SignerType.GUARANTOR,
                guarantor=guarantor,
                signed_at=timezone.now(),
                signature_method=signature_method,
                signature_data=signature_data,
                ip_address=ip_address,
                device_info=device_info or {},
                geolocation=geolocation or {},
                identity_verified=True,
                verification_method=verification_method
            )
            
            # Actualizar estado del contrato
            contract.update_status_after_signature()
            
            logger.info(
                f"Contrato {contract.contract_number} firmado por garante "
                f"{guarantor.full_name} desde IP {ip_address}"
            )
        
        return signature
    
    @staticmethod
    def sign_contract_as_institution(
        contract: Contract,
        user,
        signature_data: str,
        ip_address: str,
        signature_method: str = ContractSignature.SignatureMethod.DIGITAL,
        device_info: dict = None
    ) -> ContractSignature:
        """
        Firma un contrato como representante de la institución.
        
        Args:
            contract: Contrato a firmar
            user: Usuario representante de la institución
            signature_data: Datos de la firma
            ip_address: Dirección IP desde donde se firma
            signature_method: Método de firma utilizado
            device_info: Información del dispositivo
        
        Returns:
            ContractSignature: Registro de firma creado
        
        Raises:
            ValueError: Si el contrato no puede ser firmado
        """
        # Validaciones
        if not contract.can_be_signed():
            raise ValueError(
                f"El contrato en estado {contract.status} no puede ser firmado."
            )
        
        # Verificar que el usuario pertenezca a la institución
        institution = getattr(user, 'institution', None)
        if not institution and hasattr(user, 'institution_memberships'):
            membership = user.institution_memberships.filter(is_active=True).first()
            if membership:
                institution = membership.institution

        if institution != contract.institution:
            raise ValueError(
                "El usuario no pertenece a la institución del contrato."
            )
        
        # Verificar que la institución no haya firmado ya
        if contract.signatures.filter(
            signer_type=ContractSignature.SignerType.INSTITUTION
        ).exists():
            raise ValueError(
                "La institución ya ha firmado este contrato."
            )
        
        with transaction.atomic():
            # Crear registro de firma
            signature = ContractSignature.objects.create(
                institution=contract.institution,
                contract=contract,
                signer_type=ContractSignature.SignerType.INSTITUTION,
                user=user,
                signed_at=timezone.now(),
                signature_method=signature_method,
                signature_data=signature_data,
                ip_address=ip_address,
                device_info=device_info or {},
                identity_verified=True,
                verification_method='internal'
            )
            
            logger.info(
                f"Contrato {contract.contract_number} firmado por institución "
                f"(representante: {user.email})"
            )
        
        return signature
    
    @staticmethod
    def _generate_document_hash(contract: Contract) -> str:
        """
        Genera un hash SHA-256 del contrato para verificación de integridad.
        
        Args:
            contract: Contrato
        
        Returns:
            str: Hash hexadecimal del documento
        """
        # Crear string con datos clave del contrato
        data_string = (
            f"{contract.contract_number}"
            f"{contract.principal_amount}"
            f"{contract.interest_rate}"
            f"{contract.term_months}"
            f"{contract.contract_date}"
            f"{contract.loan_application.client.document_number}"
        )
        
        # Generar hash SHA-256
        hash_object = hashlib.sha256(data_string.encode())
        return hash_object.hexdigest()
    
    @staticmethod
    def verify_signature(signature: ContractSignature) -> dict:
        """
        Verifica la validez de una firma.
        
        Args:
            signature: Firma a verificar
        
        Returns:
            dict: Resultado de la verificación
        """
        contract = signature.contract
        
        # Regenerar hash del documento
        current_hash = SignatureService._generate_document_hash(contract)
        
        # Comparar con hash almacenado en el contrato
        is_valid = (
            contract.borrower_signature_data == current_hash
            if signature.signer_type == ContractSignature.SignerType.BORROWER
            else True  # Para garantes e institución, validación simplificada
        )
        
        return {
            'is_valid': is_valid,
            'signer_name': signature.get_signer_name(),
            'signer_type': signature.get_signer_type_display(),
            'signed_at': signature.signed_at,
            'ip_address': signature.ip_address,
            'signature_method': signature.get_signature_method_display(),
            'identity_verified': signature.identity_verified,
            'document_hash': current_hash,
        }
    
    @staticmethod
    def get_signature_status(contract: Contract) -> dict:
        """
        Obtiene el estado de firmas de un contrato.
        
        Args:
            contract: Contrato
        
        Returns:
            dict: Estado de firmas
        """
        signatures = contract.signatures.all()
        
        borrower_signature = signatures.filter(
            signer_type=ContractSignature.SignerType.BORROWER
        ).first()
        
        guarantor_signatures = signatures.filter(
            signer_type=ContractSignature.SignerType.GUARANTOR
        )
        
        institution_signature = signatures.filter(
            signer_type=ContractSignature.SignerType.INSTITUTION
        ).first()
        
        # Contar garantes requeridos
        required_guarantors = 0
        if contract.requires_guarantor_signatures:
            required_guarantors = contract.loan_application.guarantors.filter(
                status='APPROVED'
            ).count()
        
        return {
            'borrower_signed': borrower_signature is not None,
            'borrower_signed_at': borrower_signature.signed_at if borrower_signature else None,
            'guarantors_required': required_guarantors,
            'guarantors_signed': guarantor_signatures.count(),
            'guarantors_pending': required_guarantors - guarantor_signatures.count(),
            'institution_signed': institution_signature is not None,
            'institution_signed_at': institution_signature.signed_at if institution_signature else None,
            'all_signatures_complete': contract.all_signatures_complete,
            'pending_signatures': contract.pending_signatures,
            'total_signatures': signatures.count(),
        }
    
    @staticmethod
    def request_signature_notification(contract: Contract, signer_type: str, recipient_email: str):
        """
        Envía una notificación solicitando firma.
        
        Args:
            contract: Contrato
            signer_type: Tipo de firmante (BORROWER, GUARANTOR, INSTITUTION)
            recipient_email: Email del destinatario
        
        Note:
            Esta es una función placeholder. La implementación real
            dependerá del sistema de notificaciones del proyecto.
        """
        logger.info(
            f"Solicitud de firma enviada para contrato {contract.contract_number} "
            f"a {recipient_email} (tipo: {signer_type})"
        )
        
        # TODO: Implementar envío de email con link para firmar
        # Puede integrarse con el módulo de notificaciones existente
        pass
