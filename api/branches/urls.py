"""
URLs para gestión de sucursales.
"""

from django.urls import path

from api.branches.views import BranchDetailAPIView, BranchListCreateAPIView

app_name = 'branches'

urlpatterns = [
    path('', BranchListCreateAPIView.as_view(), name='branch-list-create'),
    path('<int:branch_id>/', BranchDetailAPIView.as_view(), name='branch-detail'),
]
