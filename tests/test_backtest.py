import numpy as np
import pandas as pd

from microfish.backtest import run_backtest
from microfish.config import Config
from microfish.signals import latest_signals
from microfish.strategies import Ensemble


def small_cfg(**kw) -> Config:
    defaults = dict(initial_cash=10_000.0, max_positions=3, rebalance_every=5)
    defaults.update(kw)
    return Config(**defaults)


def test_backtest_runs_and_reports(universe):
    result = run_backtest(universe, Ensemble(), small_cfg())
    assert len(result.equity) == 400
    assert result.equity.iloc[0] > 0
    for key in ("cagr", "sharpe", "max_drawdown", "ann_turnover"):
        assert key in result.metrics


def test_flat_market_loses_only_costs(flat):
    result = run_backtest({"FLAT.AX": flat}, Ensemble(), small_cfg())
    final = result.equity.iloc[-1]
    # Flat prices: any positions earn 0; only costs can drag equity, slightly.
    assert final <= 10_000.0 + 1e-6
    assert final > 9_900.0


def test_uptrend_makes_money(uptrend):
    result = run_backtest({"UP.AX": uptrend}, Ensemble(), small_cfg())
    assert result.equity.iloc[-1] > 10_000.0


def test_weights_long_only_and_unlevered(universe):
    result = run_backtest(universe, Ensemble(), small_cfg())
    assert (result.weights >= -1e-12).all().all()
    assert (result.weights.sum(axis=1) <= 1.0 + 1e-9).all()


def test_execution_lag_no_same_day_fill(universe):
    """Weights must change no earlier than the day AFTER a signal."""
    result = run_backtest(universe, Ensemble(), small_cfg(rebalance_every=1))
    w = result.weights
    changes = w.diff().abs().sum(axis=1)
    first_holding = w.sum(axis=1).gt(0).idxmax()
    scores = Ensemble().score_universe(universe)
    first_score_day = scores.notna().any(axis=1).idxmax()
    assert first_holding > first_score_day


def test_latest_signals_shape(universe):
    cfg = small_cfg()
    book = latest_signals(universe, Ensemble(), cfg)
    assert {"score", "ann_vol", "weight", "dollars"} <= set(book.columns)
    assert (book["weight"] >= 0).all()
    assert book["weight"].sum() <= 1.0 + 1e-9
    assert abs(book["dollars"].sum() - book["weight"].sum() * cfg.initial_cash) < 1.0
