"""
Business services for collateral (garantias).
"""

from decimal import Decimal
from typing import Any, Dict, Optional
from uuid import uuid4

from django.db import transaction
from django.utils import timezone

from api.audit.services import AuditService
from api.garantias.models import (
    Collateral,
    Guarantor,
    CollateralDocument,
    CollateralValuation,
)
from api.storage.constants import ALL_DOCUMENT_MIME_TYPES, SIZE_20MB
from api.storage.models import FileResource
from api.storage.services import StorageService
from api.storage.validators import validate_file_size, validate_real_mime_type


class CollateralValidationError(Exception):
    """Raised when collateral validation fails."""


class GuarantorValidationError(Exception):
    """Raised when guarantor validation fails."""


class CollateralDocumentError(Exception):
    """Raised when collateral document handling fails."""


class CollateralService:
    """Service for collateral operations."""

    @staticmethod
    def _calculate_coverage_percentage(
        loan_amount: Optional[Decimal],
        collateral_value: Optional[Decimal],
    ) -> Optional[Decimal]:
        if not loan_amount or loan_amount <= 0 or not collateral_value:
            return None
        coverage = (collateral_value / loan_amount) * Decimal('100')
        return coverage.quantize(Decimal('0.01'))

    @staticmethod
    def _get_loan_amount(loan_application) -> Optional[Decimal]:
        return loan_application.approved_amount or loan_application.requested_amount

    @staticmethod
    def _validate_type_specific_fields(data: Dict[str, Any]) -> None:
        collateral_type = data.get('collateral_type')
        if collateral_type == Collateral.CollateralType.REAL_ESTATE:
            if not data.get('property_address'):
                raise CollateralValidationError('Property address is required for real estate')
            if not data.get('property_registry_number'):
                raise CollateralValidationError('Registry number is required for real estate')
        if collateral_type == Collateral.CollateralType.VEHICLE:
            if not data.get('vehicle_plate') and not data.get('vehicle_vin'):
                raise CollateralValidationError('Vehicle plate or VIN is required for vehicle collateral')

    @staticmethod
    @transaction.atomic
    def create_collateral(user, loan_application, data: Dict[str, Any]) -> Collateral:
        """Create a collateral for a loan application."""
        CollateralService._validate_type_specific_fields(data)

        loan_amount = CollateralService._get_loan_amount(loan_application)
        collateral_value = data.get('appraised_value') or data.get('estimated_value')
        coverage = CollateralService._calculate_coverage_percentage(loan_amount, collateral_value)

        collateral = Collateral.objects.create(
            institution=loan_application.institution,
            loan_application=loan_application,
            collateral_type=data['collateral_type'],
            description=data.get('description', ''),
            estimated_value=data['estimated_value'],
            appraised_value=data.get('appraised_value'),
            coverage_percentage=coverage,
            property_address=data.get('property_address'),
            property_registry_number=data.get('property_registry_number'),
            property_area_m2=data.get('property_area_m2'),
            vehicle_plate=data.get('vehicle_plate'),
            vehicle_vin=data.get('vehicle_vin'),
            vehicle_year=data.get('vehicle_year'),
            vehicle_brand=data.get('vehicle_brand'),
            vehicle_model=data.get('vehicle_model'),
            ownership_verified=data.get('ownership_verified', False),
            has_liens=data.get('has_liens', False),
            lien_details=data.get('lien_details', ''),
            insurance_policy_number=data.get('insurance_policy_number'),
            insurance_company=data.get('insurance_company'),
            insurance_expiry_date=data.get('insurance_expiry_date'),
            registered_by=user,
            notes=data.get('notes', ''),
        )

        AuditService.log_create(
            user=user,
            resource_type='Collateral',
            resource_id=collateral.id,
            description='Collateral created',
            institution=loan_application.institution,
        )

        return collateral

    @staticmethod
    @transaction.atomic
    def update_collateral(user, collateral: Collateral, data: Dict[str, Any]) -> Collateral:
        """Update a collateral record."""
        if collateral.status in [Collateral.Status.APPROVED, Collateral.Status.RELEASED]:
            raise CollateralValidationError('Approved or released collaterals cannot be edited')

        CollateralService._validate_type_specific_fields(data)

        updatable_fields = [
            'collateral_type',
            'description',
            'estimated_value',
            'appraised_value',
            'property_address',
            'property_registry_number',
            'property_area_m2',
            'vehicle_plate',
            'vehicle_vin',
            'vehicle_year',
            'vehicle_brand',
            'vehicle_model',
            'ownership_verified',
            'has_liens',
            'lien_details',
            'insurance_policy_number',
            'insurance_company',
            'insurance_expiry_date',
            'notes',
            'is_active',
        ]

        for field in updatable_fields:
            if field in data:
                setattr(collateral, field, data[field])

        # Recalculate coverage if values changed
        if 'estimated_value' in data or 'appraised_value' in data:
            loan_amount = CollateralService._get_loan_amount(collateral.loan_application)
            collateral_value = collateral.get_effective_value()
            collateral.coverage_percentage = CollateralService._calculate_coverage_percentage(
                loan_amount,
                collateral_value,
            )

        collateral.save()

        AuditService.log_update(
            user=user,
            resource_type='Collateral',
            resource_id=collateral.id,
            description='Collateral updated',
            institution=collateral.institution,
        )

        return collateral

    @staticmethod
    @transaction.atomic
    def approve_collateral(user, collateral: Collateral, notes: str = '') -> Collateral:
        """Approve collateral after validations."""
        if collateral.status != Collateral.Status.PENDING:
            raise CollateralValidationError('Only pending collaterals can be approved')

        # Validate minimal legal and document checks
        if collateral.has_liens and not collateral.lien_details:
            raise CollateralValidationError('Lien details are required when has_liens is true')

        if collateral.collateral_type in [
            Collateral.CollateralType.REAL_ESTATE,
            Collateral.CollateralType.VEHICLE,
        ]:
            if collateral.appraised_value is None:
                raise CollateralValidationError('Appraised value is required for this collateral type')
            if not collateral.documents.filter(is_valid=True).exists():
                raise CollateralValidationError('At least one valid document is required')

        collateral.status = Collateral.Status.APPROVED
        collateral.approved_by = user
        collateral.approved_at = timezone.now()
        collateral.rejection_reason = ''
        if notes:
            collateral.notes = notes
        collateral.save(update_fields=[
            'status', 'approved_by', 'approved_at', 'rejection_reason', 'notes', 'updated_at'
        ])

        AuditService.log_update(
            user=user,
            resource_type='Collateral',
            resource_id=collateral.id,
            description='Collateral approved',
            institution=collateral.institution,
        )

        return collateral

    @staticmethod
    @transaction.atomic
    def reject_collateral(user, collateral: Collateral, reason: str) -> Collateral:
        """Reject collateral with a reason."""
        if not reason:
            raise CollateralValidationError('Rejection reason is required')

        collateral.status = Collateral.Status.REJECTED
        collateral.approved_by = None
        collateral.approved_at = None
        collateral.rejection_reason = reason
        collateral.save(update_fields=[
            'status', 'approved_by', 'approved_at', 'rejection_reason', 'updated_at'
        ])

        AuditService.log_update(
            user=user,
            resource_type='Collateral',
            resource_id=collateral.id,
            description='Collateral rejected',
            institution=collateral.institution,
        )

        return collateral

    @staticmethod
    @transaction.atomic
    def release_collateral(user, collateral: Collateral, notes: str = '') -> Collateral:
        """Release collateral (used when the loan is closed)."""
        if collateral.status != Collateral.Status.APPROVED:
            raise CollateralValidationError('Only approved collaterals can be released')

        collateral.status = Collateral.Status.RELEASED
        if notes:
            collateral.notes = notes
        collateral.save(update_fields=['status', 'notes', 'updated_at'])

        AuditService.log_update(
            user=user,
            resource_type='Collateral',
            resource_id=collateral.id,
            description='Collateral released',
            institution=collateral.institution,
        )

        return collateral

    @staticmethod
    def validate_collateral_requirements(loan_application) -> Dict[str, Any]:
        """Validate collateral coverage against product rules."""
        product = loan_application.product
        params = product.selected_parameter or product.get_parameters()
        if not params or not params.requires_collateral:
            return {'valid': True, 'errors': [], 'coverage': None}

        approved_collaterals = Collateral.objects.filter(
            loan_application=loan_application,
            status=Collateral.Status.APPROVED,
            is_active=True,
        )

        if not approved_collaterals.exists():
            return {'valid': False, 'errors': ['No approved collateral found'], 'coverage': None}

        total_value = Decimal('0')
        for collateral in approved_collaterals:
            value = collateral.get_effective_value()
            if value:
                total_value += value

        loan_amount = CollateralService._get_loan_amount(loan_application)
        coverage = CollateralService._calculate_coverage_percentage(loan_amount, total_value)

        min_coverage = None
        if params:
            min_coverage = params.get_min_collateral_coverage()

        if min_coverage and coverage is not None and coverage < min_coverage:
            return {
                'valid': False,
                'errors': [
                    f'Collateral coverage {coverage}% is below minimum {min_coverage}%'
                ],
                'coverage': coverage,
            }

        return {'valid': True, 'errors': [], 'coverage': coverage}


