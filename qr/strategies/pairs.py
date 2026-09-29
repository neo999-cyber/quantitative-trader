"""Perp pairs mean reversion (`docs/prereg/p2_perp_pairs_v1.md`): family C7.

Two economically linked perpetuals — the same layer, the same sector, the
same narrative — whose log-price spread wanders and comes back. The claim
is not cointegration as a theorem but a tradeable, low-turnover reversion:
when the spread is `entry` standard deviations from its `lookback` mean,
sell the rich leg and buy the cheap one, dollar-neutral through the
rolling hedge ratio, and unwind when it is back within `exit_z` or after
`max_hold` bars, whichever first. Everything is computed from bars up to
and including the decision bar; the runner shifts one bar.

The **pair list is frozen** in the pre-registration (`LINKED`), and the
control is the same rule on pairs drawn at random from the same names
(`random_pairs`): if unrelated pairs revert as much, the story is "any
spread reverts" and not the economic link.

A **half-life filter** keeps the family out of pairs whose spread is not
reverting over the window: the AR(1) coefficient of the spread over
`lookback` bars must give a half-life of at most `lookback / 2` bars
(ρ < 0.95 too), computed rolling and past-only. A cointegration test would
say the same thing at a hundred times the cost per bar; this is the cheap
proxy the memo names.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from qr.data.panel import Panel
from qr.strategies.base import Strategy

#: The economically linked pairs, frozen 18 September 2026 (all in the lake with >= 700 days of overlap).
LINKED = (
    ("SOLUSDT", "AVAXUSDT"), ("NEARUSDT", "APTUSDT"), ("ARBUSDT", "OPUSDT"), ("ETHUSDT", "BTCUSDT"),
    ("LTCUSDT", "BCHUSDT"), ("DOGEUSDT", "1000SHIBUSDT"), ("UNIUSDT", "AAVEUSDT"), ("SUIUSDT", "APTUSDT"),
    ("LINKUSDT", "DOTUSDT"), ("ADAUSDT", "XRPUSDT"), ("FILUSDT", "ARUSDT"), ("ETCUSDT", "LTCUSDT"),
    ("XLMUSDT", "XRPUSDT"), ("INJUSDT", "SEIUSDT"), ("STXUSDT", "ORDIUSDT"), ("PENDLEUSDT", "AAVEUSDT"),
    ("LDOUSDT", "RPLUSDT"), ("CRVUSDT", "CVXUSDT"), ("GMXUSDT", "DYDXUSDT"), ("ZECUSDT", "XMRUSDT"),
)


def random_pairs(symbols: list[str], n: int = 20, seed: int = 20260918) -> tuple[tuple[str, str], ...]:
    """`n` disjoint pairs drawn at random from `symbols`, excluding the linked ones. The control."""
    rng = np.random.default_rng(seed)
    linked = {frozenset(p) for p in LINKED}
    pool = list(symbols)
    out: list[tuple[str, str]] = []
    for _ in range(10_000):
        if len(out) >= n or len(pool) < 2:
            break
        a, b = rng.choice(pool, size=2, replace=False)
        if frozenset((a, b)) in linked:
            continue
        out.append((str(a), str(b)))
        pool.remove(a)
        pool.remove(b)
    return tuple(out)


class PerpPairs(Strategy):
    family = "perp_pairs"

    def __init__(
        self,
        lookback: int = 90,
        entry: float = 2.0,
        exit_z: float = 0.5,
        max_hold: int = 10,
        n_max: int = 10,
        gross: float = 1.0,
        pairs: str = "linked",
        seed: int = 20260918,
    ) -> None:
        if lookback < 20 or entry <= exit_z or exit_z < 0 or max_hold < 1 or n_max < 1 or gross <= 0:
            raise ValueError("lookback >= 20, entry > exit_z >= 0, max_hold >= 1, n_max >= 1, gross > 0")
        if pairs not in ("linked", "random"):
            raise ValueError("pairs is 'linked' (the family) or 'random' (the control)")
        super().__init__(lookback=int(lookback), entry=float(entry), exit_z=float(exit_z), max_hold=int(max_hold),
                         n_max=int(n_max), gross=float(gross), pairs=pairs, seed=int(seed))

    def pair_list(self, panel: Panel) -> tuple[tuple[str, str], ...]:
        if self.params["pairs"] == "linked":
            return tuple(p for p in LINKED if p[0] in panel.symbols and p[1] in panel.symbols)
        return random_pairs(panel.symbols, n=len(LINKED), seed=self.params["seed"])

    def target_weights(self, panel: Panel, universe: pd.DataFrame | None = None) -> pd.DataFrame:
        p = self.params
        L = p["lookback"]
        close = panel.close
        tradable = panel.tradable()
        if universe is not None:
            tradable = tradable & universe.reindex_like(tradable).fillna(False).astype(bool)
        logp = np.log(close.where(close > 0))
        weights = pd.DataFrame(0.0, index=close.index, columns=close.columns)
        n = len(close)
        pairs = self.pair_list(panel)
        signals: dict[tuple[str, str], np.ndarray] = {}   # pair -> per-bar desired position: +1 long a/short b, -1, 0
        betas: dict[tuple[str, str], np.ndarray] = {}
        for a, b in pairs:
            la, lb = logp[a].to_numpy(), logp[b].to_numpy()
            ok = np.isfinite(la) & np.isfinite(lb) & tradable[a].to_numpy() & tradable[b].to_numpy()
            beta = np.full(n, np.nan)
            z = np.full(n, np.nan)
            reverting = np.zeros(n, dtype=bool)
            for t in range(L, n):
                w = slice(t - L + 1, t + 1)
                if not ok[w].all():
                    continue
                x, y = lb[w], la[w]
                vx = x.var()
                if vx <= 0:
                    continue
                bt = ((x - x.mean()) * (y - y.mean())).sum() / (vx * L)
                if not (0.25 <= bt <= 4.0):
                    continue
                s = y - bt * x
                sd = s.std()
                if sd <= 0:
                    continue
                # AR(1) of the spread over the window: half-life <= L/2 and rho < 0.95
                s0, s1 = s[:-1] - s[:-1].mean(), s[1:] - s[1:].mean()
                den = (s0 * s0).sum()
                rho = (s0 * s1).sum() / den if den > 0 else 1.0
                if not (-1.0 < rho < 0.95) or (rho > 0 and np.log(0.5) / np.log(rho) > L / 2):
                    continue
                beta[t] = bt
                z[t] = (s[-1] - s.mean()) / sd
                reverting[t] = True
            pos = np.zeros(n)
            state, held = 0.0, 0
            for t in range(n):
                if state != 0.0:
                    held += 1
                    back = reverting[t] and np.isfinite(z[t]) and abs(z[t]) <= p["exit_z"]
                    if back or held >= p["max_hold"] or not ok[t]:
                        state, held = 0.0, 0  # flat over the next bar; a re-entry waits for the bar after
                        continue
                    pos[t] = state
                    continue
                if reverting[t] and np.isfinite(z[t]):
                    if z[t] >= p["entry"]:
                        state = -1.0  # a rich: short a, long b
                    elif z[t] <= -p["entry"]:
                        state = +1.0
                    held = 0
                pos[t] = state
            signals[(a, b)] = pos
            betas[(a, b)] = beta
        # up to n_max open pairs a bar, in the frozen list's order; legs dollar-neutral through beta
        col = {c: i for i, c in enumerate(weights.columns)}
        out = np.zeros((n, len(weights.columns)))
        for t in range(n):
            live = [(pr, pos[t]) for pr, pos in signals.items() if pos[t] != 0]
            if not live:
                continue
            live = live[: p["n_max"]]
            per_pair = 1.0 / len(live)
            for (a, b), side in live:
                bt = betas[(a, b)][t] if np.isfinite(betas[(a, b)][t]) else 1.0
                out[t, col[a]] += side * per_pair / (1.0 + bt)
                out[t, col[b]] += -side * per_pair * bt / (1.0 + bt)
        weights = pd.DataFrame(out, index=close.index, columns=close.columns).where(tradable, 0.0)
        return self.normalise(weights, p["gross"])
