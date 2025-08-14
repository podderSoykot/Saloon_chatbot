from django.urls import path
from . import views
from .service_views import (
    ServiceListAPIView,
    AvailabilityAPIView,
    BookServiceAPIView,
    WeeklyAvailabilityAPIView
)

urlpatterns = [
    path('test/', views.test_view, name="test"),
    path('services/', ServiceListAPIView.as_view(), name='service-list'),
    path('availability/', AvailabilityAPIView.as_view(), name='availability'),
    path('book/', BookServiceAPIView.as_view(), name='book-service'),
    path('chatbot/', views.ChatbotAPIView.as_view(), name='chatbot-api'),
    path('weekly-availability/', WeeklyAvailabilityAPIView.as_view(), name='weekly-availability'),
]
