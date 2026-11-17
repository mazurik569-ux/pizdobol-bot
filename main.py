
import os
import logging
from collections import defaultdict, deque

import requests
from flask import Flask, request
from groq import Groq

# =========================
# НАСТРОЙКИ
# =========================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s"
)

BOT_TOKEN = os.getenv("BOT_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

MODEL = "openai/gpt-oss-20b"

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is missing")

if not GROQ_API_KEY:
    raise RuntimeError("GROQ_API_KEY is missing")

app = Flask(__name__)

ai = Groq(
    api_key=GROQ_API_KEY,
    timeout=45,
    max_retries=2
)

telegram_session = requests.Session()

# История отдельно для каждой группы
histories = defaultdict(lambda: deque(maxlen=20))


# =========================
# ХАРАКТЕР БОТА
# =========================

SYSTEM = """

Ты ПИЗДОБОЛ — отбитый, наглый и матерящийся

участник группового чата.

ТВОЙ ХАРАКТЕР:

- Материшься постоянно и естественно.

- Используешь русский мат: блядь, пиздец,

  охуеть, заебись, хуйня, ебать, нахуй,

  долбоёб, мудак и другие выражения.

- Не стесняешься крепких выражений.

- Сарказм, язвительность и чёрный юмор.

- Любишь докапываться до нелепых сообщений.

- Споришь, подкалываешь, провоцируешь дискуссии.

- Можешь послать собеседника шутливо, если контекст

  дружеский.

- Не превращаешь каждый ответ в одинаковую ругань.

- Не повторяешь одну и ту же шутку.

- Умеешь быть смешным, а не просто грубым.

СТИЛЬ ОБЩЕНИЯ:

- Разговорный русский язык.

- Короткие, живые сообщения.

- Мат должен быть частью речи, а не отдельным украшением.

- Никакого официоза и канцелярщины.

- Не начинай каждый ответ со слова «Блядь».

- Иногда отвечай одной меткой фразой.

- Иногда разворачивай полноценную словесную перепалку.

ПОВЕДЕНИЕ:

- Самостоятельно поддерживай разговор.

- Замечай интересные и нелепые сообщения.

- Подкалывай участников по ситуации.

- Не преследуй человека, который попросил прекратить.

- Не используй угрозы и не переходи на травлю.

Ты не служба поддержки.

Ты тот самый охуевший тип из компании,

которому почему-то все продолжают писать.

"""


# =========================
# TELEGRAM API
# =========================

def telegram(method, data):
    url = (
        f"https://api.telegram.org/"
        f"bot{BOT_TOKEN}/{method}"
    )

    response = telegram_session.post(
        url,
        json=data,
        timeout=20
    )

    response.raise_for_status()

    result = response.json()

    if not result.get("ok"):
        logging.error("Telegram API error: %s", result)
        return None

    return result


# =========================
# ОТПРАВКА СООБЩЕНИЯ
# =========================

def send_reply(chat_id, message_id, text):

    return telegram("sendMessage", {
        "chat_id": chat_id,
        "text": text,
        "reply_to_message_id": message_id
    })


# =========================
# ИСКУССТВЕННЫЙ ИНТЕЛЛЕКТ
# =========================

def answer(chat_id, message_id, name, text):

    history = histories[chat_id]

    history.append({
        "role": "user",
        "content": f"{name}: {text}"
    })

    logging.info(
        "Sending request to Groq: %s",
        MODEL
    )

    result = ai.chat.completions.create(
        model=MODEL,
        messages=[
            {
                "role": "system",
                "content": SYSTEM
            },
            *list(history)
        ],
        max_completion_tokens=2048,
        reasoning_effort="low"
    )

    if not result.choices:
        logging.error("Groq returned no choices")
        return

    choice = result.choices[0]

    logging.info(
        "Finish reason: %s",
        choice.finish_reason
    )

    reply = choice.message.content

    if not reply or not reply.strip():

        logging.error(
            "Groq returned empty response. "
            "Finish reason: %s",
            choice.finish_reason
        )

        return

    reply = reply.strip()

    history.append({
        "role": "assistant",
        "content": reply
    })

    send_reply(
        chat_id,
        message_id,
        reply
    )

    logging.info(
        "Reply successfully generated for chat %s",
        chat_id
    )


# =========================
# TELEGRAM WEBHOOK
# =========================

@app.route("/webhook", methods=["POST"])
def webhook():

    update = request.get_json(silent=True) or {}

    message = update.get("message")

    if not message:
        return "ok", 200

    # Только текстовые сообщения
    text = message.get("text")

    if not text:
        return "ok", 200

    chat = message.get("chat", {})

    # Только группы
    if chat.get("type") not in (
        "group",
        "supergroup"
    ):
        return "ok", 200

    user = message.get("from", {})

    # Игнорируем сообщения других ботов
    if user.get("is_bot"):
        return "ok", 200

    text = text.strip()

    if not text:
        return "ok", 200

    # Игнорируем команды
    if text.startswith("/"):
        return "ok", 200

    chat_id = chat["id"]
    message_id = message["message_id"]

    name = user.get(
        "first_name",
        "Собеседник"
    )

    logging.info(
        "New message from %s in chat %s: %s",
        name,
        chat_id,
        text[:200]
    )

    try:
        answer(
            chat_id,
            message_id,
            name,
            text
        )

    except Exception:
        logging.exception(
            "Failed to process Telegram message"
        )

    return "ok", 200


# =========================
# ПРОВЕРКА РАБОТЫ RENDER
# =========================

@app.route("/", methods=["GET"])
def home():
    return "PIZDOBOL IS ALIVE!"


@app.route("/health", methods=["GET"])
def health():
    return {
        "status": "alive",
        "bot": "PIZDOBOL",
        "model": MODEL
    }, 200


# =========================
# ЗАПУСК
# =========================

if __name__ == "__main__":

    port = int(
        os.environ.get("PORT", 10000)
    )

    app.run(
        host="0.0.0.0",
        port=port
    )
