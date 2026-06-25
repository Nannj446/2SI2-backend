"""
URLs para gestión de usuarios internos.
"""

from django.urls import path

from .views import UserDetailAPIView, UserListCreateAPIView, UserRolesAPIView

urlpatterns = [
    path('', UserListCreateAPIView.as_view(), name='user-list-create'),
    path('<int:user_id>/', UserDetailAPIView.as_view(), name='user-detail'),
    path('<int:user_id>/roles/', UserRolesAPIView.as_view(), name='user-roles'),
]
