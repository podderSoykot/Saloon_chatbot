# booking/chatbot.py
import re
from datetime import datetime, timedelta
from dateutil.parser import parse as parse_date
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .utils import SERVICE_MODELS, get_service_model
from .service_views import get_available_slots_for_staff

# Thread-safe conversation state (consider using Redis in production)
conversation_state = {}

# ------------------ INTENTS ------------------
INTENTS = {
    "greeting": {
        "keywords": ["hi", "hello", "hey", "good morning", "good afternoon", "good evening", "yo", "hiya", "start"],
        "response": "Hello! Welcome to FIDDEN Salon. I'm here to help you book your appointment. We offer Haircut ($25), Beard ($15), Facial ($40), and SPA ($60) services. Which service would you like to book?"
    },
    "thanks": {
        "keywords": ["thanks", "thank you", "thx", "ty", "thank u", "thanks a lot", "appreciate"],
        "response": "You're very welcome! We look forward to serving you at FIDDEN. Feel free to ask if you need anything else!"
    },
    "service_request": {
        "keywords": ["haircut", "hair cut", "beard", "facial", "spa", "massage", "shave", "trim"],
        "response": "Great choice! Which date would you like to book your service?"
    },
    "date_keywords": {
        "keywords": ["today", "tomorrow", "next day", "day after tomorrow",
                     "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday",
                     "next week", "this week"],
        "response": "Got it! Let me check available slots for that date."
    },
    "pricing": {
        "keywords": ["price", "cost", "how much", "charge", "fee", "rates", "pricing", "expensive", "cheap"],
        "response": "Here are our service prices:\n• Haircut: $25\n• Beard: $15\n• Facial: $40\n• SPA: $60\n\nWhich service interests you?"
    },
    "working_hours": {
        "keywords": ["open", "close", "working hours", "timing", "hours", "schedule", "when open"],
        "response": "We are open Monday to Saturday, 9:00 AM to 6:00 PM. We're closed on Sundays. Would you like to book an appointment?"
    },
    "cancel_restart": {
        "keywords": ["cancel", "restart", "start over", "reset", "new booking", "begin again"],
        "response": "No problem! Let's start fresh. Which service would you like to book today?"
    },
    "help": {
        "keywords": ["help", "what can you do", "options", "commands"],
        "response": "I can help you:\n• Book appointments for Haircut, Beard, Facial, or SPA\n• Check pricing and working hours\n• Find available time slots\n\nJust tell me what service you'd like to book!"
    },
    "slot_selection": {"keywords": [], "response": "Please confirm your slot."},
    "unknown": {"keywords": [], "response": "I'm not sure I understand. You can say 'help' to see what I can do, or simply tell me which service you'd like to book."}
}

# ------------------ INTENT DETECTION ------------------
def detect_intent(message):
    """Improved intent detection with better pattern matching"""
    message_lower = message.lower().strip()
    
    # Check for specific intents first
    for intent, info in INTENTS.items():
        keywords = info.get("keywords", [])
        if any(keyword in message_lower for keyword in keywords):
            return intent
    
    # Check for date patterns
    if is_date_message(message_lower):
        return "date_keywords"
    
    # Check for time slot patterns (HH:MM or just numbers)
    if re.search(r'\b\d{1,2}:\d{2}\b', message_lower) or re.search(r'^\d+$', message_lower.strip()):
        return "slot_selection"
    
    return "unknown"

def is_date_message(message_lower):
    """Check if message contains date-related content"""
    try:
        parse_date(message_lower, fuzzy=True)
        return True
    except:
        pass
    
    # Check for relative date patterns
    date_patterns = [
        r'\btoday\b', r'\btomorrow\b', r'\bnext day\b', r'\bday after tomorrow\b',
        r'\bthis (week|month)\b', r'\bnext (week|month)\b',
        r'\b(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b',
        r'\b\d{1,2}(st|nd|rd|th)?\s+(january|february|march|april|may|june|july|august|september|october|november|december)\b'
    ]
    
    return any(re.search(pattern, message_lower) for pattern in date_patterns)

# ------------------ DATE PARSING ------------------
def parse_user_date(message):
    """Enhanced date parsing with better error handling"""
    if not message:
        return None
        
    message_lower = message.lower().strip()
    today = datetime.today().date()
    
    # Handle relative dates
    if "today" in message_lower:
        return today
    if "tomorrow" in message_lower or "next day" in message_lower:
        return today + timedelta(days=1)
    if "day after tomorrow" in message_lower:
        return today + timedelta(days=2)
    
    # Handle day names
    day_names = {
        'monday': 0, 'tuesday': 1, 'wednesday': 2, 'thursday': 3,
        'friday': 4, 'saturday': 5, 'sunday': 6
    }
    
    for day_name, day_num in day_names.items():
        if day_name in message_lower:
            days_ahead = day_num - today.weekday()
            if days_ahead <= 0:  # Target day already happened this week
                days_ahead += 7
            return today + timedelta(days=days_ahead)
    
    # Handle 'this month DD' format
    match = re.search(r'this month (\d{1,2})', message_lower)
    if match:
        try:
            day = int(match.group(1))
            return today.replace(day=day)
        except ValueError:
            pass
    
    # Try fuzzy parsing for other formats
    try:
        parsed_date = parse_date(message, fuzzy=True).date()
        # Don't allow past dates
        if parsed_date < today:
            return None
        return parsed_date
    except:
        pass
    
    return None

