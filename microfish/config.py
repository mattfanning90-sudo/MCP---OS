"""Configuration for the microfish quant."""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path

# Liquid ASX large/mid caps. Yahoo Finance suffix ".AX".
DEFAULT_UNIVERSE = [
    "BHP.AX", "CBA.AX", "CSL.AX", "NAB.AX", "WBC.AX", "ANZ.AX", "MQG.AX",
    "WES.AX", "WOW.AX", "TLS.AX", "RIO.AX", "FMG.AX", "GMG.AX", "TCL.AX",
    "ALL.AX", "WDS.AX", "STO.AX", "QBE.AX", "COL.AX", "REA.AX", "XRO.AX",
    "WTC.AX", "JBH.AX", "PME.AX", "CAR.AX", "SEK.AX", "RMD.AX", "COH.AX",
    "ORG.AX", "SUN.AX", "IAG.AX", "AMC.AX", "BXB.AX", "SHL.AX", "NST.AX",
    "EVN.AX", "MIN.AX", "PLS.AX", "A2M.AX", "TWE.AX",
]


@dataclass
class Config:
    # Universe and data
    universe: list[str] = field(default_factory=lambda: list(DEFAULT_UNIVERSE))
    start: str = "2018-01-01"
    end: str | None = None
    cache_dir: str = ".microfish_cache"

    # Strategy ensemble weights
    momentum_weight: float = 0.6
    mean_reversion_weight: float = 0.4

    # Portfolio construction
    initial_cash: float = 10_000.0
    max_positions: int = 8
    max_weight: float = 0.20          # cap per position
    entry_threshold: float = 0.15     # minimum ensemble score to hold
    vol_lookback: int = 20            # days, for ATR%-based sizing
    rebalance_every: int = 5          # trading days between rebalances

    # Costs (one-way, applied to turnover)
    commission_bps: float = 10.0
    slippage_bps: float = 5.0

    @property
    def cost_per_side(self) -> float:
        return (self.commission_bps + self.slippage_bps) / 10_000.0

    @classmethod
    def load(cls, path: str | Path) -> "Config":
        data = json.loads(Path(path).read_text())
        return cls(**data)

    def save(self, path: str | Path) -> None:
        Path(path).write_text(json.dumps(asdict(self), indent=2))
