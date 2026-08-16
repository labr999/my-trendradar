from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .backtest import Trade
from .scorer import score_technical
from .strategy import Rules, buy_cost, check_exit, sell_proceeds

LOT = 1000  # 台股一張股數


@dataclass
class PortfolioRules(Rules):
    """在單檔規則之上，加入投組層級的限制。"""

    max_positions: int = 5           # 同時最多持有幾檔
    allocation: str = "equal"        # equal | score | inverse_vol
    max_weight: float = 0.30         # 單一部位佔總資產上限
    cash_buffer: float = 0.05        # 保留現金比例，避免滿倉
    allow_odd_lot: bool = True       # 是否允許零股（高價股必開，否則買不起）
    one_per_group: bool = False      # 同產業只留一檔，分散風險


@dataclass
class Position:
    symbol: str
    shares: int
    entry_price: float
    entry_date: pd.Timestamp
    peak_price: float
    hold_days: int = 0


@dataclass
class PortfolioResult:
    trades: list[Trade] = field(default_factory=list)
    equity: pd.Series | None = None
    rejected: int = 0                # 因資金/名額不足而放棄的訊號數

    @property
    def n(self) -> int:
        return len(self.trades)

    @property
    def win_rate(self) -> float:
        return sum(t.pnl > 0 for t in self.trades) / self.n if self.n else 0.0

    @property
    def total_return(self) -> float:
        if self.equity is None or self.equity.empty:
            return 0.0
        return float(self.equity.iloc[-1] / self.equity.iloc[0] - 1)

    @property
    def cagr(self) -> float:
        if self.equity is None or len(self.equity) < 2:
            return 0.0
        days = (self.equity.index[-1] - self.equity.index[0]).days
        if days <= 0:
            return 0.0
        return float((1 + self.total_return) ** (365.25 / days) - 1)

    @property
    def max_drawdown(self) -> float:
        if self.equity is None or self.equity.empty:
            return 0.0
        return float((self.equity / self.equity.cummax() - 1).min())

    @property
    def sharpe(self) -> float:
        if self.equity is None or len(self.equity) < 20:
            return 0.0
        r = self.equity.pct_change().dropna()
        if r.std() == 0:
            return 0.0
        return float(r.mean() / r.std() * np.sqrt(252))

    @property
    def profit_factor(self) -> float:
        g = sum(t.pnl for t in self.trades if t.pnl > 0)
        l = -sum(t.pnl for t in self.trades if t.pnl < 0)
        return g / l if l else (float("inf") if g else 0.0)

    def by_symbol(self) -> pd.DataFrame:
        """每檔標的的貢獻，用來找出是誰在賺、誰在拖後腿。"""
        if not self.trades:
            return pd.DataFrame()
        rows = {}
        for t in self.trades:
            d = rows.setdefault(t.symbol, {"次數": 0, "損益": 0.0, "勝": 0})
            d["次數"] += 1
            d["損益"] += t.pnl
            d["勝"] += int(t.pnl > 0)
        df = pd.DataFrame(rows).T
        df["勝率"] = (df["勝"] / df["次數"] * 100).round(0)
        return df[["次數", "勝率", "損益"]].sort_values("損益", ascending=False)

    def summary(self) -> str:
        if self.n == 0:
            return "期間內無任何進場訊號"
        return (
            f"交易 {self.n} 次 | 勝率 {self.win_rate*100:.0f}%\n"
            f"總報酬 {self.total_return*100:+.1f}% | 年化 {self.cagr*100:+.1f}%\n"
            f"最大回檔 {self.max_drawdown*100:.1f}% | Sharpe {self.sharpe:.2f}\n"
            f"獲利因子 {self.profit_factor:.2f} | 資金不足放棄 {self.rejected} 次"
        )


def _weight(rules: PortfolioRules, cand: dict, all_cands: list[dict]) -> float:
    """算單一候選的目標權重（佔總資產比例）。"""
    if rules.allocation == "score":
        total = sum(c["score"] for c in all_cands)
        w = cand["score"] / total if total else 0
    elif rules.allocation == "inverse_vol":
        # 波動越低給越多錢，讓每檔對投組的風險貢獻接近
        inv = [1 / c["vol"] if c["vol"] > 0 else 0 for c in all_cands]
        total = sum(inv)
        my = 1 / cand["vol"] if cand["vol"] > 0 else 0
        w = my / total if total else 0
    else:  # equal
        w = 1 / rules.max_positions
    return min(w, rules.max_weight)


