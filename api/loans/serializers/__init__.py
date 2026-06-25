"""
Serializers para el módulo de loans.

Organización:
- loan_serializers.py: Serializers principales de LoanApplication
- rule_serializers.py: Serializers para CU-09 (Administración de Reglas)
- document_serializers.py: Serializers para CU-12 (Gestión Documental)
- timeline_serializers.py: Serializers para CU-07 (Timeline y Seguimiento)
- active_serializers.py: Serializers para SP3 (Créditos Activos y Pagos)
"""

# Importar serializers principales (mantener compatibilidad con código existente)
from api.loans.serializers.loan_serializers import *

# Importar serializers de reglas (CU-09)
from api.loans.serializers.rule_serializers import (
    TenantRuleSetSerializer,
    TenantRuleSetWriteSerializer,
    EligibilityRuleSerializer,
    CreditProductParameterSerializer,
    WorkflowStageDefinitionSerializer,
    DecisionThresholdSerializer,
    RuleSetAuditSerializer,
)

# Importar serializers de documentos (CU-12)
from api.loans.serializers.document_serializers import (
    LoanApplicationDocumentRequirementSerializer,
    DocumentUploadSerializer,
    DocumentReviewSerializer,
    DocumentReviewHistorySerializer,
)

# Importar serializers de timeline (CU-07)
from api.loans.serializers.timeline_serializers import (
    TimelineEventSerializer,
    PendingActionSerializer,
    LoanApplicationTimelineSerializer,
    LoanApplicationListSerializer,
)

# Importar serializers de créditos activos (SP3)
from api.loans.serializers.active_serializers import (
    ActiveCreditSerializer,
    ActiveCreditListSerializer,
    ActiveCreditSummarySerializer,
    CreditInstallmentSerializer,
    CreditInstallmentListSerializer,
    CreditPaymentSerializer,
    CreditPaymentListSerializer,
    CreatePaymentSerializer,
    ConfirmPaymentSerializer,
    StartOnlinePaymentSerializer,
    CreditPaymentAllocationSerializer,
    CreditGracePeriodSerializer,
    ApplyGracePeriodSerializer,
    CreditRestructuringSerializer,
    RestructureSerializer,
    CreditStatusHistorySerializer,
    ActivateFromContractSerializer,
)

__all__ = [
    # Serializers de reglas (CU-09)
    'TenantRuleSetSerializer',
    'TenantRuleSetWriteSerializer',
    'EligibilityRuleSerializer',
    'CreditProductParameterSerializer',
    'WorkflowStageDefinitionSerializer',
    'DecisionThresholdSerializer',
    'RuleSetAuditSerializer',
    # Serializers de documentos (CU-12)
    'LoanApplicationDocumentRequirementSerializer',
    'DocumentUploadSerializer',
    'DocumentReviewSerializer',
    'DocumentReviewHistorySerializer',
    # Serializers de timeline (CU-07)
    'TimelineEventSerializer',
    'PendingActionSerializer',
    'LoanApplicationTimelineSerializer',
    'LoanApplicationListSerializer',
    # Serializers de créditos activos (SP3)
    'ActiveCreditSerializer',
    'ActiveCreditListSerializer',
    'ActiveCreditSummarySerializer',
    'CreditInstallmentSerializer',
    'CreditInstallmentListSerializer',
    'CreditPaymentSerializer',
    'CreditPaymentListSerializer',
    'CreatePaymentSerializer',
    'ConfirmPaymentSerializer',
    'StartOnlinePaymentSerializer',
    'CreditPaymentAllocationSerializer',
    'CreditGracePeriodSerializer',
    'ApplyGracePeriodSerializer',
    'CreditRestructuringSerializer',
    'RestructureSerializer',
    'CreditStatusHistorySerializer',
    'ActivateFromContractSerializer',
]
