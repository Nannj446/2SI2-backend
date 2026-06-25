from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from api.models import FinancialInstitution
from .serializers_client import PublicInstitutionSerializer, ClientRegisterSerializer


class PublicInstitutionsListView(APIView):
    """
    Lista instituciones financieras disponibles para registro de clientes.
    Endpoint público - no requiere autenticación.
    """
    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request):
        """
        Lista todas las instituciones financieras activas disponibles 
        para que los clientes se registren.
        
        Response (200 OK):
        [
            {
                "id": 1,
                "name": "Banco Nacional",
                "slug": "banco-nacional", 
                "institution_type": "bank",
                "description": "Banco líder en servicios financieros",
                "logo_url": null,
                "website": "https://banconacional.com",
                "phone": "+591-2-123-4567",
                "email": "info@banconacional.com"
            }
        ]
        """
        institutions = FinancialInstitution.objects.filter(
            is_active=True
        ).order_by('name')
        
        serializer = PublicInstitutionSerializer(institutions, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class ClientRegisterView(APIView):
    """
    Registro de nuevos clientes en una institución financiera específica.
    Endpoint público - no requiere autenticación.
    """
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        """
        Registra un nuevo cliente en una institución financiera.
        
        Request body:
        {
            "institution_id": 1,
            "first_name": "Juan",
            "last_name": "Pérez",
            "email": "juan.perez@email.com",
            "password": "password123",
            "confirm_password": "password123",
            "phone": "+591-70123456",
            "document_type": "ci",
            "document_number": "12345678",
            "date_of_birth": "1990-01-15",
            "address": "Av. Principal 123"
        }
        
        Response (201 CREATED):
        {
            "message": "Cliente registrado exitosamente",
            "client": {
                "id": 123,
                "email": "juan.perez@email.com",
                "first_name": "Juan",
                "last_name": "Pérez",
                "phone": "+591-70123456"
            },
            "institution": {
                "id": 1,
                "name": "Banco Nacional",
                "slug": "banco-nacional"
            }
        }
        """
        serializer = ClientRegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = serializer.save()

        response_data = {
            'message': 'Cliente registrado exitosamente',
            'client': {
                'id': result.user.id,
                'email': result.user.email,
                'first_name': result.user.first_name,
                'last_name': result.user.last_name,
                'phone': result.client_profile.phone,
            },
            'institution': {
                'id': result.institution.id,
                'name': result.institution.name,
                'slug': result.institution.slug,
            }
        }

        return Response(response_data, status=status.HTTP_201_CREATED)