from __future__ import annotations

import os
import time

import requests

MAX_LEN = 3800  # Telegram 單則上限 4096，留餘裕


def _send_one(token: str, chat_id: str, text: str) -> bool:
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={
                "chat_id": chat_id,
                "text": text,
                "disable_web_page_preview": True,
            },
            timeout=30,
        )
        if r.status_code != 200:
            print(f"[notify] Telegram 回應 {r.status_code}: {r.text[:200]}")
            return False
        return True
    except Exception as e:
        print(f"[notify] 發送失敗: {e}")
        return False


def send(text: str) -> bool:
    """推播到 Telegram。太長會自動依段落分批。"""
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        print("[notify] 未設定 TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID，改印在畫面上：")
        print(text)
        return False

    chunks, cur = [], ""
    for block in text.split("\n\n"):
        if len(cur) + len(block) + 2 > MAX_LEN:
            if cur:
                chunks.append(cur)
            cur = block
        else:
            cur = f"{cur}\n\n{block}" if cur else block
    if cur:
        chunks.append(cur)

    ok = True
    for i, c in enumerate(chunks):
        prefix = f"[{i+1}/{len(chunks)}]\n" if len(chunks) > 1 else ""
        ok = _send_one(token, chat_id, prefix + c) and ok
        if i < len(chunks) - 1:
            time.sleep(1)
    return ok
