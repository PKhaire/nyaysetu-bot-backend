import os
import sqlite3
import time
import logging
from flask import Flask, request, jsonify, g
import requests
from openai import OpenAI

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

# Config
WHATSAPP_TOKEN = os.environ.get("WHATSAPP_TOKEN")
PHONE_NUMBER_ID = os.environ.get("PHONE_NUMBER_ID")
VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN", "nyaysetu_verify_token")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4")
RATE_LIMIT_SECONDS = int(os.environ.get("RATE_LIMIT_SECONDS", "3"))
DB_PATH = os.environ.get("DB_PATH", "nyaysetu_messages.db")

if not (WHATSAPP_TOKEN and PHONE_NUMBER_ID and OPENAI_API_KEY):
    app.logger.warning("Set WHATSAPP_TOKEN, PHONE_NUMBER_ID, and OPENAI_API_KEY environment variables.")

# OpenAI client
client = OpenAI(api_key=OPENAI_API_KEY)

# Rate limiter
rate_limiter = {}

# ----------------- DATABASE -----------------
def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db

@app.teardown_appcontext
def close_db(exception):
    db = g.pop("db", None)
    if db is not None:
        db.close()

def init_db():
    db = sqlite3.connect(DB_PATH)
    cur = db.cursor()
    cur.execute(
        "CREATE TABLE IF NOT EXISTS chats ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "phone TEXT, direction TEXT, message TEXT, "
        "timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)"
    )
    db.commit()
    db.close()

init_db()

def save_message(phone, direction, message):
    try:
        db = get_db()
        cur = db.cursor()
        cur.execute(
            "INSERT INTO chats (phone, direction, message) VALUES (?, ?, ?)",
            (phone, direction, message)
        )
        db.commit()
    except Exception as e:
        app.logger.exception("DB save failed: %s", e)

# ----------------- ROUTES -----------------
@app.route("/", methods=["GET"])
def home():
    return jsonify({"message": "✅ NyaySetu API live!", "status": "ok", "timestamp": int(time.time())})

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "ts": int(time.time())})

@app.route("/webhook", methods=["GET"])
def verify():
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")
    if mode == "subscribe" and token == VERIFY_TOKEN:
        return challenge, 200
    return "Forbidden", 403

@app.route("/webhook", methods=["POST"])
def webhook():
    payload = request.get_json(force=True)
    app.logger.info("Payload received: %s", payload)
    try:
        entry = payload.get("entry", [])[0]
        changes = entry.get("changes", [])[0]
        value = changes.get("value", {})
        messages = value.get("messages")
        if not messages:
            return "no_message", 200

        message = messages[0]
        from_number = message.get("from")
        text = ""
        if "text" in message:
            text = message["text"].get("body", "")
        elif "button" in message:
            text = message["button"].get("text", "")

        if not text.strip():
            send_text(from_number, "Sorry, I couldn't read that. Please send text.")
            return "ok", 200

        # Rate limiting
        now = time.time()
        last = rate_limiter.get(from_number, 0)
        if now - last < RATE_LIMIT_SECONDS:
            return "rate_limited", 200
        rate_limiter[from_number] = now

        save_message(from_number, "inbound", text)

        system_prompt = (
            "You are NyaySetu, an India-aware legal information assistant. "
            "Provide concise, practical, and informational responses. "
            "Keep answers short (<=200 words), include next steps and official portals if available. "
            "Always include a short disclaimer."
        )

        ai_reply = ask_openai(system_prompt, text)
        disclaimer = "\n\nNote: This is general information and not a substitute for legal advice."
        final_reply = ai_reply.strip() + disclaimer

        save_message(from_number, "outbound", final_reply)
        send_text(from_number, final_reply)

    except Exception as e:
        app.logger.exception("Webhook handler error: %s", e)
    return "ok", 200

# ----------------- OPENAI -----------------
def ask_openai(system_prompt, user_text):
    models_to_try = [OPENAI_MODEL, "gpt-3.5-turbo"]
    for model in models_to_try:
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_text}
                ],
                max_tokens=500,
                temperature=0.2
            )
            return resp.choices[0].message.content
        except Exception as e:
            app.logger.warning(f"Model {model} failed: {e}")
            continue
    return "Sorry, no available model could process your request."

# ----------------- WHATSAPP -----------------
def send_text(to, text):
    url = f"https://graph.facebook.com/v17.0/{PHONE_NUMBER_ID}/messages"
    headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}", "Content-Type": "application/json"}
    payload = {"messaging_product": "whatsapp", "to": to, "type": "text", "text": {"body": text}}
    try:
        r = requests.post(url, json=payload, headers=headers, timeout=15)
        if r.status_code >= 400:
            app.logger.error("WhatsApp send failed: %s %s", r.status_code, r.text)
        return r
    except Exception as e:
        app.logger.exception("Error sending WhatsApp message: %s", e)
        return None

# ----------------- MAIN -----------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
