from __future__ import annotations

import time

import pandas as pd
import yfinance as yf


def yf_symbol(symbol: str, market: str) -> str:
    market = (market or "TW").upper()
    if symbol.endswith(".TW") or symbol.endswith(".TWO"):
        return symbol
    if market == "TWO":
        return f"{symbol}.TWO"
    if market == "TW":
        return f"{symbol}.TW"
    # 其他市場（如美股）直接用原始代號，不加後綴
    return symbol


def download_history(symbol: str, market: str, period: str = "1y",
                     retries: int = 2) -> pd.DataFrame:
    ticker = yf_symbol(symbol, market)
    last_err = None
    for attempt in range(retries + 1):
        try:
            df = yf.download(ticker, period=period, interval="1d",
                             auto_adjust=False, progress=False, threads=False)
            if df is None or df.empty:
                raise ValueError(f"No price data for {ticker}")
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            missing = [c for c in ("Close", "Volume") if c not in df.columns]
            if missing:
                raise ValueError(f"Missing columns {missing} for {ticker}")
            return df.dropna(subset=["Close"]).copy()
        except Exception as e:
            last_err = e
            if attempt < retries:
                time.sleep(2 * (attempt + 1))
    raise ValueError(f"{ticker} 下載失敗: {last_err}")


def quote_info(symbol: str, market: str) -> dict:
    try:
        return yf.Ticker(yf_symbol(symbol, market)).info or {}
    except Exception:
        return {}


def load_all(stocks, period: str = "1y", verbose: bool = True):
    """批次下載。回傳 (資料 dict, 失敗清單)。

    單檔失敗不會中斷整批 —— 台股偶爾會有下市、暫停交易的代號。
    """
    from .indicators import add_indicators

    data, failed = {}, []
    for s in stocks:
        try:
            df = download_history(s.symbol, s.market, period)
            data[s.symbol] = add_indicators(df)
            if verbose:
                print(f"  ✓ {s.symbol} {s.name} ({len(df)} 筆)")
        except Exception as e:
            failed.append((s.symbol, str(e)))
            if verbose:
                print(f"  ✗ {s.symbol} {s.name}: {e}")
        time.sleep(0.5)
    return data, failed
