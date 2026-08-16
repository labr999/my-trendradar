from __future__ import annotations

import sys
from datetime import datetime

from .data import load_all
from .indicators import latest
from .news import score_all
from .notify import send
from .strategy import strategy1
from .watchlist import as_dict, load

TOP_N = 8


def build_alert(data: dict, watchlist, news_map: dict) -> str:
    """組合『進場點 + 新聞』的推播內容。

    只列出 strategy1 判定為 qualified 的標的 —— 也就是均線多頭排列、
    創120日新高、且站上MA5，這三個條件同時成立。沒達標的股票不會出現，
    這是刻意設計：這份報告是『現在可以考慮進場的名單』，不是全體排行榜。
    """
    today = datetime.now().strftime("%m/%d")
    names = {s.symbol: s.name for s in watchlist}

    candidates = []
    for sym, df in data.items():
        row = latest(df)
        plan = strategy1(row)
        if plan.get("qualified"):
            candidates.append((sym, plan))

    # 距 MA5 越近，代表現在進場的價格風險越小，排前面
    candidates.sort(key=lambda x: abs(x[1].get("distance_to_ma5") or 999))

    lines = [f"🎯 進場點提示 {today}", ""]

    if not candidates:
        lines.append("今日無標的符合進場條件")
        lines.append("（需同時滿足：均線多頭排列、創120日新高、站上MA5）")
    else:
        for sym, plan in candidates[:TOP_N]:
            name = names.get(sym, sym)
            entry = plan["entry"]
            tp = plan["take_profit_price"]
            sl = plan["stop_loss_price"]
            dist = plan["distance_to_ma5"] * 100

            lines.append(f"📈 {sym} {name}")
            lines.append(f"   進場 {entry:.1f}｜停利 {tp:.1f}（+{plan['take_profit_pct']*100:.0f}%）"
                        f"｜停損 {sl:.1f}（-{plan['stop_loss_pct']*100:.0f}%）")
            lines.append(f"   現價距MA5 {dist:+.1f}%｜建議配置 {plan['allocation']*100:.0f}%")

            news = news_map.get(sym)
            if news:
                score = news.get("score")
                reason = news.get("reason", "")
                tag = "📰"
                if score is not None:
                    if score >= 65:
                        tag = "🟢"
                    elif score <= 35:
                        tag = "🔴"
                lines.append(f"   {tag} 新聞面 {score}分：{reason}" if score is not None
                            else f"   📰 {reason}")
            lines.append("")

    lines.append("⚠️ 程式篩選結果，非投資建議；進場前請自行確認基本面與風險")
    return "\n".join(lines)


def main() -> int:
    print("讀取觀察名單...")
    stocks = load()
    print(f"共 {len(stocks)} 檔\n")

    print("下載股價...")
    data, failed = load_all(stocks, period="1y")
    if not data:
        send("⚠️ StockRadar 進場提示：所有標的下載失敗")
        return 1

    print("\n抓取新聞並評分...")
    held = [s for s in stocks if s.symbol in data]
    news_map = score_all(as_dict(held))
    print(f"新聞面完成，{len(news_map)} 檔有評分結果")

    print("\n組合報告...")
    text = build_alert(data, stocks, news_map)
    print("\n" + text)

    if failed:
        print(f"\n（{len(failed)} 檔下載失敗：{', '.join(s for s, _ in failed)}）")

    send(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
