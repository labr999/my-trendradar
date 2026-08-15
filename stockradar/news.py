from __future__ import annotations

import json
import os
import re
import time
import urllib.parse
import xml.etree.ElementTree as ET

import requests

GNEWS = ("https://news.google.com/rss/search"
         "?q={q}+when:2d&hl=zh-TW&gl=TW&ceid=TW:zh-Hant")

PROMPT = """你是台股分析師。以下是各檔股票近兩日的新聞標題。
請針對每檔給一個 0-100 的新聞面分數：
- 50 = 中性或無明確方向
- >50 = 利多，越強分數越高
- <50 = 利空，越嚴重分數越低
判斷時請注意：已被市場充分預期的消息，強度要打折。

只回傳 JSON，不要任何其他文字、不要 markdown 標記。格式：
{{"2330": {{"score": 65, "reason": "理由20字內"}}}}

新聞資料：
{payload}"""


def fetch_headlines(symbol: str, name: str, limit: int = 8) -> list[str]:
    """抓單一檔股票的新聞標題。用『代號 名稱』查詢，減少同名誤中。"""
    q = urllib.parse.quote(f"{symbol} {name}")
    try:
        r = requests.get(GNEWS.format(q=q), timeout=15,
                         headers={"User-Agent": "Mozilla/5.0"})
        r.raise_for_status()
        root = ET.fromstring(r.content)
        titles = []
        for item in root.iter("item"):
            t = item.findtext("title")
            if t:
                # Google News 標題結尾常帶 " - 媒體名"，去掉讓 LLM 更好讀
                titles.append(re.sub(r"\s+-\s+[^-]+$", "", t).strip())
            if len(titles) >= limit:
                break
        return titles
    except Exception as e:
        print(f"[news] {symbol} 抓取失敗: {e}")
        return []


def _call_llm(prompt: str) -> str:
    """呼叫 Anthropic API。沒有 key 就回空字串。"""
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        print("[news] 未設定 ANTHROPIC_API_KEY，跳過新聞評分")
        return ""
    try:
        r = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": "claude-sonnet-4-6",
                "max_tokens": 2000,
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=90,
        )
        r.raise_for_status()
        blocks = r.json().get("content", [])
        return "".join(b.get("text", "") for b in blocks if b.get("type") == "text")
    except Exception as e:
        print(f"[news] LLM 呼叫失敗: {e}")
        return ""


def score_all(watchlist: dict[str, str]) -> dict[str, dict]:
    """watchlist: {"2330": "台積電", ...} → {"2330": {"score":..,"reason":..}}

    整批送出，一天只花一次 API 呼叫。
    任何一步失敗都回空 dict，讓 scorer 自動把新聞面權重分給其他面向。
    """
    lines = []
    for sym, name in watchlist.items():
        heads = fetch_headlines(sym, name)
        if heads:
            lines.append(f"\n【{sym} {name}】")
            lines.extend(f"- {h}" for h in heads)
        time.sleep(1)  # 對 Google 客氣一點

    if not lines:
        return {}

    text = _call_llm(PROMPT.format(payload="\n".join(lines)))
    if not text:
        return {}

    # LLM 偶爾會包 ```json 圍欄，容錯處理
    cleaned = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.M).strip()
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", cleaned, re.S)
        if not m:
            print(f"[news] 無法解析 LLM 回應: {text[:200]}")
            return {}
        try:
            data = json.loads(m.group())
        except json.JSONDecodeError:
            print("[news] JSON 解析失敗")
            return {}

    return {str(k): v for k, v in data.items() if isinstance(v, dict)}
