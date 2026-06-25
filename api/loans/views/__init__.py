"""
Views para gestión de créditos.

Organización:
- rule_viewsets.py: ViewSets para CU-09 (Administración de Reglas)
- document_viewsets.py: ViewSets para CU-12 (Gestión Documental)
- timeline_viewsets.py: ViewSets para CU-07 (Timeline y Seguimiento)
- active_viewsets.py: ViewSets para SP3 (Créditos Activos)
- payment_viewsets.py: ViewSets para SP3 (Pagos)
- client_active_viewsets.py: ViewSets para SP3 (Cliente Mobile)
"""

from .rule_viewsets import (
    TenantRuleSetViewSet,
    EligibilityRuleViewSet,
    CreditProductParameterViewSet,
    WorkflowStageDefinitionViewSet,
    DecisionThresholdViewSet,
)
from .document_viewsets import (
    ClientDocumentViewSet,
    StaffDocumentViewSet,
)
from .timeline_viewsets import (
    ClientApplicationViewSet,
)
from .active_viewsets import (
    ActiveCreditViewSet,
)
from .payment_viewsets import (
    CreditPaymentViewSet,
)
from .client_active_viewsets import (
    MyActiveCreditsViewSet,
)

__all__ = [
    # Rule viewsets (CU-09)
    'TenantRuleSetViewSet',
    'EligibilityRuleViewSet',
    'CreditProductParameterViewSet',
    'WorkflowStageDefinitionViewSet',
    'DecisionThresholdViewSet',
    # Document viewsets (CU-12)
    'ClientDocumentViewSet',
    'StaffDocumentViewSet',
    # Timeline viewsets (CU-07)
    'ClientApplicationViewSet',
    # Active credit viewsets (SP3)
    'ActiveCreditViewSet',
    'CreditPaymentViewSet',
    'MyActiveCreditsViewSet',
]
