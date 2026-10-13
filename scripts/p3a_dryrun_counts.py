#!/usr/bin/env python3
"""Parser dry-run for the P3-A v2 read (`docs/prereg/p3_threshold_wedge_v2_intraday.md`, seq 934): counts only.

Reads the recording exactly the way `qr.execution.pm_replay.iter_events`
does — every hourly gzip member, every line, the inner `raw` JSON — and
counts what it finds: files, days, truncated members, unparsable lines,
messages by type and channel, tokens with quotes and with trade prints,
gaps in the recording, and the catalogue's shape. It computes **no model
probability, no wedge, no edge**: no price is compared with anything and
no Deribit value leaves the counters. The owner said yes to this on 13
October 2026; it is disclosed in the trial log as a note under the
hypothesis, not as a run.

Standard library only, so the stream pass runs on the box beside the
recorder (the mirror to the laptop is slow):

    python3 scripts/p3a_dryrun_counts.py --rec /root/pm/data --start 2026-09-21 --end 2026-10-26 --out /root/pm/dryrun/counts.json

The second stage needs the repo (`qr.data.polymarket.classify`) and runs
on the laptop from the catalogue and the first stage's JSON — coverage of
the classified markets by book data and trade prints, and the asset ×
settlement-date clusters the memo's minimum of 30 is counted over:

    python scripts/p3a_dryrun_counts.py --classify --counts counts.json --rec ~/qr/lake/mirror/polymarket_live --read-date 2026-10-27
"""
from __future__ import annotations

import argparse
import gzip
import json
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path


def _day(t: float) -> str:
    return datetime.fromtimestamp(t, tz=timezone.utc).strftime("%Y-%m-%d")


def stream_counts(rec: Path, start: float, end: float) -> dict:
    """One pass over both venues' hourly files; counters only."""
    t0 = time.time()
    files = {v: {"n": 0, "days": set(), "truncated": 0, "bad_lines": 0, "lines": 0, "bytes_gz": 0, "outside_window": 0} for v in ("polymarket", "deribit")}
    pm_types: Counter = Counter()
    pm_per_day: Counter = Counter()
    db_channels: Counter = Counter()
    db_per_day: Counter = Counter()
    tokens_book, tokens_quote = set(), set()
    trades_per_token: Counter = Counter()
    price_changes = 0
    last_t = {"polymarket": None, "deribit": None}
    gaps = {v: {"max_gap_s": 0.0, "gaps_over_600s": 0, "per_day_max_gap_s": defaultdict(float)} for v in ("polymarket", "deribit")}
    for venue in ("polymarket", "deribit"):
        for f in sorted((rec / venue).glob("*/*.jsonl.gz")):
            fv = files[venue]
            fv["n"] += 1
            fv["days"].add(f.parent.name)
            fv["bytes_gz"] += f.stat().st_size
            with gzip.open(f, "rt", encoding="utf-8") as fh:
                while True:
                    try:
                        line = fh.readline()
                    except EOFError:
                        fv["truncated"] += 1
                        break
                    if not line:
                        break
                    fv["lines"] += 1
                    try:
                        d = json.loads(line)
                        raw = json.loads(d["raw"])
                        t = float(d["recorded_at"])
                    except (json.JSONDecodeError, KeyError, TypeError, ValueError):
                        fv["bad_lines"] += 1
                        continue
                    if t < start or t > end:
                        fv["outside_window"] += 1
                        continue
                    day = _day(t)
                    prev = last_t[venue]
                    if prev is not None:
                        gap = t - prev
                        g = gaps[venue]
                        if gap > g["max_gap_s"]:
                            g["max_gap_s"] = gap
                        if gap > 600:
                            g["gaps_over_600s"] += 1
                        if gap > g["per_day_max_gap_s"][day]:
                            g["per_day_max_gap_s"][day] = gap
                    last_t[venue] = t
                    msgs = raw if isinstance(raw, list) else [raw]
                    for m in msgs:
                        if not isinstance(m, dict):
                            continue
                        if venue == "polymarket":
                            et = str(m.get("event_type"))
                            pm_types[et] += 1
                            pm_per_day[day] += 1
                            if et == "book":
                                tokens_book.add(str(m.get("asset_id")))
                            elif et == "price_change":
                                for c in m.get("price_changes") or []:
                                    if isinstance(c, dict) and "asset_id" in c:
                                        tokens_quote.add(str(c["asset_id"]))
                                        price_changes += 1
                            elif et == "last_trade_price":
                                trades_per_token[str(m.get("asset_id"))] += 1
                        else:
                            if m.get("method") == "subscription":
                                ch = str(m.get("params", {}).get("channel"))
                                db_channels[ch] += 1
                            else:
                                db_channels[f"non_subscription:{m.get('method') or ('result' if 'result' in m else 'other')}"] += 1
                            db_per_day[day] += 1
    counts = sorted(trades_per_token.values())

    def q(p: float) -> int:
        return counts[min(len(counts) - 1, int(p * len(counts)))] if counts else 0

    out = {
        "rec": str(rec), "window": [_day(start), _day(end)], "elapsed_s": round(time.time() - t0, 1),
        "files": {v: {**{k: (sorted(x) if isinstance(x, set) else x) for k, x in fv.items()}, "n_days": len(fv["days"])} for v, fv in files.items()},
        "messages": {
            "polymarket": {"total": sum(pm_types.values()), "by_type": dict(pm_types), "per_day": dict(sorted(pm_per_day.items())), "price_change_entries": price_changes},
            "deribit": {"total": sum(db_channels.values()), "by_channel": dict(db_channels), "per_day": dict(sorted(db_per_day.items()))},
        },
        "tokens": {
            "with_book_snapshot": len(tokens_book), "with_price_change": len(tokens_quote), "with_any_quote": len(tokens_book | tokens_quote),
            "with_trade_print": len(trades_per_token), "trade_prints_total": sum(counts),
            "trade_prints_per_token_quantiles": {"p10": q(0.10), "p50": q(0.50), "p90": q(0.90), "max": counts[-1] if counts else 0},
            "with_trade_ge10": sum(c >= 10 for c in counts), "with_trade_ge100": sum(c >= 100 for c in counts),
        },
        "gaps": {v: {"max_gap_s": round(g["max_gap_s"], 1), "gaps_over_600s": g["gaps_over_600s"],
                     "per_day_max_gap_s": {d: round(x, 1) for d, x in sorted(g["per_day_max_gap_s"].items())}} for v, g in gaps.items()},
        "token_ids": {"with_any_quote": sorted(tokens_book | tokens_quote), "with_trade_print": sorted(trades_per_token)},
    }
    cat = rec / "polymarket" / "catalogue.jsonl"
    if cat.exists():
        lines, markets, tokens, first, last = 0, set(), set(), None, None
        with cat.open() as fh:
            for line in fh:
                try:
                    d = json.loads(line)
                except json.JSONDecodeError:
                    continue
                lines += 1
                at = float(d.get("at") or 0)
                first = at if first is None else min(first, at)
                last = at if last is None else max(last, at)
                for m in d.get("markets") or []:
                    markets.add(str(m.get("market_id")))
                    tokens.add(str(m.get("yes_token")))
        out["catalogue"] = {"lines": lines, "distinct_markets": len(markets), "distinct_yes_tokens": len(tokens),
                            "first_at": _day(first) if first else None, "last_at": _day(last) if last else None,
                            "tokens_in_catalogue_with_any_quote": len(tokens & (tokens_book | tokens_quote)),
                            "tokens_in_catalogue_with_trade_print": len(tokens & set(trades_per_token))}
    return out


