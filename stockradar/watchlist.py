from __future__ import annotations

import csv
import io
import os
from dataclasses import dataclass
from pathlib import Path

REQUIRED = "symbol"
HEADERS = ["symbol", "name", "market", "group"]

# 手機中文鍵盤常打出的全形字元 → 半形
FULLWIDTH = {
    "，": ",", "、": ",", "；": ",", "：": ":",
    "（": "(", "）": ")", "　": " ",
}


@dataclass
class Stock:
    symbol: str
    name: str
    market: str = "TW"
    group: str = ""


def _candidates(path):
    """依序嘗試幾個常見位置，讓放錯資料夾也能救回來。"""
    if path:
        return [Path(path)]
    env = os.environ.get("WATCHLIST_PATH")
    if env:
        return [Path(env)]
    return [
        Path("watchlist.csv"),
        Path("config/watchlist.csv"),
        Path(__file__).parent / "watchlist.csv",
        Path(__file__).parent.parent / "watchlist.csv",
    ]


def _normalize(text: str) -> str:
    for bad, good in FULLWIDTH.items():
        text = text.replace(bad, good)
    return text


def _diagnose(p: Path, raw: str) -> str:
    """組出看得懂的錯誤說明，而不是丟一句『名單是空的』。"""
    lines = raw.splitlines()
    preview = "\n".join(f"    {i+1}| {ln}" for i, ln in enumerate(lines[:5]))
    hints = []
    if not raw.strip():
        hints.append("檔案是空的，沒有任何內容")
    if "，" in raw or "、" in raw:
        hints.append("偵測到全形逗號『，』或『、』，請改用半形英文逗號 ,")
    if lines and REQUIRED not in _normalize(lines[0]).lower():
        hints.append(f"第 1 行不像標題列。第一行必須是：{','.join(HEADERS)}")
    if "\t" in raw:
        hints.append("偵測到 Tab 字元，CSV 請用逗號分隔")
    if not hints:
        hints.append("有標題列但沒有任何有效資料列，請確認每行都填了 symbol")

    return (
        f"觀察名單沒有讀到任何股票。\n"
        f"  檔案位置: {p.resolve()}\n"
        f"  檔案大小: {p.stat().st_size} bytes\n"
        f"  前幾行內容:\n{preview or '    (無內容)'}\n"
        f"  可能原因:\n" + "\n".join(f"    - {h}" for h in hints)
    )


def load(path=None):
    """讀取觀察名單。

    容錯範圍：BOM、空行、# 註解、欄位前後空白、全形逗號、重複代號。
    讀不到時會印出檔案實際內容，方便直接看出哪裡錯。
    """
    tried = []
    target = None
    for cand in _candidates(path):
        tried.append(str(cand))
        if cand.exists():
            target = cand
            break

    if target is None:
        raise FileNotFoundError(
            "找不到 watchlist.csv，已嘗試以下位置：\n"
            + "\n".join(f"  - {t}" for t in tried)
            + f"\n目前工作目錄: {Path.cwd()}"
        )

    raw = target.read_text(encoding="utf-8-sig")
    text = _normalize(raw)

    body = [ln for ln in text.splitlines()
            if ln.strip() and not ln.lstrip().startswith("#")]

    # 沒有標題列時自動補上，避免第一檔股票被當成標題吃掉
    if body and REQUIRED not in body[0].lower():
        body.insert(0, ",".join(HEADERS))

    stocks = []
    seen = set()
    for row in csv.DictReader(io.StringIO("\n".join(body))):
        sym = (row.get("symbol") or "").strip()
        if not sym or sym.lower() == "symbol":
            continue
        if sym in seen:
            print(f"[watchlist] 略過重複代號: {sym}")
            continue
        seen.add(sym)
        stocks.append(Stock(
            symbol=sym,
            name=(row.get("name") or sym).strip(),
            market=(row.get("market") or "TW").strip().upper() or "TW",
            group=(row.get("group") or "").strip(),
        ))

    if not stocks:
        raise ValueError(_diagnose(target, raw))

    print(f"[watchlist] 從 {target} 讀入 {len(stocks)} 檔")
    return stocks


def as_dict(stocks):
    return {s.symbol: s.name for s in stocks}
