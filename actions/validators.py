# actions/validators.py
import re
from typing import Any, Text, Dict, Optional
from datetime import datetime
from rasa_sdk import Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.types import DomainDict
from rasa_sdk.forms import FormValidationAction

TRIGGER_WORDS = {"hi", "hello", "hey", "menu", "booking", "book", "book a table", "reserve", "table"}

def _is_trigger_phrase(value: Optional[Text], tracker: Tracker) -> bool:
    """
    Return True if value looks like a short greeting/intent-like phrase we should reject.
    NOTE: Do NOT compare value == latest_text here (slot_value will usually equal latest_text).
    Keep this conservative so normal names are accepted.
    """
    if not value:
        return False

    v = value.strip().lower()
    # latest_text and intent available if you want additional checks
    latest_text = (tracker.latest_message.get("text") or "").strip().lower()
    intent_name = (tracker.latest_message.get("intent") or {}).get("name", "")

    # If the user literally typed an intent keyword or a greeting, treat it as trigger
    if v in TRIGGER_WORDS:
        return True

    # If the intent predicted by NLU is one of the booking/greeting/etc intents,
    # and the user message is very short / looks like intent, treat as trigger.
    if intent_name in {"greet", "book_table", "show_menu", "goodbye"} and len(v.split()) <= 3:
        # avoid rejecting typical personal names; require presence of keywords
        if any(k in v for k in ["book", "booking", "menu", "reserve", "hi", "hello", "table"]):
            return True

    # Short messages (<=3 words) that explicitly contain intent-like words
    if len(v.split()) <= 3 and any(k in v for k in ["book", "booking", "menu", "reserve", "hi", "hello", "table"]):
        return True

    return False


def _normalize_digits(text: Text) -> Text:
    """Return only digits from the text."""
    return "".join(ch for ch in text if ch.isdigit())


_number_words = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14,
    "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18,
    "nineteen": 19, "twenty": 20
}


class ValidateBookingForm(FormValidationAction):
    def name(self) -> Text:
        return "validate_booking_form"

    def validate_name(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        # Only validate when 'name' was requested by the form
        requested = tracker.get_slot("requested_slot")
        if requested != "name":
            return {"name": None}

        if _is_trigger_phrase(slot_value, tracker):
            dispatcher.utter_message(text="That looks like a greeting or command rather than a name. What's the name for the booking?")
            return {"name": None}

        if not isinstance(slot_value, str) or len(slot_value.strip()) < 2:
            dispatcher.utter_message(text="Please tell me the full name (at least 2 characters).")
            return {"name": None}

        # success: normalize whitespace
        return {"name": " ".join(slot_value.strip().split())}

    def validate_phone(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        requested = tracker.get_slot("requested_slot")
        if requested != "phone":
            return {"phone": None}

        if _is_trigger_phrase(slot_value, tracker):
            dispatcher.utter_message(text="That doesn't look like a phone number. Please provide a 10-digit phone number.")
            return {"phone": None}

        s = str(slot_value)
        digits = _normalize_digits(s)
        # accept 7-15 digit numbers (10 typical)
        if len(digits) < 7 or len(digits) > 15:
            dispatcher.utter_message(text="Please provide a valid phone number (digits only, e.g. 9876543210).")
            return {"phone": None}

        return {"phone": digits}

    def validate_date(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        requested = tracker.get_slot("requested_slot")
        if requested != "date":
            return {"date": None}

        if _is_trigger_phrase(slot_value, tracker):
            dispatcher.utter_message(text="That doesn't look like a date. Please enter the booking date in DD/MM/YYYY format (example: 20/11/2025).")
            return {"date": None}

        s = str(slot_value).strip()
        # try common formats
        for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
            try:
                d = datetime.strptime(s, fmt).date()
                # optional: reject past dates
                if d < datetime.now().date():
                    dispatcher.utter_message(text="That date is in the past. Please provide a future date.")
                    return {"date": None}
                return {"date": d.isoformat()}  # store as YYYY-MM-DD
            except Exception:
                continue

        # try to extract numbers like 20/12/2025
        m = re.search(r"(\d{1,2})[^\d](\d{1,2})[^\d](\d{4})", s)
        if m:
            try:
                d = datetime(int(m.group(3)), int(m.group(2)), int(m.group(1))).date()
                if d < datetime.now().date():
                    dispatcher.utter_message(text="That date is in the past. Please provide a future date.")
                    return {"date": None}
                return {"date": d.isoformat()}
            except Exception:
                pass

        dispatcher.utter_message(text="Please enter the booking date in DD/MM/YYYY format (example: 20/11/2025).")
        return {"date": None}

    def validate_time(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        requested = tracker.get_slot("requested_slot")
        if requested != "time":
            return {"time": None}

        if _is_trigger_phrase(slot_value, tracker):
            dispatcher.utter_message(text="That doesn't look like a time. Please enter time in HH:MM (24-hour) format (example: 19:30).")
            return {"time": None}

        s = str(slot_value).strip()
        # allow HH:MM
        try:
            t = datetime.strptime(s, "%H:%M").time()
            # optional: check restaurant hours if you want
            return {"time": t.strftime("%H:%M")}
        except Exception:
            # try to extract digits like "1930" or "7:30 pm"
            m = re.search(r"(\d{1,2})[:\.]?(\d{2})", s)
            if m:
                h = int(m.group(1))
                mm = int(m.group(2))
                if 0 <= h <= 23 and 0 <= mm <= 59:
                    return {"time": f"{h:02d}:{mm:02d}"}
        dispatcher.utter_message(text="Please enter time in HH:MM (24-hour) format (example: 19:30).")
        return {"time": None}

    def validate_party_size(self, slot_value, dispatcher, tracker, domain):
        requested = tracker.get_slot("requested_slot")
        if requested != "party_size":
            return {"party_size": None}

        # If user typed "5 people" or "five", try to extract a number robustly
        if _is_trigger_phrase(slot_value, tracker):
            dispatcher.utter_message(text="Please enter a number, like 2 or 5.")
            return {"party_size": None}

        if not slot_value:
            dispatcher.utter_message(text="Please enter how many people will be coming (e.g. 5).")
            return {"party_size": None}

        sv = str(slot_value).strip().lower()
        # try digits first
        m = re.search(r"\d+", sv)
        if m:
            num = int(m.group(0))
        else:
            # try word -> number (one..twenty)
            words = re.findall(r"[a-z]+", sv)
            num = None
            for w in words:
                if w in _number_words:
                    num = _number_words[w]
                    break
            if num is None:
                dispatcher.utter_message(text="Please enter a valid number of people (e.g. 5).")
                return {"party_size": None}

        if num < 1 or num > 20:
            dispatcher.utter_message(text="We allow booking for 1–20 people.")
            return {"party_size": None}

        return {"party_size": num}
