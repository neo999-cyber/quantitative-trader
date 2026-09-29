"""The carry unit: long one unit of spot, short one unit of the perpetual.

Programme 2, family C1 (`docs/20_PROGRAMME_2.md` §5). The forced trader is
the levered long paying funding; the trade that collects it is delta-neutral,
long spot against short perp, and it earns three things: the funding the perp
pays, the change in the basis (perp over spot), and nothing else. Every other
family in this repository is a book of single legs; this one is a book of
pairs, and the cleanest way to run a pair through an engine built for legs is
to make the pair a synthetic instrument with a price of its own.

**The unit's price is the ratio spot / perp.** Its percentage change,
(1 + r_spot) / (1 + r_perp) − 1, is the return of one dollar long spot against
one dollar short perp *to second order*: the exact one-bar return of that
pair is r_spot − r_perp, and the ratio understates it by r_perp·(r_spot −
r_perp)/(1 + r_perp). Measured on the daily units on 17 September 2026 (review
22, §1.3): mean +0.13 bps a bar in the ratio's favour, 99th percentile of the
gap 5 bps, and the exact pair's daily volatility is 142 bps against the
ratio's 133 — so a Sharpe read off the ratio is ~7% high on the daily unit.
The ratio is kept as the *price* because a synthetic instrument needs one;
the per-leg dollar ledger the review asks for is the fix, not a re-labelling
(`docs/25`). The denominator is one dollar of spot notional: perp margin and
the cash reserve are the capital-committed line of gate 2, not part of the
return. The basis itself is
carried as a feature (`basis` = perp / spot − 1) because a family that enters
on funding should be able to see what it is paying in basis to get it.

**Funding changes sign.** The runner's convention (`runner.funding_pnl`) is
the venue's: a long weight pays a positive rate. The unit is *short* the perp,
so a positive perp rate is a receipt. The panel therefore carries the rate
already flipped in `funding_rate` — what one unit of the position pays per
bar, negative when it is being paid — and the perp's own rate untouched in
`perp_funding_rate`, which is the signal. Two fields with two names, so
neither is ever read with the other's sign.

**The spot leg's close is carried as `spot_close`** so a universe can apply
its volatility floor to the coin rather than to the basis, which is what the
floor is for (pegs out, speculable coins in).

**Liquidity is the thinner leg.** `quote_volume` is the smaller of the two
markets' quote volumes: a pair trades only as easily as its illiquid side.

Reads three things the lake already holds — spot bars (`market="spot"`),
perp bars (`market="futures/um"`, from `qr data ingest --market futures/um`)
and the daily funding feature (`market="futures-um"`, from `qr data
funding-ingest`) — and writes the unit's bars back as klines under
`market="carry-um"`, so `qr gates --market carry-um` loads it like any other
panel and the manifest records exactly which bytes it was built from.
"""
from __future__ import annotations

import logging
from typing import Iterable

import pandas as pd

from qr.data.funding import MARKET as FUNDING_MARKET
from qr.execution.audit import redenomination_bars

log = logging.getLogger(__name__)

PERP_MARKET = "futures/um"
CARRY_MARKET = "carry-um"
SPOT_MARKET = "spot"


