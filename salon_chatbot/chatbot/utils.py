# booking/utils.py
from datetime import datetime, timedelta
from .models import Booking, StaffAvailability, Haircut, BeardCut, Facial, Spa

SERVICE_MODELS = {
    'haircut': Haircut,
    'beard': BeardCut,
    'facial': Facial,
    'spa': Spa
}

def get_service_model(service_type):
    return SERVICE_MODELS.get(service_type.lower())

def get_available_slots(service, booking_date):
    """
    Return available slots for a given service and date.
    """
    slots = {}
    booked_slots = {}

    for staff in service.staff.all():
        day_of_week = booking_date.weekday()
        availability = StaffAvailability.objects.filter(staff=staff, day_of_week=day_of_week).first()
        if not availability:
            continue

        start_dt = datetime.combine(booking_date, availability.start_time)
        end_dt = datetime.combine(booking_date, availability.end_time)

        if not service.duration_minutes or service.duration_minutes <= 0:
            continue

        possible_slots = []
        current = start_dt
        while current + timedelta(minutes=service.duration_minutes) <= end_dt:
            possible_slots.append(current.time())
            current += timedelta(minutes=service.duration_minutes)

        # Booked times
        booked_times = Booking.objects.filter(
            staff=staff,
            booking_date=booking_date,
            service_type=service.__class__.__name__.lower()
        ).values_list('booking_time', flat=True)

        booked_times_str = [t.strftime("%H:%M") for t in booked_times]
        available_times = [t.strftime("%H:%M") for t in possible_slots if t not in booked_times]

        slots[f"{staff.first_name} {staff.last_name}"] = available_times
        booked_slots[f"{staff.first_name} {staff.last_name}"] = booked_times_str

    return slots, booked_slots

def get_weekly_available_slots(service):
    """
    Return available and booked slots for each day of the current week (Monday → Sunday)
    """
    today = datetime.today().date()
    # Monday = 0, Sunday = 6
    start_of_week = today - timedelta(days=today.weekday())
    weekly_slots = {}

    for i in range(7):
        date = start_of_week + timedelta(days=i)
        slots, booked = get_available_slots(service, date)
        weekly_slots[str(date)] = {
            "available_slots": slots,
            "booked_slots": booked
        }

    return weekly_slots
