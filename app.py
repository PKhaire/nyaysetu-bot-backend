import os
import time
import logging
from flask import Flask, request, jsonify
from openai import OpenAI, RateLimitError, BadRequestError, APIError
import httpx

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

# OpenAI client
openai_api_key = os.environ.get("OPENAI_API_KEY")
client = OpenAI(api_key=openai_api_key)

# Default and fallback models
PRIMARY_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
FALLBACK_MODELS = ["gpt-4o", "gpt-3.5-turbo"]

# WhatsApp tokens and phone number ID
WHATSAPP_TOKEN = os.environ.get("WHATSAPP_TOKEN")
PHONE_NUMBER_ID = os.environ.get("WHATSAPP_PHONE_NUMBER_ID")

# WhatsApp verification token
VERIFY_TOKEN = os.environ.get("WHATSAPP_VERIFY_TOKEN", "your_verify_token")


def send_whatsapp_message(to, text):
    """Send a WhatsApp message via the Graph API"""
    url = f"https://graph.facebook.com/v19.0/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "text": {"body": text}
    }
    response = httpx.post(url, headers=headers, json=payload)
    if response.status_code != 200:
        app.logger.error(f"Failed to send message: {response.status_code} {response.text}")
    else:
        app.logger.info(f"Message sent to {to}")


@app.route("/webhook", methods=["GET", "POST"])
def webhook():
    if request.method == "GET":
        # Verification handshake
        mode = request.args.get("hub.mode")
        token = request.args.get("hub.verify_token")
        challenge = request.args.get("hub.challenge")
        if mode == "subscribe" and token == VERIFY_TOKEN:
            return challenge, 200
        return "Verification token mismatch", 403

    if request.method == "POST":
        payload = request.get_json()
        app.logger.info(f"Payload r
