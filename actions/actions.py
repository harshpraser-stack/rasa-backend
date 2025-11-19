# actions/actions.py
import os
import json
import random
import logging
from datetime import datetime
from typing import Any, Dict, List, Text, Optional

from twilio.rest import Client
from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet

# configure logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

CURRENT_DIR = os.path.dirname(__file__)
BACKEND_DATA_DIR = os.path.abspath(os.path.join(CURRENT_DIR, "..", "backend_data"))
MENU_FILE = os.path.join(BACKEND_DATA_DIR, "menu.json")
BOOKINGS_FILE = os.path.join(BACKEND_DATA_DIR, "bookings.json")


def ensure_backend_dirs() -> None:
    if not os.path.isdir(BACKEND_DATA_DIR):
        os.makedirs(BACKEND_DATA_DIR, exist_ok=True)


def atomic_write_json(path: str, data: Any) -> None:
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(tmp, path)


def load_menu_grouped() -> Dict[str, List[Dict[str, Any]]]:
    ensure_backend_dirs()
    if not os.path.exists(MENU_FILE):
        return {}
    try:
        with open(MENU_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, dict):
                return data
            elif isinstance(data, list):
                return {"menu": data}
    except Exception:
        return {}
    return {}


def load_menu_flat() -> List[Dict[str, Any]]:
    grouped = load_menu_grouped()
    flat: List[Dict[str, Any]] = []
    for cat, items in grouped.items():
        for it in items:
            it_copy = dict(it)
            it_copy.setdefault("category", cat)
            flat.append(it_copy)
    return flat


def find_menu_item_by_name(name: str) -> Optional[Dict[str, Any]]:
    if not name:
        return None
    name_l = name.strip().lower()
    items = load_menu_flat()
    for it in items:
        if it.get("name", "").strip().lower() == name_l:
            return it
    for it in items:
        if name_l in it.get("name", "").strip().lower():
            return it
    return None


def load_bookings() -> Dict[str, Any]:
    ensure_backend_dirs()
    if not os.path.exists(BOOKINGS_FILE):
        base = {"bookings": []}
        atomic_write_json(BOOKINGS_FILE, base)
        return base
    try:
        with open(BOOKINGS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, dict) and "bookings" in data:
                return data
            base = {"bookings": []}
            atomic_write_json(BOOKINGS_FILE, base)
            return base
    except Exception:
        try:
            os.rename(BOOKINGS_FILE, BOOKINGS_FILE + ".bak")
        except Exception:
            pass
        base = {"bookings": []}
        atomic_write_json(BOOKINGS_FILE, base)
        return base


class action_show_menu(Action):
    def name(self) -> str:
        return "action_show_menu"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict) -> List[Dict]:
        grouped = load_menu_grouped()
        if not grouped:
            dispatcher.utter_message(text="Sorry, the menu is not available right now.")
            return []

        lines: List[str] = []
        for cat_key, items in grouped.items():
            cat_title = cat_key.replace("_", " ").title()
            lines.append(f"{cat_title}:")
            for it in items:
                name = it.get("name", "Unnamed")
                price = it.get("price")
                desc = it.get("description")
                if price is not None:
                    line = f" - {name} — ₹{price}"
                else:
                    line = f" - {name}"
                if desc:
                    line += f" ({desc})"
                lines.append(line)
            lines.append("")

        text_message = "\n".join(lines).strip()
        dispatcher.utter_message(text=text_message)
        cards = []
        MAX_CARDS = 40
        added = 0
        for cat_key, items in grouped.items():
            for it in items:
                if added >= MAX_CARDS:
                    break
                title = it.get("name", "")
                price = it.get("price")
                subtitle = it.get("description", "")
                card = {
                    "title": title,
                    "subtitle": subtitle,
                    "text": f"₹{price}" if price is not None else "",
                    "category": cat_key,
                    "buttons": [
                        {"title": "Details", "payload": f"/ask_details{{\"dish_name\":\"{title}\"}}"},
                        {"title": f"Order — ₹{price}" if price is not None else "Order", "payload": f"/order_item{{\"dish_name\":\"{title}\"}}"}
                    ]
                }
                cards.append(card)
                added += 1
            if added >= MAX_CARDS:
                break

        if cards:
            dispatcher.utter_message(json_message={"type": "cards", "cards": cards})

        dispatcher.utter_message(text="You can ask for details or ask the price of any dish, e.g., 'price of Roti Thali'.")
        return []


def _normalize_phone_to_e164(phone_raw: str) -> str:
    """
    Convert a user-provided phone string into an E.164-like string.
    Heuristics:
      - if phone starts with '+', keep plus and digits
      - otherwise extract digits; if length == 10 -> assume India and prefix +91
      - if digits start with '91' and length >= 11 -> prefix '+'
      - otherwise prefix '+' (best-effort)
    """
    if not phone_raw:
        return ""
    s = str(phone_raw).strip()
    if s.startswith("+"):
        # allow +91..., or other international numbers
        return "+" + "".join(ch for ch in s if ch.isdigit())
    digits = "".join(ch for ch in s if ch.isdigit())
    # strip leading zeros
    while digits.startswith("0"):
        digits = digits[1:]
    if len(digits) == 10:
        return "+91" + digits
    if digits.startswith("91") and len(digits) >= 11:
        return "+" + digits
    # fallback
    return "+" + digits


