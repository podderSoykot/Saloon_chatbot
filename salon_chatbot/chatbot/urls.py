from django.urls import path
from .import views

urlpatterns=[
    path('test/',views.test_view,name="test"),
    path('services/', views.ServiceListAPIView.as_view(), name='service-list'),
    path('availability/', views.AvailabilityAPIView.as_view(), name='availability'),
    path('book/', views.BookServiceAPIView.as_view(), name='book-service'),
    path('chatbot/', views.ChatbotAPIView.as_view(), name='chatbot-api'),
]