def run(data: dict[str, pd.DataFrame], rules: PortfolioRules | None = None,
        initial_cash: float = 1_000_000, warmup: int = 120,
        groups: dict[str, str] | None = None) -> PortfolioResult:
    """多檔共用資金池回測。

    data   : {代號: 已跑過 add_indicators 的 DataFrame}
    groups : {代號: 產業別}，配合 one_per_group 使用

    每個交易日的處理順序：
      1. 檢查持股是否該出場（先賣，釋出資金）
      2. 對所有未持有標的評分，取分數達標者排序
      3. 依剩餘名額與資金，由高分往下買
    訊號一律用第 i 根收盤判斷、第 i+1 根開盤成交。
    """
    rules = rules or PortfolioRules()
    groups = groups or {}

    # 對齊所有標的的交易日
    idx = sorted(set().union(*[df.index for df in data.values()]))
    idx = pd.DatetimeIndex(idx)

    cash = initial_cash
    positions: dict[str, Position] = {}
    trades: list[Trade] = []
    rejected = 0
    eq_vals, eq_idx = [], []

    for i in range(warmup, len(idx) - 1):
        today, tomorrow = idx[i], idx[i + 1]

        def bar(sym, ts):
            df = data[sym]
            return df.loc[ts] if ts in df.index else None

        def fill_price(sym):
            r = bar(sym, tomorrow)
            if r is None:
                return None
            p = r.get("Open")
            if p is None or pd.isna(p):
                p = r.get("Close")
            p = float(p) if p is not None and not pd.isna(p) else None
            return p if p and p > 0 else None

        # ── 1. 出場 ──────────────────────────────────
        for sym in list(positions):
            row = bar(sym, today)
            if row is None:
                continue
            pos = positions[sym]
            pos.hold_days += 1
            pos.peak_price = max(pos.peak_price, float(row["Close"]))
            score = score_technical(row).score
            reason = check_exit(rules, pos.entry_price, row, score,
                                pos.hold_days, pos.peak_price)
            if not reason:
                continue
            px = fill_price(sym)
            if px is None:
                continue
            proceeds = sell_proceeds(px, pos.shares)
            cost = buy_cost(pos.entry_price, pos.shares)
            pnl = proceeds - cost
            trades.append(Trade(
                symbol=sym, entry_date=pos.entry_date,
                entry_price=pos.entry_price, exit_date=tomorrow,
                exit_price=px, shares=pos.shares, pnl=pnl,
                ret=pnl / cost, hold_days=pos.hold_days, reason=reason,
            ))
            cash += proceeds
            del positions[sym]

        # ── 2. 找候選 ────────────────────────────────
        slots = rules.max_positions - len(positions)
        if slots > 0:
            cands = []
            held_groups = {groups.get(s, "") for s in positions}
            for sym, df in data.items():
                if sym in positions:
                    continue
                row = bar(sym, today)
                if row is None:
                    continue
                sc = score_technical(row).score
                if sc < rules.entry_score:
                    continue
                if rules.one_per_group:
                    g = groups.get(sym, "")
                    if g and g in held_groups:
                        continue
                ret20 = df["Close"].pct_change().rolling(20).std()
                vol = ret20.loc[today] if today in ret20.index else np.nan
                cands.append({
                    "symbol": sym, "score": sc,
                    "vol": float(vol) if not pd.isna(vol) else 0.02,
                })
            cands.sort(key=lambda c: -c["score"])
            cands = cands[:slots]

            # ── 3. 依權重買進 ────────────────────────
            equity_now = cash + sum(
                p.shares * float(bar(s, today)["Close"])
                for s, p in positions.items() if bar(s, today) is not None
            )
            investable = equity_now * (1 - rules.cash_buffer)

            for c in cands:
                sym = c["symbol"]
                px = fill_price(sym)
                if px is None:
                    continue
                budget = min(investable * _weight(rules, c, cands), cash)
                unit = LOT if not rules.allow_odd_lot else 1
                qty = int(budget // (px * unit * 1.002)) * unit
                if qty <= 0:
                    rejected += 1
                    continue
                cost = buy_cost(px, qty)
                if cost > cash:
                    rejected += 1
                    continue
                cash -= cost
                positions[sym] = Position(
                    symbol=sym, shares=qty, entry_price=px,
                    entry_date=tomorrow, peak_price=px,
                )
                if rules.one_per_group:
                    held_groups.add(groups.get(sym, ""))

        # ── 記錄權益 ─────────────────────────────────
        mv = 0.0
        for s, p in positions.items():
            r = bar(s, today)
            if r is not None:
                mv += p.shares * float(r["Close"])
        eq_vals.append(cash + mv)
        eq_idx.append(today)

    # 期末結算
    last = idx[-1]
    for sym, pos in list(positions.items()):
        df = data[sym]
        px = float(df["Close"].iloc[-1])
        proceeds = sell_proceeds(px, pos.shares)
        cost = buy_cost(pos.entry_price, pos.shares)
        pnl = proceeds - cost
        trades.append(Trade(
            symbol=sym, entry_date=pos.entry_date, entry_price=pos.entry_price,
            exit_date=last, exit_price=px, shares=pos.shares, pnl=pnl,
            ret=pnl / cost, hold_days=pos.hold_days, reason="回測結束",
        ))
        cash += proceeds

    equity = pd.Series(eq_vals, index=pd.DatetimeIndex(eq_idx)) if eq_vals else None
    return PortfolioResult(trades=trades, equity=equity, rejected=rejected)


def equal_weight_benchmark(data: dict[str, pd.DataFrame], warmup: int = 120) -> float:
    """全部標的等權買進持有，當作比較基準。"""
    rets = []
    for df in data.values():
        s = df["Close"].iloc[warmup:]
        if len(s) > 1:
            rets.append(s.iloc[-1] / s.iloc[0] - 1)
    return float(np.mean(rets)) if rets else 0.0
