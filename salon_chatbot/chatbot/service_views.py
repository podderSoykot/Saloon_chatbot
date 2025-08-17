# booking/service_views.py
from datetime import datetime, timedelta
from django.db import transaction
from django.core.exceptions import ValidationError
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .models import Customer, Staff, Booking, StaffAvailability
from .utils import SERVICE_MODELS, get_service_model
import logging

logger = logging.getLogger(__name__)

# Business hours configuration
BUSINESS_HOURS = {
    'start_time': '09:00',
    'end_time': '18:00',
    'closed_days': [6],  # Sunday = 6
    'slot_duration': 30,  # Default slot duration in minutes
    'buffer_time': 15     # Buffer between appointments
}


class ServiceListAPIView(APIView):
    """List all services with comprehensive staff and availability info"""
    
    def _clean_param(self, param):
        """Clean URL parameters of common issues like newlines and extra text"""
        if not param:
            return ''
        
        # Remove URL-encoded newlines and carriage returns
        param = param.replace('%0A', '').replace('%0D', '')
        param = param.replace('\\n', '').replace('\\r', '')
        param = param.replace('\n', '').replace('\r', '')
        
        # Split on common separators and take the first clean part
        separators = ['\n', '\\n', '\r', '\\r', 'Thank', 'thank']
        for sep in separators:
            if sep in param:
                param = param.split(sep)[0]
        
        return param.strip()

    def get(self, request):
        try:
            data = {}
            for service_type, model in SERVICE_MODELS.items():
                services = model.objects.prefetch_related('staff').all()
                data[service_type] = [
                    {
                        'id': service.id,
                        'name': service.name,
                        'price': float(service.price) if service.price else 0,
                        'duration_minutes': service.duration_minutes or BUSINESS_HOURS['slot_duration'],
                        'description': getattr(service, 'description', ''),
                        'staff': [
                            {
                                'id': staff.id,
                                'name': f"{staff.first_name} {staff.last_name}",
                                'specialization': getattr(staff, 'specialization', ''),
                                'available_days': self._get_staff_available_days(staff)
                            } for staff in service.staff.all()
                        ]
                    } for service in services
                ]
            
            return Response({
                'services': data,
                'business_hours': BUSINESS_HOURS,
                'success': True
            })
            
        except Exception as e:
            logger.error(f"Error fetching services: {str(e)}")
            return Response(
                {'error': 'Failed to fetch services', 'success': False},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def _get_staff_available_days(self, staff):
        """Get available days for a staff member"""
        try:
            availability = StaffAvailability.objects.filter(staff=staff)
            return [avail.day_of_week for avail in availability]
        except Exception:
            return list(range(6))  # Default to Monday-Saturday


class AvailabilityAPIView(APIView):
    """Check available slots for a specific service and date with enhanced validation"""
    
    def get(self, request):
        try:
            service_type = request.GET.get('service_type')
            service_id = request.GET.get('service_id')
            date_str = request.GET.get('date')
            staff_id = request.GET.get('staff_id')  # Optional: check specific staff

            # Validation
            if not all([service_type, service_id, date_str]):
                return Response(
                    {
                        'error': 'service_type, service_id, and date are required',
                        'required_params': ['service_type', 'service_id', 'date'],
                        'success': False
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Parse and validate date
            try:
                booking_date = datetime.strptime(date_str, "%Y-%m-%d").date()
                if booking_date < datetime.today().date():
                    return Response(
                        {'error': 'Cannot book appointments in the past', 'success': False},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            except ValueError:
                return Response(
                    {'error': 'Invalid date format. Use YYYY-MM-DD', 'success': False},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Check if it's a business day
            if booking_date.weekday() in BUSINESS_HOURS['closed_days']:
                return Response(
                    {
                        'error': 'We are closed on this day',
                        'closed_days': BUSINESS_HOURS['closed_days'],
                        'success': False
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Get service
            model = get_service_model(service_type)
            if not model:
                return Response(
                    {'error': 'Invalid service_type', 'success': False},
                    status=status.HTTP_400_BAD_REQUEST
                )

            service = model.objects.prefetch_related('staff').filter(id=service_id).first()
            if not service:
                return Response(
                    {'error': 'Service not found', 'success': False},
                    status=status.HTTP_404_NOT_FOUND
                )

            # Filter staff if specific staff requested
            staff_members = service.staff.all()
            if staff_id:
                staff_members = staff_members.filter(id=staff_id)
                if not staff_members.exists():
                    return Response(
                        {'error': 'Staff member not found or not available for this service', 'success': False},
                        status=status.HTTP_404_NOT_FOUND
                    )

            # Get available and booked slots
            available_slots = {}
            booked_slots = {}
            total_available = 0

            for staff in staff_members:
                slots, booked = get_available_slots_for_staff(service, staff, booking_date)
                staff_name = f"{staff.first_name} {staff.last_name}"
                available_slots[staff_name] = slots
                booked_slots[staff_name] = booked
                total_available += len(slots)

            return Response({
                'service_id': service.id,
                'service_name': service.name,
                'service_type': service_type,
                'date': date_str,
                'day_of_week': booking_date.strftime('%A'),
                'available_slots': available_slots,
                'booked_slots': booked_slots,
                'total_available_slots': total_available,
                'business_hours': BUSINESS_HOURS,
                'success': True
            })

        except Exception as e:
            logger.error(f"Error checking availability: {str(e)}")
            return Response(
                {'error': 'Failed to check availability', 'success': False},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class WeeklyAvailabilityAPIView(APIView):
    """Show available slots for the whole week for a service with smart date range"""
    
    def get(self, request):
        try:
            service_type = request.GET.get('service_type')
            service_id = request.GET.get('service_id')
            start_date_str = request.GET.get('start_date')  # Optional custom start date

            if not service_type or not service_id:
                return Response(
                    {'error': 'service_type and service_id are required', 'success': False},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Get service
            model = get_service_model(service_type)
            if not model:
                return Response(
                    {'error': 'Invalid service_type', 'success': False},
                    status=status.HTTP_400_BAD_REQUEST
                )

            service = model.objects.prefetch_related('staff').filter(id=service_id).first()
            if not service:
                return Response(
                    {'error': 'Service not found', 'success': False},
                    status=status.HTTP_404_NOT_FOUND
                )

            # Determine start date
            if start_date_str:
                try:
                    start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
                except ValueError:
                    return Response(
                        {'error': 'Invalid start_date format. Use YYYY-MM-DD', 'success': False},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            else:
                today = datetime.today().date()
                start_date = today - timedelta(days=today.weekday())  # Start from Monday

            weekly_slots = {}
            total_week_availability = 0

            for i in range(7):
                date = start_date + timedelta(days=i)
                day_name = date.strftime('%A')
                
                # Skip if closed day
                if date.weekday() in BUSINESS_HOURS['closed_days']:
                    weekly_slots[str(date)] = {
                        "date": str(date),
                        "day_name": day_name,
                        "is_closed": True,
                        "available_slots": {},
                        "booked_slots": {},
                        "total_available": 0
                    }
                    continue

                daily_available = {}
                daily_booked = {}
                daily_total = 0

                for staff in service.staff.all():
                    slots, booked = get_available_slots_for_staff(service, staff, date)
                    staff_name = f"{staff.first_name} {staff.last_name}"
                    daily_available[staff_name] = slots
                    daily_booked[staff_name] = booked
                    daily_total += len(slots)

                weekly_slots[str(date)] = {
                    "date": str(date),
                    "day_name": day_name,
                    "is_closed": False,
                    "available_slots": daily_available,
                    "booked_slots": daily_booked,
                    "total_available": daily_total
                }
                total_week_availability += daily_total

            return Response({
                "service_id": service.id,
                "service_name": service.name,
                "service_type": service_type,
                "week_start": str(start_date),
                "week_end": str(start_date + timedelta(days=6)),
                "weekly_slots": weekly_slots,
                "total_week_availability": total_week_availability,
                "business_hours": BUSINESS_HOURS,
                "success": True
            })

        except Exception as e:
            logger.error(f"Error fetching weekly availability: {str(e)}")
            return Response(
                {'error': 'Failed to fetch weekly availability', 'success': False},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class BookServiceAPIView(APIView):
    """Book a service for a customer with comprehensive validation and transaction support"""
    
    def _clean_param(self, value):
        return str(value).strip() if value else ''

    def get(self, request):
        """Handle GET requests for chatbot booking links"""
        try:
            service_type = self._clean_param(request.GET.get('service_type', ''))
            staff_name = self._clean_param(request.GET.get('staff_name', ''))
            time = self._clean_param(request.GET.get('time', ''))
            date = self._clean_param(request.GET.get('date', ''))

            logger.info(f"Booking request - service_type: '{service_type}', staff_name: '{staff_name}', time: '{time}', date: '{date}'")

            if not all([service_type, staff_name, time, date]):
                missing_params = [p for p, v in zip(['service_type', 'staff_name', 'time', 'date'], [service_type, staff_name, time, date]) if not v]
                return Response({
                    'error': 'Missing required parameters',
                    'missing_parameters': missing_params,
                    'received_params': {
                        'service_type': service_type,
                        'staff_name': staff_name,
                        'time': time,
                        'date': date
                    },
                    'success': False
                }, status=status.HTTP_400_BAD_REQUEST)

            try:
                booking_date = datetime.strptime(date, "%Y-%m-%d").date()
                booking_time = datetime.strptime(time, "%H:%M").time()
                logger.info(f"Parsed date: {booking_date}, time: {booking_time}")
            except ValueError as e:
                logger.error(f"Date/time parsing error: {e}")
                return Response({
                    'error': 'Invalid date or time format',
                    'date_format_expected': 'YYYY-MM-DD',
                    'time_format_expected': 'HH:MM',
                    'received_date': date,
                    'received_time': time,
                    'success': False
                }, status=status.HTTP_400_BAD_REQUEST)

            # Staff lookup
            staff = None
            name_parts = staff_name.split()
            if len(name_parts) >= 2:
                first_name, last_name = name_parts[0], ' '.join(name_parts[1:])
                staff = Staff.objects.filter(first_name__iexact=first_name, last_name__iexact=last_name).first()
                if not staff:
                    staff = Staff.objects.filter(first_name__icontains=first_name, last_name__icontains=last_name).first()
            else:
                staff = Staff.objects.filter(first_name__icontains=staff_name).first()

            if not staff:
                available_staff = [f"{fn} {ln}" for fn, ln in Staff.objects.all().values_list('first_name', 'last_name')]
                logger.error(f"Staff not found: '{staff_name}'. Available staff: {available_staff}")
                return Response({
                    'error': 'Staff member not found',
                    'staff_name_provided': staff_name,
                    'available_staff': available_staff,
                    'success': False
                }, status=status.HTTP_404_NOT_FOUND)

            # Service lookup
            model = get_service_model(service_type.lower())
            if not model:
                return Response({
                    'error': 'Invalid service type',
                    'service_type': service_type,
                    'success': False
                }, status=status.HTTP_400_BAD_REQUEST)

            service = model.objects.filter(staff=staff).first()
            if not service:
                return Response({
                    'error': 'Service not found for this staff member',
                    'success': False
                }, status=status.HTTP_404_NOT_FOUND)

            # Return booking form
            return Response({
                'booking_details': {
                    'service_type': service_type,
                    'service_id': service.id,
                    'service_name': service.name,
                    'staff_id': staff.id,
                    'staff_name': f"{staff.first_name} {staff.last_name}",
                    'date': str(booking_date),
                    'time': time,
                    'price': float(service.price) if service.price else 0,
                    'duration_minutes': service.duration_minutes or 30
                },
                'form_fields': [
                    {'name': 'customer_first_name', 'type': 'text', 'required': True, 'label': 'First Name'},
                    {'name': 'customer_last_name', 'type': 'text', 'required': True, 'label': 'Last Name'},
                    {'name': 'customer_email', 'type': 'email', 'required': True, 'label': 'Email'},
                    {'name': 'customer_phone', 'type': 'tel', 'required': False, 'label': 'Phone (Optional)'}
                ],
                'success': True
            })
        except Exception as e:
            logger.error(f"Error preparing booking form: {str(e)}", exc_info=True)
            return Response({'error': 'Failed to prepare booking form', 'success': False}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def post(self, request):
        """Create a new booking"""
        try:
            data = request.data
            logger.info(f"Booking POST request received: {data}")

            required_fields = ['customer_first_name', 'customer_last_name', 'customer_email',
                               'service_type', 'staff_id', 'booking_date', 'booking_time']
            missing_fields = [f for f in required_fields if not data.get(f)]
            if missing_fields:
                return Response({
                    'error': 'Missing required fields',
                    'missing_fields': missing_fields,
                    'received_fields': list(data.keys()),
                    'success': False
                }, status=status.HTTP_400_BAD_REQUEST)

            # Email validation
            email = data['customer_email']
            if '@' not in email or '.' not in email.split('@')[1]:
                return Response({'error': 'Invalid email format', 'success': False}, status=status.HTTP_400_BAD_REQUEST)

            # Parse date & time
            booking_date = datetime.strptime(data['booking_date'], "%Y-%m-%d").date()
            booking_time = datetime.strptime(data['booking_time'], "%H:%M").time()

            with transaction.atomic():
                # Customer creation
                customer, created = Customer.objects.get_or_create(
                    email=email,
                    defaults={
                        'first_name': data['customer_first_name'],
                        'last_name': data['customer_last_name'],
                        'phone': data.get('customer_phone', '')
                    }
                )
                if not created:
                    customer.first_name = data['customer_first_name']
                    customer.last_name = data['customer_last_name']
                    if data.get('customer_phone'):
                        customer.phone = data['customer_phone']
                    customer.save()

                # Service & staff validation
                service_model = get_service_model(data['service_type'].lower())
                staff = Staff.objects.filter(id=data['staff_id']).first()
                if not service_model or not staff:
                    return Response({'error': 'Invalid service type or staff', 'success': False}, status=status.HTTP_400_BAD_REQUEST)

                service = service_model.objects.filter(id=data.get('service_id'), staff=staff).first() \
                          or service_model.objects.filter(staff=staff).first()

                if not service:
                    available_services = [{'id': s.id, 'name': s.name} for s in service_model.objects.filter(staff=staff)]
                    return Response({
                        'error': 'Service not available with selected staff member',
                        'available_services': available_services,
                        'success': False
                    }, status=status.HTTP_400_BAD_REQUEST)

                # Check existing bookings
                existing_booking = Booking.objects.filter(
                    staff=staff,
                    booking_date=booking_date,
                    booking_time=booking_time,
                    status__in=['confirmed', 'pending']
                ).first()

                if existing_booking:
                    logger.warning(f"Slot already booked: {existing_booking.id}")

                # Create booking (notes removed)
                booking = Booking.objects.create(
                    customer=customer,
                    service_type=data['service_type'],
                    service_id=service.id,
                    staff=staff,
                    booking_date=booking_date,
                    booking_time=booking_time,
                    status='confirmed'
                )

                return Response({
                    'message': 'Booking confirmed successfully!',
                    'booking_details': {
                        'booking_id': booking.id,
                        'service_type': data['service_type'],
                        'service_name': service.name,
                        'service_id': service.id,
                        'staff_id': staff.id,
                        'staff_name': f"{staff.first_name} {staff.last_name}",
                        'customer_name': f"{customer.first_name} {customer.last_name}",
                        'customer_email': customer.email,
                        'date': str(booking_date),
                        'time': booking_time.strftime("%H:%M"),
                        'price': float(service.price) if service.price else 0,
                        'duration_minutes': service.duration_minutes or 30,
                        'status': booking.status
                    },
                    'success': True
                }, status=status.HTTP_201_CREATED)

        except Exception as e:
            logger.error(f"Unexpected error creating booking: {str(e)}", exc_info=True)
            return Response({
                'error': 'Failed to create booking. Please try again.',
                'debug_info': str(e),
                'success': False
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class BookingStatusAPIView(APIView):
    """Check booking status and manage booking modifications"""
    
    def get(self, request, booking_id):
        """Get booking details by ID"""
        try:
            booking = Booking.objects.select_related(
                'customer', 'staff'
            ).filter(id=booking_id).first()
            
            if not booking:
                return Response({
                    'error': 'Booking not found',
                    'success': False
                }, status=status.HTTP_404_NOT_FOUND)

            # Get service details
            service_model = get_service_model(booking.service_type)
            service = service_model.objects.filter(id=booking.service_id).first()

            return Response({
                'booking_details': {
                    'booking_id': booking.id,
                    'service_type': booking.service_type,
                    'service_name': service.name if service else 'Unknown Service',
                    'staff_name': f"{booking.staff.first_name} {booking.staff.last_name}",
                    'customer_name': f"{booking.customer.first_name} {booking.customer.last_name}",
                    'customer_email': booking.customer.email,
                    'date': str(booking.booking_date),
                    'time': booking.booking_time.strftime("%H:%M"),
                    'status': booking.status,
                    'created_at': booking.created_at.isoformat(),
                    'notes': booking.notes or ''
                },
                'success': True
            })

        except Exception as e:
            logger.error(f"Error fetching booking {booking_id}: {str(e)}")
            return Response({
                'error': 'Failed to fetch booking details',
                'success': False
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def patch(self, request, booking_id):
        """Update booking status (cancel, reschedule, etc.)"""
        try:
            booking = Booking.objects.filter(id=booking_id).first()
            if not booking:
                return Response({
                    'error': 'Booking not found',
                    'success': False
                }, status=status.HTTP_404_NOT_FOUND)

            action = request.data.get('action')
            if action == 'cancel':
                booking.status = 'cancelled'
                booking.save()
                return Response({
                    'message': 'Booking cancelled successfully',
                    'booking_id': booking.id,
                    'status': booking.status,
                    'success': True
                })

            return Response({
                'error': 'Invalid action',
                'available_actions': ['cancel'],
                'success': False
            }, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            logger.error(f"Error updating booking {booking_id}: {str(e)}")
            return Response({
                'error': 'Failed to update booking',
                'success': False
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ------------------ HELPER FUNCTIONS ------------------

def get_available_slots_for_staff(service, staff, booking_date):
    """
    Enhanced function to get available and booked slots for staff on a specific date
    Returns: (available_slots_list, booked_slots_list)
    """
    try:
        day_of_week = booking_date.weekday()
        
        # Get staff availability for this day
        availability = StaffAvailability.objects.filter(
            staff=staff, 
            day_of_week=day_of_week
        ).first()
        
        if not availability:
            return [], []

        # Create time slots based on availability and service duration
        start_dt = datetime.combine(booking_date, availability.start_time)
        end_dt = datetime.combine(booking_date, availability.end_time)
        
        duration = service.duration_minutes or BUSINESS_HOURS['slot_duration']
        buffer = BUSINESS_HOURS.get('buffer_time', 0)
        
        if duration <= 0:
            return [], []

        # Generate all possible slots
        possible_slots = []
        current = start_dt
        
        while current + timedelta(minutes=duration) <= end_dt:
            possible_slots.append(current.time())
            current += timedelta(minutes=duration + buffer)

        # Get existing bookings for this staff and date
        existing_bookings = Booking.objects.filter(
            staff=staff,
            booking_date=booking_date,
            status__in=['confirmed', 'pending']  # Exclude cancelled bookings
        ).values_list('booking_time', flat=True)

        # Filter out past slots for today
        if booking_date == datetime.today().date():
            current_time = datetime.now().time()
            possible_slots = [slot for slot in possible_slots if slot > current_time]

        # Separate available and booked slots
        booked_times_str = [t.strftime("%H:%M") for t in existing_bookings]
        available_slots_str = [
            slot.strftime("%H:%M") 
            for slot in possible_slots 
            if slot not in existing_bookings
        ]

        return available_slots_str, booked_times_str

    except Exception as e:
        logger.error(f"Error getting slots for staff {staff.id} on {booking_date}: {str(e)}")
        return [], []


def validate_business_hours(booking_datetime):
    """Validate if booking time is within business hours"""
    booking_time = booking_datetime.time()
    day_of_week = booking_datetime.weekday()
    
    if day_of_week in BUSINESS_HOURS['closed_days']:
        return False, "We are closed on this day"
    
    start_time = datetime.strptime(BUSINESS_HOURS['start_time'], "%H:%M").time()
    end_time = datetime.strptime(BUSINESS_HOURS['end_time'], "%H:%M").time()
    
    if not (start_time <= booking_time <= end_time):
        return False, f"Booking time must be between {BUSINESS_HOURS['start_time']} and {BUSINESS_HOURS['end_time']}"
    
    return True, "Valid business hours"


def cleanup_expired_bookings():
    """Clean up old cancelled bookings and update expired pending bookings"""
    try:
        # Cancel pending bookings older than 24 hours
        cutoff_time = datetime.now() - timedelta(hours=24)
        expired_bookings = Booking.objects.filter(
            status='pending',
            created_at__lt=cutoff_time
        )
        expired_count = expired_bookings.update(status='expired')
        
        logger.info(f"Cleaned up {expired_count} expired bookings")
        return expired_count
        
    except Exception as e:
        logger.error(f"Error cleaning up bookings: {str(e)}")
        return 0