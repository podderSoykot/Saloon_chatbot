import os
import django
import json
from datetime import datetime, time

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'salon_chatbot.settings')
django.setup()

from chatbot.models import Staff, StaffAvailability, Customer, Booking, Haircut, BeardCut, Facial, Spa

# Load JSON data
with open('data.json', 'r') as f:
    data = json.load(f)

# 1️⃣ Load Staff
for s in data['staff']:
    Staff.objects.update_or_create(
        id=s['id'],
        defaults={
            'first_name': s['first_name'],
            'last_name': s['last_name'],
            'email': s['email'],
            'phone': s['phone']
        }
    )

# 2️⃣ Load Staff Availability
for a in data['staff_availability']:
    staff = Staff.objects.get(id=a['staff_id'])
    StaffAvailability.objects.update_or_create(
        staff=staff,
        day_of_week=a['day_of_week'],
        defaults={
            'start_time': time.fromisoformat(a['start_time']),
            'end_time': time.fromisoformat(a['end_time'])
        }
    )

# 3️⃣ Load Services
def load_services(service_list, Model):
    for s in service_list:
        service_obj, _ = Model.objects.update_or_create(
            id=s['id'],
            defaults={
                'name': s['name'],
                'price': s['price'],
                'duration_minutes': s['duration_minutes']
            }
        )
        staff_objs = Staff.objects.filter(id__in=s['staff_ids'])
        service_obj.staff.set(staff_objs)
        service_obj.save()

load_services(data['haircut'], Haircut)
load_services(data['beardcut'], BeardCut)
load_services(data['facial'], Facial)
load_services(data['spa'], Spa)

# 4️⃣ Load Customers
for c in data['customers']:
    Customer.objects.update_or_create(
        id=c['id'],
        defaults={
            'first_name': c['first_name'],
            'last_name': c['last_name'],
            'email': c['email'],
            'phone': c['phone']
        }
    )

# 5️⃣ Load Bookings
for b in data['bookings']:
    Booking.objects.update_or_create(
        id=b['id'],
        defaults={
            'customer': Customer.objects.get(id=b['customer_id']),
            'service_type': b['service_type'],
            'service_id': b['service_id'],
            'staff': Staff.objects.get(id=b['staff_id']),
            'booking_date': datetime.fromisoformat(b['booking_date']).date(),
            'booking_time': datetime.strptime(b['booking_time'], "%H:%M").time(),
            'status': b['status']
        }
    )

print("✅ Dummy data loaded successfully!")