def carry_frames(spot: pd.DataFrame, perp: pd.DataFrame, funding: pd.DataFrame | None) -> pd.DataFrame:
    """One symbol's carry-unit bars from its spot bars, perp bars and funding.

    The index is the intersection of spot and perp dates: a unit needs both
    legs to exist. Funding is left-joined onto it and, where the bucket is
    silent, left missing — the runner settles nothing on a missing rate,
    which is the honest reading of "not published" (`runner.funding_pnl`).
    """
    index = spot.index.intersection(perp.index)
    s = spot.reindex(index)
    p = perp.reindex(index)
    ratio = s["close"] / p["close"]
    open_ratio = s["open"] / p["open"]
    # A redenomination that reaches spot and perp on different days puts the
    # ratio off by its factor for a few bars and then back. Those bars are
    # not prices of the unit and are left empty, so the unit is not tradable
    # on them (`Panel.tradable`) and a book is liquidated at its last real
    # close rather than credited with a 1000x move. See `redenomination_bars`.
    artefact = redenomination_bars(ratio)
    if bool(artefact.any()):
        ratio = ratio.where(~artefact)
        open_ratio = open_ratio.where(~artefact)
    quote_volume = pd.concat([s["quote_volume"], p["quote_volume"]], axis=1).min(axis=1)
    # The unit's intraday extremes are not observed (the legs' highs and lows
    # need not coincide), so its high and low are the bracket of what *is*
    # observed: its open and its close. Setting both to the close, as the
    # first version did, made `Panel.tradable()` reject every bar whose open
    # differed from its close — which is nearly all of them — and the
    # carry_top40 universe read empty on 2026-09-15 before any run.
    out = pd.DataFrame(
        {
            "open": open_ratio,
            "high": pd.concat([open_ratio, ratio], axis=1).max(axis=1),
            "low": pd.concat([open_ratio, ratio], axis=1).min(axis=1),
            "close": ratio,
            # Base volume is quote volume in the unit's own price space, so
            # `quote_volume == volume x price` holds for the unit as it does
            # for a leg. The first version copied the thinner leg's coin
            # count, whose price space is the coin's, and the QA check that
            # tests that identity failed every unit at gate 1 (2026-09-15).
            "volume": quote_volume / ratio,
            "quote_volume": quote_volume,
            "basis": p["close"] / s["close"] - 1.0,
            # the spot leg's own price, for a universe that filters on the coin's volatility
            "spot_close": s["close"],
        },
        index=index,
    )
    if "trades" in s.columns and "trades" in p.columns:
        out["trades"] = pd.concat([s["trades"], p["trades"]], axis=1).min(axis=1)
    if funding is not None and not funding.empty and "funding_rate" in funding.columns:
        rate = funding["funding_rate"].reindex(index)
        out["perp_funding_rate"] = rate
        out["funding_rate"] = -rate
        for extra in ("open_interest", "open_interest_usd"):
            if extra in funding.columns:
                out[extra] = funding[extra].reindex(index)
    else:
        out["perp_funding_rate"] = float("nan")
        out["funding_rate"] = float("nan")
    out.index.name = "open_time"
    return out


def build_carry_lake(
    lake, symbols: Iterable[str] | None = None, interval: str = "1d", funding_bucket=None
) -> pd.DataFrame:
    """Build and store every symbol that has both legs; returns a summary.

    A symbol with a perp but no spot pair (or the reverse) is skipped and
    counted, not invented: the unit cannot be held.

    On daily bars the funding feature is the lake's daily sum. On any finer
    interval each settlement is read from the mirror at its own timestamp
    (`funding_bucket`, a `FundingBucket`) and put on the bar it was paid
    for (`qr.data.funding.bar_funding`), so an 8-hour settlement lands on
    one hourly bar and the other seven carry nothing.
    """
    from qr.data.funding import bar_funding

    spot_names = set(lake.symbols(interval, market=SPOT_MARKET))
    perp_names = set(lake.symbols(interval, market=PERP_MARKET))
    funding_names = set(lake.symbols("1d", market=FUNDING_MARKET))
    if interval != "1d" and funding_bucket is None:
        raise ValueError("building carry units on intra-day bars needs the funding mirror (funding_bucket)")
    wanted = list(symbols) if symbols is not None else sorted(spot_names & perp_names)
    rows = []
    for symbol in wanted:
        if symbol not in spot_names or symbol not in perp_names:
            rows.append({"symbol": symbol, "days": 0, "note": "missing a leg"})
            continue
        spot = lake.read_klines(symbol, interval, market=SPOT_MARKET)
        perp = lake.read_klines(symbol, interval, market=PERP_MARKET)
        if interval == "1d":
            funding = lake.read_klines(symbol, "1d", market=FUNDING_MARKET) if symbol in funding_names else None
        else:
            settlements = funding_bucket.load_funding(symbol)
            funding = pd.DataFrame({"funding_rate": bar_funding(settlements, interval)}) if len(settlements) else None
        frame = carry_frames(spot, perp, funding)
        if frame.empty:
            rows.append({"symbol": symbol, "days": 0, "note": "no overlapping dates"})
            continue
        lake.write_klines(symbol, frame, interval, market=CARRY_MARKET)
        rows.append(
            {
                "symbol": symbol,
                "days": len(frame),
                "start": frame.index[0],
                "end": frame.index[-1],
                "funding_days": int(frame["perp_funding_rate"].notna().sum()),
                "mean_perp_funding_bps_day": round(float(frame["perp_funding_rate"].mean() * 1e4), 3),
                "note": "",
            }
        )
    return pd.DataFrame(rows)
