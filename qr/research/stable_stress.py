"""Stress simulator for the stablecoin yield ladder (`docs/31` §2; Programme 3 piece B).

Not a forecast. A one-year Monte Carlo over *named* loss events per tier,
with every assumption in one table (`ASSUMPTIONS`) so the owner can read
and change them, and three historical events replayed deterministically.
The output is what §2's adjectives ("the risk, named") lack: a loss
distribution per tier — expected return, probability of losing more than
10%, and the average loss in the worst 5% of years (CVaR 5%).

How a year is simulated for a tier: the stated yield accrues; each event
type fires as a Poisson count with its annual rate; each firing draws a
loss-given-event from a triangular distribution (low, mode, high) stated
per event; events that only matter under forced selling (a depeg print
that recovers) are applied with the stated probability that the holder is
forced to sell during it. Nothing here is estimated from data inside the
run: the rates are priors written down with their anchors.

Anchors (all from `docs/31` §2 and its sources): Maple 2022 unsecured
defaults (~$54M of ~$1B outstanding, 5%); USDC at $0.88 for two days in
March 2023 (SVB); USDe printed $0.65 on one exchange's oracle in October
2025 with no protocol loss, and $8.3B of $14B left in two months; Aave v3
has no principal loss; FTX 2022 for exchange failure (one top-5 venue in
~40 venue-years of the top five since 2018, LGD 20–100%); BNB's realised
vol ~60–70% a year.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class Event:
    name: str
    rate_per_year: float            # Poisson rate
    loss_low: float                 # fraction of principal, triangular (low, mode, high)
    loss_mode: float
    loss_high: float
    forced_sale_prob: float = 1.0   # the loss applies only if the holder is forced to realise it (depeg prints that recover)
    anchor: str = ""


@dataclass(frozen=True)
class Tier:
    name: str
    tier: int
    yield_pa: float
    events: tuple[Event, ...] = field(default_factory=tuple)
    price_vol_pa: float = 0.0       # for BNB-denominated parking: annual vol of the staked asset
    note: str = ""


ASSUMPTIONS: tuple[Tier, ...] = (
    Tier("US T-bill (IBKR)", 0, 0.040, (), note="the comparator; no event beyond rates"),
    Tier("Binance Simple Earn flexible USDC/USDT", 1, 0.030, (
        Event("exchange failure / withdrawal halt", 1 / 40, 0.20, 0.60, 1.00, 1.0, "FTX 2022: one failure in ~40 top-5 venue-years since 2018; creditors paid at petition prices years later"),
        Event("USDC/USDT depeg print, recovers", 1 / 3, 0.02, 0.08, 0.15, 0.10, "USDC $0.88 for two days, March 2023; loss only if forced to sell"),
        Event("Earn product gating (days illiquid)", 1 / 2, 0.00, 0.002, 0.01, 1.0, "promo caps, pauses; a time cost, not a principal loss"),
    ), note="custody risk of one venue"),
    Tier("Aave v3 USDC (Base/Arbitrum)", 1, 0.036, (
        Event("smart-contract exploit", 1 / 40, 0.20, 0.60, 1.00, 1.0, "no v3 principal loss in four years at $20B+; blue-chip base rate"),
        Event("bad debt socialised", 1 / 10, 0.001, 0.01, 0.05, 1.0, "CRV November 2023 bad debt on Aave v2, ~0.1% of pool"),
        Event("USDC depeg print, recovers", 1 / 3, 0.02, 0.08, 0.15, 0.10, "as above"),
        Event("L2 sequencer / bridge incident", 1 / 10, 0.00, 0.05, 0.50, 0.3, "bridge hacks 2022; L2 funds usually recoverable"),
    ), note="contract risk, no counterparty"),
    Tier("syrupUSDC (Maple)", 2, 0.050, (
        Event("borrower default in the pool", 1 / 4, 0.01, 0.05, 0.20, 1.0, "2022 unsecured losses ~5% of outstanding; now over-collateralised"),
        Event("smart-contract / delegate failure", 1 / 25, 0.20, 0.60, 1.00, 1.0, "industry base rate"),
        Event("USDC depeg print, recovers", 1 / 3, 0.02, 0.08, 0.15, 0.10, "as above"),
        Event("withdrawal queue (weeks illiquid)", 1 / 2, 0.00, 0.005, 0.03, 1.0, "fixed-term loans: exits queue in stress"),
    ), note="credit risk, curated"),
    Tier("sUSDe (Ethena)", 3, 0.080, (
        Event("funding negative for a quarter (yield < 0)", 1 / 2, 0.01, 0.03, 0.06, 1.0, "2022-style funding regime; reserve fund 1.1% of supply"),
        Event("exchange/custody failure of a hedge venue", 1 / 10, 0.05, 0.15, 0.40, 1.0, "hedges sit on exchanges; FTX-type loss on one venue's share"),
        Event("depeg print on one venue, recovers", 1 / 2, 0.10, 0.25, 0.35, 0.10, "USDe $0.65 October 2025; loss only if liquidated/forced"),
        Event("protocol failure (UST-type)", 1 / 50, 0.80, 0.95, 1.00, 1.0, "UST 2022; different design, kept as the tail"),
    ), note="C1's always-in carry, institutionalised"),
    Tier("Pendle PT on sUSDe (fixed to maturity)", 3, 0.070, (
        Event("funding negative for a quarter (yield < 0)", 1 / 2, 0.01, 0.03, 0.06, 1.0, "inherits sUSDe"),
        Event("exchange/custody failure of a hedge venue", 1 / 10, 0.05, 0.15, 0.40, 1.0, "inherits sUSDe"),
        Event("depeg print on one venue, recovers", 1 / 2, 0.10, 0.25, 0.35, 0.10, "inherits sUSDe"),
        Event("protocol failure (UST-type)", 1 / 50, 0.80, 0.95, 1.00, 1.0, "inherits sUSDe"),
        Event("Pendle contract failure", 1 / 25, 0.20, 0.60, 1.00, 1.0, "industry base rate"),
        Event("early exit at a discount", 1 / 2, 0.01, 0.03, 0.08, 0.5, "secondary exit before maturity in stress"),
    ), note="fixed rate, locked; sUSDe's risks plus Pendle's"),
    Tier("BNB in Simple Earn for HODLer Airdrops", 2, 0.010 + 0.08, (
        Event("exchange failure / withdrawal halt", 1 / 40, 0.20, 0.60, 1.00, 1.0, "as Simple Earn"),
    ), price_vol_pa=0.65, note="yield is BNB rate + airdrops (estimate 8%); principal is BNB"),
)


def simulate(tier: Tier, n_years: int = 20_000, seed: int = 20261001) -> np.ndarray:
    """One-year total return per simulated year, fraction of principal."""
    rng = np.random.default_rng(seed)
    r = np.full(n_years, tier.yield_pa)
    for e in tier.events:
        k = rng.poisson(e.rate_per_year, n_years)
        for i in np.nonzero(k)[0]:
            loss = 0.0
            for _ in range(int(k[i])):
                if rng.random() <= e.forced_sale_prob:
                    loss += rng.triangular(e.loss_low, e.loss_mode, e.loss_high)
            r[i] -= min(loss, 1.0)
    if tier.price_vol_pa > 0:
        r += np.exp(rng.normal(-0.5 * tier.price_vol_pa**2, tier.price_vol_pa, n_years)) - 1.0
    return np.maximum(r, -1.0)


def summarise(r: np.ndarray, principal: float = 1300.0) -> dict:
    s = np.sort(r)
    k = max(int(0.05 * len(s)), 1)
    return {
        "expected_return": float(r.mean()), "median_return": float(np.median(r)),
        "p_loss": float((r < 0).mean()), "p_loss_gt_10pct": float((r < -0.10).mean()),
        "cvar_5": float(s[:k].mean()), "worst_1pct": float(np.quantile(r, 0.01)),
        "expected_usd": float(r.mean() * principal), "cvar_5_usd": float(s[:k].mean() * principal),
    }


def ladder_table(principal: float = 1300.0, n_years: int = 20_000) -> pd.DataFrame:
    rows = []
    for t in ASSUMPTIONS:
        s = summarise(simulate(t, n_years), principal)
        rows.append({"tier": t.tier, "instrument": t.name, "yield_pa": t.yield_pa, **s})
    return pd.DataFrame(rows)


# ---------------------------------------------------------------- replays
REPLAYS = {
    "SVB March 2023 (USDC $0.88, 2 days)": {"USDC-holding tiers, not forced": 0.0, "forced to sell at the trough": -0.12},
    "UST May 2022 (algorithmic, to zero)": {"sUSDe-type design": "n/a — different mechanism; the tail event above keeps it at 2%/yr", "T-bill, Simple Earn, Aave, Maple": 0.0},
    "USDe October 2025 ($0.65 print, one exchange)": {"holder, no leverage": 0.0, "lent as collateral with that oracle, liquidated": -0.35, "Earn on another venue": 0.0},
}
