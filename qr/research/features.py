"""What the lake can actually answer, and what it cannot.

This registry exists because of a gap that would otherwise be discovered
candidate by candidate, expensively. `docs/10_NEXT.md` says to generate ideas
from "who is forced to trade?" — leveraged longs paying funding, index funds
buying on inclusion day, liquidation cascades, vesting insiders, month-end
pension rebalances, December tax-loss selling. Every one of those names a payer
you can point at, which is exactly the property the nine failed families
lacked.

**Almost none of them can be tested with what is in the lake.** The lake holds
OHLCV, quote volume and trade counts. Funding rates are not in it. Index
membership changes are not in it. Unlock schedules are not in it. A mechanism
memo that proposes one of those is not wrong, it is *blocked*, and the two need
telling apart: a wrong idea should be killed and forgotten, a blocked one
should be parked with the name of the dataset that would unblock it, because
that list is the shopping list for the next data sprint.

So every memo declares the features it needs, `available()` answers from this
table, and the autopilot routes on the answer. The output of a blocked night's
work is a queue of ideas and the exact data each one waits on — which is worth
more than another run of something momentum-shaped that happened to be
runnable.

The one mechanism family that OHLCV *can* support is the calendar. Month-end
and quarter-end rebalances, turn-of-month, the December tax-loss window: the
forced trader is real, the date is knowable in advance from the index alone,
and nothing beyond a timestamp is required. That is why `qr/strategies/calendar.py`
exists and why it is the first primitive the autopilot can actually run.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from qr.data.panel import Panel


@dataclass(frozen=True)
class Feature:
    """One thing a strategy might need, and whether this project has it."""

    key: str
    what: str
    #: Panel field it reads, or "" for things derived from the index alone.
    panel_field: str = ""
    #: Empty when the lake already has it; otherwise the dataset that would.
    needs_dataset: str = ""

    @property
    def available(self) -> bool:
        return not self.needs_dataset


#: Everything a mechanism memo is allowed to ask for. A key that is not here is
#: refused rather than assumed, because a silently ignored requirement is how a
#: backtest comes to be run on data that does not mean what the memo thought.
REGISTRY: dict[str, Feature] = {
    f.key: f
    for f in [
        # --- in the lake today
        Feature("close", "daily or hourly close", "close"),
        Feature("open", "bar open", "open"),
        Feature("high_low", "intrabar range", "high"),
        Feature("volume", "base volume", "volume"),
        Feature("quote_volume", "volume in quote currency; the liquidity screen", "quote_volume"),
        Feature("trades", "trade count per bar", "trades"),
        Feature("calendar", "the date itself: month ends, quarter ends, weekdays, December"),
        Feature("listing_dates", "when a pair started and stopped trading; survivorship"),
        Feature("fear_greed", "the crypto Fear & Greed index", needs_dataset=""),
        # --- named, and not in the lake
        Feature(
            "funding_rate",
            "perpetual funding, paid every eight hours by the crowded side",
            needs_dataset="binance futures fundingRate (public, free; needs an ingestor)",
        ),
        Feature(
            "open_interest",
            "how much leverage is on, and which way",
            needs_dataset="binance futures openInterestHist (public, free)",
        ),
        Feature(
            "liquidations",
            "forced closes; the cascade itself rather than a proxy for it",
            needs_dataset="binance forceOrder stream (live only; must be collected forward)",
        ),
        Feature(
            "index_membership",
            "inclusion and deletion dates, and the funds that must trade them",
            needs_dataset="index provider announcements (S&P/MSCI/FTSE; licensed or scraped)",
        ),
        Feature(
            "token_unlocks",
            "vesting cliffs: a seller who has no choice about the date",
            needs_dataset="DropsTab unlock calendar (docs/research/08; Phase 5 candidate)",
        ),
        Feature(
            "short_interest",
            "who is short and how crowded it is",
            needs_dataset="exchange short-interest files (equities; biweekly, lagged)",
        ),
        Feature(
            "fund_flows",
            "pension and ETF creation/redemption pressure",
            needs_dataset="ETF creation baskets / ICI flow data",
        ),
    ]
}


def known(key: str) -> bool:
    return key in REGISTRY


def available(key: str) -> bool:
    feature = REGISTRY.get(key)
    return bool(feature and feature.available)


def unknown_keys(keys: Iterable[str]) -> list[str]:
    return sorted({k for k in keys if not known(k)})


def missing(keys: Iterable[str]) -> list[Feature]:
    """The requested features this project does not have, in registry order."""
    wanted = {k for k in keys if known(k)}
    return [f for f in REGISTRY.values() if f.key in wanted and not f.available]


def datasets_needed(keys: Iterable[str]) -> list[str]:
    """The shopping list: what to go and get to unblock these ideas."""
    return sorted({f.needs_dataset for f in missing(keys)})


def satisfied_by(panel: Panel, keys: Iterable[str]) -> list[str]:
    """Features that are in the registry as available but absent from *this* panel.

    The registry says what the project can have; a panel says what was actually
    loaded. A crypto panel has `quote_volume` and a Tiingo one does not, and a
    kill test that silently treats a missing column as zero is worse than one
    that refuses to run.
    """
    gaps = []
    for key in keys:
        feature = REGISTRY.get(key)
        if feature is None or not feature.available or not feature.panel_field:
            continue
        if panel.get(feature.panel_field) is None:
            gaps.append(key)
    return sorted(set(gaps))
