import pandas as pd

from microfish.config import Config
from microfish.portfolio import target_weights


def make_cfg(**kw) -> Config:
    return Config(**kw)


def test_threshold_filters_weak_names():
    cfg = make_cfg(entry_threshold=0.5)
    scores = pd.Series({"A": 0.9, "B": 0.4, "C": 0.6})
    vols = pd.Series({"A": 0.2, "B": 0.2, "C": 0.2})
    w = target_weights(scores, vols, cfg)
    assert set(w.index) == {"A", "C"}


def test_max_positions_respected():
    cfg = make_cfg(max_positions=2, entry_threshold=0.1)
    scores = pd.Series({"A": 0.9, "B": 0.8, "C": 0.7, "D": 0.6})
    vols = pd.Series(0.2, index=scores.index)
    w = target_weights(scores, vols, cfg)
    assert len(w) == 2
    assert set(w.index) == {"A", "B"}


def test_max_weight_cap_and_no_leverage():
    cfg = make_cfg(max_positions=2, max_weight=0.2, entry_threshold=0.1)
    scores = pd.Series({"A": 0.9, "B": 0.8})
    vols = pd.Series({"A": 0.2, "B": 0.2})
    w = target_weights(scores, vols, cfg)
    assert (w <= cfg.max_weight + 1e-12).all()
    assert w.sum() <= 1.0 + 1e-12


def test_riskier_names_get_less():
    cfg = make_cfg(entry_threshold=0.1, max_weight=1.0)
    scores = pd.Series({"CALM": 0.5, "WILD": 0.5})
    vols = pd.Series({"CALM": 0.10, "WILD": 0.40})
    w = target_weights(scores, vols, cfg)
    assert w["CALM"] > w["WILD"]


def test_empty_when_nothing_qualifies():
    cfg = make_cfg(entry_threshold=0.5)
    scores = pd.Series({"A": 0.1, "B": 0.2})
    vols = pd.Series({"A": 0.2, "B": 0.2})
    assert target_weights(scores, vols, cfg).empty
