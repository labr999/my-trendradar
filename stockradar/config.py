from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import os
import yaml

@dataclass
class StockConfig:
    symbol: str
    name: str
    market: str = "US"

def load_config(path: str = "config/stock_radar.yaml") -> dict:
    with open(path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}
    return cfg

def get_stocks(cfg: dict) -> list[StockConfig]:
    result = []
    for item in cfg.get("stocks", []):
        result.append(StockConfig(
            symbol=str(item["symbol"]),
            name=str(item.get("name", item["symbol"])),
            market=str(item.get("market", "US")).upper(),
        ))
    return result

def env(name: str, default: str = "") -> str:
    return os.getenv(name, default)