# ------------------ SLOT PARSING ------------------
def parse_slot_number(message):
    """Extract slot number from message with better validation"""
    message = message.strip()
    
    # Direct number match
    if message.isdigit():
        return message
    
    # Extract first number found
    number_match = re.search(r'\b(\d+)\b', message)
    if number_match:
        return number_match.group(1)
    
    return None

def parse_time_from_message(message):
    """Extract time in HH:MM format from message"""
    time_match = re.search(r'\b(\d{1,2}:\d{2})\b', message)
    if time_match:
        return time_match.group(1)
    return None

# ------------------ VALIDATION ------------------
def validate_service_type(message):
    """Extract and validate service type from message"""
    message_lower = message.lower()
    
    service_mappings = {
        'haircut': ['haircut', 'hair cut', 'hair', 'cut'],
        'beard': ['beard', 'shave', 'trim beard'],
        'facial': ['facial', 'face', 'skincare'],
        'spa': ['spa', 'massage', 'relax', 'therapy']
    }
    
    for service_type, keywords in service_mappings.items():
        if any(keyword in message_lower for keyword in keywords):
            return service_type
    
    return None

def is_business_day(date_obj):
    """Check if date is a business day (Monday-Saturday)"""
    return date_obj.weekday() < 6  # Monday=0, Saturday=5, Sunday=6