class ActionSaveBooking(Action):
    def name(self) -> Text:
        return "action_save_booking"

    async def run(self,
                  dispatcher: CollectingDispatcher,
                  tracker: Tracker,
                  domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:

        ensure_backend_dirs()

        # read slots (they may be None if not provided)
        name = tracker.get_slot("name") or ""
        phone = tracker.get_slot("phone") or ""
        date = tracker.get_slot("date") or ""
        time = tracker.get_slot("time") or ""
        party_size = tracker.get_slot("party_size") or ""
        special_request = tracker.get_slot("special_request") or ""

        # generate booking id
        booking_id = f"BKG{random.randint(1000, 9999)}"

        booking_record = {
            "booking_id": booking_id,
            "name": name,
            "phone": phone,
            "date": date,
            "time": time,
            "party_size": party_size,
            "special_request": special_request
        }

        # Load existing bookings safely (expecting dict with "bookings": [])
        try:
            with open(BOOKINGS_FILE, "r", encoding="utf-8") as f:
                bookings_data = json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            bookings_data = {"bookings": []}

        if isinstance(bookings_data, dict) and "bookings" in bookings_data and isinstance(bookings_data["bookings"], list):
            bookings = bookings_data["bookings"]
        else:
            bookings = []

        bookings.append(booking_record)
        atomic_write_json(BOOKINGS_FILE, {"bookings": bookings})

        # Inform the chat
        dispatcher.utter_message(text=f"Saved booking {booking_id} for {name}.")

        # --- send SMS via Twilio ---
        # Twilio credentials must be set in environment variables:
        # TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_FROM_NUMBER
        account_sid = os.environ.get("TWILIO_ACCOUNT_SID")
        auth_token = os.environ.get("TWILIO_AUTH_TOKEN")
        from_number = os.environ.get("TWILIO_FROM_NUMBER")  # e.g. "+1XXXXXXXXXX" or "+91XXXXXXXXXX"

        sms_body = (
            f"Hi {name}, your table is booked!\n"
            f"Booking ID: {booking_id}\n"
            f"Date: {date}\n"
            f"Time: {time}\n"
            f"Party size: {party_size}\n"
            f"- Thank you"
        )

        if account_sid and auth_token and from_number:
            to_number = _normalize_phone_to_e164(phone)
            try:
                client = Client(account_sid, auth_token)
                message = client.messages.create(
                    body=sms_body,
                    from_=from_number,
                    to=to_number,
                )
                logger.info(f"Twilio SMS sent: sid={getattr(message, 'sid', None)} to={to_number}")
            except Exception as e:
                logger.exception("Failed to send SMS via Twilio:")
                # don't fail the action if SMS fails; inform user in chat optionally
                dispatcher.utter_message(text="(Warning) Confirmation SMS could not be sent.")
        else:
            logger.info("Twilio credentials or from number not set - skipping SMS send.")

        # Return slot updates so utter_confirm_booking can access them
        return [
            SlotSet("booking_confirmed", True),
            SlotSet("booking_id", booking_id),
            SlotSet("name", name),
            SlotSet("phone", phone),
            SlotSet("date", date),
            SlotSet("time", time),
            SlotSet("party_size", party_size),
            SlotSet("special_request", special_request)
        ]


class action_location(Action):
    def name(self) -> str:
        return "action_location"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict) -> List[Dict]:
        address = "C BLOCK , AECS Layout Brookfield,Bengaluru,Karnataka-560037"
        google_maps_link = "https://maps.app.goo.gl/kx6BaHaazrM1aBA6A?g_st=aw"
        phone = "+91-0000000000"

        msg = (
            f"Our address:\n{address}\n\n"
            f"Open in Google Maps: {google_maps_link}\n\n"
            f"For directions or phone support call: {phone}"
        )
        dispatcher.utter_message(text=msg)
        return []


class action_additional_info(Action):
    def name(self) -> str:
        return "action_additional_info"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict) -> List[Dict]:
        hours = "Daily 07:30 AM - 01:30 AM (next day)"
        cancellation = "no cancellation available"
        payment = "We accept cash and digital payments (UPI, cards)."
        parking = "Limited parking available near the restaurant."

        msg = (
            f"Working hours: {hours}\n\n"
            f"Cancellation policy: {cancellation}\n\n"
            f"Payment: {payment}\n\n"
            f"Parking: {parking}\n\n"
            "If you want any other details (menu, offers, large group policy), ask me."
        )
        dispatcher.utter_message(text=msg)
        return []
