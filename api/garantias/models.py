"""
Models for collateral (garantias) and guarantors.
"""

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models

from api.core.models import TenantModel


class Collateral(TenantModel):
    """Collateral linked to a loan application."""

    class CollateralType(models.TextChoices):
        REAL_ESTATE = 'REAL_ESTATE', 'Real Estate'
        VEHICLE = 'VEHICLE', 'Vehicle'
        MACHINERY = 'MACHINERY', 'Machinery'
        SAVINGS = 'SAVINGS', 'Savings'
        GUARANTOR = 'GUARANTOR', 'Guarantor'
        OTHER = 'OTHER', 'Other'

    class Status(models.TextChoices):
        PENDING = 'PENDING', 'Pending'
        APPROVED = 'APPROVED', 'Approved'
        REJECTED = 'REJECTED', 'Rejected'
        RELEASED = 'RELEASED', 'Released'

    # Core relation
    loan_application = models.ForeignKey(
        'loans.LoanApplication',
        on_delete=models.CASCADE,
        related_name='collaterals',
        verbose_name='Loan Application',
    )

    collateral_type = models.CharField(
        max_length=20,
        choices=CollateralType.choices,
        verbose_name='Collateral Type',
        db_index=True,
    )

    description = models.TextField(
        blank=True,
        verbose_name='Description',
    )

    estimated_value = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        verbose_name='Estimated Value',
    )

    appraised_value = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        blank=True,
        null=True,
        validators=[MinValueValidator(0)],
        verbose_name='Appraised Value',
    )

    coverage_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        blank=True,
        null=True,
        validators=[MinValueValidator(0)],
        verbose_name='Coverage Percentage',
        help_text='Coverage over the approved loan amount',
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        verbose_name='Status',
        db_index=True,
    )

    is_active = models.BooleanField(
        default=True,
        verbose_name='Active',
        db_index=True,
    )

    # Property specific fields
    property_address = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name='Property Address',
    )

    property_registry_number = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name='Property Registry Number',
    )

    property_area_m2 = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        blank=True,
        null=True,
        validators=[MinValueValidator(0)],
        verbose_name='Property Area (m2)',
    )

    # Vehicle specific fields
    vehicle_plate = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        verbose_name='Vehicle Plate',
    )

    vehicle_vin = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        verbose_name='Vehicle VIN',
    )

    vehicle_year = models.IntegerField(
        blank=True,
        null=True,
        verbose_name='Vehicle Year',
    )

    vehicle_brand = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name='Vehicle Brand',
    )

    vehicle_model = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name='Vehicle Model',
    )

    # Legal and risk data
    ownership_verified = models.BooleanField(
        default=False,
        verbose_name='Ownership Verified',
    )

    has_liens = models.BooleanField(
        default=False,
        verbose_name='Has Liens',
    )

    lien_details = models.TextField(
        blank=True,
        verbose_name='Lien Details',
    )

    insurance_policy_number = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name='Insurance Policy Number',
    )

    insurance_company = models.CharField(
        max_length=150,
        blank=True,
        null=True,
        verbose_name='Insurance Company',
    )

    insurance_expiry_date = models.DateField(
        blank=True,
        null=True,
        verbose_name='Insurance Expiry Date',
    )

    # Audit fields
    registered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='registered_collaterals',
        verbose_name='Registered By',
    )

    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_collaterals',
        verbose_name='Approved By',
    )

    approved_at = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name='Approved At',
    )

    rejection_reason = models.TextField(
        blank=True,
        verbose_name='Rejection Reason',
    )

    notes = models.TextField(
        blank=True,
        verbose_name='Notes',
    )

    class Meta:
        verbose_name = 'Collateral'
        verbose_name_plural = 'Collaterals'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['institution', 'loan_application']),
            models.Index(fields=['institution', 'status']),
            models.Index(fields=['collateral_type']),
            models.Index(fields=['is_active']),
        ]

    def __str__(self):
        return f"{self.collateral_type} - {self.loan_application.application_number}"

    def get_effective_value(self):
        """Return appraised_value if available, otherwise estimated_value."""
        return self.appraised_value if self.appraised_value is not None else self.estimated_value


