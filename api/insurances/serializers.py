"""
Serializers para Gestión de Seguros.
"""
from rest_framework import serializers

from .models import (
    Insurer, Insurance, InsuranceCoverage,
    ProductInsurance, CreditInsurance
)


class InsurerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Insurer
        fields = [
            'id', 'name', 'code', 'nit', 'phone',
            'email', 'address', 'is_active',
            'institution', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'institution', 'created_at', 'updated_at']


class InsurerListSerializer(serializers.ModelSerializer):
    insurance_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Insurer
        fields = ['id', 'name', 'code', 'is_active', 'insurance_count']


class InsuranceCoverageSerializer(serializers.ModelSerializer):
    class Meta:
        model = InsuranceCoverage
        fields = [
            'id', 'insurance', 'name', 'coverage_type',
            'value', 'max_value', 'conditions', 'exclusions',
            'display_order', 'institution', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'institution', 'created_at', 'updated_at']


class InsuranceCoverageListSerializer(serializers.ModelSerializer):
    class Meta:
        model = InsuranceCoverage
        fields = ['id', 'name', 'coverage_type', 'value', 'max_value']


class InsuranceSerializer(serializers.ModelSerializer):
    insurer_name = serializers.CharField(source='insurer.name', read_only=True)
    coverages = InsuranceCoverageSerializer(many=True, read_only=True)

    class Meta:
        model = Insurance
        fields = [
            'id', 'name', 'code', 'insurance_type', 'description',
            'insurer', 'insurer_name', 'is_mandatory', 'is_active',
            'coverage_type', 'coverage_value', 'max_coverage_amount',
            'min_term_months', 'max_term_months', 'is_renewable',
            'grace_period_days', 'premium_type', 'base_premium',
            'requires_medical_exam', 'has_deductible', 'deductible_percentage',
            'coverages', 'institution', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'institution', 'created_at', 'updated_at']


class InsuranceListSerializer(serializers.ModelSerializer):
    insurer_name = serializers.CharField(source='insurer.name', read_only=True)
    insurance_type_display = serializers.CharField(source='get_insurance_type_display', read_only=True)

    class Meta:
        model = Insurance
        fields = [
            'id', 'name', 'code', 'insurance_type', 'insurance_type_display',
            'insurer_name', 'is_mandatory', 'is_active', 'base_premium'
        ]


