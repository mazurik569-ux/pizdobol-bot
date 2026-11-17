
import os
import random
import logging
from collections import defaultdict, deque

import requests
from flask import Flask, request
from groq import Groq

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.environ["BOT_TOKEN"]
GROQ_API_KEY = os.environ["GROQ_API_KEY"]
MODEL = "llama-3.3-70b-versatile"

app = Flask(__name__)
ai = Groq(api_key=GROQ_API_KEY)

histories = defaultdict(lambda: deque(maxlen=16))

SYSTEM = """
Ты ПИЗДОБОЛ — наглый, остроумный и безумный участник
группового Telegram-чата.

Твой характер:
- Едкий сарказм, чёрный юмор, ирония.
- Разговорный русский язык, иногда мат.
- Любишь спорить, подкалывать и шутить.
- Не говоришь как робот и не повторяешься.
- Учитываешь контекст разговора и участников.
- Не оскорбляешь людей по признакам личности.
- Не преследуешь человека, если он просит остановиться.

Отвечай коротко, живо и естественно.
Ты участник компании, а не служба поддержки.
"""

def telegram(method, data):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/{method}"
    return requests.post(url, json=data, timeout=30).json()

def answer(chat_id, user_id, name, message):
    history = histories[chat_id]
    history.append({"role": "user", "content": f"{name}: {message}"})

    result = ai.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": SYSTEM},
            *history
        ],
        temperature=1.0,
        max_tokens=180
    )

    reply = result.choices[0].message.content.strip()
    history.append({"role": "assistant", "content": reply})

    telegram("sendMessage", {
        "chat_id": chat_id,
        "text": reply,
        "reply_to_message_id": user_id
    })

@app.route("/webhook", methods=["POST"])
def webhook():
    update = request.json or {}
    message = update.get("message")

    if not message or "text" not in message:
        return "ok"

    chat = message["chat"]
    if chat.get("type") not in ("group", "supergroup"):
        return "ok"

    if message.get("from", {}).get("is_bot"):
        return "ok"

    text = message["text"].strip()
    if text.startswith("/"):
        return "ok"

    chat_id = chat["id"]
    user = message.get("from", {})
    name = user.get("first_name", "Собеседник")

    # Не отвечаем на каждое сообщение подряд
    if True:
        try:
            answer(chat_id, message["message_id"], name, text)
        except Exception:
            logging.exception("AI response failed")

    return "ok"

@app.route("/", methods=["GET"])
def home():
    return "PIZDOBOL IS ALIVE"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
