import os
import time
import logging
import requests
from flask import Flask, request, jsonify
from openai import OpenAI, RateLimitError, BadRequestError, APIError

# Flask app setup
app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

# OpenAI client
openai_api_key = os.environ.get("OPENAI_API_KEY")
client = OpenAI(api_key=openai_api_key)

# Default and fallback models
PRIMARY_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
FALLBACK_MODELS = ["gpt-4o", "gpt-3.5-turbo"]

# WhatsApp verification token & phone number ID
VERIFY_TOKEN = os.environ.get("WHATSAPP_VERIFY_TOKEN", "your_verify_token")
WHATSAPP_PHONE_ID = os.environ.get("WHATSAPP_PHONE_ID", "")
WHATSAPP_ACCESS_TOKEN = os.environ.get("WHATSAPP_ACCESS_TOKEN", "")


@app.route("/webhook", methods=["GET", "POST"])
def webhook():
    # --------------------- VERIFICATION (GET) ------------------------
    if request.method == "GET":
        mode = request.args.get("hub.mode")
        token = request.args.get("hub.verify_token")
        challenge = request.args.get("hub.challenge")

        if mode == "subscribe" and token == VERIFY_TOKEN:
            return challenge, 200

        return "Verification token mismatch", 403

    # ----------------------- PROCESS MESSAGE (POST) ------------------
    if request.method == "POST":
        payload = request.get_json() or {}
        app.logger.info(f"Payload received: {payload}")

        try:
            # Safe extraction
            entry = payload.get("entry", [])
            if not entry:
                return jsonify({"status": "empty entry"}), 200

            changes = entry[0].get("changes", [])
            if not changes:
                return jsonify({"status": "empty changes"}), 200

            value = changes[0].get("value", {})
            messages = value.get("messages", [])
            if not messages:
                return jsonify({"status": "no messages"}), 200

            msg = messages[0]
            sender_id = msg.get("from", "")
            user_text = msg.get("text", {}).get("body", "")

            if not sender_id or not user_text:
                return jsonify({"status": "invalid message"}), 200

            app.logger.info(f"Received message from {sender_id}: {user_text}")

            reply_text = generate_reply("You are a helpful assistant.", user_text)

            send_whatsapp_message(sender_id, reply_text)

        except Exception as e:
            app.logger.error(f"Error processing webhook: {e}")
            return jsonify({"status": "error"}), 500

        return jsonify({"status": "success"}), 200


def generate_reply(system_prompt, user_text):
    models_to_try = [PRIMARY_MODEL] + FALLBACK_MODELS
    max_retries = 5

    for model in models_to_try:
        for attempt in range(max_retries):
            try:
                response = client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_text}
                    ],
                    max_tokens=500,
                    temperature=0.2
                )
                return response.choices[0].message.content

            except RateLimitError:
                wait_time = (2 ** attempt) + 0.1 * attempt
                time.sleep(wait_time)

            except BadRequestError as e:
                if "model_not_found" in str(e):
                    break
                else:
                    break

            except APIError:
                wait_time = (2 ** attempt) + 0.1 * attempt
                time.sleep(wait_time)

            except Exception:
                break

    return "Sorry, I'm temporarily unable to process that."


def send_whatsapp_message(to, text):
    url = f"https://graph.facebook.com/v19.0/{WHATSAPP_PHONE_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }
    data = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": text}
    }

    try:
        response = requests.post(url, headers=headers, json=data)
        response.raise_for_status()
        app.logger.info(f"Sent message to {to}")
    except requests.exceptions.RequestException as e:
        app.logger.error(f"Failed to send message to {to}: {e}")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
