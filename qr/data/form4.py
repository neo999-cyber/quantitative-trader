"""E5's Form 4 loader: the SEC insider-transactions data sets, point-in-time.

Source: `sec.gov/data-research/sec-markets-data/insider-transactions-data-sets`,
one zip a quarter since 2006 with the tables of every Form 3, 4 and 5 as
filed (SUBMISSION, NONDERIV_TRANS, REPORTINGOWNER, FOOTNOTES, ...). The data
sets carry the **filing date** only. The time a filing became public is its
EDGAR **acceptance time**, which the submissions API publishes per accession
(`data.sec.gov/submissions/CIK##########.json`, `acceptanceDateTime`, UTC);
`with_acceptance_times` writes it into `published_at`, and a row without one
is never visible to a signal (`qr.data.pit.asof_view`).

Availability columns (`docs/20_PROGRAMME_2.md` §10, item 10): `event_time`
is the transaction date, `published_at` the acceptance time,
`first_observed_at` the time the zip was downloaded into the mirror,
`ingested_at` the time it was parsed, `source_hash` the zip's SHA-256.

What qualifies (the E5 pre-registration, `docs/prereg/p2_insider_cluster_v1.md`):
non-derivative open-market purchases (code `P`, acquired), by a reporting
owner whose relationship is officer or director, not under a 10b5-1 plan
(the submission's `AFF10B5ONE` flag), with a price and at least the stated
value. Amendments (`4/A`) are separate filings under a new accession number;
the point-in-time key that lets a later amendment replace its original is
(issuer, owner, transaction date, code, security title).
"""
from __future__ import annotations

import hashlib
import io
import json
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Mapping

import pandas as pd

from qr.data.pit import AVAILABILITY_COLUMNS

DATASET_URL = "https://www.sec.gov/files/structureddata/data/insider-transactions-data-sets/{period}_form345.zip"
#: The newest quarter is published under a different prefix (seen for 2026q2
#: on 2026-09-15); tried second.
DATASET_URL_ALT = "https://www.sec.gov/files/datastandardsinnovation/data/insider-transactions-data-sets/{period}_form345.zip"
SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik:0>10}.json"
SUBMISSIONS_FILE_URL = "https://data.sec.gov/submissions/{name}"
#: The SEC asks for a descriptive User-Agent with a contact; requests
#: without one are refused.
USER_AGENT = "quantitative-trader research (neo999@gmail.com)"

QUALIFYING_RELATIONSHIPS = ("Officer", "Director")
OPEN_MARKET_PURCHASE = "P"

_SUB_COLUMNS = {
    "ACCESSION_NUMBER": "accession",
    "FILING_DATE": "filing_date",
    "DATE_OF_ORIG_SUB": "original_filing_date",
    "DOCUMENT_TYPE": "document_type",
    "ISSUERCIK": "issuer_cik",
    "ISSUERNAME": "issuer_name",
    "ISSUERTRADINGSYMBOL": "symbol",
    "AFF10B5ONE": "plan_10b5_1",
}
_TRANS_COLUMNS = {
    "ACCESSION_NUMBER": "accession",
    "NONDERIV_TRANS_SK": "trans_sk",
    "SECURITY_TITLE": "security_title",
    "TRANS_DATE": "trans_date",
    "TRANS_CODE": "trans_code",
    "TRANS_SHARES": "shares",
    "TRANS_PRICEPERSHARE": "price",
    "TRANS_PRICEPERSHARE_FN": "price_footnote",
    "TRANS_ACQUIRED_DISP_CD": "acquired_disposed",
    "DIRECT_INDIRECT_OWNERSHIP": "direct_indirect",
    "NATURE_OF_OWNERSHIP": "nature_of_ownership",
    # footnote references on the transaction row itself, as opposed to the
    # filing's other rows (holdings, awards): the row's own footnotes decide
    # the soft exclusions below
    "SECURITY_TITLE_FN": "fn_title",
    "TRANS_DATE_FN": "fn_date",
    "TRANS_SHARES_FN": "fn_shares",
    "TRANS_ACQUIRED_DISP_CD_FN": "fn_acquired",
    "SHRS_OWND_FOLWNG_TRANS_FN": "fn_owned",
    "DIRECT_INDIRECT_OWNERSHIP_FN": "fn_direct",
    "NATURE_OF_OWNERSHIP_FN": "fn_nature",
    "EQUITY_SWAP_TRANS_CD_FN": "fn_code",
}
#: `fn_owned` (the shares-owned-following column) is left out on purpose: its
#: footnotes describe the holdings total (ESPP and DRIP shares held, awards
#: vesting), not the purchase, and reading them dropped three real
#: open-market buys in the audit sample.
_ROW_FOOTNOTE_COLUMNS = ("price_footnote", "fn_title", "fn_date", "fn_shares", "fn_acquired", "fn_direct", "fn_nature", "fn_code")

