"""Prompt #4 - The Regime Checker.

    "Analyze the current yield curve, VIX term structure, and DXY.  Are we
     in a Risk-On or Risk-Off macro environment right now?  Give me a
     confidence score."

Each component is scored on [-1, +1] (negative = risk-off), the weighted
composite decides the regime, and the confidence blends the size of the
composite with how many components agree with its sign.  This is also the
input to RULE 3 (the macro regime filter).
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field, asdict
from enum import Enum

import numpy as np
import pandas as pd

from ..indicators import trend_state
from ..data.universe import REGIME_TICKERS


class Regime(str, Enum):
    RISK_ON = "RISK_ON"
    RISK_OFF = "RISK_OFF"
    NEUTRAL = "NEUTRAL"


@dataclass
class RegimeInputs:
    spy: pd.Series                       # SPY closes
    qqq: pd.Series                       # QQQ closes
    vix: pd.Series                       # ^VIX closes
    vix3m: pd.Series | None = None       # ^VIX3M closes (term structure)
    us10y: pd.Series | None = None       # 10y yield in percent (4.25 == 4.25%)
    us3m: pd.Series | None = None        # 3m yield in percent
    dxy: pd.Series | None = None         # Dollar index closes
    tlt: pd.Series | None = None         # long-bond ETF closes (bonds vs stocks)
    sp500_earnings_yield: float | None = None   # e.g. 0.045; compared with the 10y yield


@dataclass
class Component:
    name: str
    score: float           # -1 .. +1
    weight: float
    detail: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class RegimeAssessment:
    regime: Regime
    composite: float       # weighted score in [-1, 1]
    confidence: float      # 0..1
    components: list[Component] = field(default_factory=list)
    as_of: str = ""
    warnings: list[str] = field(default_factory=list)

    @property
    def bearish(self) -> bool:
        return self.regime == Regime.RISK_OFF

    def to_dict(self) -> dict:
        return {
            "regime": self.regime.value,
            "composite": round(self.composite, 3),
            "confidence": round(self.confidence, 3),
            "as_of": self.as_of,
            "components": [c.to_dict() for c in self.components],
            "warnings": self.warnings,
        }

    def summary(self) -> str:
        lines = [
            f"Regime: {self.regime.value}  (composite {self.composite:+.2f}, "
            f"confidence {self.confidence:.0%}) as of {self.as_of}"
        ]
        for c in self.components:
            lines.append(f"  {c.score:+.2f} x{c.weight:.2f}  {c.name:<18} {c.detail}")
        for w in self.warnings:
            lines.append(f"  ! {w}")
        return "\n".join(lines)


def _clip(x: float) -> float:
    return float(max(-1.0, min(1.0, x)))


def _score_trend(close: pd.Series, label: str) -> Component:
    st = trend_state(close)
    score = 0.0
    if st["above_slow"] is not None:
        score += 0.5 if st["above_slow"] else -0.5
    if st["above_fast"] is not None:
        score += 0.25 if st["above_fast"] else -0.25
    if st["downtrend"]:
        score -= 0.25
    elif st["uptrend"]:
        score += 0.25
    structure = "lower highs & lower lows" if st["downtrend"] else "higher highs & higher lows" if st["uptrend"] else "mixed structure"
    detail = (
        f"{label} {st['last']:.2f} vs 50d {st['sma_fast']:.2f} / 200d {st['sma_slow']:.2f}; "
        f"{structure}; 20d {st['return_20d']:+.1%}"
    )
    return Component(f"trend_{label.lower()}", _clip(score), 0.20, detail)


def _score_vix_level(vix: pd.Series) -> Component:
    v = float(vix.iloc[-1])
    v5 = float(vix.iloc[-6]) if len(vix) > 6 else v
    if v < 15:
        score = 1.0
    elif v < 20:
        score = 0.5
    elif v < 25:
        score = 0.0
    elif v < 30:
        score = -0.5
    else:
        score = -1.0
    spike = v / v5 - 1.0 if v5 else 0.0
    if spike > 0.25:       # VIX up >25% in a week is a spike regardless of level
        score = _clip(score - 0.5)
    return Component("vix_level", score, 0.15, f"VIX {v:.1f} ({spike:+.0%} over 5 days)")


def _score_vix_term(vix: pd.Series, vix3m: pd.Series | None) -> Component | None:
    if vix3m is None or vix3m.empty:
        return None
    joined = pd.concat([vix.rename("v"), vix3m.rename("v3")], axis=1).dropna()
    if joined.empty:
        return None
    ratio = float(joined["v"].iloc[-1] / joined["v3"].iloc[-1])
    # contango (VIX < VIX3M) is normal / risk-on; backwardation is stress
    if ratio < 0.85:
        score = 1.0
    elif ratio < 0.95:
        score = 0.5
    elif ratio <= 1.0:
        score = 0.0
    elif ratio <= 1.10:
        score = -0.5
    else:
        score = -1.0
    state = "backwardation" if ratio > 1.0 else "contango"
    return Component("vix_term_structure", score, 0.15, f"VIX/VIX3M {ratio:.2f} ({state})")


def _score_yield_curve(us10y: pd.Series | None, us3m: pd.Series | None) -> Component | None:
    if us10y is None or us3m is None or us10y.empty or us3m.empty:
        return None
    joined = pd.concat([us10y.rename("l"), us3m.rename("s")], axis=1).dropna()
    if joined.empty:
        return None
    spread = float(joined["l"].iloc[-1] - joined["s"].iloc[-1])
    spread_20 = float(joined["l"].iloc[-21] - joined["s"].iloc[-21]) if len(joined) > 21 else spread
    if spread > 1.0:
        score = 0.5
    elif spread > 0.25:
        score = 0.25
    elif spread >= 0.0:
        score = 0.0
    elif spread > -0.5:
        score = -0.25
    else:
        score = -0.5
    # a rapidly steepening curve from inversion (bull steepener) often precedes recessions
    delta = spread - spread_20
    if spread_20 < 0 and delta > 0.4:
        score = _clip(score - 0.25)
    return Component(
        "yield_curve", _clip(score), 0.15,
        f"10y-3m spread {spread:+.2f}% ({'inverted' if spread < 0 else 'positive'}, {delta:+.2f} over 20d)",
    )


def _score_dxy(dxy: pd.Series | None) -> Component | None:
    if dxy is None or len(dxy) < 22:
        return None
    chg = float(dxy.iloc[-1] / dxy.iloc[-21] - 1.0)
    # dollar strength drains global liquidity -> risk-off; scale +/-3% to +/-1
    score = _clip(-chg / 0.03)
    return Component("dollar_dxy", score, 0.15, f"DXY {float(dxy.iloc[-1]):.2f}, {chg:+.1%} over 20 days")


def _score_bonds_vs_stocks(spy: pd.Series, tlt: pd.Series | None,
                           us10y: pd.Series | None, earnings_yield: float | None) -> Component | None:
    details = []
    score = None
    if earnings_yield is not None and us10y is not None and not us10y.empty:
        gap = earnings_yield - float(us10y.iloc[-1]) / 100.0
        score = _clip(gap / 0.02)
        details.append(f"S&P earnings yield {earnings_yield:.2%} vs 10y {float(us10y.iloc[-1]):.2f}% (gap {gap:+.2%})")
    if tlt is not None and len(tlt) >= 22 and len(spy) >= 22:
        rel = float((spy.iloc[-1] / spy.iloc[-21]) / (tlt.iloc[-1] / tlt.iloc[-21]) - 1.0)
        rel_score = _clip(rel / 0.05)
        score = rel_score if score is None else (score + rel_score) / 2
        details.append(f"SPY vs TLT 20d relative {rel:+.1%}")
    if score is None:
        return None
    return Component("bonds_vs_stocks", score, 0.10, "; ".join(details))


def assess_regime(inputs: RegimeInputs, as_of: dt.date | None = None) -> RegimeAssessment:
    comps: list[Component] = [
        _score_trend(inputs.spy, "SPY"),
        _score_trend(inputs.qqq, "QQQ"),
        _score_vix_level(inputs.vix),
    ]
    warnings: list[str] = []
    for maker, name in (
        (lambda: _score_vix_term(inputs.vix, inputs.vix3m), "VIX term structure"),
        (lambda: _score_yield_curve(inputs.us10y, inputs.us3m), "yield curve"),
        (lambda: _score_dxy(inputs.dxy), "DXY"),
        (lambda: _score_bonds_vs_stocks(inputs.spy, inputs.tlt, inputs.us10y, inputs.sp500_earnings_yield), "bonds vs stocks"),
    ):
        c = maker()
        if c is None:
            warnings.append(f"{name} unavailable - excluded from composite")
        else:
            comps.append(c)

    total_w = sum(c.weight for c in comps)
    composite = sum(c.score * c.weight for c in comps) / total_w if total_w else 0.0
    if composite > 0.20:
        regime = Regime.RISK_ON
    elif composite < -0.20:
        regime = Regime.RISK_OFF
    else:
        regime = Regime.NEUTRAL

    sign = np.sign(composite) if regime != Regime.NEUTRAL else 0
    if sign == 0:
        agreement = sum(c.weight for c in comps if abs(c.score) <= 0.25) / total_w
    else:
        agreement = sum(c.weight for c in comps if np.sign(c.score) == sign) / total_w
    confidence = float(min(1.0, 0.5 * min(1.0, abs(composite) / 0.6) + 0.5 * agreement))
    if len(comps) < 5:
        confidence *= 0.8
        warnings.append("fewer than 5 components available; confidence discounted")

    date = as_of or (inputs.spy.index[-1].date() if len(inputs.spy) else dt.date.today())
    return RegimeAssessment(regime, float(composite), confidence, comps, str(date), warnings)


def fetch_regime_inputs(provider, years: int = 2, sp500_earnings_yield: float | None = None) -> RegimeInputs:
    """Pull every regime series through a MarketDataProvider."""
    hist = provider.histories(REGIME_TICKERS.values(), years=years)

    def closes(key: str) -> pd.Series | None:
        df = hist.get(REGIME_TICKERS[key])
        return df["Close"] if df is not None and len(df) else None

    spy, qqq, vix = closes("spy"), closes("qqq"), closes("vix")
    if spy is None or qqq is None or vix is None:
        raise RuntimeError("SPY, QQQ and ^VIX are required for the regime check")
    return RegimeInputs(
        spy=spy, qqq=qqq, vix=vix,
        vix3m=closes("vix3m"), us10y=closes("us10y"), us3m=closes("us3m"),
        dxy=closes("dxy"), tlt=closes("tlt"),
        sp500_earnings_yield=sp500_earnings_yield,
    )
