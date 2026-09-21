"""The position/cash ledger: quantities and cash in, an equity curve out.

`run_backtest` works in weight space — targets, shift, drift, `held ×
returns` — and review 22 (`docs/25` §1.2, 1.3, 1.5) lists what that cannot
represent: cash and a short's liability in the denominator, the two legs of a
carry unit at their own prices, whole shares at a real price with a count
that persists. This engine holds **state** instead — `qty[symbol]`, `cash`,
`nav = cash + Σ qty · price` — and derives weights from it. It produces the
same `BacktestResult` the gates read, and on a clean panel with a
proportional cost model it reproduces the weight runner's curve exactly
(`tests/qr_platform/test_ledger.py`); where it differs, the difference is
the thing the review asked for.

Events, in order, on every bar *t*:

1. **Mark** every position to bar *t*'s close: price P&L. A position whose
   price is not valid on *t* (`Panel.price_valid`) is liquidated at its last
   valid close — the convention the runner keeps for a bucket that stops.
2. **Funding** on held notional at the mark, `rate × qty × price`, with the
   venue's sign: a long pays a positive rate. Gross, not a cost.
3. **Borrow** on short notional at the mark, `borrow_bps_per_year / bars`.
4. **Round-trip exit** for an instrument whose bar *is* the round trip
   (`Strategy.round_trip_each_bar`): the position held over *t* is sold at
   *t*'s mark, so consecutive signals are consecutive fills, not a hold.
5. **Cash interest** at the risk-free rate on the balance carried through
   the bar, when `risk_free` is given; zero otherwise. A negative balance
   pays the same rate — leverage is not free, and it is not modelled as
   cheaper than cash either. Interest is in `nav` and in the
   `cash_interest` series, and **not in `gross` or `net`**: those are the
   active return the gates score, as on the weight engine, and the rate is
   the cash benchmark's job (gate 5). Booking it into gross made a
   near-flat carry book read gross Sharpe 20 on 18 September 2026.
6. **Orders** decided from bar *t*'s targets (for `lag=1`), filled at bar
   *t*'s close, on the bars the strategy's `trades_on` allows. Between marks
   no order is generated, quantities are constant and weights drift by
   themselves. An order needs `tradable()` at its decision bar; otherwise
   it is refused and the position is carried. Fees — per-side bps, per-share
   commission with its floor and cap, half-spread, slippage, impact — leave
   cash at the fill.

**Where a fee is booked.** The runner charges the trade that sets the book
held over bar *t* in bar *t*'s return, and gate 2 reads that split. The
ledger keeps it: an order filled at the close of *t−1* has its fee taken
from cash at the fill, and reported in bar *t*'s `costs`, the bar the
position is held over. `nav[t]` is the account marked at *t*'s close before
that close's orders; `cash[t]` is the balance after them. A forced fill
inside the bar — a liquidation or a round-trip exit — is booked on that bar.

**Prices.** P&L is on the panel's `close`, which for an equity panel is the
total-return series; the *fill price* an order actually gets is
`close_unadjusted` where the loader carries it, `session_close` on the
synthetic overnight and intraday instruments (their `close` is a level, not
a price), and `close` otherwise. Share counts, whole-share flooring and
per-share commissions use the fill price; the quantity carried is in units
of `close`, so a dividend paid between fills accrues to the position as the
adjusted series intends and the share count read back at the next fill is
the real one.

**Two-leg units** (`carry-um`, `xvenue-um`). A unit order becomes one order
per leg — spot buy plus perp sell, or perp/perp — each at its own price,
with its own fee model and its own funding. The unit's return is the sum of
the legs' P&L over NAV; the ratio stays the panel's `close` for signals.
Capital convention: the unit is sized on **spot notional** and the perp's
margin (`margin`, default 100%) is recorded in the report as the reserve
line, not charged to the return; `count_margin=True` sizes the unit on spot
notional plus margin instead, which is the +5%-on-$200 reading of the
acceptance test. A unit's target weight is delivered the way every other
family's is (`unit_sizing="dollars"`): on each decision bar the unit is
re-sized to `w × nav` of spot notional, so the coin's own drift is traded
back like any single leg's. The ratio runner never charged that — the
ratio barely drifts — and on the real carry unit the difference is eight
times the turnover (12.4 vs 1.6 a year, three names, always-in, measured
17 September 2026). `unit_sizing="coins"` instead re-sizes a unit only when
its target changes (entry, exit, a new `n`) and holds the coins between: no
re-hedge cost, but the unit's notional then floats with the coin against a
NAV that does not, which is leverage the margin line would have to carry
(the same smoke: annual vol doubles). It is an option, stated in the
report, not the default. Legs are taken from the cost model (`CostModel.legs`, set
by `carry_pair`) and the panel's `spot_close`; a pair model on a panel
without leg prices, or a single-venue model on a unit panel, runs the unit
as one instrument on the ratio, as the runner does.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

import numpy as np
import pandas as pd

from qr.data.panel import Panel
from qr.execution.costs import BPS, CostModel
from qr.strategies.base import Strategy

__all__ = ["Leg", "run_ledger", "unit_legs"]


@dataclass(frozen=True)
class Leg:
    """One physical instrument behind a (possibly synthetic) panel symbol."""

    name: str
    #: +1 long one unit of the leg per unit of the book, −1 short.
    side: float
    #: bars × symbols, the leg's own price. P&L and notional are on it.
    price: pd.DataFrame
    costs: CostModel
    #: The rate settled per bar on this leg's held notional, venue sign
    #: (a long pays a positive rate). None settles nothing.
    funding: pd.DataFrame | None = None
    #: The real fill price for share counts and per-share commissions; the
    #: leg's `price` when None.
    fill_price: pd.DataFrame | None = None
    #: The real price a round-trip exit gets (the session open on the
    #: overnight instrument); `fill_price` when None.
    exit_price: pd.DataFrame | None = None


def unit_legs(panel: Panel, costs: CostModel) -> list[Leg] | None:
    """The physical legs of a carry or cross-venue unit panel, or None.

    Needs a pair cost model (`costs.legs`) and the panel's `spot_close`.
    The carry unit is long spot at `spot_close`, short the perp at
    `spot_close / close`, funding on the perp leg at `perp_funding_rate`.
    The cross-venue unit's long and short leg are read off the symbol's
    suffix (`-BNBY`: long Binance at `spot_close`, short Bybit at
    `spot_close / close`; `-BYBN` the reverse); its panel carries only the
    *difference* of the two venues' rates, so that is settled on the long
    leg's notional.
    """
    spot = panel.get("spot_close")
    if spot is None or len(costs.legs) != 2:
        return None
    close = panel.close
    symbols = list(close.columns)
    xvenue = all(s.endswith("-BNBY") or s.endswith("-BYBN") for s in symbols) and bool(symbols)
    long_model, short_model = costs.legs
    if xvenue:
        binance = spot  # `spot_close` on the cross-venue unit is Binance's close whichever way round
        long_price = pd.DataFrame(index=close.index, columns=symbols, dtype=float)
        short_price = pd.DataFrame(index=close.index, columns=symbols, dtype=float)
        for s in symbols:
            if s.endswith("-BNBY"):
                long_price[s], short_price[s] = binance[s], binance[s] / close[s]
            else:
                long_price[s], short_price[s] = close[s] * binance[s], binance[s]
        rate = panel.get("funding_rate")
        return [
            Leg("long", +1.0, long_price, long_model, funding=rate),
            Leg("short", -1.0, short_price, short_model),
        ]
    perp = spot / close
    return [
        Leg("spot", +1.0, spot, long_model),
        Leg("perp", -1.0, perp, short_model, funding=panel.get("perp_funding_rate")),
    ]


def _single_leg(panel: Panel, costs: CostModel) -> Leg:
    fill = panel.get("close_unadjusted")
    if fill is None:
        fill = panel.get("session_close")
    exit_price = panel.get("session_open")
    funding = panel.get("funding_rate") if costs.funding else None
    return Leg("book", +1.0, panel.close, costs, funding=funding, fill_price=fill, exit_price=exit_price)


def _rate_per_bar(risk_free, index: pd.DatetimeIndex, periods_per_year: float) -> np.ndarray:
    if risk_free is None:
        return np.zeros(len(index))
    from qr.validate.spa import cash_benchmark

    return cash_benchmark(index, periods_per_year, risk_free).to_numpy(dtype=float)


def run_ledger(
    panel: Panel,
    strategy: Strategy,
    costs: CostModel | None = None,
    universe: pd.DataFrame | None = None,
    equity: float = 10_000.0,
    charge_impact: bool = False,
    lag: int = 1,
    risk_free: pd.Series | float | None = None,
    legs: Sequence[Leg] | None = None,
    margin: float = 1.0,
    count_margin: bool = False,
    unit_sizing: str = "dollars",
):
    """Run one strategy over one panel on the position/cash ledger.

    Arguments match `run_backtest`; `equity` is the opening cash and, unlike
    the runner's constant, compounds. See the module docstring for `legs`,
    `margin` and `count_margin`.
    """
    from qr.research.runner import BacktestResult, volume_adv

    costs = costs or CostModel.trial()
    if lag < 0:
        raise ValueError("lag is a non-negative number of bars")
    if margin < 0:
        raise ValueError("margin is a non-negative fraction of perp notional")
    if unit_sizing not in ("coins", "dollars"):
        raise ValueError("unit_sizing is 'dollars' (deliver the target weight on every decision bar) or 'coins' (re-size only when the target changes)")

    close = panel.close
    index = close.index
    symbols = list(close.columns)
    n, m = close.shape
    ppy = float(panel.periods_per_year)

    if legs is None:
        legs = unit_legs(panel, costs)
    if legs is None:
        legs = [_single_leg(panel, costs)]
    legs = list(legs)
    two_legged = len(legs) > 1

    targets = strategy.target_weights(panel, universe)
    targets = targets.reindex_like(close).fillna(0.0)
    targets = Strategy.mask_to_universe(targets, panel, universe)
    target = targets.to_numpy(dtype=float)
    marks = strategy.trades_on(index) if hasattr(strategy, "trades_on") else None
    mark = np.ones(n, dtype=bool) if marks is None else marks.reindex(index).fillna(False).to_numpy(dtype=bool)
    round_trip = bool(getattr(strategy, "round_trip_each_bar", False))
    whole = bool(costs.whole_shares)

    valid = np.array(panel.price_valid().to_numpy(dtype=bool), copy=True)
    tradable = panel.tradable().to_numpy(dtype=bool)
    prices = [leg.price.reindex_like(close).to_numpy(dtype=float) for leg in legs]
    for p in prices:
        valid &= np.isfinite(p) & (p > 0)
    fills_px = [
        (leg.fill_price.reindex_like(close) if leg.fill_price is not None else leg.price.reindex_like(close)).to_numpy(dtype=float)
        for leg in legs
    ]
    exits_px = [
        (leg.exit_price.reindex_like(close).to_numpy(dtype=float) if leg.exit_price is not None else fills_px[k])
        for k, leg in enumerate(legs)
    ]
    fundings = [
        (leg.funding.reindex_like(close).to_numpy(dtype=float) if leg.funding is not None else None) for leg in legs
    ]
    settles = any(f is not None for f in fundings)
    sides = np.array([leg.side for leg in legs], dtype=float)
    borrow_per_bar = np.array([leg.costs.borrow_bps_per_year * BPS / ppy for leg in legs]) if ppy > 0 else np.zeros(len(legs))
    rf = _rate_per_bar(risk_free, index, ppy)
    scale = 1.0 / (1.0 + margin) if (count_margin and two_legged) else 1.0
    hold_coins = two_legged and unit_sizing == "coins"

    adv = vol = None
    if charge_impact:
        adv_frame = volume_adv(panel)
        if adv_frame is not None:
            adv = adv_frame.reindex_like(close).to_numpy(dtype=float)
            vol = panel.returns().rolling(30, min_periods=5).std().reindex_like(close).to_numpy(dtype=float)

    # -- state ------------------------------------------------------------
    qty = np.zeros(m)  # units of the book (leg k holds sides[k] * qty)
    cash = float(equity)
    last = [np.full(m, np.nan) for _ in legs]  # last valid price per leg
    last0 = [np.zeros(m) for _ in legs]  # the same with 0 for "never priced", for the hot loop
    pending = np.zeros(3)  # commission, spread, impact of the orders at t-1
    pending_notional = 0.0
    nav_prev = float(equity)

    gross = np.zeros(n)
    net = np.zeros(n)
    turnover = np.zeros(n)
    parts = np.zeros((n, 4))  # commission, spread, impact, borrow
    carry = np.zeros(n)
    interest = np.zeros(n)
    nav_path = np.zeros(n)
    cash_path = np.zeros(n)
    qty_path = np.zeros((n, m))
    held = np.zeros((n, m))
    fills: list[tuple] = []  # per (bar, leg): columns of the fills table, see `_fills_frame`

    def leg_fees(k: int, notional: np.ndarray, shares: np.ndarray, t: int) -> np.ndarray:
        """Commission, spread and impact in dollars for one leg's orders on bar t."""
        model = legs[k].costs
        traded = notional.sum()
        out = np.zeros(3)
        if traded <= 0:
            return out
        mult = model.multiplier
        if model.per_share_usd > 0:
            commission = np.abs(shares) * model.per_share_usd
            if model.min_commission_usd > 0:
                commission = np.maximum(commission, model.min_commission_usd)
            if model.max_commission_pct > 0:
                commission = np.minimum(commission, notional * model.max_commission_pct)
            commission = np.where(notional > 0, commission, 0.0)
            out[0] = commission.sum() * mult
            out[1] = traded * mult * (model.half_spread_bps + model.slippage_bps) * BPS
        else:
            out[0] = traded * mult * model.fee_bps * BPS
            out[1] = traded * ((0.0 if model.use_maker else mult * model.half_spread_bps) + mult * model.slippage_bps) * BPS
        if adv is not None and vol is not None:
            bps = model.impact_bps(notional, adv[t], vol[t])
            out[2] = float((notional * np.nan_to_num(bps)).sum() * BPS)
        return out

    def book_fills(t: int, delta: np.ndarray, at: list[np.ndarray], real: list[np.ndarray], reason: str) -> tuple[np.ndarray, float]:
        """Apply `delta` units of the book at each leg's price; returns (fees, unit notional)."""
        nonlocal cash
        fees = np.zeros(3)
        moved = np.abs(delta) > 1e-15
        if not moved.any():
            return fees, 0.0
        for k in range(len(legs)):
            leg_delta = sides[k] * delta
            notional = np.where(moved, np.abs(leg_delta * at[k]), 0.0)
            with np.errstate(divide="ignore", invalid="ignore"):
                shares = np.where(moved & (real[k] > 0), notional / real[k], 0.0)
            cash -= float((leg_delta * np.where(moved, at[k], 0.0)).sum())
            fee = leg_fees(k, notional, shares, t)
            fees += fee
            rows = np.flatnonzero(moved)
            fills.append(
                (
                    np.full(len(rows), t),
                    rows,
                    np.full(len(rows), k),
                    [reason] * len(rows),
                    leg_delta[rows],
                    at[k][rows],
                    np.where(np.isfinite(real[k][rows]), real[k][rows], at[k][rows]),
                    shares[rows],
                    notional[rows],
                )
            )
        cash -= float(fees.sum())
        # a symbol that is not allowed has a NaN price and a zero delta: 0 x NaN
        # is NaN, and one such symbol on a bar turned the whole bar's turnover
        # into NaN (found on the real perp panels, 18 September 2026 — the
        # night5 table's "turnover 0.0" and a $1bn capacity for C1)
        unit_notional = float(np.where(moved, np.abs(delta * at[0]), 0.0).sum())
        return fees, unit_notional

    for t in range(n):
        held[t] = qty * last0[0] / nav_prev if nav_prev > 0 else 0.0
        qty_path[t] = qty
        forced = np.zeros(3)
        forced_notional = 0.0

        # 1. mark; a held position with no valid price goes at its last close
        gone = (np.abs(qty) > 0) & ~valid[t]
        if gone.any():
            delta = np.where(gone, -qty, 0.0)
            fee, notional = book_fills(t, delta, last, last, "no_price")
            forced += fee
            forced_notional += notional
            qty = qty + delta
        pnl = 0.0
        for k, p in enumerate(prices):
            move = np.where(valid[t] & np.isfinite(last[k]), p[t] - last[k], 0.0)
            pnl += float((sides[k] * qty * move).sum())
            last[k] = np.where(valid[t], p[t], last[k])
            last0[k] = np.where(np.isfinite(last[k]), last[k], 0.0)
        # 2. funding on held notional at the mark, venue sign
        funding_flow = 0.0
        for k, f in enumerate(fundings):
            if f is None:
                continue
            rate = np.nan_to_num(f[t])
            funding_flow -= float((rate * sides[k] * qty * last0[k]).sum())
        cash += funding_flow
        # 3. borrow on short notional at the mark
        borrow = 0.0
        for k in range(len(legs)):
            if borrow_per_bar[k] > 0:
                short = np.minimum(sides[k] * qty, 0.0)
                borrow += float((np.abs(short) * last0[k]).sum() * borrow_per_bar[k])
        cash -= borrow
        # 4. an instrument whose bar is the round trip is flat by the mark
        if round_trip and np.abs(qty).sum() > 0:
            fee, notional = book_fills(t, -qty, last, exits_px_at(exits_px, t, fills_px), "round_trip_exit")
            forced += fee
            forced_notional += notional
            qty = np.zeros(m)
        # 5. interest on the balance carried through the bar
        paid = cash * rf[t]
        cash += paid

        nav = cash + sum(float((sides[k] * qty * last0[k]).sum()) for k in range(len(legs)))
        nav_path[t] = nav
        if nav_prev > 0:
            # cash interest is in NAV and reported on its own; it is *not* in
            # gross or net, which stay the active return the gates score —
            # found on 18 September 2026 when a cross-venue book with ~100%
            # cash read gross Sharpe 20 and gate-3 t 11.6: the T-bill rate's
            # t-statistic, tripping gate 1's ceiling. The cash benchmark is
            # where the rate belongs, and gate 5 already compares to it.
            gross[t] = (pnl + funding_flow) / nav_prev
            carry[t] = funding_flow / nav_prev
            interest[t] = paid / nav_prev
            parts[t, :3] = (pending + forced) / nav_prev
            parts[t, 3] = borrow / nav_prev
            turnover[t] = (pending_notional + forced_notional) / nav_prev
            net[t] = (nav - paid) / nav_prev - 1.0
        pending = np.zeros(3)
        pending_notional = 0.0

        # 6. orders: the book to hold over t+1 is decided at bar t+1-lag
        decision = t + 1 - lag
        if t + 1 < n and mark[t + 1] and 0 <= decision < n and nav > 0:
            want = target[decision] * nav * scale
            allowed = tradable[decision] & valid[t]
            if hold_coins:
                # `unit_sizing="coins"`: a unit is re-sized only when the
                # strategy's target for it changes (entry, exit, a new n), not
                # because the coin moved. See the module docstring for what
                # that trades away.
                previous = target[decision - 1] if decision > 0 else np.zeros(m)
                allowed &= np.abs(target[decision] - previous) > 1e-12
            with np.errstate(divide="ignore", invalid="ignore"):
                if whole:
                    real = fills_px[0][t]
                    shares = np.floor(np.abs(want) / np.where(real > 0, real, np.nan))
                    new = np.sign(want) * shares * real / prices[0][t]
                else:
                    new = want / prices[0][t]
            new = np.where(allowed & np.isfinite(new), new, qty)
            delta = new - qty
            at = [np.where(allowed, p[t], np.nan) for p in prices]
            real_px = [np.where(allowed, fp[t], np.nan) for fp in fills_px]
            fee, notional = book_fills(t, delta, at, real_px, "target")
            pending = fee
            pending_notional = notional
            qty = new
        cash_path[t] = cash
        nav_prev = nav

    cost_parts = pd.DataFrame(parts, index=index, columns=["commission", "spread", "impact", "borrow"])
    cost = cost_parts.sum(axis=1).rename("cost")
    gross_s = pd.Series(gross, index=index, name="gross")
    net_s = pd.Series(net, index=index, name="net")
    held_frame = pd.DataFrame(held, index=index, columns=symbols)
    fills_frame = _fills_frame(fills, index, symbols, [leg.name for leg in legs])
    return BacktestResult(
        name=strategy.name,
        gross=gross_s,
        net=net_s,
        costs=cost,
        cost_parts=cost_parts,
        carry=pd.Series(carry, index=index, name="carry") if settles else None,
        turnover=pd.Series(turnover, index=index, name="turnover"),
        weights=targets,
        held=held_frame,
        periods_per_year=ppy,
        nav=pd.Series(nav_path, index=index, name="nav"),
        cash=pd.Series(cash_path, index=index, name="cash"),
        quantities=pd.DataFrame(qty_path, index=index, columns=symbols),
        fills=fills_frame,
        cash_interest=pd.Series(interest, index=index, name="cash_interest") if risk_free is not None else None,
        meta={
            "engine": "ledger",
            "strategy": strategy.describe(),
            "costs": costs.describe(),
            "lag": lag,
            "symbols": symbols,
            "start": str(index[0]) if n else None,
            "end": str(index[-1]) if n else None,
            "opening_cash": float(equity),
            "closing_nav": float(nav_path[-1]) if n else float(equity),
            "legs": [leg.name for leg in legs],
            "fill_price_field": _fill_field(panel, two_legged),
            "risk_free": "none" if risk_free is None else ("series" if not np.isscalar(risk_free) else float(risk_free)),
            "capital_convention": {
                "sized_on": "spot notional plus perp margin" if (count_margin and two_legged) else ("spot notional" if two_legged else "nav"),
                "perp_margin": float(margin) if two_legged else 0.0,
                "reserve_per_unit_notional": float(margin) if two_legged and not count_margin else 0.0,
                "unit_sizing": (unit_sizing if two_legged else "n/a"),
            },
            "fills": int(len(fills_frame)),
        },
    )


