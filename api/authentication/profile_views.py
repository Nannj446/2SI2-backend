"""
Vistas para gestión de perfil de usuario.
"""
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from api.clients.serializers import ClientSerializer


class ProfileAPIView(APIView):
    """Vista para obtener el perfil del usuario autenticado."""
    
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """
        Obtiene el perfil del usuario autenticado.
        
        Returns:
            Response con datos del usuario y su perfil de cliente si existe
        """
        user = request.user
        
        # Datos básicos del usuario
        profile_data = {
            'id': user.id,
            'email': user.email,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'is_active': user.is_active,
        }
        
        # Obtener institución desde membresías activas
        membership = user.institution_memberships.filter(is_active=True).select_related('institution').first()
        if membership and membership.institution:
            profile_data['institution'] = {
                'id': membership.institution.id,
                'name': membership.institution.name,
                'slug': membership.institution.slug,
                'institution_type': membership.institution.institution_type,
            }
        else:
            profile_data['institution'] = None
        
        # Agregar datos de 2FA
        if hasattr(user, 'two_factor'):
            profile_data['two_factor_enabled'] = user.two_factor.is_enabled
            profile_data['two_factor_method'] = user.two_factor.method
        else:
            profile_data['two_factor_enabled'] = False
            profile_data['two_factor_method'] = None
        
        # Agregar phone desde UserProfile si existe
        if hasattr(user, 'profile'):
            profile_data['phone'] = user.profile.phone
        else:
            profile_data['phone'] = None
        
        # Si el usuario tiene perfil de cliente, agregar esos datos
        try:
            from api.models import Client
            client = Client.objects.get(user=user)
            client_serializer = ClientSerializer(client)
            # Actualizar con datos del cliente (esto sobrescribirá algunos campos básicos)
            profile_data.update(client_serializer.data)
        except Client.DoesNotExist:
            pass
        
        return Response(profile_data, status=status.HTTP_200_OK)


class ProfileUpdateAPIView(APIView):
    """Vista para actualizar el perfil del usuario autenticado."""
    
    permission_classes = [IsAuthenticated]

    def patch(self, request):
        """
        Actualiza el perfil del usuario autenticado.
        
        Request body puede incluir:
            - first_name, last_name (campos de User)
            - phone (campo de UserProfile)
            - Cualquier campo de Client
        
        Returns:
            Response con datos actualizados
        """
        user = request.user
        data = request.data
        
        # Actualizar campos básicos del usuario
        if 'first_name' in data:
            user.first_name = data['first_name']
        if 'last_name' in data:
            user.last_name = data['last_name']
        user.save()
        
        # Actualizar phone en UserProfile si existe
        if 'phone' in data and hasattr(user, 'profile'):
            user.profile.phone = data['phone']
            user.profile.save()
        
        # Actualizar perfil de cliente si existe
        try:
            from api.models import Client
            client = Client.objects.get(user=user)
            
            # Actualizar campos del cliente
            client_fields = [
                'document_type', 'document_number', 'document_extension',
                'birth_date', 'gender', 'mobile_phone', 'address', 'city',
                'department', 'country', 'postal_code', 'employment_status',
                'employer_name', 'employer_nit', 'job_title', 'employment_start_date',
                'monthly_income', 'additional_income'
            ]
            
            for field in client_fields:
                if field in data:
                    setattr(client, field, data[field])
            
            client.save()
            
            # Retornar datos actualizados completos
            client_serializer = ClientSerializer(client)
            profile_data = {
                'id': user.id,
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'is_active': user.is_active,
            }
            
            # Agregar datos de 2FA
            if hasattr(user, 'two_factor'):
                profile_data['two_factor_enabled'] = user.two_factor.is_enabled
                profile_data['two_factor_method'] = user.two_factor.method
            else:
                profile_data['two_factor_enabled'] = False
                profile_data['two_factor_method'] = None
            
            # Agregar phone desde UserProfile
            if hasattr(user, 'profile'):
                profile_data['phone'] = user.profile.phone
            else:
                profile_data['phone'] = None
            
            profile_data.update(client_serializer.data)
            
            return Response(profile_data, status=status.HTTP_200_OK)
            
        except Client.DoesNotExist:
            # Si no es cliente, solo retornar datos básicos
            profile_data = {
                'id': user.id,
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'is_active': user.is_active,
            }
            
            if hasattr(user, 'two_factor'):
                profile_data['two_factor_enabled'] = user.two_factor.is_enabled
                profile_data['two_factor_method'] = user.two_factor.method
            else:
                profile_data['two_factor_enabled'] = False
                profile_data['two_factor_method'] = None
            
            if hasattr(user, 'profile'):
                profile_data['phone'] = user.profile.phone
            else:
                profile_data['phone'] = None
            
            return Response(profile_data, status=status.HTTP_200_OK)
