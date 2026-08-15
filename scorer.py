from __future__ import annotations

def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None

def score_technical(row) -> tuple[int, list[str]]:
    score = 0
    reasons = []

    close = _num(row.get("Close"))
    ma20 = _num(row.get("MA20"))
    ma60 = _num(row.get("MA60"))
    ma120 = _num(row.get("MA120"))
    rsi = _num(row.get("RSI14"))
    macd = _num(row.get("MACD"))
    signal = _num(row.get("MACD_SIGNAL"))
    vol = _num(row.get("Volume"))
    vol20 = _num(row.get("VOL20"))
    high60 = _num(row.get("HIGH60"))

    if None not in (close, ma20, ma60) and close > ma20 > ma60:
        score += 10; reasons.append("MA20>MA60")
    if None not in (ma60, ma120) and ma60 > ma120:
        score += 10; reasons.append("MA60>MA120")
    if rsi is not None and 50 <= rsi <= 70:
        score += 10; reasons.append("RSI50-70")
    if None not in (macd, signal) and macd > signal:
        score += 10; reasons.append("MACD多頭")
    if None not in (vol, vol20) and vol > vol20 * 1.2:
        score += 10; reasons.append("量能放大")
    if None not in (close, high60) and close > high60:
        score += 15; reasons.append("突破60日高")

    return score, reasons

def score_fundamental(info: dict) -> tuple[int, list[str]]:
    score = 0
    reasons = []

    roe = _num(info.get("returnOnEquity"))
    pe = _num(info.get("trailingPE"))
    growth = _num(info.get("earningsGrowth"))
    revenue_growth = _num(info.get("revenueGrowth"))

    if roe is not None and roe >= 0.15:
        score += 10; reasons.append("ROE>=15%")
    if growth is not None and growth > 0:
        score += 10; reasons.append("EPS成長")
    if revenue_growth is not None and revenue_growth > 0:
        score += 10; reasons.append("營收成長")
    # PE is reported as a descriptive factor, not a hard buy rule.
    if pe is not None and 0 < pe <= 35:
        reasons.append("本益比<=35")

    return score, reasons

def final_score(technical: int, fundamental: int) -> int:
    return min(100, technical + fundamental)