def _fills_frame(fills: list[tuple], index: pd.DatetimeIndex, symbols: list[str], leg_names: list[str]) -> pd.DataFrame:
    """One row per fill: bar, symbol, leg, reason, units, price, fill_price, shares, notional."""
    columns = ["bar", "symbol", "leg", "reason", "units", "price", "fill_price", "shares", "notional"]
    if not fills:
        return pd.DataFrame(columns=columns)
    bar = np.concatenate([f[0] for f in fills]).astype(int)
    sym = np.concatenate([f[1] for f in fills]).astype(int)
    leg = np.concatenate([f[2] for f in fills]).astype(int)
    reason = [r for f in fills for r in f[3]]
    numeric = [np.concatenate([f[i] for f in fills]).astype(float) for i in range(4, 9)]
    return pd.DataFrame(
        {
            "bar": index[bar],
            "symbol": np.asarray(symbols, dtype=object)[sym],
            "leg": np.asarray(leg_names, dtype=object)[leg],
            "reason": reason,
            "units": numeric[0],
            "price": numeric[1],
            "fill_price": numeric[2],
            "shares": numeric[3],
            "notional": numeric[4],
        },
        columns=columns,
    )


def exits_px_at(exits: list[np.ndarray], t: int, fills: list[np.ndarray]) -> list[np.ndarray]:
    """The real exit price on bar t per leg: the session open where it exists, else the fill price."""
    return [np.where(np.isfinite(e[t]), e[t], f[t]) for e, f in zip(exits, fills)]


def _fill_field(panel: Panel, two_legged: bool) -> str:
    if two_legged:
        return "leg prices"
    for name in ("close_unadjusted", "session_close"):
        if panel.get(name) is not None:
            return name
    return "close"
