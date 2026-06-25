"""
ViewSet para webhooks de Stripe.

Endpoint público sin autenticación (solo validación de firma).
"""

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import AllowAny

from api.loans.services.stripe_service import StripePaymentService


class StripeWebhookViewSet(viewsets.ViewSet):
    """
    Endpoint para recibir webhooks de Stripe.

    POST /api/loans/stripe/webhook/
    """
    permission_classes = [AllowAny]
    authentication_classes = []

    @action(detail=False, methods=['post'], url_path='webhook', permission_classes=[AllowAny])
    def webhook(self, request):
        """
        Recibe y procesa webhooks de Stripe.
        """
        payload = request.body
        sig_header = request.META.get('HTTP_STRIPE_SIGNATURE', '')

        if not sig_header:
            return Response({'error': 'Missing Stripe signature'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            result = StripePaymentService.handle_webhook(payload, sig_header)
            return Response(result, status=status.HTTP_200_OK)
        except ValueError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
