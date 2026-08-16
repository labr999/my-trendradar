from __future__ import annotations

import math

# ── 各面向權重（總和 1.0）。回測後再調整這裡就好 ─────────────
WEIGHTS = {
    "technical": 0.45,
    "fundamental": 0.35,
    "news": 0.20,
}


def _num(v):
    """轉成 float；NaN / None / 空值一律回傳 None，避免靜默污染分數。"""
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(f) else f


class Facet:
    """單一面向的評分結果。

    raw      : 實得分數
    possible : 該面向在「資料齊全」情況下的滿分
    reasons  : 觸發的條件說明
    fields   : (有值欄位數, 需要欄位數) → 用來判斷資料是否足夠
    """

    def __init__(self, raw, possible, reasons, have, need):
        self.raw = raw
        self.possible = possible
        self.reasons = reasons
        self.have = have
        self.need = need

    @property
    def available(self) -> bool:
        # 至少要有一半欄位有資料，這個面向才算數
        return self.need > 0 and self.have / self.need >= 0.5

    @property
    def score(self) -> int:
        """正規化到 0-100。"""
        if not self.available or self.possible <= 0:
            return 0
        return int(round(max(0, min(self.raw, self.possible)) / self.possible * 100))


# ── 技術面（= 策略一：均線多頭 + 120日突破）────────────────
# 40分 均線多頭排列 | 20分 120日新高 | 15分 距MA5遠近
# 15分 量能健康度   | 10分 RSI
#
# 這個函式取代了原本較簡單的技術面規則。backtest.py / portfolio.py /
# __main__.py 都是呼叫 score_technical()，所以換掉這裡，
# 回測跟每日選股會自動用同一套邏輯，不用改呼叫端。
def score_technical(row) -> Facet:
    raw, reasons = 0, []

    close = _num(row.get("Close"))
    ma5 = _num(row.get("MA5"))
    ma20 = _num(row.get("MA20"))
    ma60 = _num(row.get("MA60"))
    ma120 = _num(row.get("MA120"))
    high120 = _num(row.get("HIGH120"))
    volume = _num(row.get("Volume"))
    vol20 = _num(row.get("VOL20"))
    rsi = _num(row.get("RSI14"))

    have = sum(v is not None for v in
               (close, ma5, ma20, ma60, ma120, high120, volume, vol20, rsi))
    need = 9

    # 1. 均線趨勢 40分
    if None not in (ma5, ma20, ma60, ma120):
        if ma5 > ma20 > ma60 > ma120:
            raw += 40
            reasons.append("MA5>MA20>MA60>MA120")
        else:
            if ma5 > ma20:
                raw += 10
            if ma20 > ma60:
                raw += 10
            if ma60 > ma120:
                raw += 10

    # 2. 120日新高 20分
    if None not in (close, high120) and high120 > 0 and close >= high120:
        raw += 20
        reasons.append("創120日新高")

    # 3. 距MA5遠近 15分
    distance = None
    if None not in (close, ma5) and ma5 > 0:
        distance = close / ma5 - 1
        if 0 <= distance <= 0.01:
            raw += 15
            reasons.append("MA5附近")
        elif distance <= 0.03:
            raw += 12
            reasons.append("距MA5 3%內")
        elif distance <= 0.05:
            raw += 7
            reasons.append("距MA5 5%內")
        elif distance > 0.08:
            raw += 2
            reasons.append("離MA5偏遠")

    # 4. 成交量健康度 15分
    if None not in (volume, vol20) and vol20 > 0:
        ratio = volume / vol20
        if 1.0 <= ratio <= 2.5:
            raw += 15
            reasons.append(f"量能健康 {ratio:.1f}倍")
        elif ratio > 2.5:
            raw += 8
            reasons.append(f"量能偏大 {ratio:.1f}倍")
        elif ratio >= 0.7:
            raw += 6
            reasons.append("量能尚可")

    # 5. RSI 10分
    if rsi is not None:
        if 50 <= rsi <= 70:
            raw += 10
            reasons.append(f"RSI {rsi:.0f} 強勢區")
        elif 45 <= rsi < 50 or 70 < rsi <= 75:
            raw += 6
            reasons.append(f"RSI {rsi:.0f}")
        elif rsi > 80:
            raw += 2
            reasons.append(f"RSI {rsi:.0f} 過熱")

    # raw 本身就落在 0-100，possible 設 100
    f = Facet(raw, 100, reasons, have, need)
    f.distance_to_ma5 = distance  # 給 rank_by_distance 排序用
    return f


# 舊名稱保留為別名，避免有地方還沒改到
score_strategy1 = score_technical


