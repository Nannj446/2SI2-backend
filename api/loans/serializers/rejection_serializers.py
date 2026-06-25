"""
Serializers para motivos de rechazo.

SP3-99: Aprobación o Rechazo de Créditos
"""

from rest_framework import serializers
from api.loans.models_rejection import RejectionReason


class RejectionReasonSerializer(serializers.ModelSerializer):
    """Serializer para motivos de rechazo"""
    
    category_display = serializers.CharField(
        source='get_category_display',
        read_only=True
    )
    
    class Meta:
        model = RejectionReason
        fields = [
            'id', 'code', 'name', 'description', 'category',
            'category_display', 'is_active', 'display_order',
            'requires_notes'
        ]
        read_only_fields = ['id']
