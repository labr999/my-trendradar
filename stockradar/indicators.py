from __future__ import annotations

import numpy as np
import pandas as pd


def add_indicators(
    df: pd.DataFrame
) -> pd.DataFrame:

    x = df.copy()

    close = x["Close"]
    volume = x["Volume"]

    # =========================
    # Moving Average
    # =========================

    x["MA5"] = (
        close
        .rolling(5)
        .mean()
    )

    x["MA20"] = (
        close
        .rolling(20)
        .mean()
    )

    x["MA60"] = (
        close
        .rolling(60)
        .mean()
    )

    x["MA120"] = (
        close
        .rolling(120)
        .mean()
    )

    # =========================
    # RSI 14
    # =========================

    delta = close.diff()

    gain = delta.clip(
        lower=0
    )

    loss = -delta.clip(
        upper=0
    )

    avg_gain = gain.ewm(
        alpha=1 / 14,
        min_periods=14,
        adjust=False
    ).mean()

    avg_loss = loss.ewm(
        alpha=1 / 14,
        min_periods=14,
        adjust=False
    ).mean()

    rs = (
        avg_gain
        /
        avg_loss.replace(
            0,
            np.nan
        )
    )

    x["RSI14"] = (
        100
        -
        (
            100
            /
            (1 + rs)
        )
    )

    # =========================
    # MACD
    # =========================

    ema12 = close.ewm(
        span=12,
        adjust=False
    ).mean()

    ema26 = close.ewm(
        span=26,
        adjust=False
    ).mean()

    x["MACD"] = (
        ema12 - ema26
    )

    x["MACD_SIGNAL"] = (
        x["MACD"]
        .ewm(
            span=9,
            adjust=False
        )
        .mean()
    )

    x["MACD_HIST"] = (
        x["MACD"]
        -
        x["MACD_SIGNAL"]
    )

    # =========================
    # Volume
    # =========================

    x["VOL20"] = (
        volume
        .rolling(20)
        .mean()
    )

    # =========================
    # 60日突破
    # =========================

    x["HIGH60"] = (
        close
        .rolling(60)
        .max()
        .shift(1)
    )

    # =========================
    # 120日新高
    #
    # shift(1)：
    # 不把今天算進前120日高點
    # =========================

    x["HIGH120"] = (
        close
        .rolling(120)
        .max()
        .shift(1)
    )

    # =========================
    # 20日報酬
    # =========================

    x["RETURN20"] = (
        close
        .pct_change(20)
        * 100
    )

    return x


def latest(
    df: pd.DataFrame
) -> pd.Series:

    return df.iloc[-1]

def latest(df: pd.DataFrame) -> pd.Series:
    return df.iloc[-1]