class GuarantorService:
    """Service for guarantor operations."""

    @staticmethod
    @transaction.atomic
    def create_guarantor(user, loan_application, data: Dict[str, Any]) -> Guarantor:
        if data.get('monthly_income') is not None and data['monthly_income'] < 0:
            raise GuarantorValidationError('Monthly income must be positive')

        collateral = data.get('collateral')
        if collateral:
            if collateral.institution_id != loan_application.institution_id:
                raise GuarantorValidationError('Collateral does not belong to the same institution')
            if collateral.loan_application_id != loan_application.id:
                raise GuarantorValidationError('Collateral does not belong to the same loan application')

        guarantor = Guarantor.objects.create(
            institution=loan_application.institution,
            loan_application=loan_application,
            collateral=collateral,
            first_name=data['first_name'],
            last_name=data['last_name'],
            document_type=data['document_type'],
            document_number=data['document_number'],
            document_extension=data.get('document_extension'),
            birth_date=data['birth_date'],
            gender=data.get('gender'),
            email=data['email'],
            phone=data['phone'],
            mobile_phone=data.get('mobile_phone'),
            address=data['address'],
            city=data['city'],
            department=data['department'],
            employment_type=data['employment_type'],
            employer_name=data.get('employer_name'),
            job_title=data.get('job_title'),
            monthly_income=data['monthly_income'],
            relationship_to_borrower=data['relationship_to_borrower'],
        )

        AuditService.log_create(
            user=user,
            resource_type='Guarantor',
            resource_id=guarantor.id,
            description='Guarantor created',
            institution=loan_application.institution,
        )

        return guarantor

    @staticmethod
    @transaction.atomic
    def update_guarantor(user, guarantor: Guarantor, data: Dict[str, Any]) -> Guarantor:
        if guarantor.status == Guarantor.Status.APPROVED:
            raise GuarantorValidationError('Approved guarantors cannot be edited')

        if 'collateral' in data and data['collateral'] is not None:
            collateral = data['collateral']
            if collateral.institution_id != guarantor.institution_id:
                raise GuarantorValidationError('Collateral does not belong to the same institution')
            if collateral.loan_application_id != guarantor.loan_application_id:
                raise GuarantorValidationError('Collateral does not belong to the same loan application')

        updatable_fields = [
            'collateral',
            'first_name',
            'last_name',
            'document_type',
            'document_number',
            'document_extension',
            'birth_date',
            'gender',
            'email',
            'phone',
            'mobile_phone',
            'address',
            'city',
            'department',
            'employment_type',
            'employer_name',
            'job_title',
            'monthly_income',
            'relationship_to_borrower',
            'is_active',
        ]

        for field in updatable_fields:
            if field in data:
                setattr(guarantor, field, data[field])

        guarantor.save()

        AuditService.log_update(
            user=user,
            resource_type='Guarantor',
            resource_id=guarantor.id,
            description='Guarantor updated',
            institution=guarantor.institution,
        )

        return guarantor

    @staticmethod
    @transaction.atomic
    def approve_guarantor(user, guarantor: Guarantor) -> Guarantor:
        if guarantor.status != Guarantor.Status.PENDING:
            raise GuarantorValidationError('Only pending guarantors can be approved')

        guarantor.status = Guarantor.Status.APPROVED
        guarantor.approved_by = user
        guarantor.approved_at = timezone.now()
        guarantor.rejection_reason = ''
        guarantor.save(update_fields=[
            'status', 'approved_by', 'approved_at', 'rejection_reason', 'updated_at'
        ])

        AuditService.log_update(
            user=user,
            resource_type='Guarantor',
            resource_id=guarantor.id,
            description='Guarantor approved',
            institution=guarantor.institution,
        )

        return guarantor

    @staticmethod
    @transaction.atomic
    def reject_guarantor(user, guarantor: Guarantor, reason: str) -> Guarantor:
        if not reason:
            raise GuarantorValidationError('Rejection reason is required')

        guarantor.status = Guarantor.Status.REJECTED
        guarantor.approved_by = None
        guarantor.approved_at = None
        guarantor.rejection_reason = reason
        guarantor.save(update_fields=[
            'status', 'approved_by', 'approved_at', 'rejection_reason', 'updated_at'
        ])

        AuditService.log_update(
            user=user,
            resource_type='Guarantor',
            resource_id=guarantor.id,
            description='Guarantor rejected',
            institution=guarantor.institution,
        )

        return guarantor


