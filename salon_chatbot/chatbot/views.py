from django.shortcuts import render
from django.http import JsonResponse
from datetime import datetime, timedelta
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .models import Staff, Customer, Booking, Haircut, BeardCut, Facial, Spa, StaffAvailability

# -----------------------------
# Test View
# -----------------------------
def test_view(request):
    return JsonResponse({"message": "Chatbot API is working!"})

# -----------------------------
# Utility Functions
# -----------------------------
SERVICE_MODELS = {
    'haircut': Haircut,
    'beard': BeardCut,
    'facial': Facial,
    'spa': Spa
}

def get_service_model(service_type):
    """Return the model class based on service type"""
    return SERVICE_MODELS.get(service_type.lower())

def get_available_slots(service, booking_date):
    """Return available slots for all staff of a service on a given date"""
    slots = {}
    for staff in service.staff.all():
        day_of_week = booking_date.weekday()
        availability = StaffAvailability.objects.filter(staff=staff, day_of_week=day_of_week).first()
        if not availability:
            continue

        start_dt = datetime.combine(booking_date, availability.start_time)
        end_dt = datetime.combine(booking_date, availability.end_time)
        possible_slots = []
        current = start_dt
        while current + timedelta(minutes=service.duration_minutes) <= end_dt:
            possible_slots.append(current.time())
            current += timedelta(minutes=service.duration_minutes)

        booked_times = Booking.objects.filter(
            staff=staff,
            booking_date=booking_date,
            service_type=service.__class__.__name__.lower()
        ).values_list('booking_time', flat=True)

        available_times = [t.strftime("%H:%M") for t in possible_slots if t not in booked_times]
        if available_times:
            slots[f"{staff.first_name} {staff.last_name}"] = available_times
    return slots

# -----------------------------
# API Views
# -----------------------------
class ServiceListAPIView(APIView):
    """List all services with staff info"""
    def get(self, request):
        data = {}
        for service_type, model in SERVICE_MODELS.items():
            services = model.objects.all()
            data[service_type] = [
                {
                    'id': s.id,
                    'name': s.name,
                    'price': float(s.price),
                    'duration_minutes': s.duration_minutes,
                    'staff': [staff.id for staff in s.staff.all()]
                } for s in services
            ]
        return Response(data)

