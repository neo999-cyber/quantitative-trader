"""ETF creation and redemption flow, recorded forward because it cannot be bought back.

`fund_flows` was the most-requested dataset across the autopilot nights, and it
is the only named mechanism whose forced trader trades **the same instrument
this project trades**. When an ETF takes in money it does not buy at its
leisure: an authorised participant delivers a basket and receives new shares,
and the fund's share count rises that day. The daily change in shares
outstanding, times NAV, *is* the creation/redemption flow. Nobody is guessing
at sentiment; a share was issued or it was not.

## Why this is recorded rather than downloaded

There is no free historical series. Issuers publish **today's** share count;
history is a paid product (Intrinio, EODHD, ETF Global). Tiingo has a Mutual
Fund API, and the plan this project pays for answers `403 — You do not have
permission`, so whether it even carries the field is unknown and paying to find
out is the wrong order.

So it is recorded daily and accumulates. That is slower, and it buys a property
worth more than the wait: **data you record yourself is point-in-time by
construction.** No revision, no restatement, no look-ahead, because you cannot
record what you do not yet know. It is the same reason the perpetual funding
data was trustworthy the moment it landed.

The cost of the wait is honest and should be stated: a year of collection is
~250 daily observations, which is a workable sample for a *daily* flow signal
and a hopeless one for a month-end effect — twelve month-ends is not a test of
anything.

## Why the parser is written to fail loudly

**None of these URLs could be verified from the environment this was written
in**, which has no egress to issuer sites. The shape below is written from the
documented pattern; the first run on a networked machine is the verification,
exactly as it was for the Binance funding bucket. So every parser quotes the
payload it actually received, and `--dump` saves the raw response, because a
discovery run that prints "failed" without showing what arrived wastes the
round trip it cost.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Sequence

#: The seven basket members BlackRock runs. One issuer, one endpoint, a
#: majority of the universe: the cheapest possible first step, and if the shape
#: is wrong it is wrong once rather than in four different ways.
ISHARES_TICKERS: tuple[str, ...] = ("IWM", "EFA", "EEM", "TLT", "IEF", "LQD", "HYG")

#: The product screener returns every US iShares fund in one document. Chosen
#: over per-fund pages because those need a numeric product id per ticker,
#: which is five more things to get wrong before anything can be tested.
ISHARES_SCREENER = (
    "https://www.ishares.com/us/product-screener/product-screener-v3.1.jsn"
    "?dcrPath=/templatedata/config/product-screener-v3/data/en/us-ishares"
    "/ishares-product-screener-backend-config&siteEntryPassthrough=true"
)

#: Field names to hunt for, in any spelling an issuer might use. A match is
#: reported rather than trusted: `sharesOutstanding` and `totalNetAssets` mean
#: what we want; something merely containing "shares" may not.
SHARE_KEYS = ("sharesoutstanding", "shares_outstanding", "sharesout", "sharecount")
ASSET_KEYS = ("totalnetassets", "total_net_assets", "netassets", "fundnetassets", "aum")
NAV_KEYS = ("nav", "navamount", "netassetvalue")


class FlowSourceError(RuntimeError):
    """The response did not contain what the parser needed, and says what it did."""


@dataclass(frozen=True)
class ShareCount:
    """One fund's share count on one observation date."""

    observed_utc: str
    ticker: str
    shares_outstanding: float | None
    total_net_assets: float | None
    nav: float | None
    source: str
    #: "reported" when the issuer published a share count, "derived" when it
    #: was computed as net assets / NAV. Recorded rather than assumed, because
    #: the two have different error behaviour and a later reader must be able
    #: to tell which one a row is.
    shares_basis: str = "reported"

    def as_dict(self) -> dict[str, Any]:
        return {
            "observed_utc": self.observed_utc,
            "ticker": self.ticker,
            "shares_outstanding": self.shares_outstanding,
            "total_net_assets": self.total_net_assets,
            "nav": self.nav,
            "source": self.source,
            "shares_basis": self.shares_basis,
        }