class CollateralDocumentService:
    """Service for collateral document operations."""

    @staticmethod
    @transaction.atomic
    def upload_document(
        collateral: Collateral,
        document_type: str,
        file,
        uploaded_by,
        description: str = '',
        expiry_date=None,
        notes: str = '',
    ) -> CollateralDocument:
        if not file:
            raise CollateralDocumentError('File is required')

        # Basic file validation with shared storage rules
        try:
            validate_file_size(file, SIZE_20MB)
            mime_type = validate_real_mime_type(file, set(ALL_DOCUMENT_MIME_TYPES))
        except Exception as exc:
            raise CollateralDocumentError(str(exc)) from exc
        extension = file.name.rsplit('.', 1)[-1].lower() if '.' in file.name else ''

        try:
            storage_service = StorageService()
        except Exception as exc:
            raise CollateralDocumentError(str(exc)) from exc
        file_id = str(uuid4())
        stored_name = f"{file_id}.{extension}" if extension else file_id
        storage_path = (
            f"collateral_documents/{collateral.institution_id}/{collateral.id}/{stored_name}"
        )

        # Upload content to storage
        try:
            file.seek(0)
            file_content = file.read()
            storage_service.upload_to_storage(
                file_path=storage_path,
                file_content=file_content,
                content_type=mime_type,
            )
        except Exception as exc:
            raise CollateralDocumentError(str(exc)) from exc

        file_resource = FileResource.objects.create(
            tenant=collateral.institution,
            resource_type=FileResource.ResourceType.COLLATERAL,
            entity_type='collateral_document',
            entity_id=collateral.id,
            original_name=file.name,
            stored_name=stored_name,
            file_path=storage_path,
            mime_type=mime_type,
            extension=extension,
            size=file.size,
            category=document_type,
            visibility=FileResource.Visibility.PRIVATE,
            uploaded_by=uploaded_by,
            status=FileResource.Status.ACTIVE,
        )

        document = CollateralDocument.objects.create(
            institution=collateral.institution,
            collateral=collateral,
            document_type=document_type,
            file_resource=file_resource,
            description=description,
            uploaded_by=uploaded_by,
            expiry_date=expiry_date,
            notes=notes,
        )

        AuditService.log_create(
            user=uploaded_by,
            resource_type='CollateralDocument',
            resource_id=document.id,
            description='Collateral document uploaded',
            institution=collateral.institution,
        )

        return document

    @staticmethod
    @transaction.atomic
    def verify_document(
        user,
        document: CollateralDocument,
        is_valid: bool,
        notes: str = '',
    ) -> CollateralDocument:
        document.is_valid = is_valid
        document.verified_by = user
        document.verified_at = timezone.now()
        if notes:
            document.notes = notes
        document.save(update_fields=[
            'is_valid', 'verified_by', 'verified_at', 'notes', 'updated_at'
        ])

        AuditService.log_update(
            user=user,
            resource_type='CollateralDocument',
            resource_id=document.id,
            description='Collateral document verified',
            institution=document.institution,
        )

        return document


