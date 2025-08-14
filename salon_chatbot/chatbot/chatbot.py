# booking/chatbot.py
import re
from datetime import datetime, timedelta
from dateutil.parser import parse as parse_date
from rest_framework.views import APIView
from rest_framework.response import Response
from .utils import SERVICE_MODELS, get_service_model
from .service_views import get_available_slots_for_staff

conversation_state = {}

# ------------------ INTENTS ------------------
INTENTS = {
    "greeting": {"keywords": ["hi", "hello", "hey", "good morning", "good afternoon", "good evening", "yo", "hiya"],
                 "response": "Hello! Welcome to FIDDEN. How can I assist you today?"},
    "thanks": {"keywords": ["thanks", "thank you", "thx", "ty", "thank u", "thanks a lot"],
               "response": "You're welcome! We also provide Haircut, Beard, Facial, SPA."},
    "service_request": {"keywords": ["haircut", "hair cut", "beard", "facial", "spa", "massage", "shave"],
                        "response": "Great choice! Which date would you like to book your service?"},
    "date_keywords": {"keywords": ["today", "tomorrow", "next day", "day after tomorrow",
                                   "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"],
                      "response": "Got it! Let's check available slots for that date."},
    "pricing": {"keywords": ["price", "cost", "how much", "charge", "fee"],
                "response": "Our prices vary by service. Haircut: $25, Beard: $15, Facial: $40, SPA: $60."},
    "working_hours": {"keywords": ["open", "close", "working hours", "timing", "hours"],
                      "response": "We are open Monday to Saturday, 9:00 AM to 6:00 PM."},
    "slot_selection": {"keywords": [], "response": "Please confirm your slot."},
    "unknown": {"keywords": [], "response": "Sorry, I didn't understand. Can you please rephrase?"}
}

# ------------------ INTENT DETECTION ------------------
def detect_intent(message):
    message_lower = message.lower()
    for intent, info in INTENTS.items():
        if any(k in message_lower for k in info.get("keywords", [])):
            return intent
    # Check for date parsing
    try:
        parse_date(message, fuzzy=True)
        return "date_keywords"
    except:
        pass
    # Check for HH:MM slot selection
    if re.search(r'\b\d{1,2}:\d{2}\b', message_lower):
        return "slot_selection"
    return "unknown"

# ------------------ DATE PARSING ------------------
def parse_user_date(message):
    """Parse multiple user-friendly date formats into a datetime.date object."""
    message_lower = message.lower().strip()
    today = datetime.today().date()

    # Relative dates
    if "today" in message_lower:
        return today
    if "tomorrow" in message_lower or "next day" in message_lower:
        return today + timedelta(days=1)
    
    # 'this month 15' → 15th of current month
    match = re.search(r'this month (\d{1,2})', message_lower)
    if match:
        day = int(match.group(1))
        try:
            return today.replace(day=day)
        except:
            return None

    # Fuzzy parsing for standard formats or "August 15"
    try:
        return parse_date(message, fuzzy=True).date()
    except:
        return None

# ------------------ SLOT NUMBER PARSING ------------------
def parse_slot_number(message):
    """Extract slot number from the message if present."""
    number_match = re.search(r'\b(\d+)\b', message)
    if number_match:
        return number_match.group(1)
    return None

