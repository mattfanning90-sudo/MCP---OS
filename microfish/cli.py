"""Command-line interface for microfish.

Usage:
    microfish backtest [--start 2018-01-01] [--config cfg.json] [--out reports/]
    microfish signals  [--config cfg.json] [--cash 10000]
    microfish universe
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .config import Config, DEFAULT_UNIVERSE
from .data import fetch_history, default_start_for_signals
from .strategies import Ensemble
from .backtest import run_backtest
from .signals import latest_signals


def _load_config(args: argparse.Namespace) -> Config:
    cfg = Config.load(args.config) if getattr(args, "config", None) else Config()
    if getattr(args, "start", None):
        cfg.start = args.start
    if getattr(args, "cash", None):
        cfg.initial_cash = args.cash
    return cfg


def _strategy(cfg: Config) -> Ensemble:
    return Ensemble(
        momentum_weight=cfg.momentum_weight,
        mean_reversion_weight=cfg.mean_reversion_weight,
    )


def cmd_backtest(args: argparse.Namespace) -> int:
    cfg = _load_config(args)
    print(f"Fetching {len(cfg.universe)} tickers from {cfg.start}...", file=sys.stderr)
    history = fetch_history(cfg.universe, cfg.start, cfg.end, cfg.cache_dir)
    if not history:
        print("No data fetched — check network access and tickers.", file=sys.stderr)
        return 1
    print(f"Got data for {len(history)} tickers. Running backtest...", file=sys.stderr)

    result = run_backtest(history, _strategy(cfg), cfg)
    print("\n=== microfish backtest ===")
    print(result.summary())

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    result.equity.rename("equity").to_csv(out_dir / "equity_curve.csv")
    result.weights.to_csv(out_dir / "weights.csv")
    print(f"\nWrote equity_curve.csv and weights.csv to {out_dir}/")
    return 0


def cmd_signals(args: argparse.Namespace) -> int:
    cfg = _load_config(args)
    start = default_start_for_signals()
    print(f"Fetching {len(cfg.universe)} tickers from {start}...", file=sys.stderr)
    history = fetch_history(cfg.universe, start, None, cfg.cache_dir)
    if not history:
        print("No data fetched — check network access and tickers.", file=sys.stderr)
        return 1

    book = latest_signals(history, _strategy(cfg), cfg)
    as_of = book.attrs.get("as_of", "?")
    held = book[book["weight"] > 0]

    print(f"\n=== microfish signals as of {as_of} ===")
    print(f"\nTarget portfolio ({len(held)} positions, "
          f"{held['weight'].sum():.0%} invested, cash {cfg.initial_cash:,.0f}):\n")
    if held.empty:
        print("  (no names above the entry threshold — stay in cash)")
    else:
        print(held.to_string(
            formatters={
                "score": "{:.3f}".format,
                "ann_vol": "{:.1%}".format,
                "weight": "{:.1%}".format,
                "dollars": "{:,.0f}".format,
            }
        ))

    print("\nFull ranking (top 15):\n")
    print(book.head(15)[["score", "ann_vol"]].to_string(
        formatters={"score": "{:.3f}".format, "ann_vol": "{:.1%}".format}
    ))
    return 0


def cmd_universe(_: argparse.Namespace) -> int:
    print("\n".join(DEFAULT_UNIVERSE))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="microfish", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p_bt = sub.add_parser("backtest", help="Run a historical backtest")
    p_bt.add_argument("--start", default=None, help="Backtest start date (YYYY-MM-DD)")
    p_bt.add_argument("--config", default=None, help="Path to JSON config")
    p_bt.add_argument("--out", default="reports", help="Output directory")
    p_bt.set_defaults(func=cmd_backtest)

    p_sig = sub.add_parser("signals", help="Print today's target portfolio")
    p_sig.add_argument("--config", default=None, help="Path to JSON config")
    p_sig.add_argument("--cash", type=float, default=None, help="Capital to allocate")
    p_sig.set_defaults(func=cmd_signals)

    p_uni = sub.add_parser("universe", help="Print the default universe")
    p_uni.set_defaults(func=cmd_universe)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
