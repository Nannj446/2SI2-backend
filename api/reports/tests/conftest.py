"""
Fixtures para tests del módulo de reportes.
"""
import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from api.tenants.models import FinancialInstitution

User = get_user_model()


@pytest.fixture
def test_tenant(db):
    """Crea un tenant de prueba."""
    return FinancialInstitution.objects.create(
        name="Banco Test",
        code="TEST001",
        is_active=True
    )


@pytest.fixture
def test_user(db, test_tenant):
    """Crea un usuario de prueba."""
    user = User.objects.create_user(
        email="test@example.com",
        password="testpass123",
        first_name="Test",
        last_name="User"
    )
    # Asignar tenant al usuario si el modelo lo soporta
    if hasattr(user, 'institution'):
        user.institution = test_tenant
        user.save()
    return user


@pytest.fixture
def authenticated_client(test_user):
    """Crea un cliente autenticado."""
    client = APIClient()
    refresh = RefreshToken.for_user(test_user)
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')
    return client


@pytest.fixture
def admin_user(db, test_tenant):
    """Crea un usuario administrador de prueba."""
    user = User.objects.create_user(
        email="admin@example.com",
        password="adminpass123",
        first_name="Admin",
        last_name="User",
        is_staff=True
    )
    if hasattr(user, 'institution'):
        user.institution = test_tenant
        user.save()
    return user


@pytest.fixture
def authenticated_admin_client(admin_user):
    """Crea un cliente autenticado como admin."""
    client = APIClient()
    refresh = RefreshToken.for_user(admin_user)
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')
    return client
