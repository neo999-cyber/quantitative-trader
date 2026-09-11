"""Cost models. Gate 2 (cost survival) is decided here, so the defaults are
deliberately pessimistic and every number is named and sourced.

A trade pays three things, all expressed in basis points of traded notional:

* **fee** — the venue's schedule, per side. Binance spot is a flat 0.10% for
  VIP0 and drops with 30-day volume or by paying fees in BNB (−25%).
* **spread** — crossing the book costs roughly half the quoted spread per side.
  Taker orders always pay it; a maker order that actually rests earns it back,
  which is why `maker` is a separate, and by default unused, path.
* **impact** — the square-root law, Δ = coef · σ · √(Q/V): pushing size through
  a book moves it, superlinearly in participation. At the sizes this platform
  trades it is small, and it is the term that decides capacity.

Nothing here charges funding: this is a **spot** model. Perps add a funding leg
and get their own model (`PerpCostModel`) when Phase 4 needs it.

The fee schedule below is a snapshot and must be re-verified against
<https://www.binance.com/en/fee/schedule> before a cost model is frozen for a
live strategy — `verified_on` records when it last was, and it travels with the
model into the trial log so a Hypothesis Report can never quietly cite an
unverified fee.

`trial_costs()` is the one the crypto trial runs on: VIP0 with the BNB discount
on, checked against the account's own fee panel on 2026-09-11.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
import numpy as np
import pandas as pd

BPS = 1e-4


@dataclass(frozen=True)
class BinanceSpotFees:
    """Binance spot fee schedule, in basis points per side.

    Snapshot of the public VIP schedule. `bnb_discount` applies the 25% rebate
    for paying fees in BNB; `verified_on` is the date a human last checked it.
    """

    maker_bps: float
    taker_bps: float
    tier: str = "VIP0"
    bnb_discount: bool = False
    verified_on: str = "unverified"

    @classmethod
    def tier_table(cls) -> dict[str, tuple[float, float]]:
        return {
            "VIP0": (10.0, 10.0),
            "VIP1": (9.0, 10.0),
            "VIP2": (8.0, 10.0),
            "VIP3": (7.0, 9.0),
            "VIP4": (7.0, 9.0),
            "VIP5": (6.0, 8.0),
            "VIP6": (5.0, 7.0),
            "VIP7": (4.0, 6.0),
            "VIP8": (2.0, 4.0),
            "VIP9": (2.0, 4.0),
        }

    @classmethod
    def for_tier(cls, tier: str = "VIP0", bnb_discount: bool = False, verified_on: str = "unverified"):
        table = cls.tier_table()
        key = tier.upper()
        if key not in table:
            raise ValueError(f"unknown Binance spot tier {tier!r}; known: {sorted(table)}")
        maker, taker = table[key]
        if bnb_discount:
            maker, taker = maker * 0.75, taker * 0.75
        return cls(maker, taker, key, bnb_discount, verified_on)


#: The account's own fee panel, read on this date: 30-day volume 0.00 USD, so
#: VIP0, with the BNB fee discount switched on -> 0.07500% maker and taker.
TRIAL_FEE_TIER = "VIP0"
TRIAL_BNB_DISCOUNT = True
TRIAL_FEES_VERIFIED_ON = "2026-09-11"

#: Half the quoted spread, per side. 2 bps is a deliberately pessimistic stand-in
#: for the top-30 USDT pairs, which mostly quote inside 1 bp; it is the number to
#: replace first once the bucket's 1h bars give a real intrabar spread estimate.
TRIAL_HALF_SPREAD_BPS = 2.0


@dataclass(frozen=True)
class CostModel:
    """Per-side transaction costs in basis points of traded notional.

    `charge()` takes a turnover matrix — the absolute change in each position's
    weight at each bar — and returns the portfolio return drag per bar.
    """

    fee_bps: float = 10.0
    half_spread_bps: float = 2.0
    impact_coef: float = 1.0
    use_maker: bool = False
    multiplier: float = 1.0
    name: str = "binance_spot_vip0_taker"
    verified_on: str = "unverified"

    @classmethod
    def binance_spot(
        cls,
        tier: str = "VIP0",
        bnb_discount: bool = False,
        half_spread_bps: float = 2.0,
        impact_coef: float = 1.0,
        verified_on: str = "unverified",
    ) -> "CostModel":
        fees = BinanceSpotFees.for_tier(tier, bnb_discount, verified_on)
        suffix = "_bnb" if bnb_discount else ""
        return cls(
            fee_bps=fees.taker_bps,
            half_spread_bps=half_spread_bps,
            impact_coef=impact_coef,
            name=f"binance_spot_{fees.tier.lower()}{suffix}_taker",
            verified_on=verified_on,
        )

    @classmethod
    def trial(cls, half_spread_bps: float = TRIAL_HALF_SPREAD_BPS, impact_coef: float = 1.0) -> "CostModel":
        """The crypto trial's frozen cost model. Every gate is judged against this.

        VIP0 + BNB discount = 7.5 bps of fee per side, plus the half-spread, so
        9.5 bps per side and 19 bps for a round trip. Gate 2 additionally
        requires the edge to survive `stressed(2.0)`, i.e. 38 bps a round trip.
        """
        return cls.binance_spot(
            tier=TRIAL_FEE_TIER,
            bnb_discount=TRIAL_BNB_DISCOUNT,
            half_spread_bps=half_spread_bps,
            impact_coef=impact_coef,
            verified_on=TRIAL_FEES_VERIFIED_ON,
        )

    @property
    def linear_bps(self) -> float:
        """Everything that does not depend on size: fee plus the half-spread."""
        fee = self.fee_bps  # taker; a maker path would net the spread back
        return self.multiplier * (fee + (0.0 if self.use_maker else self.half_spread_bps))

    def stressed(self, multiplier: float) -> "CostModel":
        """Gate 2 asks whether the edge survives 2x costs. This is that knob."""
        return replace(self, multiplier=self.multiplier * float(multiplier))

    def impact_bps(
        self,
        turnover_notional: pd.DataFrame | np.ndarray,
        adv_notional: pd.DataFrame | np.ndarray,
        volatility: pd.DataFrame | np.ndarray,
    ) -> np.ndarray:
        """Square-root impact: coef · σ · √(traded / ADV), in basis points.

        `volatility` is a per-bar return standard deviation (a fraction, not
        bps). Bars with no ADV get no impact charge and no free lunch either:
        they should have been filtered out by the liquidity screen upstream.
        """
        traded = np.asarray(turnover_notional, dtype=float)
        adv = np.asarray(adv_notional, dtype=float)
        sigma = np.asarray(volatility, dtype=float)
        with np.errstate(divide="ignore", invalid="ignore"):
            participation = np.where(adv > 0, traded / adv, 0.0)
        participation = np.nan_to_num(participation, nan=0.0, posinf=0.0)
        sigma = np.nan_to_num(sigma, nan=0.0, posinf=0.0)
        return self.multiplier * self.impact_coef * sigma * np.sqrt(participation) / BPS

    def charge(
        self,
        turnover: pd.DataFrame,
        equity: pd.Series | float | None = None,
        adv_notional: pd.DataFrame | None = None,
        volatility: pd.DataFrame | None = None,
    ) -> pd.Series:
        """Return drag per bar, as a positive fraction of equity.

        `turnover` is |Δweight| per asset per bar. With `equity`, `adv_notional`
        and `volatility` supplied, the square-root impact term is added on top
        of the linear one; without them the model is linear, which is the right
        default while position sizes are small relative to Binance's book.
        """
        linear = turnover.sum(axis=1) * self.linear_bps * BPS
        if adv_notional is None or volatility is None or equity is None:
            return linear.rename("cost")
        eq = pd.Series(equity, index=turnover.index) if np.isscalar(equity) else equity.reindex(turnover.index)
        traded_notional = turnover.mul(eq, axis=0)
        adv = adv_notional.reindex_like(turnover)
        vol = volatility.reindex_like(turnover)
        imp_bps = self.impact_bps(traded_notional, adv, vol)
        impact = pd.DataFrame(imp_bps, index=turnover.index, columns=turnover.columns)
        impact = (turnover * impact).sum(axis=1) * BPS
        return (linear + impact).rename("cost")

    def describe(self) -> dict[str, float | str | bool]:
        return {
            "name": self.name,
            "fee_bps": self.fee_bps,
            "half_spread_bps": self.half_spread_bps,
            "impact_coef": self.impact_coef,
            "use_maker": self.use_maker,
            "multiplier": self.multiplier,
            "linear_bps_per_side": self.linear_bps,
            "fees_verified_on": self.verified_on,
        }
