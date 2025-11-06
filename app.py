import os
import logging
import requests
from flask import Flask, request, jsonify

# Initialize Flask app
app = Flask(__name__)

# Setup logging to see info and errors in your console/logs
logging.basicConfig(level=logging.INFO)

# Environment variables for configuration (make sure these are set exactly in your environment)
VERIFY_TOKEN = os.environ.get("WHATSAPP_VERIFY_TOKEN", "your_verify_token")  # webhook verification token
WHATSAPP_PHONE_ID = os.environ.get("WHATSAPP_PHONE_ID", "")                 # WhatsApp Business phone number ID
WHATSAPP_ACCESS_TOKEN = os.environ.get("WHATSAPP_ACCESS_TOKEN", "")         # WhatsApp Cloud API access token


@app.route("/webhook", methods=["GET", "POST"])
def webhook():
    if request.method == "GET":
        # Facebook webhook verification step
        mode = request.args.get("hub.mode")
        token = request.args.get("hub.verify_token")
        challenge = request.args.get("hub.challenge")

        if mode == "subscribe" and token == VERIFY_TOKEN:
            app.logger.info("Webhook verified successfully")
            return challenge, 200
        else:
            app.logger.warning("Webhook verification failed: token mismatch")
            return "Verification token mismatch", 403

    if request.method == "POST":
        # Handle incoming WhatsApp messages here
        data = request.get_json()
        app.logger.info(f"Received webhook data: {data}")

        try:
            # Extract the message details from the payload
            changes = data.get("entry", [])[0].get("changes", [])
            if not changes:
                app.logger.info("No changes found in webhook payload")
                return jsonify({"status": "no changes"}), 200

            messages = changes[0]["value"].get("messages", [])
            if not messages:
                app.logger.info("No messages found in webhook payload")
                return jsonify({"status": "no messages"}), 200

            message = messages[0]
            sender_id = message.get("from")
            user_text = message.get("text", {}).get("body", "")

            app.logger.info(f"Message from {sender_id}: {user_text}")

            # Send a simple reply back
            send_whatsapp_message(sender_id, "Hi! Your message was received.")

        except Exception as e:
            app.logger.error(f"Error in webhook POST: {e}")
            return jsonify({"status": "error"}), 500

        return jsonify({"status": "success"}), 200


def send_whatsapp_message(to, text):
    url = f"https://graph.facebook.com/v16.0/{WHATSAPP_PHONE_ID}/messages"
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
        resp = requests.post(url, headers=headers, json=data)
        app.logger.info(f"WhatsApp API response status: {resp.status_code}, body: {resp.text}")
        resp.raise_for_status()
        app.logger.info(f"Sent message to {to}: {text}")
    except requests.exceptions.RequestException as e:
        app.logger.error(f"Failed to send message: {e}")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
