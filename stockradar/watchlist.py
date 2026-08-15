from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Stock:
    symbol: str
    name: str
    market: str = "TW"
    group: str = ""


def load(path: str | Path = "watchlist.csv") -> list[Stock]:
    """讀取觀察名單。

    CSV 格式刻意選得寬鬆：空行、以 # 開頭的行、欄位前後空白都會被忽略，
    在手機上編輯不容易弄壞（比 YAML 安全得多）。
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"找不到觀察名單: {p}")

    stocks: list[Stock] = []
    seen: set[str] = set()

    with p.open(encoding="utf-8-sig") as f:
        rows = [r for r in f if r.strip() and not r.lstrip().startswith("#")]
        for row in csv.DictReader(rows):
            sym = (row.get("symbol") or "").strip()
            if not sym:
                continue
            if sym in seen:
                print(f"[watchlist] 略過重複代號: {sym}")
                continue
            seen.add(sym)
            stocks.append(Stock(
                symbol=sym,
                name=(row.get("name") or sym).strip(),
                market=(row.get("market") or "TW").strip().upper(),
                group=(row.get("group") or "").strip(),
            ))

    if not stocks:
        raise ValueError("觀察名單是空的")
    return stocks


def as_dict(stocks: list[Stock]) -> dict[str, str]:
    """給 news.py 用的 {代號: 名稱}。"""
    return {s.symbol: s.name for s in stocks}
