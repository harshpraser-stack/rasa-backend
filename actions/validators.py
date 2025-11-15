from typing import Any, Text, Dict
from rasa_sdk import FormValidationAction
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk import Tracker
from rasa_sdk.types import DomainDict
from datetime import datetime, date, time, timedelta
from typing import Optional
import re

# ===== configuration =====
OPENING_TIME = time(hour=7, minute=30)   # 07:30
CLOSING_TIME = time(hour=1, minute=30)   # 01:30 (next day) -> handled as overnight
MAX_BOOKING_DAYS_AHEAD = 90
MIN_PARTY_SIZE = 1
MAX_PARTY_SIZE = 20
# =========================


def _only_digits(text: str) -> str:
    return re.sub(r"\D", "", text or "")

def _normalize_phone(digits: str) -> Optional[str]:

    if not digits:
        return None


    if len(digits) == 12 and digits.startswith("91"):
        digits = digits[2:]


    if len(digits) == 11 and digits.startswith("0"):
        digits = digits[1:]


    if len(digits) == 10:
        return digits

    return None



def _time_within_business_hours(parsed_time: time) -> bool:

    if OPENING_TIME <= CLOSING_TIME:
        return OPENING_TIME <= parsed_time <= CLOSING_TIME
    else:

        return (parsed_time >= OPENING_TIME) or (parsed_time <= CLOSING_TIME)


class ValidateBookingForm(FormValidationAction):
    def name(self) -> Text:
        return "validate_booking_form"


    async def validate_date(
        self,
        value: Text,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        raw = (value or "").strip()
        try:
            parsed = datetime.strptime(raw, "%d/%m/%Y").date()
        except Exception:
            dispatcher.utter_message(
                text="Invalid date format. Please enter the date in DD/MM/YYYY format (for example: 20/11/2025)."
            )
            return {"date": None}

        today = date.today()
        if parsed < today:
            dispatcher.utter_message(text="The date you entered is in the past. Please enter a future date.")
            return {"date": None}

        if parsed > today + timedelta(days=MAX_BOOKING_DAYS_AHEAD):
            dispatcher.utter_message(
                text=f"We accept bookings up to {MAX_BOOKING_DAYS_AHEAD} days in advance. Please choose an earlier date."
            )
            return {"date": None}

        normalized = parsed.strftime("%Y-%m-%d")
        return {"date": normalized}


    async def validate_time(
        self,
        value: Text,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        raw = (value or "").strip()

        try:
            parsed_time = datetime.strptime(raw, "%H:%M").time()
        except Exception:
            dispatcher.utter_message(text="Invalid time format. Please enter time in HH:MM (24-hour) format, e.g., 19:30.")
            return {"time": None}

        if not _time_within_business_hours(parsed_time):
            open_str = OPENING_TIME.strftime("%H:%M")
            close_str = CLOSING_TIME.strftime("%H:%M")
            # user-friendly note about overnight hours
            if OPENING_TIME > CLOSING_TIME:
                dispatcher.utter_message(
                    text=f"Our hours are {open_str} until midnight and then until {close_str} (we close after midnight). Please pick a time within these hours."
                )
            else:
                dispatcher.utter_message(text=f"We accept bookings between {open_str} and {close_str}. Please pick a time within these hours.")
            return {"time": None}

        return {"time": parsed_time.strftime("%H:%M")}

    # ---------------- phone ----------------
    async def validate_phone(
        self,
        value: Text,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        raw = (value or "").strip()
        digits = _only_digits(raw)
        normalized = _normalize_phone(digits)
        if normalized:
            return {"phone": normalized}
        else:
            dispatcher.utter_message(text="Invalid phone number. Please enter a 10-digit phone number (e.g., 9876543210).")
            return {"phone": None}

    # ---------------- party_size ----------------
    async def validate_party_size(
        self,
        value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        raw = str(value).strip()
        if not raw.isdigit():
            dispatcher.utter_message(text="Please enter the number of people as a number (for example: 2).")
            return {"party_size": None}

        num = int(raw)
        if num < MIN_PARTY_SIZE or num > MAX_PARTY_SIZE:
            dispatcher.utter_message(text=f"We accept bookings for {MIN_PARTY_SIZE} to {MAX_PARTY_SIZE} people. Please enter a different party size.")
            return {"party_size": None}

        return {"party_size": num}
