# booking/views.py
from django.http import JsonResponse

# Import service-related API views
from .service_views import ServiceListAPIView, AvailabilityAPIView, BookServiceAPIView,WeeklyAvailabilityAPIView

# Import chatbot API view
from .chatbot import ChatbotAPIView

# Test view
def test_view(request):
    return JsonResponse({"message": "Chatbot API is working!"})
