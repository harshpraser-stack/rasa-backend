# actions/actions.py
import os
import json
import random
import logging
from datetime import datetime
from typing import Any, Dict, List, Text, Optional

# Twilio is optional: we import at runtime so actions still run when twilio is absent
try:
    from twilio.rest import Client as TwilioClient
except Exception:
    TwilioClient = None

from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet

# configure logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
if not logger.handlers:
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s - %(message)s")
    ch.setFormatter(formatter)
    logger.addHandler(ch)

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
            if isinstance(data, list):
                return {"menu": data}
    except Exception:
        logger.exception("Failed to load menu.json")
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
    """Return dict with key 'bookings' -> list."""
    ensure_backend_dirs()
    if not os.path.exists(BOOKINGS_FILE):
        base = {"bookings": []}
        atomic_write_json(BOOKINGS_FILE, base)
        return base
    try:
        with open(BOOKINGS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, dict) and "bookings" in data and isinstance(data["bookings"], list):
                return data
            if isinstance(data, list):
                # convert legacy list -> new dict shape
                return {"bookings": data}
            # unexpected shape: reset safely
            base = {"bookings": []}
            atomic_write_json(BOOKINGS_FILE, base)
            return base
    except Exception:
        logger.exception("Failed to read bookings file; creating fresh file.")
        try:
            os.rename(BOOKINGS_FILE, BOOKINGS_FILE + ".bak")
        except Exception:
            pass
        base = {"bookings": []}
        atomic_write_json(BOOKINGS_FILE, base)
        return base


def save_bookings(bookings_list: List[Dict[str, Any]]) -> None:
    atomic_write_json(BOOKINGS_FILE, {"bookings": bookings_list})


def _normalize_digits(text: Text) -> Text:
    return "".join(ch for ch in (text or "") if ch.isdigit())


def _format_phone_for_send(digits: str) -> str:
    """Return E.164-ish phone for Twilio send if possible.
    - if digits length == 10: assume India (+91)
    - if digits starts with country code (e.g. 91...) add '+'
    - otherwise add '+' if missing
    """
    if not digits:
        return ""
    if digits.startswith("+"):
        return "+" + "".join(ch for ch in digits if ch.isdigit())
    if len(digits) == 10:
        return f"+91{digits}"
    if 10 < len(digits) <= 15:
        return f"+{digits}"
    return digits


class ActionShowMenu(Action):
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

        # optional UI cards
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
                        {"title": "Details", "payload": f'/ask_details{{"dish_name":"{title}"}}'},
                        {"title": f"Order — ₹{price}" if price is not None else "Order", "payload": f'/order_item{{"dish_name":"{title}"}}'}
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


class ActionSaveBooking(Action):
    def name(self) -> Text:
        return "action_save_booking"

    async def run(self,
                  dispatcher: CollectingDispatcher,
                  tracker: Tracker,
                  domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:

        ensure_backend_dirs()

        # read slots (they may be None)
        name = tracker.get_slot("name") or ""
        raw_phone = tracker.get_slot("phone") or ""
        date = tracker.get_slot("date") or ""
        time = tracker.get_slot("time") or ""
        party_size = tracker.get_slot("party_size") or ""
        special_request = tracker.get_slot("special_request") or ""

        # normalize for storage and for send
        phone_digits = _normalize_digits(str(raw_phone))

        # generate booking id
        booking_id = f"BKG{random.randint(1000, 9999)}"

        booking_record = {
            "booking_id": booking_id,
            "name": name,
            "phone": phone_digits,
            "date": date,
            "time": time,
            "party_size": party_size,
            "special_request": special_request,
            "created_at": datetime.utcnow().isoformat() + "Z"
        }

        data = load_bookings()
        bookings = data.get("bookings", [])
        bookings.append(booking_record)
        save_bookings(bookings)

        dispatcher.utter_message(text=f"Saved booking {booking_id} for {name}.")

        # --- send SMS via Twilio (optional) ---
        twilio_sid = os.getenv("TWILIO_ACCOUNT_SID")
        twilio_token = os.getenv("TWILIO_AUTH_TOKEN")
        twilio_from = os.getenv("TWILIO_FROM_NUMBER")  # must be E.164 (e.g. +1415...)

        sms_sent = False
        sms_error = None
        if TwilioClient and twilio_sid and twilio_token and twilio_from and phone_digits:
            try:
                client = TwilioClient(twilio_sid, twilio_token)
                to_number = _format_phone_for_send(phone_digits)
                message_body = (
                    f"Booking confirmed: {booking_id}\n"
                    f"Name: {name}\n"
                    f"Date: {date} Time: {time}\n"
                    f"Party: {party_size}\n"
                    f"Requests: {special_request or 'None'}"
                )
                msg = client.messages.create(body=message_body, from_=twilio_from, to=to_number)
                logger.info("Twilio message sent sid=%s to=%s", getattr(msg, "sid", None), to_number)
                sms_sent = True
            except Exception as e:
                logger.exception("Failed to send SMS via Twilio")
                sms_error = str(e)
        else:
            logger.info("Twilio not configured or Twilio package not installed; skipping SMS.")

        if sms_sent:
            dispatcher.utter_message(text=f"A confirmation SMS was sent to {phone_digits}.")
        elif sms_error:
            dispatcher.utter_message(text=f"Booking saved, but failed to send SMS: {sms_error}")
        else:
            dispatcher.utter_message(text="Booking saved. (SMS not sent — Twilio not configured.)")

        # Return slot updates so utter_confirm_booking can use them
        return [
            SlotSet("booking_confirmed", True),
            SlotSet("booking_id", booking_id),
            SlotSet("name", name),
            SlotSet("phone", phone_digits),
            SlotSet("date", date),
            SlotSet("time", time),
            SlotSet("party_size", party_size),
            SlotSet("special_request", special_request),
        ]


class ActionLocation(Action):
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


class ActionAdditionalInfo(Action):
    def name(self) -> str:
        return "action_additional_info"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict) -> List[Dict]:
        hours = "Daily 07:30 AM - 01:30 AM (next day)"
        cancellation = "No cancellation available."
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