class CollateralValuationService:
    """Service for collateral valuation operations."""

    @staticmethod
    @transaction.atomic
    def create_valuation(user, collateral: Collateral, data: Dict[str, Any]) -> CollateralValuation:
        valuation = CollateralValuation.objects.create(
            institution=collateral.institution,
            collateral=collateral,
            valuation_type=data['valuation_type'],
            appraiser_name=data['appraiser_name'],
            appraiser_license=data.get('appraiser_license'),
            appraiser_company=data.get('appraiser_company'),
            valuation_date=data['valuation_date'],
            appraised_value=data['appraised_value'],
            valuation_method=data.get('valuation_method', ''),
            observations=data.get('observations', ''),
            report_file=data.get('report_file'),
            valid_until=data.get('valid_until'),
        )

        AuditService.log_create(
            user=user,
            resource_type='CollateralValuation',
            resource_id=valuation.id,
            description='Collateral valuation created',
            institution=collateral.institution,
        )

        return valuation

    @staticmethod
    @transaction.atomic
    def approve_valuation(user, valuation: CollateralValuation) -> CollateralValuation:
        valuation.approved_by = user
        valuation.approved_at = timezone.now()
        valuation.save(update_fields=['approved_by', 'approved_at', 'updated_at'])

        # Sync collateral appraised value for the latest approved valuation
        collateral = valuation.collateral
        collateral.appraised_value = valuation.appraised_value
        loan_amount = CollateralService._get_loan_amount(collateral.loan_application)
        collateral.coverage_percentage = CollateralService._calculate_coverage_percentage(
            loan_amount,
            collateral.appraised_value,
        )
        collateral.save(update_fields=['appraised_value', 'coverage_percentage', 'updated_at'])

        AuditService.log_update(
            user=user,
            resource_type='CollateralValuation',
            resource_id=valuation.id,
            description='Collateral valuation approved',
            institution=valuation.institution,
        )

        return valuation
