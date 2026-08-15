from __future__ import annotations
import os
import requests

def send_telegram(text: str) -> bool:
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat_id:
        print("Telegram secrets not configured; skip notification.")
        return False

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    r = requests.post(url, data={
        "chat_id": chat_id,
        "text": text,
        "disable_web_page_preview": "true",
    }, timeout=20)
    r.raise_for_status()
    return True

def send_slack(text: str) -> bool:
    webhook = os.getenv("SLACK_WEBHOOK_URL", "").strip()
    if not webhook:
        return False
    r = requests.post(webhook, json={"text": text}, timeout=20)
    r.raise_for_status()
    return True
