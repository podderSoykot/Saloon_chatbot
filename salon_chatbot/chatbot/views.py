from django.shortcuts import render
from django.http import JsonResponse
from datetime import datetime, timedelta
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from dateutil.parser import parse as parse_date
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

# Intent keywords
INTENTS = {
    "greeting": ["hi", "hello", "hey", "good morning", "good afternoon", "good evening", "yo", "hiya"],
    "thanks": ["thanks", "thank you", "thx", "ty", "thank u", "thanks a lot"],
    "service_request": ["haircut", "hair cut", "beard", "facial", "spa", "massage", "shave"],
    "date_keywords": ["today", "tomorrow", "next day", "day after tomorrow",
                      "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"],
    "slot_selection": [],  # populated dynamically (HH:MM or staff + HH:MM)
    "unknown": []
}

# -----------------------------
# Intent Detection Function
# -----------------------------
def detect_intent(message):
    message = message.lower()

    # Check greetings
    if any(g in message for g in INTENTS["greeting"]):
        return "greeting"

    # Check thanks
    if any(t in message for t in INTENTS["thanks"]):
        return "thanks"

    # Check service request
    if any(s in message for s in INTENTS["service_request"]):
        return "service_request"

    # Check for date keywords or explicit dates
    if any(d in message for d in INTENTS["date_keywords"]):
        return "date_keywords"
    try:
        parse_date(message, fuzzy=True)
        return "date_keywords"
    except:
        pass

    # Check for slot selection: HH:MM or staff + HH:MM
    if re.search(r'\b\d{1,2}:\d{2}\b', message):
        return "slot_selection"

    # Fallback unknown
    return "unknown"

class ChatbotAPIView(APIView):
    """Intent-based conversational chatbot for salon with real slot checking"""

    def post(self, request):
        user_id = request.data.get("user_id")
        message = request.data.get("message", "").strip()

        if not user_id or not message:
            return Response({"bot": "Please provide user_id and message."})

        if user_id not in conversation_state:
            conversation_state[user_id] = {
                "stage": "greeting",
                "service_type": None,
                "selected_slot": None,
                "requested_date": None,
                "available_slots": {}
            }

        state = conversation_state[user_id]
        stage = state["stage"]
        intent = detect_intent(message)

        # -----------------------------
        # Stage 1: Greeting
        # -----------------------------
        if stage == "greeting":
            if intent in ["greeting", "service_request"]:
                state["stage"] = "choose_service"
                return Response({
                    "bot": "Welcome to our salon! We provide Haircut, Beard, Facial, and SPA services. Which service would you like today?"
                })
            return Response({"bot": "Hi! Say 'hi' or type the service you want."})

        # -----------------------------
        # Stage 2: Choose Service
        # -----------------------------
        if stage == "choose_service":
            if intent != "service_request":
                return Response({"bot": "I didn't catch that. Which service would you like: Haircut, Beard, Facial, or SPA?"})

            # Detect service type
            for service_type in SERVICE_MODELS.keys():
                if service_type in message.lower():
                    state["service_type"] = service_type
                    break

            if not state["service_type"]:
                return Response({"bot": "Please choose a valid service: Haircut, Beard, Facial, or SPA."})

            # Detect requested date
            requested_date = datetime.today().date()
            if "tomorrow" in message or "next day" in message:
                requested_date += timedelta(days=1)
            else:
                try:
                    requested_date = parse_date(message, fuzzy=True).date()
                except:
                    pass
            state["requested_date"] = requested_date

            # Fetch all service instances with staff
            service_model = get_service_model(state["service_type"])
            services_with_staff = service_model.objects.filter(staff__isnull=False)

            all_slots = {}
            for service_instance in services_with_staff:
                slots = get_available_slots(service_instance, requested_date)
                for staff, times in slots.items():
                    if staff not in all_slots:
                        all_slots[staff] = times
                    else:
                        all_slots[staff].extend(times)

            # Remove duplicates and sort times
            for staff in all_slots:
                all_slots[staff] = sorted(list(set(all_slots[staff])))

            if not all_slots:
                return Response({"bot": f"Sorry, no available slots for {state['service_type']} on {requested_date}."})

            state["available_slots"] = all_slots
            state["stage"] = "pick_slot"

            # Prepare message with numbered slots
            slot_message = ""
            counter = 1
            slot_map = {}
            for staff, times in all_slots.items():
                for t in times:
                    slot_map[str(counter)] = f"{staff} {t}"
                    slot_message += f"{counter}. {staff}: {t}\n"
                    counter += 1
            state["slot_map"] = slot_map

            return Response({
                "bot": f"Available slots for {state['service_type']} on {requested_date}:\n{slot_message}\nReply with the number of your preferred slot."
            })

        # -----------------------------
        # Stage 3: Pick Slot
        # -----------------------------
        if stage == "pick_slot":
            slot_map = state.get("slot_map", {})
            if message not in slot_map:
                return Response({"bot": "Please reply with a valid slot number from the list."})

            selected = slot_map[message]  # e.g., "John Doe 10:00"
            state["selected_slot"] = selected
            state["stage"] = "booking_link"

            staff_name, slot_time = " ".join(selected.split()[:-1]), selected.split()[-1]
            booking_url = f"/api/book/?service_type={state['service_type']}&staff_name={staff_name}&time={slot_time}&date={state['requested_date']}"

            return Response({
                "bot": f"Perfect! Confirm your {state['service_type']} at {selected} here: {booking_url}\nThanks! We also offer Beard, Facial, and SPA services."
            })

        # -----------------------------
        # Stage 4: Thanks
        # -----------------------------
        if intent == "thanks":
            state["stage"] = "end"
            return Response({"bot": "You're welcome! We also provide Haircut, Beard, Facial, and SPA services. Feel free to ask."})

        # Default fallback
        return Response({"bot": "Sorry, I didn't understand. Can you please rephrase?"})
