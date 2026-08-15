from __future__ import annotations
import time
import pandas as pd
import yfinance as yf

def yf_symbol(symbol: str, market: str) -> str:
    if market == "TW":
        if symbol.endswith(".TW") or symbol.endswith(".TWO"):
            return symbol
        return f"{symbol}.TW"
    return symbol

def download_history(symbol: str, market: str, period: str = "1y") -> pd.DataFrame:
    ticker = yf_symbol(symbol, market)
    df = yf.download(ticker, period=period, interval="1d",
                     auto_adjust=False, progress=False, threads=False)
    if df is None or df.empty:
        raise ValueError(f"No price data for {ticker}")
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    required = ["Close", "Volume"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Missing columns {missing} for {ticker}")
    return df.dropna(subset=["Close"]).copy()

def quote_info(symbol: str, market: str) -> dict:
    ticker = yf.Ticker(yf_symbol(symbol, market))
    try:
        return ticker.info or {}
    except Exception:
        return {}