# ── 基本面 ────────────────────────────────────────────────
def score_fundamental(info: dict) -> Facet:
    raw, reasons = 0, []

    roe = _num(info.get("returnOnEquity"))
    pe = _num(info.get("trailingPE"))
    eps_growth = _num(info.get("earningsGrowth"))
    rev_growth = _num(info.get("revenueGrowth"))
    margin = _num(info.get("profitMargins"))

    have = sum(v is not None for v in (roe, pe, eps_growth, rev_growth, margin))
    need = 5

    if roe is not None:
        if roe >= 0.20:
            raw += 20
            reasons.append(f"ROE {roe*100:.0f}%")
        elif roe >= 0.15:
            raw += 12
            reasons.append(f"ROE {roe*100:.0f}%")
        elif roe < 0:
            raw -= 10
            reasons.append("ROE 為負")
    if eps_growth is not None:
        if eps_growth > 0.20:
            raw += 20
            reasons.append(f"EPS +{eps_growth*100:.0f}%")
        elif eps_growth > 0:
            raw += 10
            reasons.append("EPS 成長")
        else:
            raw -= 10
            reasons.append("EPS 衰退")
    if rev_growth is not None:
        if rev_growth > 0.20:
            raw += 15
            reasons.append(f"營收 +{rev_growth*100:.0f}%")
        elif rev_growth > 0:
            raw += 8
            reasons.append("營收成長")
        else:
            raw -= 8
            reasons.append("營收衰退")
    if margin is not None and margin > 0.10:
        raw += 10
        reasons.append(f"淨利率 {margin*100:.0f}%")
    if pe is not None:
        if 0 < pe <= 20:
            raw += 15
            reasons.append(f"PE {pe:.0f} 偏低")
        elif 0 < pe <= 35:
            raw += 8
            reasons.append(f"PE {pe:.0f}")
        elif pe > 50:
            raw -= 10
            reasons.append(f"PE {pe:.0f} 偏高")

    # 滿分 = 20+20+15+10+15 = 80
    return Facet(raw, 80, reasons, have, need)


# ── 策略一輔助函式（score_strategy1 本體已併入 score_technical）──
def strategy1_trade_plan(row, allocation: float = 0.15,
                         take_profit_pct: float = 0.08,
                         stop_loss_pct: float = 0.02) -> dict:
    """策略一的進出場價位。進場價用 MA5（不是現價），
    代表『拉回或站上 5 日線再進場』，不是追當前市價。
    """
    ma5 = _num(row.get("MA5"))
    return {
        "allocation": allocation,
        "take_profit_pct": take_profit_pct,
        "stop_loss_pct": stop_loss_pct,
        "entry_price": ma5,
        "take_profit_price": ma5 * (1 + take_profit_pct) if ma5 else None,
        "stop_loss_price": ma5 * (1 - stop_loss_pct) if ma5 else None,
    }


def rank_strategy1(rows_by_symbol: dict) -> list[tuple[str, Facet, dict]]:
    """rows_by_symbol: {代號: 該股最新一列資料}

    回傳依分數排序的清單，分數相同時距 MA5 越近排越前面
    （代表現在進場的價格風險比較小）。
    """
    ranked = []
    for sym, row in rows_by_symbol.items():
        f = score_technical(row)
        plan = strategy1_trade_plan(row)
        ranked.append((sym, f, plan))

    def sort_key(item):
        _, f, _ = item
        dist = getattr(f, "distance_to_ma5", None)
        return (f.score, -abs(dist) if dist is not None else -999)

    ranked.sort(key=sort_key, reverse=True)
    return ranked


# ── 新聞面（由 news.py 提供 0-100 分）─────────────────────
def score_news(news_result: dict | None) -> Facet:
    if not news_result:
        return Facet(0, 100, [], 0, 1)
    s = _num(news_result.get("score"))
    if s is None:
        return Facet(0, 100, [], 0, 1)
    reason = news_result.get("reason")
    return Facet(s, 100, [reason] if reason else [], 1, 1)


# ── 合成總分 ──────────────────────────────────────────────
def final_score(technical: Facet, fundamental: Facet, news: Facet | None = None):
    """回傳 (總分, 明細 dict)。

    某面向資料不足時，該面向的權重會平均分配給其他有資料的面向，
    避免「抓不到基本面 → 一律 0 分」把排名整個扭曲。
    """
    facets = {"technical": technical, "fundamental": fundamental}
    if news is not None:
        facets["news"] = news

    usable = {k: f for k, f in facets.items() if f.available}
    if not usable:
        return 0, {"note": "資料不足", "facets": {}}

    total_w = sum(WEIGHTS[k] for k in usable)
    score = sum(f.score * WEIGHTS[k] for k, f in usable.items()) / total_w

    detail = {
        "facets": {
            k: {
                "score": f.score,
                "available": f.available,
                "reasons": f.reasons,
            }
            for k, f in facets.items()
        },
        "missing": [k for k in facets if k not in usable],
    }
    return int(round(score)), detail
