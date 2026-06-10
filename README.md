# Microfish 🐟

A small-capital trading quant. Microfish scores a configurable equity
universe (ASX large/mid caps by default) with an ensemble of momentum and
mean-reversion strategies, sizes positions by volatility with hard risk
caps, and validates everything through a cost-aware backtester.

**Signals + backtest only** — microfish tells you what to hold; it never
touches a broker. Not financial advice.

## Install

```bash
pip install -e ".[dev]"
```

## Usage

```bash
# Print today's target portfolio (fetches ~400 days of data, cached locally)
microfish signals --cash 10000

# Backtest the strategy
microfish backtest --start 2018-01-01
# -> prints CAGR / Sharpe / max drawdown etc., writes reports/equity_curve.csv

# Show the default universe
microfish universe
```

Custom config: copy the defaults, edit, and pass `--config`:

```python
from microfish.config import Config
Config().save("my_config.json")
```

Key knobs in `Config`: `universe`, `max_positions` (8), `max_weight` (20%),
`entry_threshold` (0.15), `rebalance_every` (5 trading days),
`commission_bps` + `slippage_bps` (15 bps/side total).

## How it works

1. **Data** (`data.py`) — daily OHLCV via yfinance, cached as CSV in
   `.microfish_cache/` for 12 hours.
2. **Strategies** (`strategies/`) — each scores every ticker in [-1, 1]
   per day, long-only:
   - **Momentum**: 12-1 month volatility-adjusted return, gated by a
     200-day trend filter and 50/200 MA regime check.
   - **Mean reversion**: buys RSI(2)/z-score dips, but only for names
     above their 200-day average.
   - **Ensemble**: 60/40 weighted blend with a volume-confirmation
     haircut for drying-up liquidity.
3. **Portfolio** (`portfolio.py`) — top-N names above the entry
   threshold, sized inverse to realized volatility, capped per position,
   never levered; excess stays in cash.
4. **Backtest** (`backtest.py`) — signals computed on close t fill at
   close t+1 (no lookahead), one-way costs charged on turnover.

Adding a strategy: subclass `microfish.strategies.Strategy`, implement
`score(ohlcv) -> Series`, and blend it in `Ensemble` (or use it directly).

## Tests

```bash
pytest
```

Tests run entirely on synthetic data — no network needed. They cover
indicator math, strategy behavior (including a no-lookahead check),
risk caps, and backtest accounting.
