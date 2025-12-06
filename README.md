🍽️ Restaurant Chatbot using Rasa

A conversational AI assistant built using the Rasa framework to automate restaurant-related interactions such as menu browsing, table booking, recommendations, and general customer queries. The bot also includes robust data validation to ensure users provide correct and meaningful information during the booking process.


---

⭐ Key Features

🍽️ Restaurant Capabilities

View food menu and categories
Get dish recommendations
Check table availability
Book a table with required details
Retrieve restaurant timings & FAQs


🧠 AI / NLP Features

Intent classification
Entity extraction (dish, date, time, number of people, phone number)
Multi-turn dialogue handling
Slot filling and dynamic conversation flow

🔍 Data Validation Features (Important)

The chatbot validates user-provided data before confirming a booking:
Past Date Validation
If the user enters a date earlier than the current date, the bot asks them to enter a valid future date.

Example:
User: “Book a table for yesterday.”
Bot: “Please enter a future date for booking.”


Incorrect Phone Number Validation
Ensures the phone number contains exactly 10 digits.
Rejects alphabetic characters or numbers with less/more digits.

Example:
User: “My number is 12345.”
Bot: “That doesn’t look like a valid phone number. Please enter a 10-digit number.”


Time Format Validation
Checks whether the user has entered a valid time format (e.g., 7 PM, 19:00).
Prevents invalid entries like “25 PM” or “77:00”.

People Count Validation
Ensures number of guests is a positive whole number and within restaurant limits.

These validations are handled using slots, custom actions, and Python validation methods in Rasa.

---

🧱 Architecture Overview

User → Rasa NLU (Intent & Entity Extraction) 
     → Rasa Core (Stories, Rules, Policies)
     → Custom Actions (Menu, Booking, Validations)
     → Bot Response

NLU: Understands what the user wants
Core: Decides the next action
Action Server: Runs Python logic for menu, booking, and validations
Response Layer: Sends a natural reply

---

📂 Project Structure

restaurant-chatbot/
│
├── actions/
│   └── actions.py         # Menu logic, booking, data validation
│
├── data/
│   ├── nlu.yml            # Intents & training phrases
│   ├── stories.yml        # Dialogue stories
│   ├── rules.yml          # Rule-based behaviors
│
├── domain.yml             # Slots, responses, intents, entities
├── config.yml             # NLP pipeline and dialogue policies
├── credentials.yml
├── endpoints.yml
└── README.md


---

▶️ How to Run the Project (Local Setup)

1. Clone the Repository

git clone https://github.com/your-username/restaurant-chatbot.git
cd restaurant-chatbot

2. Create a Virtual Environment

python -m venv venv
source venv/bin/activate     # macOS/Linux
venv\Scripts\activate        # Windows

3. Install Rasa

pip install rasa

4. Train the Model

rasa train

5. Start Action Server

rasa run actions

6. Run the Chatbot

rasa shell


---

💬 Example Conversations

User: Book a table for yesterday.
Bot: That date has already passed. Please enter a future date.

User: My phone number is 123.
Bot: That doesn’t look like a valid number. Please provide a 10-digit phone number.

User: Show me the menu.
Bot: Here are today’s menu categories…


---

📌 Use Cases

Restaurant automation
Reservation/chat-based assistance
Menu browsing & recommendations
Hospitality customer service

---

🔮 Future Enhancements

WhatsApp / Telegram Integration
Cloud deployment
Live menu API
Integration with a real reservation database



---

🤝 Contributing

Pull requests and suggestions are welcome.


---

⭐ Support

If you find this project helpful, consider giving it a ⭐ on GitHub!


---

If you want, I can now:
✨ Insert badges at the top
🎨 Create a visual banner PNG
📊 Create a clean architecture diagram image

Just tell me “add badges”, “generate banner image”, or “generate diagram image.”