# ------------------ CHATBOT API ------------------
class ChatbotAPIView(APIView):
    """Enhanced intent-based chatbot for salon booking"""

    def post(self, request):
        try:
            user_id = request.data.get("user_id")
            message = request.data.get("message", "").strip()

            if not user_id:
                return Response(
                    {"bot": "User ID is required.", "error": True}, 
                    status=status.HTTP_400_BAD_REQUEST
                )

            if not message:
                return Response(
                    {"bot": "Please send a message.", "error": False}
                )

            # Initialize user state if not exists
            if user_id not in conversation_state:
                conversation_state[user_id] = {
                    "stage": "greeting",
                    "service_type": None,
                    "selected_slot": None,
                    "requested_date": None,
                    "available_slots": {},
                    "slot_map": {},
                    "last_activity": datetime.now()
                }

            state = conversation_state[user_id]
            state["last_activity"] = datetime.now()
            stage = state["stage"]
            intent = detect_intent(message)

            # Handle restart/cancel at any stage
            if intent == "cancel_restart":
                state.update({
                    "stage": "greeting",
                    "service_type": None,
                    "selected_slot": None,
                    "requested_date": None,
                    "available_slots": {},
                    "slot_map": {}
                })
                return Response({"bot": INTENTS["cancel_restart"]["response"]})

            # Handle help at any stage
            if intent == "help":
                return Response({"bot": INTENTS["help"]["response"]})

            # Handle pricing and working hours at any stage
            if intent == "pricing":
                return Response({"bot": INTENTS["pricing"]["response"]})
            
            if intent == "working_hours":
                return Response({"bot": INTENTS["working_hours"]["response"]})

            return self._handle_conversation_stage(state, intent, message)

        except Exception as e:
            print(e)
            return Response(
                {"bot": "I'm experiencing some technical difficulties. Please try again.", "error": True},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
                
            )

    def _handle_conversation_stage(self, state, intent, message):
        """Handle different conversation stages"""
        stage = state["stage"]

        if stage == "greeting":
            return self._handle_greeting_stage(state, intent, message)
        elif stage == "choose_service":
            return self._handle_service_selection(state, intent, message)
        elif stage == "pick_slot":
            return self._handle_slot_selection(state, intent, message)
        elif stage == "booking_link":
            return self._handle_booking_confirmation(state, intent, message)
        else:
            # Reset to greeting if unknown stage
            state["stage"] = "greeting"
            return Response({"bot": INTENTS["greeting"]["response"]})

    def _handle_greeting_stage(self, state, intent, message):
        """Handle greeting and initial service request"""
        if intent in ["greeting", "service_request"]:
            service_type = validate_service_type(message)
            if service_type:
                state["service_type"] = service_type
                state["stage"] = "choose_service"
                return Response({"bot": f"Great! You've chosen {service_type.title()}. Which date would you prefer for your appointment?"})
            else:
                state["stage"] = "choose_service"
                return Response({"bot": INTENTS["greeting"]["response"]})
        
        return Response({"bot": "Welcome! Please say 'hello' or tell me which service you'd like to book."})

    def _handle_service_selection(self, state, intent, message):
        """Handle service type selection and date parsing"""
        # If service not yet selected, try to extract it
        if not state["service_type"]:
            service_type = validate_service_type(message)
            if service_type:
                state["service_type"] = service_type
            else:
                return Response({"bot": "Please choose from our services: Haircut, Beard, Facial, or SPA. Which one interests you?"})

        # Parse date from message
        requested_date = parse_user_date(message)
        if not requested_date:
            requested_date = datetime.today().date()

        # Validate business day
        if not is_business_day(requested_date):
            return Response({"bot": "We're closed on Sundays. Please choose Monday through Saturday."})

        state["requested_date"] = requested_date

        # Get available slots
        try:
            available_slots = self._get_available_slots(state["service_type"], requested_date)
            
            if not available_slots:
                return Response({
                    "bot": f"Sorry, no slots available for {state['service_type']} on {requested_date.strftime('%B %d, %Y')}. Please try another date."
                })

            state["available_slots"] = available_slots
            state["stage"] = "pick_slot"

            # Create slot map and response
            slot_map = {}
            slot_message = f"Available slots for {state['service_type'].title()} on {requested_date.strftime('%B %d, %Y')}:\n\n"
            counter = 1
            
            for staff_name, times in available_slots.items():
                for time_slot in times:
                    slot_map[str(counter)] = f"{staff_name} {time_slot}"
                    slot_message += f"{counter}. {staff_name}: {time_slot}\n"
                    counter += 1
            
            state["slot_map"] = slot_map
            slot_message += "\nPlease reply with the slot number (e.g., '1') or the time (e.g., '10:00')."

            return Response({"bot": slot_message})

        except Exception as e:
            return Response({"bot": "Sorry, I couldn't check availability right now. Please try again."})

    def _handle_slot_selection(self, state, intent, message):
        """Handle slot selection with improved validation"""
        # Check if user wants to change date
        new_date = parse_user_date(message)
        if new_date and new_date != state["requested_date"]:
            state["requested_date"] = new_date
            return self._handle_service_selection(state, intent, f"{state['service_type']} {message}")

        slot_map = state.get("slot_map", {})
        if not slot_map:
            return Response({"bot": "Please start over by telling me which service you'd like."})

        selected_slot = None
        
        # Try to match by slot number
        slot_number = parse_slot_number(message)
        if slot_number and slot_number in slot_map:
            selected_slot = slot_map[slot_number]
        
        # Try to match by time
        if not selected_slot:
            time_str = parse_time_from_message(message)
            if time_str:
                for slot_key, slot_value in slot_map.items():
                    if slot_value.endswith(time_str):
                        selected_slot = slot_value
                        break

        if not selected_slot:
            available_options = "\n".join([f"{k}. {v}" for k, v in slot_map.items()])
            return Response({
                "bot": f"Please choose a valid option:\n\n{available_options}\n\nReply with the number or time."
            })

        # Validate slot is still available
        staff_name = " ".join(selected_slot.split()[:-1])
        slot_time = selected_slot.split()[-1]
        
        if slot_time not in state["available_slots"].get(staff_name, []):
            return Response({
                "bot": f"Sorry, {slot_time} with {staff_name} is no longer available. Please choose another slot."
            })

        state["selected_slot"] = selected_slot
        state["stage"] = "booking_link"

        # Generate booking URL
        booking_url = (
            f"http://127.0.0.1:8000/api/book/"
        )

        return Response({
            "bot": f"Perfect! Your {state['service_type']} appointment is reserved with {staff_name} at {slot_time} on {state['requested_date'].strftime('%B %d, %Y')}.\n\nClick here to complete your booking: {booking_url} \nThank you for choosing FIDDEN!"
        })


    def _handle_booking_confirmation(self, state, intent, message):
        """Handle post-booking conversation"""
        if intent == "thanks":
            state["stage"] = "end"
            return Response({"bot": INTENTS["thanks"]["response"]})
        
        # Reset for new booking
        if intent in ["service_request", "greeting"]:
            state.update({
                "stage": "greeting",
                "service_type": None,
                "selected_slot": None,
                "requested_date": None,
                "available_slots": {},
                "slot_map": {}
            })
            return self._handle_greeting_stage(state, intent, message)
        
        return Response({"bot": "Your booking link is ready above. Is there anything else I can help you with?"})

    def _get_available_slots(self, service_type, date):
        """Get available slots for a service on a specific date"""
        try:
            service_model = get_service_model(service_type)
            services_with_staff = service_model.objects.filter(staff__isnull=False)
            
            all_slots = {}
            for service_instance in services_with_staff:
                for staff in service_instance.staff.all():
                    available_slots, _ = get_available_slots_for_staff(service_instance, staff, date)
                    if available_slots:
                        staff_name = f"{staff.first_name} {staff.last_name}"
                        all_slots[staff_name] = sorted(list(set(available_slots)))
            
            return all_slots
        except Exception as e:
            return {}

# ------------------ UTILITY FUNCTIONS ------------------
def cleanup_old_conversations():
    """Clean up conversations older than 24 hours"""
    cutoff_time = datetime.now() - timedelta(hours=24)
    expired_users = [
        user_id for user_id, state in conversation_state.items()
        if state.get("last_activity", datetime.min) < cutoff_time
    ]
    for user_id in expired_users:
        del conversation_state[user_id]