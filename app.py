import os
import time
import logging
from flask import Flask, request, jsonify
from openai import OpenAI, RateLimitError, BadRequestError, APIError

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

# OpenAI client
openai_api_key = os.environ.get("OPENAI_API_KEY")
client = OpenAI(api_key=openai_api_key)

# Default and fallback models (updated for OpenAI SDK v1.43.0)
PRIMARY_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
FALLBACK_MODELS = ["gpt-4o", "gpt-3.5-turbo"]

# WhatsApp verification token
VERIFY_TOKEN = os.environ.get("WHATSAPP_VERIFY_TOKEN", "your_verify_token")


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
        app.logger.info(f"Payload received: {payload}")

        try:
            messages = payload["entry"][0]["changes"][0]["value"].get("messages", [])
            if not messages:
                return jsonify({"status": "no messages"}), 200

            msg = messages[0]
            user_text = msg.get("text", {}).get("body", "")
            sender_id = msg.get("from")

            reply_text = generate_reply("You are a helpful assistant.", user_text)
            app.logger.info(f"Reply to {sender_id}: {reply_text}")

        except Exception as e:
            app.logger.error(f"Error processing webhook: {e}")
            return jsonify({"status": "error"}), 500

        return jsonify({"status": "success"}), 200


def generate_reply(system_prompt, user_text):
    """
    Generates a reply using OpenAI, automatically falling back to alternate models if needed.
    """
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
                # Retry with exponential backoff
                wait_time = (2 ** attempt) + 0.1 * attempt
                app.logger.warning(
                    f"Rate limit hit for model {model}. Retrying in {wait_time:.2f}s (attempt {attempt+1})"
                )
                time.sleep(wait_time)

            except BadRequestError as e:
                # Handle invalid or missing model gracefully
                if "model_not_found" in str(e):
                    app.logger.warning(f"Model {model} not found. Trying next model.")
                else:
                    app.logger.warning(f"Bad request with model {model}: {e}")
                break

            except APIError as e:
                # Temporary API error, retry
                wait_time = (2 ** attempt) + 0.1 * attempt
                app.logger.warning(
                    f"OpenAI API error: {e}. Retrying in {wait_time:.2f}s (attempt {attempt+1})"
                )
                time.sleep(wait_time)

            except Exception as e:
                app.logger.error(f"Unexpected error with model {model}: {e}")
                break

    # If all models fail
    return "Sorry, I'm temporarily unable to process requests. Please try again later."


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
