from django.urls import path

from .views import (
    PermissionListAPIView,
    RoleDetailAPIView,
    RoleListCreateAPIView,
    RolePermissionAssignmentAPIView,
    RolePermissionDetailAPIView,
    # Sprint 8: Endpoints adicionales
    RolePermissionsAPIView,
    RolePermissionsAssignAPIView,
    AvailablePermissionsAPIView,
)

urlpatterns = [
    # Roles
    path('roles/', RoleListCreateAPIView.as_view(), name='role-list-create'),
    path('roles/<int:role_id>/', RoleDetailAPIView.as_view(), name='role-detail'),
    
    # Permisos (existentes)
    path('roles/<int:role_id>/permissions/', RolePermissionAssignmentAPIView.as_view(), name='role-assign-permissions'),
    path(
        'roles/<int:role_id>/permissions/<int:permission_id>/',
        RolePermissionDetailAPIView.as_view(),
        name='role-remove-permission',
    ),
    path('permissions/', PermissionListAPIView.as_view(), name='permission-list'),
    
    # Sprint 8: Endpoints adicionales para asignación de permisos
    path('roles/<int:role_id>/permissions/list/', RolePermissionsAPIView.as_view(), name='role-permissions-list'),
    path('roles/<int:role_id>/permissions/assign/', RolePermissionsAssignAPIView.as_view(), name='role-permissions-assign'),
    path('permissions/available/', AvailablePermissionsAPIView.as_view(), name='permissions-available'),
]