def _number(value: Any) -> float | None:
    """A figure from a vendor payload, which may be nested, formatted or absent.

    Issuers wrap numbers in `{"r": 1234.5, "d": "1,234.5"}` shapes often enough
    that reaching for the raw value first and the display string second is
    worth the four lines. A display string is parsed only after the commas and
    currency marks are stripped, and anything still unparseable is `None`
    rather than a zero — an absent share count is not a fund with no shares.
    """
    if value is None:
        return None
    if isinstance(value, dict):
        for key in ("r", "raw", "value"):
            if key in value:
                return _number(value[key])
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace(",", "").replace("$", "").replace("%", "")
    if not text or text in {"-", "--", "N/A", "NA"}:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _pick(record: dict, wanted: Sequence[str]) -> float | None:
    for key, value in record.items():
        if key.lower().replace(" ", "") in wanted:
            number = _number(value)
            if number is not None:
                return number
    return None


def parse_ishares(payload: Any, tickers: Iterable[str] = ISHARES_TICKERS) -> list[ShareCount]:
    """Pull share counts out of the iShares product screener document.

    The screener nests one record per fund under a product id. The ticker lives
    under a key this parser does not assume the name of, because that is
    precisely the kind of detail written blind and discovered wrong: any string
    field whose value matches a wanted ticker identifies the record.
    """
    observed = datetime.now(timezone.utc).isoformat(timespec="seconds")
    wanted = {t.upper() for t in tickers}

    # Walk the whole document rather than assuming its nesting. The first
    # attempt guessed at the depth and mistook each figure's `{"r": .., "d": ..}`
    # wrapper for a fund record, which is exactly the kind of detail that
    # cannot be got right without the live payload. A record is identified by
    # what it *contains* — a ticker we asked for — not by where it sits.
    records: list[dict] = []
    others: list[dict] = []

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            if any(isinstance(v, str) and v.upper() in wanted for v in node.values()):
                records.append(node)
            elif len(node) > 2:
                others.append(node)
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(payload)

    if not records:
        top = sorted(payload)[:20] if isinstance(payload, dict) else type(payload).__name__
        raise FlowSourceError(
            f"no fund records in the screener response: none of {sorted(wanted)} appear as a "
            f"value anywhere in it. Top level: {top}. "
            + (f"A representative object had fields {sorted(others[0])[:40]}." if others else "")
        )

    out: list[ShareCount] = []
    seen: set[str] = set()
    for record in records:
        ticker = next(
            (
                str(v).upper()
                for v in record.values()
                if isinstance(v, str) and v.upper() in wanted
            ),
            None,
        )
        if ticker is None or ticker in seen:
            continue
        seen.add(ticker)
        shares = _pick(record, SHARE_KEYS)
        assets = _pick(record, ASSET_KEYS)
        nav = _pick(record, NAV_KEYS)
        basis = "reported"
        if shares is None and assets is not None and nav:
            # The screener publishes net assets and NAV but no share count, so
            # the count is their quotient — which is the same identity the flow
            # itself rests on, since net assets are shares times NAV by
            # definition. Nothing is being estimated; a division is being done.
            shares = assets / nav
            basis = "derived"
        out.append(
            ShareCount(
                observed_utc=observed,
                ticker=ticker,
                shares_outstanding=shares,
                total_net_assets=assets,
                nav=nav,
                source="ishares_product_screener",
                shares_basis=basis,
            )
        )

    missing = [s.ticker for s in out if s.shares_outstanding is None and s.total_net_assets is None]
    if missing:
        sample = sorted(records[0])[:40] if records else []
        raise FlowSourceError(
            f"found {len(out)} funds but no share count or net assets for {missing}. "
            f"Fields available on the first record: {sample}. "
            "If the figure is there under another name, add it to SHARE_KEYS/ASSET_KEYS."
        )
    return out