class Guarantor(TenantModel):
    """Personal guarantor for a loan application."""

    class DocumentType(models.TextChoices):
        CI = 'CI', 'Identity Card'
        NIT = 'NIT', 'Tax ID'
        PASSPORT = 'PASSPORT', 'Passport'

    class EmploymentType(models.TextChoices):
        EMPLOYED = 'EMPLOYED', 'Employed'
        SELF_EMPLOYED = 'SELF_EMPLOYED', 'Self Employed'
        BUSINESS_OWNER = 'BUSINESS_OWNER', 'Business Owner'
        RETIRED = 'RETIRED', 'Retired'
        OTHER = 'OTHER', 'Other'

    class Status(models.TextChoices):
        PENDING = 'PENDING', 'Pending'
        APPROVED = 'APPROVED', 'Approved'
        REJECTED = 'REJECTED', 'Rejected'

    loan_application = models.ForeignKey(
        'loans.LoanApplication',
        on_delete=models.CASCADE,
        related_name='guarantors',
        verbose_name='Loan Application',
    )

    collateral = models.ForeignKey(
        'garantias.Collateral',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='guarantors',
        verbose_name='Related Collateral',
    )

    # Personal info
    first_name = models.CharField(
        max_length=100,
        verbose_name='First Name',
    )

    last_name = models.CharField(
        max_length=100,
        verbose_name='Last Name',
    )

    document_type = models.CharField(
        max_length=20,
        choices=DocumentType.choices,
        verbose_name='Document Type',
    )

    document_number = models.CharField(
        max_length=30,
        verbose_name='Document Number',
    )

    document_extension = models.CharField(
        max_length=10,
        blank=True,
        null=True,
        verbose_name='Document Extension',
    )

    birth_date = models.DateField(
        verbose_name='Birth Date',
    )

    gender = models.CharField(
        max_length=1,
        choices=[('M', 'Male'), ('F', 'Female'), ('O', 'Other')],
        blank=True,
        null=True,
        verbose_name='Gender',
    )

    # Contact info
    email = models.EmailField(
        verbose_name='Email',
    )

    phone = models.CharField(
        max_length=20,
        verbose_name='Phone',
    )

    mobile_phone = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        verbose_name='Mobile Phone',
    )

    address = models.TextField(
        verbose_name='Address',
    )

    city = models.CharField(
        max_length=100,
        verbose_name='City',
    )

    department = models.CharField(
        max_length=100,
        verbose_name='Department',
    )

    # Employment and financial info
    employment_type = models.CharField(
        max_length=20,
        choices=EmploymentType.choices,
        verbose_name='Employment Type',
    )

    employer_name = models.CharField(
        max_length=200,
        blank=True,
        null=True,
        verbose_name='Employer Name',
    )

    job_title = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name='Job Title',
    )

    monthly_income = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        verbose_name='Monthly Income',
    )

    relationship_to_borrower = models.CharField(
        max_length=100,
        verbose_name='Relationship To Borrower',
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        verbose_name='Status',
        db_index=True,
    )

    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_guarantors',
        verbose_name='Approved By',
    )

    approved_at = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name='Approved At',
    )

    rejection_reason = models.TextField(
        blank=True,
        verbose_name='Rejection Reason',
    )

    is_active = models.BooleanField(
        default=True,
        verbose_name='Active',
        db_index=True,
    )

    class Meta:
        verbose_name = 'Guarantor'
        verbose_name_plural = 'Guarantors'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['institution', 'loan_application']),
            models.Index(fields=['institution', 'document_number']),
            models.Index(fields=['status']),
            models.Index(fields=['is_active']),
        ]

    def __str__(self):
        return f"{self.first_name} {self.last_name} - {self.document_number}"

    def get_full_name(self):
        """Return full name for convenience in serializers."""
        return f"{self.first_name} {self.last_name}".strip()


