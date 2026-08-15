from __future__ import annotations
import argparse
import traceback
from .config import load_config, get_stocks
from .data import download_history, quote_info
from .indicators import add_indicators, latest
from .scorer import score_technical, score_fundamental, final_score
from .report import build_report
from .notify import send_telegram, send_slack

def run(config_path: str) -> int:
    cfg = load_config(config_path)
    rows = []

    for stock in get_stocks(cfg):
        try:
            df = add_indicators(download_history(
                stock.symbol, stock.market, cfg.get("data", {}).get("period", "1y")
            ))
            if len(df) < 130:
                print(f"Skip {stock.symbol}: insufficient history")
                continue

            row = latest(df)
            tech_score, tech_reasons = score_technical(row)
            info = quote_info(stock.symbol, stock.market)
            fund_score, fund_reasons = score_fundamental(info)
            total = final_score(tech_score, fund_score)

            rows.append({
                "symbol": stock.symbol,
                "name": stock.name,
                "score": total,
                "technical": tech_score,
                "fundamental": fund_score,
                "close": row.get("Close"),
                "rsi": row.get("RSI14"),
                "macd": "🟢" if row.get("MACD", 0) > row.get("MACD_SIGNAL", 0) else "🔴",
                "reasons": tech_reasons + fund_reasons,
            })
        except Exception as e:
            print(f"ERROR {stock.symbol}: {e}")
            traceback.print_exc()

    rows.sort(key=lambda x: x["score"], reverse=True)
    min_score = int(cfg.get("scoring", {}).get("min_score", 50))
    rows = [r for r in rows if r["score"] >= min_score]

    report = build_report(rows)
    print(report)

    if cfg.get("notifications", {}).get("telegram", True):
        send_telegram(report)
    if cfg.get("notifications", {}).get("slack", False):
        send_slack(report)
    return 0

def main():
    parser = argparse.ArgumentParser(description="TrendRadar Phase 2 stock scanner")
    parser.add_argument("--config", default="config/stock_radar.yaml")
    args = parser.parse_args()
    raise SystemExit(run(args.config))

if __name__ == "__main__":
    main()
