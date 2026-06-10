"""Cost-aware daily backtester.

Execution model: scores are computed on day t's close; the resulting
target weights are held from day t+1 (i.e. trades fill at the next close).
One-way costs (commission + slippage) are charged on turnover.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .config import Config
from .data import close_panel
from .portfolio import target_weights, universe_vols
from .strategies.base import Strategy


@dataclass
class BacktestResult:
    equity: pd.Series           # portfolio value over time
    weights: pd.DataFrame       # weights actually held each day
    daily_returns: pd.Series
    metrics: dict

    def summary(self) -> str:
        lines = [f"{k:>16}: {v}" for k, v in self.metrics.items()]
        return "\n".join(lines)


def _metrics(equity: pd.Series, daily: pd.Series, weights: pd.DataFrame) -> dict:
    n_years = max(len(daily) / 252.0, 1e-9)
    total_return = equity.iloc[-1] / equity.iloc[0] - 1.0
    cagr = (1.0 + total_return) ** (1.0 / n_years) - 1.0
    vol = daily.std() * np.sqrt(252)
    sharpe = (daily.mean() / daily.std() * np.sqrt(252)) if daily.std() > 0 else 0.0
    downside = daily[daily < 0].std()
    sortino = (daily.mean() / downside * np.sqrt(252)) if downside and downside > 0 else 0.0
    running_max = equity.cummax()
    max_dd = (equity / running_max - 1.0).min()
    exposure = weights.sum(axis=1).mean()
    turnover = weights.diff().abs().sum(axis=1).mean() * 252
    return {
        "start": str(equity.index[0].date()),
        "end": str(equity.index[-1].date()),
        "total_return": f"{total_return:+.1%}",
        "cagr": f"{cagr:+.1%}",
        "ann_vol": f"{vol:.1%}",
        "sharpe": f"{sharpe:.2f}",
        "sortino": f"{sortino:.2f}",
        "max_drawdown": f"{max_dd:.1%}",
        "avg_exposure": f"{exposure:.1%}",
        "ann_turnover": f"{turnover:.1f}x",
    }


def run_backtest(
    history: dict[str, pd.DataFrame],
    strategy: Strategy,
    cfg: Config,
) -> BacktestResult:
    closes = close_panel(history)
    scores = strategy.score_universe(history).reindex(closes.index)
    vols = universe_vols(history, cfg.vol_lookback).reindex(closes.index)
    rets = closes.pct_change()

    dates = closes.index
    held = _build_held(dates, scores, vols, cfg)

    # Drop weights for days where the price is missing (halts/IPOs).
    held = held.where(closes.notna(), 0.0)

    port_ret = (held * rets.fillna(0.0)).sum(axis=1)
    turnover = held.diff().abs().sum(axis=1).fillna(0.0)
    costs = turnover * cfg.cost_per_side
    daily = port_ret - costs

    equity = cfg.initial_cash * (1.0 + daily).cumprod()
    metrics = _metrics(equity, daily, held)
    return BacktestResult(equity=equity, weights=held, daily_returns=daily, metrics=metrics)


def _build_held(
    dates: pd.DatetimeIndex,
    scores: pd.DataFrame,
    vols: pd.DataFrame,
    cfg: Config,
) -> pd.DataFrame:
    """Weights held each day: rebalance targets applied with a 1-day lag."""
    held = pd.DataFrame(0.0, index=dates, columns=scores.columns)
    pending: pd.Series | None = None
    current = pd.Series(0.0, index=scores.columns)
    days_since = cfg.rebalance_every

    for i, day in enumerate(dates):
        if pending is not None:
            current = pd.Series(0.0, index=scores.columns)
            current[pending.index] = pending.values
            pending = None
        held.iloc[i] = current

        days_since += 1
        day_scores = scores.loc[day]
        if days_since >= cfg.rebalance_every and day_scores.notna().any():
            pending = target_weights(day_scores, vols.loc[day], cfg)
            days_since = 0

    return held