class CollateralDocument(TenantModel):
    """Documents associated with a collateral."""

    class DocumentType(models.TextChoices):
        DEED = 'DEED', 'Deed'
        APPRAISAL = 'APPRAISAL', 'Appraisal'
        PHOTOS = 'PHOTOS', 'Photos'
        INSURANCE = 'INSURANCE', 'Insurance'
        REGISTRATION = 'REGISTRATION', 'Registration'
        OTHER = 'OTHER', 'Other'

    collateral = models.ForeignKey(
        Collateral,
        on_delete=models.CASCADE,
        related_name='documents',
        verbose_name='Collateral',
    )

    document_type = models.CharField(
        max_length=20,
        choices=DocumentType.choices,
        verbose_name='Document Type',
        db_index=True,
    )

    file_resource = models.ForeignKey(
        'storage.FileResource',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='collateral_documents',
        verbose_name='File Resource',
    )

    description = models.TextField(
        blank=True,
        verbose_name='Description',
    )

    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='uploaded_collateral_documents',
        verbose_name='Uploaded By',
    )

    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='verified_collateral_documents',
        verbose_name='Verified By',
    )

    verified_at = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name='Verified At',
    )

    is_valid = models.BooleanField(
        default=False,
        verbose_name='Valid',
    )

    expiry_date = models.DateField(
        blank=True,
        null=True,
        verbose_name='Expiry Date',
    )

    notes = models.TextField(
        blank=True,
        verbose_name='Notes',
    )

    class Meta:
        verbose_name = 'Collateral Document'
        verbose_name_plural = 'Collateral Documents'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['collateral', 'document_type']),
            models.Index(fields=['is_valid']),
        ]

    def __str__(self):
        return f"{self.document_type} - {self.collateral_id}"

    def get_signed_url(self, expires_in=3600):
        """Return signed url if a file resource is available."""
        if self.file_resource:
            return self.file_resource.get_signed_url(expires_in=expires_in)
        return None


class CollateralValuation(TenantModel):
    """Valuations linked to a collateral."""

    class ValuationType(models.TextChoices):
        INTERNAL = 'INTERNAL', 'Internal'
        EXTERNAL = 'EXTERNAL', 'External'
        MARKET_COMPARISON = 'MARKET_COMPARISON', 'Market Comparison'

    collateral = models.ForeignKey(
        Collateral,
        on_delete=models.CASCADE,
        related_name='valuations',
        verbose_name='Collateral',
    )

    valuation_type = models.CharField(
        max_length=30,
        choices=ValuationType.choices,
        verbose_name='Valuation Type',
    )

    appraiser_name = models.CharField(
        max_length=200,
        verbose_name='Appraiser Name',
    )

    appraiser_license = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name='Appraiser License',
    )

    appraiser_company = models.CharField(
        max_length=200,
        blank=True,
        null=True,
        verbose_name='Appraiser Company',
    )

    valuation_date = models.DateField(
        verbose_name='Valuation Date',
    )

    appraised_value = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        verbose_name='Appraised Value',
    )

    valuation_method = models.TextField(
        blank=True,
        verbose_name='Valuation Method',
    )

    observations = models.TextField(
        blank=True,
        verbose_name='Observations',
    )

    report_file = models.ForeignKey(
        'storage.FileResource',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='collateral_valuations',
        verbose_name='Report File',
    )

    valid_until = models.DateField(
        blank=True,
        null=True,
        verbose_name='Valid Until',
    )

    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_collateral_valuations',
        verbose_name='Approved By',
    )

    approved_at = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name='Approved At',
    )

    class Meta:
        verbose_name = 'Collateral Valuation'
        verbose_name_plural = 'Collateral Valuations'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['collateral', 'valuation_date']),
            models.Index(fields=['approved_at']),
        ]

    def __str__(self):
        return f"{self.collateral_id} - {self.valuation_type}"
