import os
import time
import logging
from flask import Flask, request, jsonify
import openai
from openai import OpenAI
from requests.exceptions import HTTPError

app = Flask(__name__)

# Logging setup
logging.basicConfig(level=logging.INFO)

# OpenAI API Key & model
openai.api_key = os.environ.get("OPENAI_API_KEY")
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-3.5-turbo")

client = OpenAI(api_key=openai.api_key)

# WhatsApp webhook verification
VERIFY_TOKEN = os.environ.get("WHATSAPP_VERIFY_TOKEN", "your_verify_token")


@app.route("/webhook", methods=["GET", "POST"])
def webhook():
    if request.method == "GET":
        # Verification handshake with WhatsApp
        mode = request.args.get("hub.mode")
        token = request.args.get("hub.verify_token")
        challenge = request.args.get("hub.challenge")
        if mode == "subscribe" and token == VERIFY_TOKEN:
            return challenge, 200
        return "Verification token mismatch", 403

    if request.method == "POST":
        payload = request.get_json()
        app.logger.info(f"Payload received: {payload}")

        try:
            entry = payload.get("entry", [])[0]
            changes = entry.get("changes", [])[0]
            value = changes.get("value", {})
            messages = value.get("messages", [])
            if not messages:
                return jsonify({"status": "no messages"}), 200

            msg = messages[0]
            user_text = msg.get("text", {}).get("body", "")
            sender_id = msg.get("from")

            # Generate reply using OpenAI
            reply_text = generate_reply("You are a helpful assistant.", user_text)

            # TODO: Send reply back via WhatsApp API
            app.logger.info(f"Reply to {sender_id}: {reply_text}")

        except Exception as e:
            app.logger.error(f"Error processing webhook: {e}")

        return jsonify({"status": "success"}), 200


def generate_reply(system_prompt, user_text):
    """
    Generate a reply from OpenAI with model fallback and rate-limit retry.
    """
    models_to_try = [OPENAI_MODEL, "gpt-3.5-turbo"]
    max_retries = 5
    for model in models_to_try:
        for attempt in range(max_retries):
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

            except openai.error.RateLimitError as e:
                # Exponential backoff
                wait_time = (2 ** attempt) + (0.1 * attempt)
                app.logger.warning(f"Rate limit hit for model {model}. Retrying in {wait_time:.2f}s (attempt {attempt+1})")
                time.sleep(wait_time)
            except openai.error.InvalidRequestError as e:
                app.logger.warning(f"Model {model} invalid or unavailable: {e}")
                break  # No point retrying an invalid model
            except Exception as e:
                app.logger.error(f"Unexpected OpenAI error with model {model}: {e}")
                break  # Other errors shouldn't be retried

    # Fallback message if all models fail
    return "Sorry, I'm temporarily unable to process requests. Please try again later."


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
