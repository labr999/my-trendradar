from __future__ import annotations

def _f(v, digits=2):
    try:
        return f"{float(v):.{digits}f}"
    except (TypeError, ValueError):
        return "-"

def build_report(rows: list[dict]) -> str:
    lines = [
        "🤖 AI TrendRadar｜第二期",
        "━━━━━━━━━━━━━━━━━━",
        "📈 技術面 + 基本面選股",
        "",
    ]
    if not rows:
        lines.append("今日沒有符合基本條件的股票。")
        return "\n".join(lines)

    for i, r in enumerate(rows[:20], 1):
        lines += [
            f"{i}. {r['name']} ({r['symbol']})",
            f"⭐ 總分：{r['score']}/100",
            f"💵 收盤：{_f(r['close'])}",
            f"📊 技術：{r['technical']}/65｜基本面：{r['fundamental']}/30",
            f"RSI：{_f(r['rsi'])}｜MACD：{r['macd']}",
            f"訊號：{', '.join(r['reasons']) or '無'}",
            "",
        ]
    lines += [
        "━━━━━━━━━━━━━━━━━━",
        "⚠️ 這是量化篩選，不是投資保證。",
    ]
    return "\n".join(lines)
