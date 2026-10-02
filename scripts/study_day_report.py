#!/usr/bin/env python3
"""Stage 1 of the maker-fill study: one day's numbers from the journal, against stage 0's (`docs/24`).

Read-only. Entries are the study's post-only orders (`study_attempts`); a
fill is counted within 60 / 300 / 900 seconds of the venue's acknowledgement;
the adverse-selection mark uses stage 0's convention, `side × (fill − mid_h) /
fill` in bps (positive = the mid moved against the fill) at 5, 60 and 300
seconds; exits are split into maker and taker; money is the wallet change
since the session's opening snapshot, fees and realised P&L apart.

    QR_ROOT=~/qr/lake python scripts/study_day_report.py [--day 2026-10-02] [--account stage1-binance-live]
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from qr.config import paths

STAGE0 = {"fill_900": 0.963, "fill_300": 0.932, "fill_60": 0.838, "median_mark_60": 0.92}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--day", default=datetime.now(timezone.utc).strftime("%Y-%m-%d"))
    ap.add_argument("--account", default="stage1-binance-live")
    ap.add_argument("--out", type=Path, default=None)
    a = ap.parse_args(argv)
    p = paths()
    db = p.root / "study" / "stage1.sqlite"
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    nxt = (pd.Timestamp(a.day) + pd.Timedelta(days=1)).strftime("%Y-%m-%d")
    att = pd.read_sql_query("select a.seq, a.slot, a.symbol, a.side, a.outcome, a.detail, a.client_id, o.state, o.filled_qty from study_attempts a "
                            "left join orders o on o.client_id = a.client_id left join intents i on i.client_id = a.client_id "
                            "where a.slot >= ? and a.slot < ? and (i.account = ? or i.account is null)", con, params=(a.day, nxt, a.account))   # a refused attempt has no intent
    if att.empty:
        print(f"no attempts for {a.day} on {a.account}")
        return 1
    ev = pd.read_sql_query("select client_id, ts, to_state, evidence from order_events", con)
    ex = pd.read_sql_query("select client_id, qty, price, fee, venue_ts from executions", con)
    ack = ev[ev.to_state == "ACKED"].groupby("client_id").ts.min()
    last_fill = ex.groupby("client_id").venue_ts.max().astype("int64")
    placed = att[att.outcome == "placed:ACKED"].copy()
    placed["ack"] = pd.to_datetime(placed.client_id.map(ack), utc=True)
    placed["fill"] = pd.to_datetime(placed.client_id.map(last_fill), unit="ms", utc=True)
    placed["filled"] = placed.state.eq("FILLED")
    placed["wait_s"] = (placed["fill"] - placed["ack"]).dt.total_seconds().where(placed.filled)
    n = len(placed)
    fill = {h: float(((placed.wait_s <= h) & placed.filled).mean()) for h in (60, 300, 900)}
    rej = att[att.outcome == "placed:REJECTED"].copy()
    rej["why"] = rej.client_id.map(ev[ev.to_state == "REJECTED"].groupby("client_id").evidence.last())
    post_only_rej = int(rej.why.fillna("").str.contains("-5022").sum())
    perm_rej = int(rej.why.fillna("").str.contains("-2015").sum())
    refused = att[att.outcome == "refused"]
    # marks
    mk = pd.read_sql_query("select m.client_id, m.symbol, m.side, m.fill_price, h.horizon_s, h.mid from study_marks m join study_mark_horizons h on h.client_id = m.client_id "
                           "where m.client_id in (%s)" % ",".join("?" * len(placed)), con, params=list(placed.client_id))
    marks = {}
    if len(mk):
        mk["bps"] = np.where(mk.side == "BUY", 1.0, -1.0) * (mk.fill_price.astype(float) - mk.mid.astype(float)) / mk.fill_price.astype(float) * 1e4
        for h, g in mk.groupby("horizon_s"):
            marks[int(h)] = (float(g.bps.median()), float(g.bps.mean()), float(g.bps.quantile(0.9)), int(len(g)))
    # exits
    exits = pd.read_sql_query("select i.client_id, i.post_only, i.signal_id, o.state from intents i join orders o on o.client_id = i.client_id "
                              "where i.account = ? and i.action = 'EXIT' and i.staged_at >= ? and i.staged_at < ?", con, params=(a.account, a.day, nxt))
    ex_maker = exits[exits.post_only == 1]
    ex_taker = exits[exits.post_only == 0]
    # money
    day_exec = ex[ex.client_id.isin(set(placed.client_id) | set(exits.client_id))]
    fees = float(day_exec.fee.astype(float).sum())
    notional = float((day_exec.qty.astype(float) * day_exec.price.astype(float)).sum())
    snap = con.execute("select amount from cash_events where account = ? and kind = 'venue_balance_snapshot' and recorded_at >= ? and recorded_at < ? order by recorded_at limit 1", (a.account, a.day, nxt)).fetchone()
    cash_now = con.execute("select amount from cash where account = ? and currency = 'USDT'", (a.account,)).fetchone()
    start, now = (float(snap[0]) if snap else float("nan")), (float(cash_now[0]) if cash_now else float("nan"))
    net = now - start
    open_pos = con.execute("select symbol, qty from positions where account = ? and cast(qty as real) != 0", (a.account,)).fetchall()
    slots = att.slot.nunique()
    L = [f"# Stage 1 — {a.day} (UTC), account `{a.account}`", "",
         f"Slots {slots} ({att.slot.min()[11:16]} → {att.slot.max()[11:16]} UTC); entry attempts {len(att)}: **{n} accepted**, {post_only_rej} post-only rejections (would have crossed), "
         f"{perm_rej} refused for key permissions, {len(refused)} refused by the policy ({', '.join(sorted(set(d.split(':')[0] for d in refused.detail))) or '—'}).", "",
         "| | live today | stage 0 (tape) | rule |", "|---|---|---|---|",
         f"| fill within 60 s | {fill[60]:.1%} | {STAGE0['fill_60']:.1%} | |",
         f"| fill within 300 s | {fill[300]:.1%} | {STAGE0['fill_300']:.1%} | |",
         f"| **fill within 900 s** | **{fill[900]:.1%}** | {STAGE0['fill_900']:.1%} | within 10 points → **{'OK' if abs(fill[900] - STAGE0['fill_900']) <= 0.10 else 'OUTSIDE'}** |",
         f"| median wait to fill | {placed.wait_s.median():.0f} s (p90 {placed.wait_s.quantile(0.9):.0f} s) | 3 s (p90 84 s) | |"]
    for h in (5, 60, 300):
        if h in marks:
            med, mean, p90, k = marks[h]
            L.append(f"| mark at +{h} s (median / mean / p90, bps; n={k}) | {med:+.2f} / {mean:+.2f} / {p90:+.2f} | {'0.92 median' if h == 60 else ''} | {'registered horizon' if h == 60 else ''} |")
    L += ["", f"Exits: {len(ex_maker)} maker orders — " + ", ".join(f"{k.lower()} {v}" for k, v in ex_maker.state.value_counts().items()) + f"; {len(ex_taker)} taker closes"
          + (" — " + ", ".join(f"{k.lower()} {v}" for k, v in ex_taker.state.value_counts().items()) if len(ex_taker) else "") + ". A maker exit that is not filled within its TTL is cancelled and re-posted; an entry on the other side at the next slot nets what is still open.",
          f"Money: wallet {start:.4f} → {now:.4f} USDT, **net {net:+.4f}**; fees {fees:.4f} on {notional:,.0f} of notional ({fees / notional * 1e4 if notional else float('nan'):.2f} bps a side); realised P&L before fees {net + fees:+.4f}.",
          f"Open positions in the journal: {open_pos or 'none'}.", "",
          "By symbol (accepted / filled within 900 s):", ""]
    for sym, g in placed.groupby("symbol"):
        L.append(f"- {sym}: {len(g)} / {int(((g.wait_s <= 900) & g.filled).sum())}; by side " + ", ".join(f"{s} {len(x)}/{int(x.filled.sum())}" for s, x in g.groupby("side")))
    text = "\n".join(L) + "\n"
    out = a.out or Path("reports/stage1") / f"day_{a.day}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text)
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
