#!/usr/bin/env python3
"""C3 kill test: does the Binance mid revert after an OKX/Bybit liquidation burst? (`docs/prereg/p2_liquidation_fade_v1.md`, seq 799)

Runs once, at ≥ 300 merged events on the eighteen names, on the owner's
yes. Events from `qr/research/liq_events.py`; the price path is the
Binance top-of-book tape (`mirror/tape/binance/book/YYYY-MM-DD.jsonl.gz`,
lines `{"t","s","T","b","B","a","A"}`), mid = (b + a)/2 at the nearest
update at or before each stamp. Measured as frozen: signed return from t₀
to t₀ + h for h ∈ {1, 5, 15, 60} min (reversion positive), the move into
the burst (first bin's start → t₀) and the pre-move (t₀ − 5 min → t₀);
HAC-free cluster-robust standard errors by symbol × hour; BTC/ETH as the
control; a placebo stamp per event — same symbol, same day, same hour, a
random minute at least 15 minutes from any burst of that symbol, seed
20260799. Counted in the trial log.

    QR_ROOT=~/qr/lake python scripts/c3_liquidation_fade.py
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from qr.config import paths
from qr.execution.tape import read_tape
from qr.research.liq_events import BINANCE, events
from qr.validate.trial_log import TrialLog

HYP = "p2_liquidation_fade_v1"
HORIZONS_MIN = (1, 5, 15, 60)
SEED = 20260799


# -------------------------------------------------------------- the mid path
def load_mids(tape: Path, days: list[str], symbols: set[str]) -> dict[str, tuple[np.ndarray, np.ndarray]]:
    """Per symbol: sorted exchange timestamps (ms) and mids over the given days."""
    buf: dict[str, list[tuple[int, float]]] = {s: [] for s in symbols}
    for day in days:
        f = tape / "binance" / "book" / f"{day}.jsonl.gz"
        if not f.exists():
            continue
        for rec in read_tape(f):
            s = rec.get("s")
            if s in buf:
                try:
                    buf[s].append((int(rec["T"]), (float(rec["b"]) + float(rec["a"])) / 2))
                except (KeyError, TypeError, ValueError):
                    continue
    out = {}
    for s, rows in buf.items():
        if not rows:
            continue
        a = np.array(rows, dtype=float)
        order = np.argsort(a[:, 0], kind="stable")
        out[s] = (a[order, 0].astype(np.int64), a[order, 1])
    return out


def mid_at(series: tuple[np.ndarray, np.ndarray], t_ms: int, max_stale_ms: int = 120_000) -> float:
    """The mid at the last update at or before `t_ms`; NaN when none within `max_stale_ms`."""
    ts, mids = series
    i = np.searchsorted(ts, t_ms, side="right") - 1
    if i < 0 or t_ms - ts[i] > max_stale_ms:
        return float("nan")
    return float(mids[i])


# ------------------------------------------------------------- measurement
def measure(ev: pd.DataFrame, mids: dict) -> pd.DataFrame:
    rows = []
    for r in ev.itertuples(index=False):
        sym = BINANCE[r.base]
        if sym not in mids:
            continue
        t0 = int(r.t0.timestamp() * 1000)
        m0 = mid_at(mids[sym], t0)
        if not np.isfinite(m0):
            continue
        sign = 1.0 if r.dir == "sell" else -1.0      # after sell-liquidations a bounce is +; after buy-liquidations a drop is +
        row = {"base": r.base, "dir": r.dir, "t0": r.t0, "usd": r.usd, "z": r.z, "bins": r.bins, "control": bool(r.control), "mid0": m0,
               "hour": r.t0.hour, "cluster": f"{r.base}|{r.t0:%Y-%m-%d %H}", "placebo": bool(getattr(r, "placebo", False))}
        m_in = mid_at(mids[sym], int(r.start.timestamp() * 1000)) if hasattr(r, "start") and pd.notna(r.start) else float("nan")
        row["into_bps"] = sign * (m0 / m_in - 1) * 1e4 if np.isfinite(m_in) else float("nan")   # the move into the burst, in the reversion's sign (should be negative)
        m_pre = mid_at(mids[sym], t0 - 300_000)
        row["pre5_bps"] = sign * (m0 / m_pre - 1) * 1e4 if np.isfinite(m_pre) else float("nan")
        for h in HORIZONS_MIN:
            mh = mid_at(mids[sym], t0 + h * 60_000)
            row[f"rev_{h}m_bps"] = sign * (mh / m0 - 1) * 1e4 if np.isfinite(mh) else float("nan")
        rows.append(row)
    return pd.DataFrame(rows)


def clustered(x: pd.Series, cluster: pd.Series) -> dict:
    """Mean with a cluster-robust SE (clusters = symbol × hour)."""
    ok = x.notna()
    x, cluster = x[ok].to_numpy(), cluster[ok].to_numpy()
    if len(x) < 3:
        return {"n": int(len(x)), "mean": float("nan"), "median": float("nan"), "se": float("nan"), "t": float("nan")}
    mean = x.mean()
    sums = pd.Series(x - mean).groupby(cluster).sum()
    G = len(sums)
    se = float(np.sqrt((sums**2).sum()) / len(x) * np.sqrt(G / max(G - 1, 1)))
    return {"n": int(len(x)), "clusters": int(G), "mean": float(mean), "median": float(np.median(x)), "se": se, "t": float(mean / se) if se > 0 else float("nan")}


def placebo_stamps(ev: pd.DataFrame, seed: int = SEED) -> pd.DataFrame:
    """One stamp per event: same symbol, same UTC day and hour, a random minute ≥ 15 min from any burst of that symbol."""
    rng = np.random.default_rng(seed)
    all_t0 = {b: g.t0.to_numpy() for b, g in ev.groupby("base")}
    rows = []
    for r in ev.itertuples(index=False):
        hour_start = r.t0.floor("h")
        others = all_t0[r.base]
        for _ in range(60):
            cand = hour_start + pd.Timedelta(seconds=int(rng.integers(0, 3600)))
            if np.all(np.abs((others - cand.to_datetime64()).astype("timedelta64[s]").astype(int)) >= 900):
                rows.append({"base": r.base, "dir": r.dir, "t0": cand, "start": pd.NaT, "usd": float("nan"), "z": float("nan"), "bins": 0, "control": r.control, "placebo": True})
                break
    return pd.DataFrame(rows)


def verdict(stats: dict) -> dict:
    fam = stats["events"]
    pl = stats["placebo"]
    ctl = stats["control"]
    r15, r1 = fam["rev_15m_bps"], fam["rev_1m_bps"]
    passes_15 = r15["mean"] >= 8.0 and r15["t"] >= 3.0
    placebo_ok = abs(pl["rev_15m_bps"]["mean"]) <= 3.0
    control_smaller = (ctl["rev_15m_bps"]["mean"] < r15["mean"] / 2) if np.isfinite(ctl["rev_15m_bps"]["mean"]) else True
    pre_negative = fam["pre5_bps"]["mean"] < 0
    one_minute_only = (r1["mean"] >= 8.0 and r1["t"] >= 3.0) and not passes_15
    out = {"rev_15m_ge_8bps_t_ge_3": passes_15, "placebo_within_3bps": placebo_ok, "control_reverts_less": control_smaller,
           "pre_move_negative": pre_negative, "one_minute_only": one_minute_only}
    out["PASS"] = passes_15 and placebo_ok and control_smaller and pre_negative
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tape", type=Path, default=None)
    ap.add_argument("--no-log", action="store_true")
    a = ap.parse_args(argv)
    p = paths().ensure()
    mirror = p.root / "mirror"
    tape = a.tape or (mirror / "tape")
    ev, liq = events(mirror)
    ev["placebo"] = False
    names = ev[~ev.control]
    print(f"{len(names)} merged events on the eighteen names, {int(ev.control.sum())} on BTC/ETH; tape days {sorted({d for d in ev.t0.dt.strftime('%Y-%m-%d')})[0]} → {sorted({d for d in ev.t0.dt.strftime('%Y-%m-%d')})[-1]}", flush=True)
    if len(names) < 300:
        print("below the 300-event minimum: the study does not run")
        return 1
    pl = placebo_stamps(ev)
    stamps = pd.concat([ev, pl], ignore_index=True)
    days = sorted({d for d in stamps.t0.dt.strftime("%Y-%m-%d")} | {(t + pd.Timedelta(minutes=61)).strftime("%Y-%m-%d") for t in stamps.t0})
    mids = load_mids(tape, days, set(BINANCE.values()))
    print(f"mid path loaded for {len(mids)} symbols over {len(days)} days", flush=True)
    m = measure(stamps, mids)
    fam, plc = m[~m.control & ~m.placebo], m[~m.control & m.placebo]
    ctl, ctl_pl = m[m.control & ~m.placebo], m[m.control & m.placebo]
    cols = [f"rev_{h}m_bps" for h in HORIZONS_MIN] + ["into_bps", "pre5_bps"]
    stats = {"events": {c: clustered(fam[c], fam["cluster"]) for c in cols}, "placebo": {c: clustered(plc[c], plc["cluster"]) for c in cols},
             "control": {c: clustered(ctl[c], ctl["cluster"]) for c in cols}, "control_placebo": {c: clustered(ctl_pl[c], ctl_pl["cluster"]) for c in cols}}
    stats["by_direction"] = {d: {c: clustered(g[c], g["cluster"]) for c in cols[:4]} for d, g in fam.groupby("dir")}
    v = verdict(stats)
    print("\n%-16s %6s %8s %8s %6s" % ("", "n", "mean bps", "median", "t"))
    for grp in ("events", "placebo", "control"):
        for c in cols:
            s = stats[grp][c]
            print("%-16s %6d %8.2f %8.2f %6.2f" % (f"{grp}:{c}", s["n"], s["mean"], s["median"], s["t"]))
    print("\nverdict:", json.dumps(v))
    out = p.root / "reports" / "c3"
    out.mkdir(parents=True, exist_ok=True)
    m.to_parquet(out / f"{HYP}_measurements.parquet", index=False)
    (out / f"{HYP}_summary.json").write_text(json.dumps({"hypothesis": HYP, "n_events": int(len(fam)), "n_control": int(len(ctl)), "stats": stats, "verdict": v}, indent=1, default=str))
    if not a.no_log:
        rec = TrialLog(p.trial_log).run(HYP, "liquidation_fade", {"engine": "scripts/c3_liquidation_fade.py", "horizons_min": HORIZONS_MIN, "events": int(len(fam))}, "okx_bybit_liquidations_x_binance_tape",
                                         metrics={"rev_15m": stats["events"]["rev_15m_bps"], "rev_1m": stats["events"]["rev_1m_bps"], "placebo_15m": stats["placebo"]["rev_15m_bps"], "control_15m": stats["control"]["rev_15m_bps"], "verdict": v}, variants=1)
        print("trial log seq", rec.seq)
    return 0


if __name__ == "__main__":
    sys.exit(main())
