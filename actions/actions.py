# actions/actions.py
import os
import json
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet


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
                # if someone stored a flat list, put it under 'menu'
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
            # if unexpected shape, reset
            base = {"bookings": []}
            atomic_write_json(BOOKINGS_FILE, base)
            return base
    except Exception:
        # on error, back up and create fresh
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

class action_save_booking(Action):
    def name(self) -> str:
        return "action_save_booking"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict) -> List[Dict]:
        name = tracker.get_slot("name") or tracker.get_slot("customer_name") or "Guest"
        phone = tracker.get_slot("phone") or ""
        date_slot = tracker.get_slot("date") or ""  # assumed normalized YYYY-MM-DD
        time_slot = tracker.get_slot("time") or ""  # HH:MM
        party_size = tracker.get_slot("party_size") or ""
        special = tracker.get_slot("special_request") or tracker.get_slot("note") or ""

        bookings_data = load_bookings()
        bookings_list = bookings_data.get("bookings", [])


        booking_id = "BKG-" + uuid.uuid4().hex[:8].upper()
        created_at = datetime.now().isoformat(timespec="seconds")

        booking = {
            "booking_id": booking_id,
            "name": name,
            "phone": phone,
            "date": date_slot,
            "time": time_slot,
            "party_size": party_size,
            "special_request": special,
            "created_at": created_at,
        }

        bookings_list.append(booking)
        bookings_data["bookings"] = bookings_list

        try:
            atomic_write_json(BOOKINGS_FILE, bookings_data)
        except Exception:
            dispatcher.utter_message(text="Sorry, I couldn't save your booking due to a technical issue. Please try again.")
            return []

        confirm_text = (
            f"Thank you {name}! Your table for {party_size} on {date_slot} at {time_slot} is booked.\n"
            f"Booking ID: {booking_id}"
        )
        dispatcher.utter_message(text=confirm_text)

        # set slot(s) for downstream use
        return [SlotSet("booking_confirmed", True), SlotSet("booking_id", booking_id)]



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
        # Edit or expand as needed
        hours = "Daily 07:30 AM - 01:30 AM (next day)"
        cancellation = "no cancellation availabe"
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
