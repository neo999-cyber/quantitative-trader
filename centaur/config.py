"""Account and rulebook configuration.

Resolution order (later wins): built-in defaults -> ./centaur.json ->
~/.centaur.json -> environment variables (CENTAUR_*) -> explicit overrides.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, asdict, fields
from pathlib import Path
from typing import Any


@dataclass
class AccountConfig:
    # RULE 5 - the sleep test
    equity: float = 10_000.0          # total account equity in dollars
    risk_pct: float = 0.01            # max fraction of equity risked per trade (1%)
    max_risk_pct: float = 0.02        # hard ceiling; anything above is rejected outright

    # RULE 1 - asymmetry
    min_reward_risk: float = 3.0      # 1:3 minimum

    # RULE 2 - confluence
    min_signals: int = 3              # at least three independent signals
    min_categories: int = 3           # ...from three distinct, non-correlated categories

    # RULE 4 - catalyst & liquidity
    min_avg_dollar_volume: float = 20_000_000.0   # $20M/day: below this is a "zombie stock"
    max_position_pct_of_adv: float = 0.01         # position <= 1% of average daily dollar volume
    earnings_buffer_days: int = 1                 # earnings within holding window + buffer => abort

    # Default holding horizon for swing setups (days), used for earnings checks
    default_holding_days: int = 10

    # Data / paths
    cache_dir: str = ".cache"
    journal_path: str = "journal/trades.jsonl"
    briefs_dir: str = "briefs"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


_ENV_MAP = {
    "CENTAUR_EQUITY": ("equity", float),
    "CENTAUR_RISK_PCT": ("risk_pct", float),
    "CENTAUR_MAX_RISK_PCT": ("max_risk_pct", float),
    "CENTAUR_MIN_RR": ("min_reward_risk", float),
    "CENTAUR_MIN_ADV": ("min_avg_dollar_volume", float),
    "CENTAUR_CACHE_DIR": ("cache_dir", str),
    "CENTAUR_JOURNAL": ("journal_path", str),
    "CENTAUR_BRIEFS_DIR": ("briefs_dir", str),
}


def load_config(path: str | os.PathLike | None = None, **overrides: Any) -> AccountConfig:
    """Build an AccountConfig from files, environment, and explicit overrides."""
    values: dict[str, Any] = {}
    valid = {f.name for f in fields(AccountConfig)}

    candidates = [Path(path)] if path else [Path("centaur.json"), Path.home() / ".centaur.json"]
    for p in candidates:
        if p.is_file():
            with open(p) as fh:
                data = json.load(fh)
            values.update({k: v for k, v in data.items() if k in valid})

    for env_key, (field, caster) in _ENV_MAP.items():
        raw = os.environ.get(env_key)
        if raw not in (None, ""):
            values[field] = caster(raw)

    values.update({k: v for k, v in overrides.items() if k in valid and v is not None})
    cfg = AccountConfig(**values)
    if cfg.risk_pct > cfg.max_risk_pct:
        raise ValueError(
            f"risk_pct {cfg.risk_pct:.2%} exceeds max_risk_pct {cfg.max_risk_pct:.2%}. "
            "Veterans never risk more than 1-2% per trade."
        )
    return cfg
