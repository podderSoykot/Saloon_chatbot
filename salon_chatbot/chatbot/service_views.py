# booking/service_views.py
from datetime import datetime, timedelta
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .models import Customer, Staff, Booking
from .utils import SERVICE_MODELS, get_service_model, get_available_slots   


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
                    'staff': [{'id': staff.id, 'name': f"{staff.first_name} {staff.last_name}"} for staff in s.staff.all()]
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
            return Response(
                {'error': 'service_type, service_id, and date are required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            booking_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            return Response(
                {'error': 'Invalid date format. Use YYYY-MM-DD'},
                status=status.HTTP_400_BAD_REQUEST
            )

        model = get_service_model(service_type)
        if not model:
            return Response({'error': 'Invalid service_type'}, status=status.HTTP_400_BAD_REQUEST)

        service = model.objects.filter(id=service_id).first()
        if not service:
            return Response({'error': 'Service not found'}, status=status.HTTP_404_NOT_FOUND)

        # Get available and booked slots for this date
        available_slots = {}
        booked_slots = {}
        for staff in service.staff.all():
            slots, booked = get_available_slots_for_staff(service, staff, booking_date)
            available_slots[f"{staff.first_name} {staff.last_name}"] = slots
            booked_slots[f"{staff.first_name} {staff.last_name}"] = booked

        return Response({
            'service_id': service.id,
            'service_name': service.name,
            'available_slots': available_slots,
            'booked_slots': booked_slots
        })


class WeeklyAvailabilityAPIView(APIView):
    """Show available slots for the whole week for a service"""
    def get(self, request):
        service_type = request.GET.get('service_type')
        service_id = request.GET.get('service_id')

        if not service_type or not service_id:
            return Response({'error': 'service_type and service_id are required'}, status=400)

        model = get_service_model(service_type)
        if not model:
            return Response({'error': 'Invalid service_type'}, status=400)

        service = model.objects.filter(id=service_id).first()
        if not service:
            return Response({'error': 'Service not found'}, status=404)

        today = datetime.today().date()
        start_of_week = today - timedelta(days=today.weekday())  # Monday
        weekly_slots = {}

        for i in range(7):
            date = start_of_week + timedelta(days=i)
            daily_available = {}
            daily_booked = {}
            for staff in service.staff.all():
                slots, booked = get_available_slots_for_staff(service, staff, date)
                daily_available[f"{staff.first_name} {staff.last_name}"] = slots
                daily_booked[f"{staff.first_name} {staff.last_name}"] = booked

            weekly_slots[str(date)] = {
                "available_slots": daily_available,
                "booked_slots": daily_booked
            }

        return Response({
            "service_id": service.id,
            "service_name": service.name,
            "weekly_slots": weekly_slots
        })


class BookServiceAPIView(APIView):
    """Book a service for a customer"""
    def post(self, request):
        data = request.data
        required_fields = [
            'customer_first_name', 'customer_last_name', 'customer_email',
            'service_type', 'service_id', 'staff_id', 'booking_date', 'booking_time'
        ]

        for field in required_fields:
            if field not in data or not data[field]:
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

        service_model = get_service_model(data['service_type'])
        if not service_model:
            return Response({'error': 'Invalid service_type'}, status=status.HTTP_400_BAD_REQUEST)

        service = service_model.objects.filter(id=data['service_id']).first()
        staff = Staff.objects.filter(id=data['staff_id']).first()
        if not service or not staff:
            return Response({'error': 'Service or Staff not found'}, status=status.HTTP_404_NOT_FOUND)

        try:
            booking_date = datetime.strptime(data['booking_date'], "%Y-%m-%d").date()
            booking_time = datetime.strptime(data['booking_time'], "%H:%M").time()
        except ValueError:
            return Response({'error': 'Invalid date or time format'}, status=status.HTTP_400_BAD_REQUEST)

        # Check if slot is already booked
        if Booking.objects.filter(staff=staff, booking_date=booking_date, booking_time=booking_time).exists():
            return Response({'error': 'This time slot is already booked'}, status=status.HTTP_400_BAD_REQUEST)

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
            'message': f"Booking confirmed! Thank you. Confirm here: {booking_link}\nWe also offer Beard, Facial, and SPA services.",
            'booking_id': booking.id,
            'service_type': data['service_type'],
            'staff': f"{staff.first_name} {staff.last_name}",
            'date': str(booking_date),
            'time': booking_time.strftime("%H:%M")
        })


# --------------------------
# Helper function for staff
# --------------------------
from .utils import get_available_slots as original_get_available_slots

def get_available_slots_for_staff(service, staff, booking_date):
    """
    Returns two lists:
        1. available times for the given staff & date
        2. booked times for the given staff & date
    """
    day_of_week = booking_date.weekday()
    from .models import StaffAvailability
    availability = StaffAvailability.objects.filter(staff=staff, day_of_week=day_of_week).first()
    if not availability:
        return [], []

    start_dt = datetime.combine(booking_date, availability.start_time)
    end_dt = datetime.combine(booking_date, availability.end_time)

    duration = service.duration_minutes
    if not duration or duration <= 0:
        return [], []

    possible_slots = []
    current = start_dt
    while current + timedelta(minutes=duration) <= end_dt:
        possible_slots.append(current.time())
        current += timedelta(minutes=duration)

    from .models import Booking
    booked_times = Booking.objects.filter(
        staff=staff,
        booking_date=booking_date,
        service_type=service.__class__.__name__.lower()
    ).values_list('booking_time', flat=True)

    booked_times_str = [t.strftime("%H:%M") for t in booked_times]
    available_slots_str = [t.strftime("%H:%M") for t in possible_slots if t not in booked_times]

    return available_slots_str, booked_times_str
