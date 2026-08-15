from __future__ import annotations

from dataclasses import dataclass

# ── 台股交易成本（雙向手續費 + 賣出證交稅）────────────────
FEE_RATE = 0.001425      # 手續費 0.1425%（券商折扣自行調整，如 6 折 = *0.6）
TAX_RATE = 0.003         # 證交稅 0.3%，只在賣出時課
FEE_DISCOUNT = 1.0       # 券商折扣，1.0 = 無折扣，0.6 = 六折


@dataclass
class Rules:
    """進出場規則。所有參數集中在這裡，方便做參數敏感度測試。"""

    entry_score: int = 70        # 技術分數 >= 此值才進場
    exit_score: int = 45         # 分數跌破此值出場
    stop_loss: float = -0.08     # 停損 -8%
    take_profit: float = 0.25    # 停利 +25%
    max_hold_days: int = 60      # 最長持有天數，避免長期套牢佔用資金
    trail_stop: float | None = None   # 移動停利，如 0.10 = 從高點回檔 10% 出場


def buy_cost(price: float, shares: int) -> float:
    """買進總成本（含手續費）。手續費最低 20 元。"""
    gross = price * shares
    fee = max(gross * FEE_RATE * FEE_DISCOUNT, 20)
    return gross + fee


def sell_proceeds(price: float, shares: int) -> float:
    """賣出實收（扣手續費與證交稅）。"""
    gross = price * shares
    fee = max(gross * FEE_RATE * FEE_DISCOUNT, 20)
    tax = gross * TAX_RATE
    return gross - fee - tax


def position_size(cash: float, price: float, pct: float = 1.0) -> int:
    """算可買股數（台股一張 = 1000 股）。pct = 投入資金比例。"""
    budget = cash * pct
    lots = int(budget // (price * 1000 * (1 + FEE_RATE)))
    return lots * 1000


def check_exit(rules: Rules, entry_price: float, row, score: int,
               hold_days: int, peak_price: float) -> str | None:
    """回傳出場原因，None = 續抱。順序即優先序。"""
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