#: A reporting owner that is an institution, not a person. A director's own
#: living trust, LLC or family partnership is that person's money and is
#: kept; a fund with a board seat is not, and its purchases are allocation
#: decisions, not the mechanism the E5 pre-registration names. Found by the
#: labelling audit (docs/audit/e5_form4_labels_2025q1.csv): EcoR1 Capital
#: LLC, OrbiMed Capital GP VIII LLC, Diamondback Energy Inc, Haveli
#: Investments LP were all "Director" purchases.
_ENTITY_OWNER = r"\b(?:L\.?L\.?C|L\.?P|LP|Fund|Capital|Partners|Management|Advisors|Advisers|Holdings|Inc\.?|Corp\.?|Ltd\.?|Limited|GP|Investments|Ventures|Group)\b"
#: Filing-level: a footnote saying the shares came from a placement, an
#: offering, a negotiated purchase or a plan describes the transaction, not
#: a holding, whenever a purchase is reported in the same filing.
_NOT_OPEN_MARKET = (
    r"10b5-1|private placement|privately negotiated|securities purchase agreement|subscription agreement|"
    r"registered direct|public offering|initial public offering|underwriting agreement|\bPIPE\b|"
    r"exchange agreement|debt exchange|in exchange for|rights offering"
)
#: Row-level: employee and dividend plans are routine, not opportunistic.
#: Applied only to the footnotes the transaction row itself references,
#: because a filing often notes an ESPP or DRIP against its *holdings*
#: column while reporting a real open-market buy.
_PLAN_PURCHASE = r"employee stock purchase plan|\bESPP\b|dividend reinvestment|reinvestment of dividends|\b401\(k\)"
_UNTRADED_SYMBOLS = ("", "NONE", "N/A", "NA", "NOT APPLICABLE")
_OWNER_COLUMNS = {
    "ACCESSION_NUMBER": "accession",
    "RPTOWNERCIK": "owner_cik",
    "RPTOWNERNAME": "owner_name",
    "RPTOWNER_RELATIONSHIP": "owner_relationship",
    "RPTOWNER_TITLE": "owner_title",
}


def _read(zf: zipfile.ZipFile, name: str, columns: Mapping[str, str]) -> pd.DataFrame:
    with zf.open(name) as handle:
        frame = pd.read_csv(
            io.TextIOWrapper(handle, encoding="utf-8", errors="replace"),
            sep="\t",
            dtype=str,
            keep_default_na=False,
            usecols=lambda c: c in columns,
        )
    frame = frame.rename(columns=columns)
    # Older quarters predate some columns (AFF10B5ONE, the 10b5-1 checkbox,
    # exists from 2023; the audit's footnote-reference columns vary), so a
    # missing optional column is empty rather than an error.
    for name in columns.values():
        if name not in frame.columns:
            frame[name] = ""
    return frame


def _sec_date(values: pd.Series) -> pd.Series:
    return pd.to_datetime(values.replace("", pd.NA), format="%d-%b-%Y", errors="coerce")


