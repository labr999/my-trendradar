from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from scorer import score_technical
from strategy import (Rules, buy_cost, check_exit, position_size,
                      sell_proceeds)


@dataclass
class Trade:
    symbol: str
    entry_date: pd.Timestamp
    entry_price: float
    exit_date: pd.Timestamp
    exit_price: float
    shares: int
    pnl: float
    ret: float
    hold_days: int
    reason: str


@dataclass
class Result:
    symbol: str
    trades: list[Trade] = field(default_factory=list)
    equity: pd.Series | None = None

    # ── 績效指標 ──────────────────────────────────────
    @property
    def n(self) -> int:
        return len(self.trades)

    @property
    def win_rate(self) -> float:
        if not self.trades:
            return 0.0
        return sum(t.pnl > 0 for t in self.trades) / self.n

    @property
    def total_return(self) -> float:
        if self.equity is None or self.equity.empty:
            return 0.0
        return self.equity.iloc[-1] / self.equity.iloc[0] - 1

    @property
    def max_drawdown(self) -> float:
        if self.equity is None or self.equity.empty:
            return 0.0
        peak = self.equity.cummax()
        return float((self.equity / peak - 1).min())

    @property
    def profit_factor(self) -> float:
        gains = sum(t.pnl for t in self.trades if t.pnl > 0)
        losses = -sum(t.pnl for t in self.trades if t.pnl < 0)
        if losses == 0:
            return float("inf") if gains > 0 else 0.0
        return gains / losses

    @property
    def avg_hold(self) -> float:
        if not self.trades:
            return 0.0
        return sum(t.hold_days for t in self.trades) / self.n

    def summary(self) -> str:
        if self.n == 0:
            return f"{self.symbol}: 期間內無任何進場訊號"
        return (
            f"{self.symbol}\n"
            f"  交易次數 {self.n} | 勝率 {self.win_rate*100:.0f}%\n"
            f"  總報酬 {self.total_return*100:+.1f}% | 最大回檔 {self.max_drawdown*100:.1f}%\n"
            f"  獲利因子 {self.profit_factor:.2f} | 平均持有 {self.avg_hold:.0f} 天"
        )


def run(symbol: str, df: pd.DataFrame, rules: Rules | None = None,
        initial_cash: float = 500_000, warmup: int = 120) -> Result:
    """逐日回測單一標的。

    df 必須是已經跑過 add_indicators() 的資料。
    warmup: 前 N 根不交易，等 MA120 等長週期指標有值。

    避免未來函數的兩個關鍵設計：
      1. 訊號用第 i 根的收盤資料判斷，第 i+1 根的『開盤價』成交
      2. 只用滾動指標，不使用任何當下才知道的資訊（如 .info 的財報快照）
    """
    rules = rules or Rules()
    cash = initial_cash
    shares = 0
    entry_price = entry_date = None
    peak_price = 0.0
    hold_days = 0
    trades: list[Trade] = []
    equity_vals, equity_idx = [], []

    has_open = "Open" in df.columns

    for i in range(warmup, len(df) - 1):
        row = df.iloc[i]
        nxt = df.iloc[i + 1]
        # 隔日成交價：有開盤價用開盤價，否則退回隔日收盤
        fill = float(nxt["Open"]) if has_open and not pd.isna(nxt["Open"]) \
            else float(nxt["Close"])
        if fill <= 0 or np.isnan(fill):
            continue

        score = score_technical(row).score

        if shares > 0:
            hold_days += 1
            peak_price = max(peak_price, float(row["Close"]))
            reason = check_exit(rules, entry_price, row, score,
                                hold_days, peak_price)
            if reason:
                proceeds = sell_proceeds(fill, shares)
                cost = buy_cost(entry_price, shares)
                pnl = proceeds - cost
                trades.append(Trade(
                    symbol=symbol,
                    entry_date=entry_date, entry_price=entry_price,
                    exit_date=df.index[i + 1], exit_price=fill,
                    shares=shares, pnl=pnl, ret=pnl / cost,
                    hold_days=hold_days, reason=reason,
                ))
                cash += proceeds
                shares = 0
                entry_price = entry_date = None
                peak_price = 0.0
                hold_days = 0
        elif score >= rules.entry_score:
            qty = position_size(cash, fill)
            if qty > 0:
                cost = buy_cost(fill, qty)
                if cost <= cash:
                    cash -= cost
                    shares = qty
                    entry_price = fill
                    entry_date = df.index[i + 1]
                    peak_price = fill
                    hold_days = 0

        equity_vals.append(cash + shares * float(row["Close"]))
        equity_idx.append(df.index[i])

    # 期末仍持有 → 用最後一根收盤結算
    if shares > 0:
        last = float(df["Close"].iloc[-1])
        proceeds = sell_proceeds(last, shares)
        cost = buy_cost(entry_price, shares)
        pnl = proceeds - cost
        trades.append(Trade(
            symbol=symbol, entry_date=entry_date, entry_price=entry_price,
            exit_date=df.index[-1], exit_price=last, shares=shares,
            pnl=pnl, ret=pnl / cost, hold_days=hold_days, reason="回測結束",
        ))
        cash += proceeds

    equity = pd.Series(equity_vals, index=equity_idx) if equity_vals else None
    return Result(symbol=symbol, trades=trades, equity=equity)


def buy_and_hold(df: pd.DataFrame, warmup: int = 120) -> float:
    """同期間單純買進持有的報酬，當作比較基準。"""
    sub = df["Close"].iloc[warmup:]
    if sub.empty:
        return 0.0
    return float(sub.iloc[-1] / sub.iloc[0] - 1)
