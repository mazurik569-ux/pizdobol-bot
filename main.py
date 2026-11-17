
import os
import logging
from collections import defaultdict, deque

import requests
from flask import Flask, request
from groq import Groq

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s"
)

BOT_TOKEN = os.environ["BOT_TOKEN"]
GROQ_API_KEY = os.environ["GROQ_API_KEY"]

MODEL = "openai/gpt-oss-20b"

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

    response = requests.post(
        url,
        json=data,
        timeout=30
    )

    response.raise_for_status()

    result = response.json()

    if not result.get("ok"):
        raise RuntimeError(f"Telegram API error: {result}")

    logging.info("Telegram %s successful", method)

    return result


def answer(chat_id, message_id, name, message):

    history = histories[chat_id]

    history.append({
        "role": "user",
        "content": f"{name}: {message}"
    })

    logging.info("Sending request to Groq: %s", MODEL)

    result = ai.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": SYSTEM},
            *history
        ],
        temperature=1.0,
        max_tokens=180
    )

    reply = result.choices[0].message.content

    if not reply or not reply.strip():
        logging.error("Groq returned empty response")
        return

    reply = reply.strip()

    logging.info("Groq response received: %s", reply[:100])

    telegram("sendMessage", {
        "chat_id": chat_id,
        "text": reply,
        "reply_to_message_id": message_id
    })

    history.append({
        "role": "assistant",
        "content": reply
    })


@app.route("/webhook", methods=["POST"])
def webhook():

    update = request.get_json(silent=True) or {}

    message = update.get("message")

    if not message:
        return "ok", 200

    if not message.get("text"):
        return "ok", 200

    chat = message.get("chat", {})

    if chat.get("type") not in ("group", "supergroup"):
        return "ok", 200

    user = message.get("from", {})

    if user.get("is_bot"):
        return "ok", 200

    text = message["text"].strip()

    if not text or text.startswith("/"):
        return "ok", 200

    chat_id = chat["id"]
    message_id = message["message_id"]

    name = user.get("first_name", "Собеседник")

    logging.info(
        "New message from %s in chat %s: %s",
        name,
        chat_id,
        text[:100]
    )

    try:
        answer(
            chat_id,
            message_id,
            name,
            text
        )

    except Exception:
        logging.exception("BOT RESPONSE FAILED")

    return "ok", 200


@app.route("/", methods=["GET"])
def home():
    return "PIZDOBOL IS ALIVE", 200


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 10000))
    )
