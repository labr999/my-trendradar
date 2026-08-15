from __future__ import annotations

import argparse
import sys

from .data import load_all
from .portfolio import PortfolioRules, equal_weight_benchmark
from .portfolio import run as run_portfolio
from .watchlist import load


def main() -> int:
    ap = argparse.ArgumentParser(description="StockRadar 投組回測")
    ap.add_argument("--period", default="3y", help="回測期間，如 2y / 3y / 5y")
    ap.add_argument("--cash", type=float, default=1_000_000)
    ap.add_argument("--entry", type=int, default=70, help="進場分數門檻")
    ap.add_argument("--exit", type=int, default=45, dest="exit_score")
    ap.add_argument("--positions", type=int, default=5, help="同時持有檔數")
    ap.add_argument("--alloc", default="equal",
                    choices=["equal", "score", "inverse_vol"])
    ap.add_argument("--max-weight", type=float, default=0.30)
    ap.add_argument("--stop", type=float, default=-0.08)
    ap.add_argument("--profit", type=float, default=0.25)
    ap.add_argument("--trail", type=float, default=None, help="移動停利，如 0.08")
    ap.add_argument("--one-per-group", action="store_true")
    args = ap.parse_args()

    stocks = load()
    print(f"觀察名單 {len(stocks)} 檔，下載 {args.period} 資料...\n")
    data, failed = load_all(stocks, period=args.period)
    if len(data) < 2:
        print("可用標的不足 2 檔，無法做投組回測")
        return 1

    groups = {s.symbol: s.group for s in stocks}
    rules = PortfolioRules(
        entry_score=args.entry, exit_score=args.exit_score,
        stop_loss=args.stop, take_profit=args.profit, trail_stop=args.trail,
        max_positions=args.positions, allocation=args.alloc,
        max_weight=args.max_weight, one_per_group=args.one_per_group,
    )

    res = run_portfolio(data, rules, initial_cash=args.cash, groups=groups)
    bench = equal_weight_benchmark(data)

    print("\n" + "=" * 40)
    print(f"參數：進場{args.entry} 持有{args.positions}檔 {args.alloc}"
          f"{f' 移動停利{args.trail}' if args.trail else ''}")
    print("=" * 40)
    print(res.summary())
    print(f"\n等權買進持有基準：{bench*100:+.1f}%")
    edge = res.total_return - bench
    print(f"超額報酬：{edge*100:+.1f}% " +
          ("✅ 勝過基準" if edge > 0 else "❌ 不如直接買進持有"))

    if res.n:
        print("\n各標的貢獻：")
        print(res.by_symbol().to_string())

    if res.n < 30:
        print(f"\n⚠️ 交易僅 {res.n} 次，樣本太少，勝率與報酬多半是運氣")
    return 0


if __name__ == "__main__":
    sys.exit(main())
