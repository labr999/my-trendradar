from __future__ import annotations

import math


def _num(value):

    try:

        value = float(value)

    except (
        TypeError,
        ValueError
    ):

        return None

    if math.isnan(value):

        return None

    return value


def strategy1(
    row,
    allocation=0.15,
    take_profit=0.08,
    stop_loss=0.02,
):

    close = _num(
        row.get("Close")
    )

    ma5 = _num(
        row.get("MA5")
    )

    ma20 = _num(
        row.get("MA20")
    )

    ma60 = _num(
        row.get("MA60")
    )

    ma120 = _num(
        row.get("MA120")
    )

    high120 = _num(
        row.get("HIGH120")
    )

    values = (
        close,
        ma5,
        ma20,
        ma60,
        ma120,
        high120,
    )

    if any(
        value is None
        for value in values
    ):

        return {
            "qualified": False,
            "reason": "資料不足",
        }

    # =========================
    # Strategy 1
    # =========================

    bullish = (
        ma5 > ma20
        and ma20 > ma60
        and ma60 > ma120
    )

    above_ma5 = (
        close > ma5
    )

    new_high_120 = (
        close >= high120
    )

    qualified = (
        bullish
        and above_ma5
        and new_high_120
    )

    distance = (
        close / ma5 - 1
    )

    result = {

        "qualified":
            qualified,

        "bullish":
            bullish,

        "above_ma5":
            above_ma5,

        "new_high_120":
            new_high_120,

        "close":
            close,

        "ma5":
            ma5,

        "ma20":
            ma20,

        "ma60":
            ma60,

        "ma120":
            ma120,

        "high120":
            high120,

        "distance_to_ma5":
            distance,
    }

    if qualified:

        entry = ma5

        result.update({

            "entry":
                entry,

            "allocation":
                allocation,

            "take_profit_price":
                entry
                *
                (1 + take_profit),

            "stop_loss_price":
                entry
                *
                (1 - stop_loss),

            "take_profit_pct":
                take_profit,

            "stop_loss_pct":
                stop_loss,

            "entry_note":
                "等待回測MA5，不追高",
        })

    return result
    if ret >= rules.take_profit:
        return "停利"
    if score < rules.exit_score:
        return "轉弱"
    if hold_days >= rules.max_hold_days:
        return "持有到期"
    return None