def parse_quarter(path: str | Path, first_observed_at: pd.Timestamp | None = None) -> pd.DataFrame:
    """One quarter's zip -> one row per non-derivative transaction per owner.

    A filing with two reporting owners (a joint filing) yields a row per
    owner, which is what the cluster count needs: two directors on one Form 4
    are two insiders.
    """
    path = Path(path)
    payload = path.read_bytes()
    digest = hashlib.sha256(payload).hexdigest()
    observed = first_observed_at or pd.Timestamp(datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc))
    with zipfile.ZipFile(io.BytesIO(payload)) as zf:
        sub = _read(zf, "SUBMISSION.tsv", _SUB_COLUMNS)
        trans = _read(zf, "NONDERIV_TRANS.tsv", _TRANS_COLUMNS)
        owners = _read(zf, "REPORTINGOWNER.tsv", _OWNER_COLUMNS)
        footnotes = _read(zf, "FOOTNOTES.tsv", {"ACCESSION_NUMBER": "accession", "FOOTNOTE_ID": "footnote_id", "FOOTNOTE_TXT": "footnote"})

    sub["filing_date"] = _sec_date(sub["filing_date"])
    sub["original_filing_date"] = _sec_date(sub["original_filing_date"])
    sub["plan_10b5_1"] = sub["plan_10b5_1"].fillna("0").astype(str).str.strip().eq("1")
    sub["is_amendment"] = sub["document_type"].str.endswith("/A")

    trans["trans_date"] = _sec_date(trans["trans_date"])
    trans["shares"] = pd.to_numeric(trans["shares"].replace("", pd.NA), errors="coerce")
    trans["price"] = pd.to_numeric(trans["price"].replace("", pd.NA), errors="coerce")
    trans["value_usd"] = trans["shares"] * trans["price"]

    owners["is_officer"] = owners["owner_relationship"].str.split(",").apply(lambda parts: "Officer" in parts)
    owners["is_director"] = owners["owner_relationship"].str.split(",").apply(lambda parts: "Director" in parts)

    notes = (
        footnotes.groupby("accession")["footnote"].apply(lambda s: " | ".join(s)).rename("footnotes")
        if len(footnotes)
        else pd.Series(dtype=str, name="footnotes")
    )
    frame = trans.merge(sub, on="accession", how="inner").merge(owners, on="accession", how="inner")
    frame = frame.merge(notes, left_on="accession", right_index=True, how="left")
    frame["footnotes"] = frame["footnotes"].fillna("")
    # the footnotes this row itself points at
    by_id = {(a, i): t for a, i, t in footnotes[["accession", "footnote_id", "footnote"]].itertuples(index=False)} if len(footnotes) else {}
    def _row_notes(row) -> str:
        ids = set()
        for column in _ROW_FOOTNOTE_COLUMNS:
            for token in str(row.get(column, "")).replace(";", ",").split(","):
                token = token.strip()
                if token:
                    ids.add(token)
        return " | ".join(by_id.get((row["accession"], i), "") for i in sorted(ids))
    frame["row_footnotes"] = frame.apply(_row_notes, axis=1) if len(frame) else ""

    # Availability. The transaction happened during the session of its date;
    # 16:00 New York is the conservative reading of "that day".
    frame["event_time"] = frame["trans_date"].dt.tz_localize("America/New_York") + pd.Timedelta(hours=16)
    frame["published_at"] = pd.Series(pd.NaT, index=frame.index, dtype="datetime64[ns, UTC]")
    frame["first_observed_at"] = pd.Timestamp(observed).tz_convert("UTC")
    frame["ingested_at"] = pd.Timestamp.now(tz="UTC")
    frame["source_hash"] = digest
    frame.attrs["source"] = str(path)
    return frame.reset_index(drop=True)


def with_acceptance_times(frame: pd.DataFrame, times: Mapping[str, str | pd.Timestamp]) -> pd.DataFrame:
    """Write EDGAR acceptance times into `published_at`, by accession number."""
    stamps = pd.Series({k: pd.Timestamp(v) for k, v in times.items()}, dtype="datetime64[ns, UTC]")
    if len(stamps):
        stamps = stamps.dt.tz_convert("UTC") if stamps.dt.tz is not None else stamps.dt.tz_localize("UTC")
    out = frame.copy()
    out["published_at"] = out["accession"].map(stamps).astype("datetime64[ns, UTC]")
    return out


def exclusion_reasons(frame: pd.DataFrame) -> pd.Series:
    """Why a code-P row is not an insider's own open-market purchase, or ''.

    The rules are the labelling audit's findings turned mechanical
    (`docs/audit/e5_form4_labels_2025q1.csv`, 15 September 2026): the first
    parser reached 76% precision on 100 filings and every miss was visible
    in the filing's own fields.
    """
    reasons = pd.Series("", index=frame.index, dtype=object)

    def mark(mask: pd.Series, reason: str) -> None:
        hit = mask.fillna(False) & reasons.eq("")
        reasons[hit] = reason

    symbol = frame["symbol"].fillna("").str.strip().str.upper()
    mark(symbol.isin(_UNTRADED_SYMBOLS), "issuer_not_traded")
    mark(frame["plan_10b5_1"], "10b5-1_flag")
    mark(frame["owner_name"].fillna("").str.contains(_ENTITY_OWNER, case=False, regex=True) & ~frame["owner_name"].fillna("").str.contains(r"trust", case=False), "entity_reporting_owner")
    ten_percent = frame["owner_relationship"].fillna("").str.contains("TenPercentOwner")
    mark(ten_percent & frame["direct_indirect"].eq("I"), "ten_percent_owner_indirect")
    mark(frame["footnotes"].fillna("").str.contains(_NOT_OPEN_MARKET, case=False, regex=True), "not_open_market_footnote")
    row_text = frame["row_footnotes"].fillna("") + " " + frame["nature_of_ownership"].fillna("")
    mark(row_text.str.contains(_PLAN_PURCHASE, case=False, regex=True), "plan_purchase")
    return reasons


def qualifying_purchases(frame: pd.DataFrame, min_each_usd: float = 25_000.0) -> pd.DataFrame:
    """The rows the pre-registration counts: open-market buys by insiders."""
    if "row_footnotes" not in frame.columns:
        frame = frame.assign(row_footnotes="")
    mask = (
        frame["trans_code"].eq(OPEN_MARKET_PURCHASE)
        & frame["acquired_disposed"].eq("A")
        & (frame["is_officer"] | frame["is_director"])
        & frame["price"].gt(0)
        & frame["shares"].gt(0)
        & frame["value_usd"].ge(float(min_each_usd))
    )
    candidates = frame[mask]
    reasons = exclusion_reasons(candidates)
    return candidates[reasons.eq("")].copy()


