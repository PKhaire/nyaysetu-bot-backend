
# NyaySetu Bot Backend (Production-ready starter)

This repository contains a production-ready starter backend for the NyaySetu WhatsApp AI assistant.
It uses Flask, OpenAI (ChatGPT), and the WhatsApp Cloud API to receive messages and send AI-generated replies.

## Files included
- `app.py` — Flask webhook + AI integration + simple SQLite logging and rate-limiting.
- `requirements.txt` — Python dependencies.
- `Procfile` — start command for Render / Heroku-like platforms.
- `.gitignore` — common ignores.
- `init_db.py` — optional initializer for local DB.

## Quick setup (Render)
1. Create a new GitHub repo and push these files.
2. In Render, create a **Web Service** and connect your repo.
3. Build command: `pip install -r requirements.txt`
4. Start command: `gunicorn app:app --bind 0.0.0.0:$PORT --workers 3`
5. Add environment variables in Render:
   - `WHATSAPP_TOKEN` = <your Meta permanent access token>
   - `PHONE_NUMBER_ID` = <your phone number id>
   - `OPENAI_API_KEY` = <your OpenAI API key>
   - `VERIFY_TOKEN` = nyaysetu_verify_token
   - `OPENAI_MODEL` = gpt-4 (or gpt-3.5-turbo)
   - `RATE_LIMIT_SECONDS` = 3
6. Add custom domain `api.nyaysetu.in` in Render and add CNAME in GoDaddy DNS for `api` -> Render target.
7. In Meta Developer Console → WhatsApp → Webhooks, set webhook URL: `https://api.nyaysetu.in/webhook` and Verify Token: `nyaysetu_verify_token` then verify.
8. Test by messaging your NyaySetu WhatsApp number.

## Security & production tips
- Do not commit secrets to Git. Use Render environment variables.
- Use a managed DB for scale (Postgres) instead of SQLite for production.
- Add monitoring, logging, alerts, and backups.
- Rotate tokens periodically and store in a secrets manager.