def classify_coverage(rec: Path, counts: dict, read_date: str) -> dict:
    """Laptop stage: the catalogue's markets through the frozen classifier, joined to the stream's token sets."""
    from qr.data import polymarket as pm  # the repo's own regexes, unchanged since registration

    quoted = set(counts["token_ids"]["with_any_quote"])
    traded = set(counts["token_ids"]["with_trade_print"])
    read_ts = datetime.fromisoformat(read_date).replace(tzinfo=timezone.utc)
    markets: dict[str, dict] = {}
    with (rec / "polymarket" / "catalogue.jsonl").open() as fh:
        for line in fh:
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                continue
            for m in d.get("markets") or []:
                tok = str(m.get("yes_token"))
                if tok not in markets:
                    markets[tok] = m
    by_asset_kind: Counter = Counter()
    unclassified = 0
    clusters_all, clusters_quoted, clusters_traded, clusters_resolvable_traded = set(), set(), set(), set()
    n_quoted = n_traded = n_resolvable = 0
    for tok, m in markets.items():
        c = pm.classify(m.get("question") or "")
        if not c:
            unclassified += 1
            continue
        by_asset_kind[f"{c['asset']}:{c['kind']}"] += 1
        try:
            end = datetime.fromisoformat(str(m["end"]).replace("Z", "+00:00"))
        except (KeyError, ValueError):
            continue
        g = (c["asset"], end.strftime("%Y-%m-%d"))
        clusters_all.add(g)
        if tok in quoted:
            n_quoted += 1
            clusters_quoted.add(g)
        if tok in traded:
            n_traded += 1
            clusters_traded.add(g)
            if end <= read_ts:
                n_resolvable += 1
                clusters_resolvable_traded.add(g)
    return {
        "read_date": read_date, "catalogue_markets": len(markets), "classified": len(markets) - unclassified, "unclassified": unclassified,
        "by_asset_kind": dict(sorted(by_asset_kind.items())),
        "classified_with_any_quote": n_quoted, "classified_with_trade_print": n_traded, "classified_traded_ending_by_read_date": n_resolvable,
        "clusters": {"all_classified": len(clusters_all), "with_any_quote": len(clusters_quoted), "with_trade_print": len(clusters_traded),
                     "with_trade_print_ending_by_read_date": len(clusters_resolvable_traded), "memo_minimum_with_a_fill": 30},
        "note": "clusters with a trade print are an upper bound on clusters with a fill; no wedge was computed",
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rec", type=Path, required=True)
    ap.add_argument("--start", default="2026-09-21")
    ap.add_argument("--end", default="2026-10-26")
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--classify", action="store_true", help="second stage (laptop): classify the catalogue and join the stream counts")
    ap.add_argument("--counts", type=Path, default=None, help="first stage's JSON, for --classify")
    ap.add_argument("--read-date", default="2026-10-27")
    a = ap.parse_args(argv)
    if a.classify:
        counts = json.loads(a.counts.read_text())
        cov = classify_coverage(a.rec, counts, a.read_date)
        print(json.dumps(cov, indent=1))
        if a.out:
            a.out.write_text(json.dumps({**{k: v for k, v in counts.items() if k != "token_ids"}, "coverage": cov}, indent=1))
        return 0
    start = datetime.fromisoformat(a.start).replace(tzinfo=timezone.utc).timestamp()
    end = (datetime.fromisoformat(a.end).replace(tzinfo=timezone.utc) + timedelta(days=1)).timestamp()
    out = stream_counts(a.rec, start, end)
    shown = {k: v for k, v in out.items() if k != "token_ids"}
    print(json.dumps(shown, indent=1))
    if a.out:
        a.out.parent.mkdir(parents=True, exist_ok=True)
        a.out.write_text(json.dumps(out))
        print(f"written {a.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
