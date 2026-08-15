from __future__ import annotations

import os
import sys
from datetime import datetime

from .data import load_all, quote_info
from .indicators import latest
from .news import score_all
from .notify import send
from .scorer import final_score, score_fundamental, score_news, score_technical
from .watchlist import as_dict, load

TOP_N = int(os.environ.get("TOP_N", "5"))
ENABLE_NEWS = os.environ.get("ENABLE_NEWS", "0") == "1"


def build_report(rows: list[dict], failed: list) -> str:
    today = datetime.now().strftime("%m/%d")
    lines = [f"📊 選股排行 {today}", ""]

    if not rows:
        lines.append("今日無資料可評分")
    medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣"]
    for i, r in enumerate(rows[:TOP_N]):
        mark = medals[i] if i < len(medals) else f"{i+1}."
        d = r["detail"]["facets"]
        parts = []
        for key, label in (("technical", "技"), ("fundamental", "基"), ("news", "新")):
            f = d.get(key)
            if f:
                parts.append(f"{label}{f['score']}" if f["available"] else f"{label}--")
        lines.append(f"{mark} {r['symbol']} {r['name']}  {r['score']}分")
        lines.append(f"   {' '.join(parts)}")
        reasons = d.get("technical", {}).get("reasons", [])[:3]
        if reasons:
            lines.append(f"   💬 {'、'.join(reasons)}")
        lines.append("")

    if r_missing := [r for r in rows if r["detail"].get("missing")]:
        miss = {m for r in r_missing for m in r["detail"]["missing"]}
        lines.append(f"ℹ️ 缺漏資料面向：{'、'.join(miss)}（權重已自動重分配）")
    if failed:
        lines.append(f"⚠️ {len(failed)} 檔下載失敗：{', '.join(s for s, _ in failed[:5])}")

    lines.append("")
    lines.append("⚠️ 程式篩選結果，非投資建議")
    return "\n".join(lines)


def main() -> int:
    print("讀取觀察名單...")
    stocks = load()
    print(f"共 {len(stocks)} 檔\n")

    print("下載股價...")
    data, failed = load_all(stocks, period="1y")
    if not data:
        send("⚠️ StockRadar：所有標的下載失敗，請檢查網路或名單")
        return 1

    news_map = {}
    if ENABLE_NEWS:
        print("\n抓取新聞並評分...")
        held = [s for s in stocks if s.symbol in data]
        news_map = score_all(as_dict(held))

    print("\n評分中...")
    rows = []
    for s in stocks:
        df = data.get(s.symbol)
        if df is None:
            continue
        tech = score_technical(latest(df))
        funda = score_fundamental(quote_info(s.symbol, s.market))
        news = score_news(news_map.get(s.symbol)) if ENABLE_NEWS else None
        score, detail = final_score(tech, funda, news)
        rows.append({"symbol": s.symbol, "name": s.name,
                     "score": score, "detail": detail})

    rows.sort(key=lambda r: -r["score"])
    report = build_report(rows, failed)
    print("\n" + report)
    send(report)
    return 0


if __name__ == "__main__":
    sys.exit(main())
