from __future__ import annotations

import math
from dataclasses import dataclass


def _num(value):
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(value):
        return None
    return value


# ── 台股交易成本（雙向手續費 + 賣出證交稅）────────────────
FEE_RATE = 0.001425
TAX_RATE = 0.003
FEE_DISCOUNT = 1.0


@dataclass
class Rules:
    """回測用的進出場規則，給 backtest.py / portfolio.py 使用。"""
    entry_score: int = 70
    exit_score: int = 45
    stop_loss: float = -0.08
    take_profit: float = 0.25
    max_hold_days: int = 60
    trail_stop: float | None = None


def buy_cost(price: float, shares: int) -> float:
    gross = price * shares
    fee = max(gross * FEE_RATE * FEE_DISCOUNT, 20)
    return gross + fee


def sell_proceeds(price: float, shares: int) -> float:
    gross = price * shares
    fee = max(gross * FEE_RATE * FEE_DISCOUNT, 20)
    tax = gross * TAX_RATE
    return gross - fee - tax


def position_size(cash: float, price: float, pct: float = 1.0) -> int:
    budget = cash * pct
    lots = int(budget // (price * 1000 * (1 + FEE_RATE)))
    return lots * 1000


def check_exit(rules: Rules, entry_price: float, row, score: int,
              hold_days: int, peak_price: float) -> str | None:
    price = float(row["Close"])
    ret = price / entry_price - 1

    if ret <= rules.stop_loss:
        return "停損"
    if rules.trail_stop is not None and peak_price > entry_price:
        if price / peak_price - 1 <= -rules.trail_stop:
            return "移動停利"
    if ret >= rules.take_profit:
        return "停利"
    if score < rules.exit_score:
        return "轉弱"
    if hold_days >= rules.max_hold_days:
        return "持有到期"
    return None


# ============================================================
# Strategy 1：均線多頭 + 120日突破 + 距MA5 進出場計畫
# 給每日選股報告用，計算個股的建議進場價／停利價／停損價
# ============================================================
def strategy1(
    row,
    allocation=0.15,
    take_profit=0.08,
    stop_loss=0.02,
):
    close = _num(row.get("Close"))
    ma5 = _num(row.get("MA5"))
    ma20 = _num(row.get("MA20"))
    ma60 = _num(row.get("MA60"))
    ma120 = _num(row.get("MA120"))
    high120 = _num(row.get("HIGH120"))

    values = (close, ma5, ma20, ma60, ma120, high120)

    if any(value is None for value in values):
        return {
            "qualified": False,
            "reason": "資料不足",
        }

    bullish = (
        ma5 > ma20
        and ma20 > ma60
        and ma60 > ma120
    )

    above_ma5 = close > ma5

    new_high_120 = close >= high120

    qualified = (
        bullish
        and above_ma5
        and new_high_120
    )

    distance = close / ma5 - 1

    result = {
        "qualified": qualified,
        "bullish": bullish,
        "above_ma5": above_ma5,
        "new_high_120": new_high_120,
        "close": close,
        "ma5": ma5,
        "ma20": ma20,
        "ma60": ma60,
        "ma120": ma120,
        "high120": high120,
        "distance_to_ma5": distance,
    }

    if qualified:
        entry = ma5

        result.update({
            "entry": entry,
            "allocation": allocation,
            "take_profit_price": entry * (1 + take_profit),
            "stop_loss_price": entry * (1 - stop_loss),
            "take_profit_pct": take_profit,
            "stop_loss_pct": stop_loss,
            "entry_note": "等待回測MA5，不追高",
        })

    return result