class CreateInsuranceSerializer(serializers.ModelSerializer):
    coverages = InsuranceCoverageSerializer(many=True, required=False)

    class Meta:
        model = Insurance
        fields = [
            'name', 'code', 'insurance_type', 'description',
            'insurer', 'is_mandatory', 'is_active',
            'coverage_type', 'coverage_value', 'max_coverage_amount',
            'min_term_months', 'max_term_months', 'is_renewable',
            'grace_period_days', 'premium_type', 'base_premium',
            'requires_medical_exam', 'has_deductible', 'deductible_percentage',
            'coverages'
        ]

    def create(self, validated_data):
        coverages_data = validated_data.pop('coverages', [])
        insurance = Insurance.objects.create(**validated_data)
        for coverage_data in coverages_data:
            InsuranceCoverage.objects.create(insurance=insurance, **coverage_data)
        return insurance

    def update(self, instance, validated_data):
        coverages_data = validated_data.pop('coverages', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        if coverages_data is not None:
            instance.coverages.all().delete()
            for coverage_data in coverages_data:
                InsuranceCoverage.objects.create(insurance=instance, **coverage_data)
        return instance


class ProductInsuranceSerializer(serializers.ModelSerializer):
    insurance_name = serializers.CharField(source='insurance.name', read_only=True)
    insurance_code = serializers.CharField(source='insurance.code', read_only=True)
    insurance_type = serializers.CharField(source='insurance.insurance_type', read_only=True)
    premium_type_display = serializers.CharField(source='get_premium_type_display', read_only=True)

    class Meta:
        model = ProductInsurance
        fields = [
            'id', 'product', 'insurance', 'insurance_name', 'insurance_code',
            'insurance_type', 'is_required', 'premium_type', 'premium_type_display',
            'custom_premium', 'display_order', 'institution', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'institution', 'created_at', 'updated_at']


class ProductInsuranceListSerializer(serializers.ModelSerializer):
    insurance_name = serializers.CharField(source='insurance.name', read_only=True)
    insurance_code = serializers.CharField(source='insurance.code', read_only=True)
    is_required_display = serializers.SerializerMethodField()

    class Meta:
        model = ProductInsurance
        fields = ['id', 'insurance', 'insurance_name', 'insurance_code', 'is_required', 'is_required_display']

    def get_is_required_display(self, obj):
        return 'Sí' if obj.is_required else 'No'


class CreateProductInsuranceSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductInsurance
        fields = [
            'insurance', 'is_required', 'premium_type',
            'custom_premium', 'display_order'
        ]


class CreditInsuranceSerializer(serializers.ModelSerializer):
    insurance_name = serializers.CharField(source='insurance.name', read_only=True)
    insurance_type = serializers.CharField(source='insurance.insurance_type', read_only=True)
    insurer_name = serializers.CharField(source='insurance.insurer.name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    is_expired = serializers.BooleanField(read_only=True)
    days_until_expiry = serializers.IntegerField(read_only=True)
    active_credit_code = serializers.CharField(source='active_credit.code', read_only=True)

    class Meta:
        model = CreditInsurance
        fields = [
            'id', 'active_credit', 'active_credit_code', 'insurance',
            'insurance_name', 'insurance_type', 'insurer_name',
            'policy_number', 'start_date', 'end_date',
            'total_premium', 'premium_paid', 'status', 'status_display',
            'beneficiary_name', 'beneficiary_nit', 'notes',
            'is_expired', 'days_until_expiry',
            'institution', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'institution', 'created_at', 'updated_at',
            'is_expired', 'days_until_expiry'
        ]


class CreditInsuranceListSerializer(serializers.ModelSerializer):
    insurance_name = serializers.CharField(source='insurance.name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    days_until_expiry = serializers.IntegerField(read_only=True)

    class Meta:
        model = CreditInsurance
        fields = [
            'id', 'policy_number', 'insurance_name', 'status',
            'status_display', 'start_date', 'end_date',
            'total_premium', 'days_until_expiry'
        ]


class CreateCreditInsuranceSerializer(serializers.ModelSerializer):
    class Meta:
        model = CreditInsurance
        fields = [
            'insurance', 'policy_number', 'start_date', 'end_date',
            'total_premium', 'beneficiary_name', 'beneficiary_nit', 'notes'
        ]


class UpdateCreditInsuranceSerializer(serializers.ModelSerializer):
    class Meta:
        model = CreditInsurance
        fields = [
            'status', 'end_date', 'total_premium', 'premium_paid',
            'beneficiary_name', 'beneficiary_nit', 'notes'
        ]


class PremiumCalculationSerializer(serializers.Serializer):
    insurance_id = serializers.IntegerField()
    loan_amount = serializers.DecimalField(max_digits=15, decimal_places=2)
    loan_term_months = serializers.IntegerField()
    balance = serializers.DecimalField(max_digits=15, decimal_places=2, required=False)


class PremiumCalculationResponseSerializer(serializers.Serializer):
    insurance_id = serializers.IntegerField()
    insurance_name = serializers.CharField()
    premium_type = serializers.CharField()
    premium_mode = serializers.CharField()
    base_premium = serializers.DecimalField(max_digits=10, decimal_places=4)
    calculated_premium = serializers.DecimalField(max_digits=15, decimal_places=2)
    monthly_premium = serializers.DecimalField(max_digits=15, decimal_places=2, required=False)
    lump_sum_premium = serializers.DecimalField(max_digits=15, decimal_places=2, required=False)
    annual_premium = serializers.DecimalField(max_digits=15, decimal_places=2, required=False)
