"""
URLs for collateral (garantias) module.
"""

from django.urls import path

from api.garantias.views import (
    CollateralListCreateAPIView,
    CollateralDetailAPIView,
    CollateralApproveAPIView,
    CollateralRejectAPIView,
    CollateralReleaseAPIView,
    CollateralDocumentsAPIView,
    CollateralDocumentVerifyAPIView,
    CollateralValuationsAPIView,
    CollateralValuationApproveAPIView,
    GuarantorListCreateAPIView,
    GuarantorDetailAPIView,
    GuarantorApproveAPIView,
    GuarantorRejectAPIView,
)

app_name = 'garantias'

urlpatterns = [
    # Collaterals
    path('', CollateralListCreateAPIView.as_view(), name='collateral-list-create'),
    path('<int:collateral_id>/', CollateralDetailAPIView.as_view(), name='collateral-detail'),
    path('<int:collateral_id>/approve/', CollateralApproveAPIView.as_view(), name='collateral-approve'),
    path('<int:collateral_id>/reject/', CollateralRejectAPIView.as_view(), name='collateral-reject'),
    path('<int:collateral_id>/release/', CollateralReleaseAPIView.as_view(), name='collateral-release'),
    path('<int:collateral_id>/documents/', CollateralDocumentsAPIView.as_view(), name='collateral-documents'),
    path('documents/<int:document_id>/verify/', CollateralDocumentVerifyAPIView.as_view(), name='collateral-document-verify'),
    path('<int:collateral_id>/valuations/', CollateralValuationsAPIView.as_view(), name='collateral-valuations'),
    path('valuations/<int:valuation_id>/approve/', CollateralValuationApproveAPIView.as_view(), name='collateral-valuation-approve'),

    # Guarantors
    path('guarantors/', GuarantorListCreateAPIView.as_view(), name='guarantor-list-create'),
    path('guarantors/<int:guarantor_id>/', GuarantorDetailAPIView.as_view(), name='guarantor-detail'),
    path('guarantors/<int:guarantor_id>/approve/', GuarantorApproveAPIView.as_view(), name='guarantor-approve'),
    path('guarantors/<int:guarantor_id>/reject/', GuarantorRejectAPIView.as_view(), name='guarantor-reject'),
]