# ------------------ CHATBOT API ------------------
class ChatbotAPIView(APIView):
    """Intent-based chatbot for salon with slot checking"""

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

        # ------------------ Greeting Stage ------------------
        if stage == "greeting":
            if intent in ["greeting", "service_request"]:
                state["stage"] = "choose_service"
                return Response({"bot": INTENTS["greeting"]["response"]})
            return Response({"bot": "Hi! Say 'hi' or type the service you want."})

        # ------------------ Choose Service Stage ------------------
        if stage == "choose_service":
            if intent != "service_request":
                return Response({"bot": "We provide several services: Haircut, Beard, Facial, SPA."})

            # Identify service type
            for service_type in SERVICE_MODELS.keys():
                if service_type in message.lower():
                    state["service_type"] = service_type
                    break
            if not state["service_type"]:
                return Response({"bot": "Please choose Haircut, Beard, Facial, or SPA."})

            # Determine requested date
            requested_date = parse_user_date(message) or datetime.today().date()
            state["requested_date"] = requested_date

            # Generate available slots
            all_slots = {}
            service_model = get_service_model(state["service_type"])
            services_with_staff = service_model.objects.filter(staff__isnull=False)
            for service_instance in services_with_staff:
                for staff in service_instance.staff.all():
                    available, booked = get_available_slots_for_staff(service_instance, staff, requested_date)
                    staff_name = f"{staff.first_name} {staff.last_name}"
                    all_slots.setdefault(staff_name, []).extend(available)
            for staff in all_slots:
                all_slots[staff] = sorted(list(set(all_slots[staff])))

            if not all_slots:
                return Response({"bot": f"No available slots for {state['service_type']} on {requested_date}."})

            state["available_slots"] = all_slots
            state["stage"] = "pick_slot"

            # Prepare slot map
            slot_map = {}
            slot_message = ""
            counter = 1
            for staff, times in all_slots.items():
                for t in times:
                    slot_map[str(counter)] = f"{staff} {t}"
                    slot_message += f"{counter}. {staff}: {t}\n"
                    counter += 1
            state["slot_map"] = slot_map

            return Response({
                "bot": f"Available slots for {state['service_type']} on {requested_date}:\n{slot_message}\nReply with the slot number or time."
            })

        # ------------------ Pick Slot Stage ------------------
        # ------------------ Pick Slot Stage ------------------
        if stage == "pick_slot":
            message_clean = message.strip().lower()
            selected = None

            # ✅ Extract date from message first
            parsed_date = parse_user_date(message)
            if parsed_date:
                state["requested_date"] = parsed_date

                # Regenerate slots for this date
                all_slots = {}
                service_model = get_service_model(state["service_type"])
                services_with_staff = service_model.objects.filter(staff__isnull=False)
                for service_instance in services_with_staff:
                    for staff in service_instance.staff.all():
                        available, booked = get_available_slots_for_staff(service_instance, staff, parsed_date)
                        staff_name = f"{staff.first_name} {staff.last_name}"
                        all_slots.setdefault(staff_name, []).extend(available)
                for staff in all_slots:
                    all_slots[staff] = sorted(list(set(all_slots[staff])))
                if not all_slots:
                    return Response({"bot": f"No available slots for {state['service_type']} on {parsed_date}."})

                # Update slot map and available slots
                slot_map = {}
                counter = 1
                for staff, times in all_slots.items():
                    for t in times:
                        slot_map[str(counter)] = f"{staff} {t}"
                        counter += 1
                state["slot_map"] = slot_map
                state["available_slots"] = all_slots
            else:
                slot_map = state.get("slot_map", {})

            # ✅ Extract slot number from message
            slot_number = parse_slot_number(message)
            if slot_number:
                selected = slot_map.get(slot_number)

            # Fallback: match by HH:MM
            if not selected:
                time_match = re.search(r'\b\d{1,2}:\d{2}\b', message_clean)
                if time_match:
                    time_str = time_match.group(0)
                    for value in slot_map.values():
                        if value.endswith(time_str):
                            selected = value
                            break

            # Last slot fallback
            if not selected and "last" in message_clean and slot_map:
                last_key = max(slot_map.keys(), key=int)
                selected = slot_map[last_key]

            if not selected:
                return Response({"bot": "Please reply with a valid slot number or time from the list."})

            # ✅ Validate slot availability using the correct date
            staff_name, slot_time = " ".join(selected.split()[:-1]), selected.split()[-1]
            booking_date = state["requested_date"]

            if slot_time not in state["available_slots"].get(staff_name, []):
                return Response({"bot": f"Sorry, {slot_time} with {staff_name} is no longer available. Please choose another slot."})

            state["selected_slot"] = selected
            state["stage"] = "booking_link"

            booking_url = (
                f"/api/book/?service_type={state['service_type']}"
                f"&staff_name={staff_name}"
                f"&time={slot_time}"
                f"&date={booking_date}"
            )

            return Response({
                "bot": f"Confirm your {state['service_type']} at {selected} here: {booking_url}\nThanks!"
            })

        # ------------------ Thanks Stage ------------------
        if intent == "thanks":
            state["stage"] = "end"
            return Response({"bot": INTENTS["thanks"]["response"]})

        # ------------------ Unknown ------------------
        return Response({"bot": INTENTS["unknown"]["response"]})