class AvailabilityAPIView(APIView):
    """Check available slots for a specific service and date"""
    def get(self, request):
        service_type = request.GET.get('service_type')
        service_id = request.GET.get('service_id')
        date_str = request.GET.get('date')

        if not service_type or not service_id or not date_str:
            return Response({'error': 'service_type, service_id, and date are required'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            booking_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            return Response({'error': 'Invalid date format. Use YYYY-MM-DD'}, status=status.HTTP_400_BAD_REQUEST)

        model = get_service_model(service_type)
        if not model:
            return Response({'error': 'Invalid service_type'}, status=status.HTTP_400_BAD_REQUEST)

        service = model.objects.filter(id=service_id).first()
        if not service:
            return Response({'error': 'Service not found'}, status=status.HTTP_404_NOT_FOUND)

        slots = get_available_slots(service, booking_date)
        return Response({'service_id': service.id, 'available_slots': slots})

class BookServiceAPIView(APIView):
    """Book a service for a customer"""
    def post(self, request):
        data = request.data
        required_fields = [
            'customer_first_name', 'customer_last_name', 'customer_email',
            'service_type', 'service_id', 'staff_id', 'booking_date', 'booking_time'
        ]

        # Validate fields
        for field in required_fields:
            if field not in data:
                return Response({'error': f'{field} is required'}, status=status.HTTP_400_BAD_REQUEST)

        # Create or get customer
        customer, _ = Customer.objects.get_or_create(
            email=data['customer_email'],
            defaults={
                'first_name': data['customer_first_name'],
                'last_name': data['customer_last_name'],
                'phone': data.get('customer_phone', '')
            }
        )

        # Get service and staff
        service_model = get_service_model(data['service_type'])
        service = service_model.objects.filter(id=data['service_id']).first()
        staff = Staff.objects.filter(id=data['staff_id']).first()
        if not service or not staff:
            return Response({'error': 'Service or Staff not found'}, status=status.HTTP_404_NOT_FOUND)

        # Parse date/time
        try:
            booking_date = datetime.strptime(data['booking_date'], "%Y-%m-%d").date()
            booking_time = datetime.strptime(data['booking_time'], "%H:%M").time()
        except ValueError:
            return Response({'error': 'Invalid date or time format'}, status=status.HTTP_400_BAD_REQUEST)

        # Check availability
        if Booking.objects.filter(staff=staff, booking_date=booking_date, booking_time=booking_time).exists():
            return Response({'error': 'This time slot is already booked'}, status=status.HTTP_400_BAD_REQUEST)

        # Create booking
        booking = Booking.objects.create(
            customer=customer,
            service_type=data['service_type'],
            service_id=service.id,
            staff=staff,
            booking_date=booking_date,
            booking_time=booking_time,
            status='confirmed'
        )

        booking_link = f"/api/book/?service_type={data['service_type']}&staff_id={staff.id}&date={booking_date}&time={booking_time}"

        return Response({
            'message': f"Booking confirmed! Thank you. You can confirm your booking here: {booking_link}\nWe also offer other services like Beard, Facial, and SPA.",
            'booking_id': booking.id,
            'service_type': data['service_type'],
            'staff': str(staff),
            'date': str(booking_date),
            'time': str(booking_time)
        })

# -----------------------------
# Chatbot API
# -----------------------------
conversation_state = {}

class ChatbotAPIView(APIView):
    """Handle conversational chatbot for salon"""
    def post(self, request):
        user_id = request.data.get("user_id")
        message = request.data.get("message", "").lower().strip()

        if user_id not in conversation_state:
            conversation_state[user_id] = {"stage": "greeting", "service_type": None, "selected_slot": None}

        state = conversation_state[user_id]
        stage = state["stage"]

        # Stage 1: Greeting
        if stage == "greeting":
            if any(g in message for g in ["hi","hello","hey"]):
                state["stage"] = "choose_service"
                return Response({"bot": "Welcome to our salon! We provide Haircut, Beard, Facial, and SPA services. What would you like today?"})
            return Response({"bot": "Hi! Say 'hi' to start."})

        # Stage 2: Choose Service
        if stage == "choose_service":
            for service_type in SERVICE_MODELS.keys():
                if service_type in message:
                    state["service_type"] = service_type
                    service_model = get_service_model(service_type)
                    today = datetime.today().date()
                    slots = get_available_slots(service_model.objects.first(), today)
                    if slots:
                        state["stage"] = "pick_slot"
                        slot_message = "\n".join([f"{staff}: {', '.join(times)}" for staff, times in slots.items()])
                        return Response({"bot": f"Great! Available slots for {service_type} today:\n{slot_message}\nReply with your preferred time and staff."})
                    else:
                        return Response({"bot": f"Sorry, no available slots for {service_type} today."})
            return Response({"bot": "I didn't understand. Which service would you like? Haircut, Beard, Facial, or SPA?"})

        # Stage 3: Pick Slot
        if stage == "pick_slot":
            state["selected_slot"] = message
            state["stage"] = "booking_link"
            booking_url = f"/api/book/?service_type={state['service_type']}&slot={message}"
            return Response({"bot": f"Perfect! To confirm your {state['service_type']} at {message}, please complete your booking here: {booking_url}\nThanks! We also offer Beard, Facial, and SPA services if you want more."})

        # Stage 4: After user thanks
        if "thanks" in message or "thank you" in message:
            state["stage"] = "end"
            return Response({"bot": "You're welcome! We also provide Haircut, Beard, Facial, and SPA services. Feel free to ask."})

        return Response({"bot": "Sorry, I didn't understand. Can you please rephrase?"})
