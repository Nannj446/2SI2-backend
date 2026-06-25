from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import RegisterUserSerializer


class RegisterUserAPIView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = RegisterUserSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = serializer.save()

        response_payload = {
            'message': 'Registro completado exitosamente.',
            'institution': {
                'id': result.institution.id,
                'name': result.institution.name,
                'slug': result.institution.slug,
                'institution_type': result.institution.institution_type,
            },
            'user': {
                'id': result.user.id,
                'email': result.user.email,
                'first_name': result.user.first_name,
                'last_name': result.user.last_name,
                'role': 'Administrador de Institución',  # Rol fijo para registro
            },
        }

        return Response(response_payload, status=status.HTTP_201_CREATED)
