from django.urls import path
from .views import ChatbotResponseView

app_name = 'chatbot'

urlpatterns = [
    path('ask/', ChatbotResponseView.as_view(), name='chatbot-ask'),
]
