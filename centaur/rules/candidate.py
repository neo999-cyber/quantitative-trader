"""The object that goes through the gauntlet.

An AI screen (or the human) fills this in.  Everything the five rules need
lives here so the rulebook stays a set of pure functions.
"""
from __future__ import annotations

import datetime as dt
import json
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path


class SignalCategory(str, Enum):
    TECHNICAL = "technical"            # price/volume structure: MA bounce, breakout, capitulation
    FUNDAMENTAL = "fundamental"        # buybacks, guidance raise, earnings beat, valuation
    SENTIMENT_FLOW = "sentiment_flow"  # options flow, insider buying, short interest, positioning
    MACRO = "macro"                    # sector rotation, rates, regime tailwind
    STATISTICAL = "statistical"        # backtested edge of the setup itself


class Direction(str, Enum):
    LONG = "long"
    SHORT = "short"


@dataclass
class Signal:
    category: SignalCategory
    description: str
    source: str = ""          # where it came from: "pattern_matcher", "options_flow", "human", ...

    @classmethod
    def parse(cls, text: str, source: str = "") -> "Signal":
        """Parse "category: description" strings the screens emit."""
        if ":" in text:
            cat, desc = text.split(":", 1)
            try:
                return cls(SignalCategory(cat.strip().lower()), desc.strip(), source)
            except ValueError:
                pass
        return cls(SignalCategory.TECHNICAL, text.strip(), source)

    def to_dict(self) -> dict:
        return {"category": self.category.value, "description": self.description, "source": self.source}


@dataclass
class TradeCandidate:
    ticker: str
    entry: float
    stop: float
    target: float
    direction: Direction = Direction.LONG
    signals: list[Signal] = field(default_factory=list)
    catalyst: str = ""                                   # WHY is it moving now?
    avg_dollar_volume: float | None = None               # 20-day average $ volume
    resistance_levels: list[float] = field(default_factory=list)   # overhead supply (longs)
    support_levels: list[float] = field(default_factory=list)      # underfoot demand (shorts)
    next_earnings: dt.date | None = None
    holding_days: int | None = None                      # planned horizon; default from config
    defensive: bool = False                              # a defensive, highest-conviction setup?
    conviction: str = "normal"                           # "normal" | "high"
    notes: str = ""
    ai_thesis: str = ""                                  # what the AI said, verbatim-ish, for the journal

    # ------------------------------------------------------------------ #
    @property
    def is_long(self) -> bool:
        return self.direction == Direction.LONG

    @property
    def risk_per_share(self) -> float:
        return abs(self.entry - self.stop)

    @property
    def reward_per_share(self) -> float:
        return abs(self.target - self.entry)

    @property
    def reward_risk(self) -> float:
        return self.reward_per_share / self.risk_per_share if self.risk_per_share else float("inf")

    def validate(self) -> list[str]:
        problems: list[str] = []
        if self.entry <= 0 or self.stop <= 0 or self.target <= 0:
            problems.append("entry, stop and target must be positive")
        if self.is_long:
            if not self.stop < self.entry:
                problems.append("long trade: stop must be below entry")
            if not self.target > self.entry:
                problems.append("long trade: target must be above entry")
        else:
            if not self.stop > self.entry:
                problems.append("short trade: stop must be above entry")
            if not self.target < self.entry:
                problems.append("short trade: target must be below entry")
        return problems

    # ------------------------------------------------------------------ #
    def to_dict(self) -> dict:
        d = asdict(self)
        d["direction"] = self.direction.value
        d["signals"] = [s.to_dict() for s in self.signals]
        d["next_earnings"] = self.next_earnings.isoformat() if self.next_earnings else None
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "TradeCandidate":
        d = dict(d)
        sigs = []
        for s in d.pop("signals", []) or []:
            if isinstance(s, str):
                sigs.append(Signal.parse(s))
            else:
                sigs.append(Signal(SignalCategory(s["category"]), s["description"], s.get("source", "")))
        ne = d.pop("next_earnings", None)
        direction = Direction(str(d.pop("direction", "long")).lower())
        known = {f for f in cls.__dataclass_fields__}
        extra = {k: v for k, v in d.items() if k not in known}
        d = {k: v for k, v in d.items() if k in known}
        cand = cls(direction=direction, signals=sigs,
                   next_earnings=dt.date.fromisoformat(ne) if ne else None, **d)
        if extra:
            cand.notes = (cand.notes + " " if cand.notes else "") + f"(ignored fields: {sorted(extra)})"
        return cand

    @classmethod
    def load(cls, path: str | Path) -> "TradeCandidate":
        with open(path) as fh:
            return cls.from_dict(json.load(fh))

    def save(self, path: str | Path) -> None:
        with open(path, "w") as fh:
            json.dump(self.to_dict(), fh, indent=2)
