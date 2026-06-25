"""
Serializers for collateral (garantias) and guarantors.
"""

from rest_framework import serializers

from api.garantias.models import (
    Collateral,
    Guarantor,
    CollateralDocument,
    CollateralValuation,
)
from api.storage.serializers import FileResourceSerializer


class CollateralListSerializer(serializers.ModelSerializer):
    """Serializer for collateral list views."""

    collateral_type_display = serializers.CharField(
        source='get_collateral_type_display',
        read_only=True,
    )
    status_display = serializers.CharField(
        source='get_status_display',
        read_only=True,
    )
    loan_application_number = serializers.CharField(
        source='loan_application.application_number',
        read_only=True,
    )

    class Meta:
        model = Collateral
        fields = [
            'id',
            'loan_application',
            'loan_application_number',
            'collateral_type',
            'collateral_type_display',
            'estimated_value',
            'appraised_value',
            'coverage_percentage',
            'status',
            'status_display',
            'created_at',
            'updated_at',
        ]
        read_only_fields = fields


class CollateralDetailSerializer(serializers.ModelSerializer):
    """Serializer for collateral detail views."""

    collateral_type_display = serializers.CharField(
        source='get_collateral_type_display',
        read_only=True,
    )
    status_display = serializers.CharField(
        source='get_status_display',
        read_only=True,
    )
    loan_application_number = serializers.CharField(
        source='loan_application.application_number',
        read_only=True,
    )
    registered_by_name = serializers.SerializerMethodField()
    approved_by_name = serializers.SerializerMethodField()
    documents_count = serializers.SerializerMethodField()
    valuations_count = serializers.SerializerMethodField()

    class Meta:
        model = Collateral
        fields = [
            'id',
            'loan_application',
            'loan_application_number',
            'collateral_type',
            'collateral_type_display',
            'description',
            'estimated_value',
            'appraised_value',
            'coverage_percentage',
            'status',
            'status_display',
            'is_active',
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
            'registered_by',
            'registered_by_name',
            'approved_by',
            'approved_by_name',
            'approved_at',
            'rejection_reason',
            'notes',
            'documents_count',
            'valuations_count',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'id',
            'coverage_percentage',
            'approved_at',
            'documents_count',
            'valuations_count',
            'created_at',
            'updated_at',
        ]

    def get_registered_by_name(self, obj):
        if obj.registered_by:
            return f"{obj.registered_by.first_name} {obj.registered_by.last_name}".strip()
        return None

    def get_approved_by_name(self, obj):
        if obj.approved_by:
            return f"{obj.approved_by.first_name} {obj.approved_by.last_name}".strip()
        return None

    def get_documents_count(self, obj):
        return obj.documents.count()

    def get_valuations_count(self, obj):
        return obj.valuations.count()


class CollateralCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating collaterals."""

    class Meta:
        model = Collateral
        fields = [
            'loan_application',
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
        ]


class CollateralUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating collaterals."""

    class Meta:
        model = Collateral
        fields = [
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


class GuarantorListSerializer(serializers.ModelSerializer):
    """Serializer for guarantor list views."""

    status_display = serializers.CharField(
        source='get_status_display',
        read_only=True,
    )
    full_name = serializers.CharField(
        source='get_full_name',
        read_only=True,
    )

    class Meta:
        model = Guarantor
        fields = [
            'id',
            'loan_application',
            'collateral',
            'full_name',
            'document_number',
            'monthly_income',
            'status',
            'status_display',
            'created_at',
            'updated_at',
        ]
        read_only_fields = fields


class GuarantorDetailSerializer(serializers.ModelSerializer):
    """Serializer for guarantor detail views."""

    status_display = serializers.CharField(
        source='get_status_display',
        read_only=True,
    )
    full_name = serializers.CharField(
        source='get_full_name',
        read_only=True,
    )
    approved_by_name = serializers.SerializerMethodField()

    class Meta:
        model = Guarantor
        fields = [
            'id',
            'loan_application',
            'collateral',
            'first_name',
            'last_name',
            'full_name',
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
            'status',
            'status_display',
            'approved_by',
            'approved_by_name',
            'approved_at',
            'rejection_reason',
            'is_active',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'id',
            'approved_at',
            'created_at',
            'updated_at',
        ]

    def get_approved_by_name(self, obj):
        if obj.approved_by:
            return f"{obj.approved_by.first_name} {obj.approved_by.last_name}".strip()
        return None


class GuarantorCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating guarantors."""

    class Meta:
        model = Guarantor
        fields = [
            'loan_application',
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
        ]


class GuarantorUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating guarantors."""

    class Meta:
        model = Guarantor
        fields = [
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


class CollateralDocumentSerializer(serializers.ModelSerializer):
    """Serializer for collateral documents."""

    document_type_display = serializers.CharField(
        source='get_document_type_display',
        read_only=True,
    )
    uploaded_by_name = serializers.SerializerMethodField()
    verified_by_name = serializers.SerializerMethodField()
    file_resource_detail = FileResourceSerializer(
        source='file_resource',
        read_only=True,
    )
    signed_url = serializers.SerializerMethodField()

    class Meta:
        model = CollateralDocument
        fields = [
            'id',
            'collateral',
            'document_type',
            'document_type_display',
            'file_resource',
            'file_resource_detail',
            'signed_url',
            'description',
            'uploaded_by',
            'uploaded_by_name',
            'verified_by',
            'verified_by_name',
            'verified_at',
            'is_valid',
            'expiry_date',
            'notes',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'id',
            'uploaded_by',
            'verified_by',
            'verified_at',
            'created_at',
            'updated_at',
        ]

    def get_uploaded_by_name(self, obj):
        if obj.uploaded_by:
            return f"{obj.uploaded_by.first_name} {obj.uploaded_by.last_name}".strip()
        return None

    def get_verified_by_name(self, obj):
        if obj.verified_by:
            return f"{obj.verified_by.first_name} {obj.verified_by.last_name}".strip()
        return None

    def get_signed_url(self, obj):
        return obj.get_signed_url(expires_in=3600)


class CollateralDocumentUploadSerializer(serializers.Serializer):
    """Serializer for uploading collateral documents."""

    document_type = serializers.ChoiceField(
        choices=CollateralDocument.DocumentType.choices,
    )
    file = serializers.FileField()
    description = serializers.CharField(required=False, allow_blank=True)
    expiry_date = serializers.DateField(required=False, allow_null=True)
    notes = serializers.CharField(required=False, allow_blank=True)

    def validate_file(self, value):
        if not value or value.size == 0:
            raise serializers.ValidationError('File is required')
        return value


class CollateralDocumentVerifySerializer(serializers.Serializer):
    """Serializer for document verification."""

    is_valid = serializers.BooleanField()
    notes = serializers.CharField(required=False, allow_blank=True)


class CollateralValuationSerializer(serializers.ModelSerializer):
    """Serializer for collateral valuations."""

    valuation_type_display = serializers.CharField(
        source='get_valuation_type_display',
        read_only=True,
    )
    approved_by_name = serializers.SerializerMethodField()

    class Meta:
        model = CollateralValuation
        fields = [
            'id',
            'collateral',
            'valuation_type',
            'valuation_type_display',
            'appraiser_name',
            'appraiser_license',
            'appraiser_company',
            'valuation_date',
            'appraised_value',
            'valuation_method',
            'observations',
            'report_file',
            'valid_until',
            'approved_by',
            'approved_by_name',
            'approved_at',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'id',
            'approved_at',
            'created_at',
            'updated_at',
        ]

    def get_approved_by_name(self, obj):
        if obj.approved_by:
            return f"{obj.approved_by.first_name} {obj.approved_by.last_name}".strip()
        return None


class CollateralValuationCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating valuations."""

    class Meta:
        model = CollateralValuation
        fields = [
            'collateral',
            'valuation_type',
            'appraiser_name',
            'appraiser_license',
            'appraiser_company',
            'valuation_date',
            'appraised_value',
            'valuation_method',
            'observations',
            'report_file',
            'valid_until',
        ]
