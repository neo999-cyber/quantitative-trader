"""The cross-venue unit: long one dollar of a perp on one venue, short one dollar of the same perp on another.

Programme 2, family C2 (`docs/20_PROGRAMME_2.md` §5). The same levered longs
pay funding on every venue, but the venues clear at different rates; a unit
long the venue whose rate is lower and short the venue whose rate is higher
collects the difference and carries almost no price risk — the two legs are
the same contract on the same coin, so the unit's price is the ratio of the
two perps' closes and its return is the change in the cross-venue basis.

Built the way the carry unit is (`qr/data/carry.py`): a synthetic instrument
with bars of its own, written under `market="xvenue-um"`, so it runs through
the same engine and the same gates. **Two units a symbol**, one each way —
`<SYM>-BNBY` is long Binance / short Bybit, `<SYM>-BYBN` the reverse — so
the long-only `FundingCarry` family, unchanged, can hold whichever side is
being paid. The two are exact mirrors and a book never holds both, because
only one has a positive spread on any bar.

Fields follow the carry unit's convention: `funding_rate` is what one unit
of the position *pays* per bar (negative when it is paid), `perp_funding_rate`
is the signal — the spread the unit collects, so `FundingCarry` reads it
with the sign it expects — and `quote_volume` is the thinner leg's.
"""
from __future__ import annotations

from pathlib import Path
from typing import Iterable

import pandas as pd

from qr.data.funding import MARKET as FUNDING_MARKET
from qr.data.funding import daily_funding
from qr.execution.audit import redenomination_bars

PERP_MARKET = "futures/um"
XVENUE_MARKET = "xvenue-um"
SIDES = {"BNBY": 1.0, "BYBN": -1.0}


def bybit_daily(mirror: Path, symbol: str) -> tuple[pd.DataFrame, pd.Series]:
    """Bybit daily bars and the day's summed funding from the mirror."""
    bars = pd.read_parquet(mirror / "klines_1d" / f"{symbol}.parquet").set_index("open_time").sort_index()
    bars.index = pd.DatetimeIndex(bars.index).tz_convert("UTC")
    settlements = pd.read_parquet(mirror / "funding" / f"{symbol}.parquet").set_index("calc_time").sort_index()
    settlements.index = pd.DatetimeIndex(settlements.index).tz_convert("UTC")
    return bars, daily_funding(settlements)


def xvenue_frames(
    binance: pd.DataFrame, bybit: pd.DataFrame, f_binance: pd.Series, f_bybit: pd.Series, side: str
) -> pd.DataFrame:
    """One unit's bars. `side` BNBY: long Binance / short Bybit."""
    sign = SIDES[side]
    index = binance.index.intersection(bybit.index)
    a, b = (binance, bybit) if sign > 0 else (bybit, binance)
    a, b = a.reindex(index), b.reindex(index)
    ratio = a["close"] / b["close"]
    open_ratio = a["open"] / b["open"]
    artefact = redenomination_bars(ratio)
    if bool(artefact.any()):
        ratio = ratio.where(~artefact)
        open_ratio = open_ratio.where(~artefact)
    quote_volume = pd.concat([a["quote_volume"], b["quote_volume"]], axis=1).min(axis=1)
    f_long = (f_binance if sign > 0 else f_bybit).reindex(index)
    f_short = (f_bybit if sign > 0 else f_binance).reindex(index)
    out = pd.DataFrame(
        {
            "open": open_ratio,
            "high": pd.concat([open_ratio, ratio], axis=1).max(axis=1),
            "low": pd.concat([open_ratio, ratio], axis=1).min(axis=1),
            "close": ratio,
            "volume": quote_volume / ratio,
            "quote_volume": quote_volume,
            "basis": b["close"] / a["close"] - 1.0,
            "spot_close": binance.reindex(index)["close"],
            # the long leg pays its rate, the short leg receives its rate
            "funding_rate": f_long - f_short,
            # the signal: what the unit collects, positive when it is paid
            "perp_funding_rate": f_short - f_long,
        },
        index=index,
    )
    out.index.name = "open_time"
    return out


def build_xvenue_lake(lake, bybit_mirror: Path, symbols: Iterable[str] | None = None) -> pd.DataFrame:
    perp_names = set(lake.symbols("1d", market=PERP_MARKET))
    funding_names = set(lake.symbols("1d", market=FUNDING_MARKET))
    bybit_names = {p.stem for p in (bybit_mirror / "klines_1d").glob("*.parquet")} & {
        p.stem for p in (bybit_mirror / "funding").glob("*.parquet")
    }
    wanted = list(symbols) if symbols is not None else sorted(perp_names & funding_names & bybit_names)
    rows = []
    for symbol in wanted:
        if symbol not in perp_names or symbol not in funding_names or symbol not in bybit_names:
            rows.append({"symbol": symbol, "days": 0, "note": "missing a leg"})
            continue
        binance = lake.read_klines(symbol, "1d", market=PERP_MARKET)
        f_binance = lake.read_klines(symbol, "1d", market=FUNDING_MARKET)["funding_rate"]
        bybit, f_bybit = bybit_daily(bybit_mirror, symbol)
        for side in SIDES:
            frame = xvenue_frames(binance, bybit, f_binance, f_bybit, side)
            frame = frame[frame["funding_rate"].notna()]
            if frame.empty:
                rows.append({"symbol": f"{symbol}-{side}", "days": 0, "note": "no overlapping dates"})
                continue
            lake.write_klines(f"{symbol}-{side}", frame, "1d", market=XVENUE_MARKET)
            rows.append(
                {
                    "symbol": f"{symbol}-{side}",
                    "days": len(frame),
                    "start": frame.index[0],
                    "end": frame.index[-1],
                    "mean_spread_bps_day": round(float(frame["perp_funding_rate"].mean() * 1e4), 3),
                    "note": "",
                }
            )
    return pd.DataFrame(rows)