def cluster_signals(
    purchases: pd.DataFrame,
    window_days: int = 10,
    min_insiders: int = 2,
    min_combined_usd: float = 100_000.0,
) -> pd.DataFrame:
    """Clusters of distinct insiders buying the same issuer within `window_days`.

    Rows are ordered by publication; a cluster is complete on the filing
    that brings the count of distinct owners to `min_insiders` and the
    combined value to `min_combined_usd` within the trailing window of
    **trading-calendar days approximated as calendar days** here (the
    window is measured on `trans_date`; the pre-registration's 10 trading
    days is applied at the security master). The signal's time is that
    filing's acceptance time, which is when the information was public.
    One signal per issuer per window: a cluster already signalled does not
    fire again on a third buyer inside the same window.
    """
    if purchases.empty:
        return pd.DataFrame(
            columns=["issuer_cik", "symbol", "signal_time", "completing_accession", "n_insiders", "combined_usd", "window_start"]
        )
    rows = purchases.dropna(subset=["published_at"]).sort_values(["published_at", "accession"], kind="stable")
    out = []
    window = pd.Timedelta(days=int(window_days))
    for issuer, group in rows.groupby("issuer_cik", sort=False):
        last_signal_end = None
        for _, row in group.iterrows():
            start = row["trans_date"] - window
            in_window = group[(group["published_at"] <= row["published_at"]) & (group["trans_date"] >= start) & (group["trans_date"] <= row["trans_date"] + window)]
            if last_signal_end is not None and row["trans_date"] <= last_signal_end:
                continue
            owners = in_window["owner_cik"].nunique()
            combined = float(in_window["value_usd"].sum())
            if owners >= int(min_insiders) and combined >= float(min_combined_usd):
                out.append(
                    {
                        "issuer_cik": issuer,
                        "symbol": row["symbol"],
                        "signal_time": row["published_at"],
                        "completing_accession": row["accession"],
                        "n_insiders": int(owners),
                        "combined_usd": combined,
                        "window_start": start,
                    }
                )
                last_signal_end = row["trans_date"] + window
    return pd.DataFrame(out)


# ------------------------------------------------------------------ network


def fetch_quarter(period: str, mirror: Path, session=None) -> Path:
    """Download one quarter's zip into the mirror unless it is already there."""
    import urllib.request

    mirror.mkdir(parents=True, exist_ok=True)
    target = mirror / f"{period}_form345.zip"
    if target.exists():
        return target
    last_error: Exception | None = None
    for url in (DATASET_URL, DATASET_URL_ALT):
        request = urllib.request.Request(url.format(period=period), headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(request, timeout=300) as response:
                payload = response.read()
        except Exception as exc:  # noqa: BLE001 — try the other prefix
            last_error = exc
            continue
        target.write_bytes(payload)
        return target
    raise RuntimeError(f"{period}: {last_error}")


def acceptance_times(ciks: Iterable[str], cache: Path, pause: float = 0.11) -> dict[str, str]:
    """Accession -> acceptanceDateTime (UTC ISO string) for every filing of each CIK.

    One request per CIK (plus its older-filings pages), cached as JSON in
    `cache`. The SEC's fair-access limit is ten requests a second; `pause`
    keeps under it.
    """
    import urllib.request

    cache.mkdir(parents=True, exist_ok=True)
    out: dict[str, str] = {}

    def get(url: str, name: str) -> dict:
        path = cache / name
        if path.exists():
            return json.loads(path.read_text())
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(request, timeout=60) as response:
            payload = response.read()
        path.write_bytes(payload)
        time.sleep(pause)
        return json.loads(payload)

    def harvest(block: dict) -> None:
        for acc, stamp in zip(block.get("accessionNumber", []), block.get("acceptanceDateTime", [])):
            if acc and stamp:
                out[acc] = stamp

    for cik in ciks:
        cik = str(cik).lstrip("0") or "0"
        name = f"CIK{int(cik):010d}.json"
        try:
            data = get(SUBMISSIONS_URL.format(cik=cik), name)
        except Exception:  # noqa: BLE001 — a missing CIK is a fact to record, not a crash
            continue
        harvest(data.get("filings", {}).get("recent", {}))
        for older in data.get("filings", {}).get("files", []):
            try:
                harvest(get(SUBMISSIONS_FILE_URL.format(name=older["name"]), older["name"]))
            except Exception:  # noqa: BLE001
                continue
    return out
