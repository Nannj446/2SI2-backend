import os
import requests
import logging
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated

logger = logging.getLogger(__name__)

class ChatbotResponseView(APIView):
    """
    Vista de API para manejar la interacción con el Chatbot usando Groq Cloud API.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user_message = request.data.get("message")
        history = request.data.get("history", [])

        if not user_message:
            return Response(
                {"error": "El mensaje no puede estar vacío."},
                status=status.HTTP_400_BAD_REQUEST
            )

        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            logger.error("GROQ_API_KEY no está configurada en las variables de entorno.")
            return Response(
                {"error": "El servicio de chatbot no está configurado actualmente."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )

        # Sistema de Prompt contextualizado con el sistema financiero
        system_prompt = (
            "Tu nombre es Vansii. Eres un asistente virtual súper amigable, cálido y empático.\n"
            "Trabajas para la plataforma financiera Fincore, especializada en gestión de créditos y microfinanzas.\n"
            "Tu objetivo principal es hacer sentir a los clientes cómodos y ayudarlos de forma sencilla y cero técnica.\n\n"
            "Detalles clave de Fincore que debes conocer:\n"
            "1. **Clientes**: Las personas se registran fácil, suben sus fotos de documentos y aplicamos a sus préstamos.\n"
            "2. **Préstamos**: Tenemos varios tipos (consumo, casita, negocio) con tasas claras que cada institución elige.\n"
            "3. **Solicitudes**: Todo se pide y se sigue súper fácil desde la app o la web.\n"
            "4. **Garantías**: Para respaldar el préstamo, se pueden registrar casitas, autos o ahorros de forma segura.\n"
            "5. **Contratos**: ¡Cero papeles! Cuando te aprueban, el contrato se firma digitalmente directo en la app.\n"
            "6. **Reportes**: Los jefes pueden sacar reportes súper completos y ¡hasta pidiéndolos con la voz!\n\n"
            "Instrucciones de comportamiento:\n"
            "- Sé muy amigable, usa un tono cercano y relajado (puedes usar algún emoji ocasional si encaja bien 😊).\n"
            "- Evita jergas bancarias aburridas o muy complejas. Explica como si hablaras con un amigo.\n"
            "- Responde siempre en español.\n"
            "- Si te preguntan cosas que no tienen nada que ver con Fincore o finanzas, diles con cariño que solo estás entrenado para temas de la plataforma Fincore."
        )

        # Construir lista de mensajes incluyendo el historial
        messages = [
            {"role": "system", "content": system_prompt}
        ]

        # Validar y agregar historial para mantener contexto
        for chat in history:
            role = chat.get("role")
            content = chat.get("content")
            if role in ["user", "assistant"] and content:
                messages.append({"role": role, "content": content})

        # Agregar el mensaje actual del usuario
        messages.append({"role": "user", "content": user_message})

        # Configurar la llamada a Groq
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        # Usamos llama-3.3-70b-versatile o llama3-8b-8192 por velocidad y eficiencia
        payload = {
            "model": "llama-3.3-70b-versatile",
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": 1024
        }

        try:
            response = requests.post(url, json=payload, headers=headers, timeout=15)
            response.raise_for_status()
            res_data = response.json()
            
            reply = res_data["choices"][0]["message"]["content"]
            return Response({"reply": reply}, status=status.HTTP_200_OK)

        except requests.exceptions.Timeout:
            logger.error("Timeout al conectar con Groq API.")
            return Response(
                {"error": "Tiempo de espera agotado al conectar con el servidor del chatbot. Por favor intenta de nuevo."},
                status=status.HTTP_504_GATEWAY_TIMEOUT
            )
        except requests.exceptions.HTTPError as e:
            logger.error(f"Error HTTP de Groq API: {e.response.status_code} - {e.response.text}")
            return Response(
                {"error": f"Error del servicio de chatbot: {e.response.status_code}"},
                status=status.HTTP_502_BAD_GATEWAY
            )
        except Exception as e:
            logger.error(f"Error inesperado en chatbot: {str(e)}")
            return Response(
                {"error": "Ocurrió un error inesperado al procesar tu solicitud de chat."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
