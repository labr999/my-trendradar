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


# ── 技術面 ────────────────────────────────────────────────
def score_technical(row) -> Facet:
    raw, reasons = 0, []

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

    have = sum(v is not None for v in
               (close, ma20, ma60, ma120, rsi, macd, signal, vol, vol20, high60))
    need = 10

    if None not in (close, ma20, ma60) and close > ma20 > ma60:
        raw += 10
        reasons.append("多頭排列")
    if None not in (ma60, ma120) and ma60 > ma120:
        raw += 10
        reasons.append("季線>半年線")
    if rsi is not None:
        if 50 <= rsi <= 70:
            raw += 15
            reasons.append(f"RSI {rsi:.0f} 強勢")
        elif rsi > 80:
            raw -= 10
            reasons.append(f"RSI {rsi:.0f} 過熱")
        elif rsi < 30:
            raw -= 5
            reasons.append(f"RSI {rsi:.0f} 弱勢")
    if None not in (macd, signal) and macd > signal:
        raw += 10
        reasons.append("MACD 多頭")
    if None not in (vol, vol20) and vol20 > 0:
        ratio = vol / vol20
        if ratio > 1.5:
            raw += 10
            reasons.append(f"爆量 {ratio:.1f}倍")
        elif ratio > 1.2:
            raw += 5
            reasons.append("量能放大")
    if None not in (close, high60) and close > high60:
        raw += 15
        reasons.append("突破60日高")

    # 滿分 = 10+10+15+10+10+15 = 70
    return Facet(raw, 70, reasons, have, need)


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