def append(path: Path, counts: Sequence[ShareCount]) -> int:
    """Append today's observations. Append-only, because a correction is a lie here.

    The whole value of recording forward is that each line is what was true
    when it was written. A collector that rewrote yesterday's number would
    reintroduce exactly the revision problem this exists to avoid.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        for count in counts:
            handle.write(json.dumps(count.as_dict(), sort_keys=True) + "\n")
    return len(counts)


def load(path: Path):
    """Everything recorded so far, as a frame; empty if collection has not started."""
    import pandas as pd

    if not path.exists():
        return pd.DataFrame(columns=["observed_utc", "ticker", "shares_outstanding",
                                     "total_net_assets", "nav", "source"])
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    frame = pd.DataFrame(rows)
    if not frame.empty:
        frame["observed_utc"] = pd.to_datetime(frame["observed_utc"], utc=True, format="mixed")
    return frame.sort_values(["ticker", "observed_utc"]).reset_index(drop=True)


def daily_flow(frame):
    """Shares created or redeemed since the previous observation, per fund.

    The first observation of each fund has no predecessor and yields NaN, not
    zero: "we do not know" and "nothing was created" are different claims, and
    only one of them is true on day one.
    """
    import pandas as pd

    if frame.empty:
        return frame.assign(shares_change=pd.Series(dtype=float), flow_usd=pd.Series(dtype=float))
    out = frame.sort_values(["ticker", "observed_utc"]).copy()
    out["shares_change"] = out.groupby("ticker")["shares_outstanding"].diff()
    out["flow_usd"] = out["shares_change"] * out["nav"]
    return out


def fetch(url: str = ISHARES_SCREENER, timeout: int = 60, dump: Path | None = None) -> Any:
    """Get the screener document. Needs network; the cloud sandbox has none.

    `dump` writes the raw bytes before parsing. That is not a debugging luxury:
    this parser was written against a documented shape nobody here could load,
    so the first run is a discovery run, and a discovery run that reports
    "failed" without keeping what arrived has to be paid for twice.
    """
    import urllib.request

    request = urllib.request.Request(
        url,
        headers={
            # Issuer sites serve a consent page to clients that look like
            # scrapers. This is not evasion of a paywall — the document is
            # public and free — it is asking for the JSON rather than the
            # marketing page.
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
            "Accept": "application/json, text/plain, */*",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        raw = response.read()
    if dump is not None:
        dump.parent.mkdir(parents=True, exist_ok=True)
        dump.write_bytes(raw)
    text = raw.decode("utf-8", "replace").lstrip("\ufeff").strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise FlowSourceError(
            f"the screener did not return JSON ({exc}). First 300 characters:\n{text[:300]}"
        ) from exc


def significant_digits(value: float | None) -> int:
    """How many digits the source actually committed to.

    The number that decides whether this dataset is usable at all. A daily
    creation is on the order of 0.1% of a fund's shares, so a net-asset figure
    published to four significant figures cannot express one: the flow is
    smaller than the rounding, and every day would read as either zero or a
    step of 0.05%. Four digits means the record is worthless no matter how long
    it is collected, and it is much better to know that on day one.
    """
    if value is None or value != value or value == 0:
        return 0
    text = f"{abs(float(value)):.17g}"
    if "e" in text or "E" in text:
        text = text.split("e")[0].split("E")[0]
    digits = text.replace(".", "").replace("-", "").lstrip("0")
    return len(digits.rstrip("0")) or 1


def precision_warning(counts: Sequence[ShareCount], needed: int = 6) -> str:
    """A sentence to print when the source is too rounded to show a flow, else ""."""
    worst = [
        (c.ticker, c.total_net_assets, significant_digits(c.total_net_assets))
        for c in counts
        if significant_digits(c.total_net_assets) < needed
    ]
    if not worst:
        return ""
    listed = ", ".join(f"{t} ({d} digits)" for t, _, d in worst[:5])
    return (
        f"WARNING: net assets are published to fewer than {needed} significant figures for "
        f"{listed}.\n"
        "A daily creation is about 0.1% of a fund, so a flow computed from figures this "
        "rounded is rounding noise, not flow. Collecting for a year would not fix it — the "
        "source has to publish more precision, or the figure has to come from somewhere else."
    )
