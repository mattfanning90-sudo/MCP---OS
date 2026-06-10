import numpy as np

from microfish.strategies import Momentum, MeanReversion, Ensemble


def test_scores_bounded(universe):
    for strat in (Momentum(), MeanReversion(), Ensemble()):
        scores = strat.score_universe(universe)
        vals = scores.stack().dropna()
        assert (vals >= -1.0).all() and (vals <= 1.0).all()


def test_momentum_prefers_uptrend(uptrend, downtrend):
    strat = Momentum()
    up_score = strat.score(uptrend).iloc[-1]
    down_score = strat.score(downtrend).iloc[-1]
    assert up_score > 0.1
    assert down_score == 0.0  # long-only: downtrends score zero, not negative


def test_mean_reversion_buys_dips_in_uptrend(uptrend):
    strat = MeanReversion()
    base = strat.score(uptrend).iloc[-1]

    dipped = uptrend.copy()
    last = dipped.index[-5:]
    dipped.loc[last, "Close"] = dipped.loc[last, "Close"] * 0.93  # sharp 7% dip
    dip_score = strat.score(dipped).iloc[-1]
    assert dip_score > base
    assert dip_score > 0.3


def test_mean_reversion_ignores_downtrend_dips(downtrend):
    scores = MeanReversion().score(downtrend).dropna()
    assert (scores == 0.0).all()


def test_ensemble_combines(universe):
    scores = Ensemble().score_universe(universe)
    last = scores.iloc[-1]
    assert last["UP.AX"] > last["DOWN.AX"]
    assert last["DOWN.AX"] == 0.0


def test_no_lookahead(uptrend):
    """Truncating the future must not change past scores."""
    strat = Ensemble()
    full = strat.score(uptrend)
    truncated = strat.score(uptrend.iloc[:-30])
    common = truncated.index
    assert np.allclose(
        full.loc[common].fillna(-999), truncated.fillna(-999), atol=1e-12
    )
