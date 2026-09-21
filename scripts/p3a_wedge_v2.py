#!/usr/bin/env python3
"""P3-A v2 kill test on the recorded intraday book (`docs/prereg/p3_threshold_wedge_v2_intraday.md`, seq 934).

    QR_ROOT=~/qr/lake python scripts/p3a_wedge_v2.py --start 2026-09-21 --end 2026-10-26            # the registered read, 27 October
    QR_ROOT=~/qr/lake python scripts/p3a_wedge_v2.py --start ... --end ... --mirror <dir> --no-log  # fixtures only

Inputs: the mirrored recording (`mirror/polymarket_live/{polymarket,deribit}`),
the recorder's `catalogue.jsonl` (every hourly refresh), resolutions from
Gamma at read time (`--resolutions <json>` to pass them instead). Writes
the trade table, the summary and the fill statistics under `reports/p3/`
and counts itself in the trial log. The minimum sample (30 asset ×
settlement-date clusters with a fill) is checked and printed; the verdict
line says "DEFERRED" when it is not met.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd

from qr.config import paths
from qr.data import polymarket as pm
from qr.execution.pm_replay import Market, WedgeSession, iter_events
from qr.validate import stats as st
from qr.validate.trial_log import TrialLog

HYP = "p3_threshold_wedge_v2_intraday"
GRID = [{"k": k, "T": T} for k in (0.05, 0.08) for T in (3, "resolution")]
MIN_CLUSTERS = 30
CAP_USD, MAX_OPEN, SLEEVE = 25.0, 5, 200.0


def load_markets(rec_dir: Path) -> dict[str, Market]:
    out: dict[str, Market] = {}
    with (rec_dir / "polymarket" / "catalogue.jsonl").open() as fh:
        for line in fh:
            for m in json.loads(line)["markets"]:
                if m["yes_token"] in out:
                    continue
                c = pm.classify(m["question"])
                if not c:
                    continue
                out[m["yes_token"]] = Market(m["yes_token"], m["market_id"], c["asset"], c["kind"], c["strike"], pd.Timestamp(m["end"]).tz_convert("UTC") if pd.Timestamp(m["end"]).tzinfo else pd.Timestamp(m["end"], tz="UTC"))
    return out


def fetch_resolutions(markets: dict[str, Market]) -> dict[str, float | None]:
    res = {}
    for mk in markets.values():
        try:
            with urllib.request.urlopen(urllib.request.Request(f"{pm.GAMMA}/markets/{mk.market_id}", headers={"User-Agent": "Mozilla/5.0"}), timeout=30) as r:
                d = json.loads(r.read())
            prices = d.get("outcomePrices")
            if isinstance(prices, str):
                prices = json.loads(prices)
            res[mk.market_id] = float(prices[0]) if (d.get("closed") and prices) else None
        except Exception:  # noqa: BLE001
            res[mk.market_id] = None
    return res


def clustered(tr: pd.DataFrame) -> dict:
    e = tr["edge"].to_numpy()
    g = (tr["asset"].astype(str) + "|" + tr["end"].dt.normalize().astype(str)).to_numpy()
    N, mean = len(e), e.mean()
    df = pd.DataFrame({"e": e - mean, "g": g}).groupby("g")["e"].sum()
    G = len(df)
    se = np.sqrt((df**2).sum()) / N * np.sqrt(G / max(G - 1, 1))
    return {"n_trades": int(N), "n_clusters": int(G), "mean_edge": float(mean), "se": float(se), "t": float(mean / se) if se > 0 else float("nan"),
            "win_rate": float((e > 0).mean()), "mean_hold_days": float(tr["hold_days"].mean())}


def book_returns(tr: pd.DataFrame, side: str) -> pd.Series:
    """The capped book's daily P&L on the $200 sleeve: ≤ 5 open, $25 of capital each, cash flows at fill and exit."""
    tr = tr.sort_values("fill_day").reset_index(drop=True)
    open_pos: list[pd.Timestamp] = []
    flows = {}
    for _, r in tr.iterrows():
        open_pos = [d for d in open_pos if d > r.fill_day]
        if len(open_pos) >= MAX_OPEN:
            continue
        open_pos.append(r.exit_day)
        n = CAP_USD / r.capital_per_share
        d = r.exit_day.normalize()
        flows[d] = flows.get(d, 0.0) + n * r.edge
    if not flows:
        return pd.Series(dtype=float)
    s = pd.Series(flows).sort_index() / SLEEVE
    return s.reindex(pd.date_range(s.index.min(), s.index.max(), freq="D", tz="UTC")).fillna(0.0)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", required=True)
    ap.add_argument("--end", required=True)
    ap.add_argument("--mirror", type=Path, default=None, help="recording directory (default <lake>/mirror/polymarket_live)")
    ap.add_argument("--resolutions", type=Path, default=None, help="json {market_id: resolved_yes} instead of Gamma")
    ap.add_argument("--no-log", action="store_true")
    a = ap.parse_args(argv)
    p = paths().ensure()
    rec = a.mirror or (p.root / "mirror" / "polymarket_live")
    start, end = pd.Timestamp(a.start, tz="UTC"), pd.Timestamp(a.end, tz="UTC") + pd.Timedelta(days=1)
    markets = load_markets(rec)
    res = json.loads(a.resolutions.read_text()) if a.resolutions else fetch_resolutions(markets)
    for mk in markets.values():
        mk.resolved_yes = res.get(mk.market_id)
    print(f"{len(markets)} markets in the recording, {sum(v is not None for v in res.values())} resolved", flush=True)
    runs = [(f"k{int(v['k']*100)}_T{v['T']}", v["k"], v["T"], "sell", "dvol", False) for v in GRID]
    runs += [(f"mirror_k{int(v['k']*100)}_T{v['T']}", v["k"], v["T"], "buy", "dvol", False) for v in GRID]
    runs += [(f"placebo_k{int(v['k']*100)}_T{v['T']}", v["k"], v["T"], "sell", "rv", False) for v in GRID]
    runs += [("naive_le20c", 0.0, "resolution", "sell", "dvol", True)]
    results, books, tables = {}, {}, []
    for name, k, T, side, sig, naive in runs:
        sess = WedgeSession({t: Market(**{**m.__dict__}) for t, m in markets.items()}, k, T, side, sigma_source=sig, naive=naive)
        sess.run(iter_events(rec, start, end))
        tr = sess.trade_table()
        n_attempt = len(tr)
        filled = tr[tr["edge"].notna()].copy() if len(tr) else tr
        r = {"attempts": int(n_attempt), "unfilled": int((tr.get("reason") == "entry_unfilled").sum()) if len(tr) else 0,
             "unresolved": int((tr.get("reason") == "unresolved_at_read").sum()) if len(tr) else 0}
        if len(filled):
            r.update(clustered(filled))
            r["fill_rate"] = float(len(filled) / max(n_attempt - r["unresolved"], 1))
            r["crossed_share"] = float(filled["reason"].str.startswith("crossed").mean())
            b = book_returns(filled, side)
            r["book_sharpe"] = st.annualised_sharpe(b, 365.0) if len(b) > 10 else float("nan")
            r["book_total_return"] = float(b.sum()) if len(b) else 0.0
            books[name] = b
            filled.insert(0, "run", name)
            tables.append(filled)
        results[name] = r
        print(f"{name:26s} attempts={r['attempts']:4d} filled={r.get('n_trades',0):4d} clusters={r.get('n_clusters',0):3d} fill_rate={r.get('fill_rate',float('nan')):.2f} edge={r.get('mean_edge',float('nan'))*100:6.2f}pt t={r.get('t',float('nan')):5.2f} book_sharpe={r.get('book_sharpe',float('nan')):.2f}", flush=True)
    fam = results.get("k5_T3", {})
    verdict = "DEFERRED (below the cluster minimum)" if fam.get("n_clusters", 0) < MIN_CLUSTERS else "READ"
    print(f"family clusters at k=5: {fam.get('n_clusters', 0)} (minimum {MIN_CLUSTERS}) → {verdict}")
    out = p.root / "reports" / "p3"
    out.mkdir(parents=True, exist_ok=True)
    tag = f"{a.start}_{a.end}"
    if tables:
        pd.concat(tables).to_parquet(out / f"{HYP}_{tag}_trades.parquet", index=False)
    (out / f"{HYP}_{tag}_summary.json").write_text(json.dumps({"hypothesis": HYP, "window": [a.start, a.end], "results": results, "verdict": verdict, "grid": GRID}, indent=1, default=str))
    if not a.no_log:
        log = TrialLog(p.trial_log)
        rec_ = log.run(HYP, "threshold_wedge_intraday", {"grid": GRID, "window": [a.start, a.end], "engine": "scripts/p3a_wedge_v2.py"}, "polymarket_live_recording",
                       metrics={n: {kk: results[n].get(kk) for kk in ("n_trades", "n_clusters", "fill_rate", "mean_edge", "t", "book_sharpe")} for n in results} | {"verdict": verdict}, variants=len(GRID))
        print("trial log seq", rec_.seq)
    return 0


if __name__ == "__main__":
    sys.exit(main())
