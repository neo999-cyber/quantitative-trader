#!/usr/bin/env python3
"""The three runnable scenarios from cloud9markets.com's "24/7 AI trading bot" page, run on our own data (15 Oct 2026).

`docs/research/10_cloud9_decision_bot_review.md`. The page (a research-desk write-up of a paper-trading
"decision engine": code computes order-book features every second, a decision model is woken only when
the market moves, plain-code policy, risk engine vetoes) makes three things that can be run without
calling the model or spending anything:

1. **wake** — its trigger rule ("only think when the market moves": 5 bps mid move, imbalance shift,
   volatility ratio crossing 1.5, an aggressive-flow burst of 4× the usual pace and ≥ $250k in 10 s, a
   30-second heartbeat, at least 3 s between calls) on one day of our recorded Binance tape; it claims
   85–95% of seconds skipped and its live desk shows 92.9%. The tape is top-of-book and every print, so
   the depth triggers (walls, absorption, book drain) cannot be computed here; the measured wake rate is
   therefore a *floor*.
2. **macross** — the baseline strategy it tells readers to start with: a 20/50 moving-average cross on
   15-minute BTC candles, long above both, short below both, exit on the opposite cross, "backtest it
   with fees and slippage; if it loses money on its own, the AI filter won't rescue it". Run on the
   Binance USDⓈ-M BTCUSDT 15-minute bars, January 2024 → September 2026, at our measured costs.
   Counted in the trial log as a review run (not a candidate; no registration).
3. **policy** — its plain-code policy table applied to the answers its live desk displayed on 15 October,
   to check the table reproduces the action the desk showed (TRADE SMALL).

    QR_ROOT=~/qr/lake python scripts/review_cloud9_scenarios.py wake --day 2026-09-20 --symbol BTCUSDT
    QR_ROOT=~/qr/lake python scripts/review_cloud9_scenarios.py macross --bars <dir of monthly 15m zips>
    python scripts/review_cloud9_scenarios.py policy
"""
from __future__ import annotations

import argparse
import csv
import glob
import io
import json
import math
import statistics
import sys
import zipfile
from collections import deque
from pathlib import Path

COST_PER_CALL = 0.000026   # the desk's own measured figure, USD


# ------------------------------------------------------------------ 1. wake
def wake(tape: Path, day: str, symbol: str, cost_per_call: float = COST_PER_CALL) -> dict:
    from qr.execution.tape import merge_streams, read_tape

    book = (r for r in read_tape(tape / "binance" / "book" / f"{day}.jsonl.gz") if r.get("s") == symbol)
    trades = (r for r in read_tape(tape / "binance" / "trade" / f"{day}.jsonl.gz") if r.get("s") == symbol)
    mid = None
    imb = None
    flow = deque()            # (T_ms, notional, taker_bought)
    mids_1s = deque(maxlen=61)  # one mid a second, for the 60-s realised vol
    rv_hist = deque(maxlen=3600)
    flow_hist = deque(maxlen=3600)
    imb_10 = deque(maxlen=10)
    last_look = {"t": None, "mid": None, "imb": None, "vol_above": False}
    seconds = 0
    calls = 0
    reasons = {"mid_5bps": 0, "imbalance_shift": 0, "vol_ratio_1.5": 0, "aggressive_burst": 0, "heartbeat": 0}
    cur_sec = None
    first_sec = None
    for kind, rec in merge_streams(book, trades):
        T = int(rec.get("T", rec["t"]))
        if kind == "book":
            b, a = float(rec["b"]), float(rec["a"])
            B, A = float(rec["B"]), float(rec["A"])
            mid = (b + a) / 2
            imb = B / (B + A) if (B + A) > 0 else 0.5
        else:
            p, q = float(rec["p"]), float(rec["q"])
            flow.append((T, p * q, not bool(rec.get("m"))))
        sec = T // 1000
        if cur_sec is None:
            cur_sec, first_sec = sec, sec
            continue
        if sec == cur_sec or mid is None:
            continue
        # a new second: evaluate the previous one on the state at its end
        seconds += 1
        while flow and flow[0][0] < (cur_sec - 10) * 1000:
            flow.popleft()
        notional_10 = sum(n for _, n, _ in flow)
        mids_1s.append(mid)
        if imb is not None:
            imb_10.append(imb)
        imb10 = statistics.fmean(imb_10) if imb_10 else 0.5
        rv = 0.0
        if len(mids_1s) >= 30:
            rets = [math.log(mids_1s[i] / mids_1s[i - 1]) for i in range(1, len(mids_1s)) if mids_1s[i - 1] > 0]
            rv = statistics.pstdev(rets) if len(rets) > 2 else 0.0
        rv_hist.append(rv)
        flow_hist.append(notional_10)
        rv_med = statistics.median(rv_hist) if len(rv_hist) >= 300 else None
        flow_med = statistics.median(flow_hist) if len(flow_hist) >= 300 else None
        vol_ratio = (rv / rv_med) if (rv_med and rv_med > 0) else 0.0
        fired = None
        if last_look["t"] is None:
            fired = "heartbeat"
        elif cur_sec - last_look["t"] >= 3:
            if abs(mid / last_look["mid"] - 1) >= 0.0005:
                fired = "mid_5bps"
            elif abs(imb10 - last_look["imb"]) >= 0.35:
                fired = "imbalance_shift"
            elif vol_ratio >= 1.5 and not last_look["vol_above"]:
                fired = "vol_ratio_1.5"
            elif flow_med is not None and notional_10 >= 250_000 and notional_10 >= 4 * flow_med:
                fired = "aggressive_burst"
            elif cur_sec - last_look["t"] >= 30:
                fired = "heartbeat"
        if fired:
            calls += 1
            reasons[fired] += 1
            last_look = {"t": cur_sec, "mid": mid, "imb": imb10, "vol_above": vol_ratio >= 1.5}
        cur_sec = sec
    hours = (cur_sec - first_sec) / 3600 if cur_sec and first_sec else 0
    return {"day": day, "symbol": symbol, "seconds": seconds, "hours": round(hours, 2), "calls": calls,
            "skipped_pct": round(100 * (1 - calls / seconds), 1) if seconds else None,
            "calls_per_minute": round(calls / max(hours * 60, 1e-9), 2), "calls_per_day_equiv": round(calls / max(hours, 1e-9) * 24),
            "cost_per_day_usd": round(calls / max(hours, 1e-9) * 24 * cost_per_call, 3), "by_reason": reasons,
            "note": "top-of-book and prints only: the depth triggers (walls, absorption, book drain) are not computable here, so this wake rate is a floor"}


# -------------------------------------------------------------- 2. macross
def load_15m(bars_dir: Path):
    import pandas as pd

    frames = []
    for z in sorted(glob.glob(str(bars_dir / "*.zip"))):
        with zipfile.ZipFile(z) as zf:
            name = zf.namelist()[0]
            raw = zf.read(name).decode()
        rows = list(csv.reader(io.StringIO(raw)))
        if rows and rows[0][0] == "open_time":
            rows = rows[1:]
        frames.append(pd.DataFrame([r[:6] for r in rows], columns=["open_time", "open", "high", "low", "close", "volume"]))
    df = pd.concat(frames, ignore_index=True)
    df["open_time"] = pd.to_datetime(df["open_time"].astype("int64"), unit="ms", utc=True)
    for c in ("open", "high", "low", "close", "volume"):
        df[c] = df[c].astype(float)
    return df.drop_duplicates("open_time").sort_values("open_time").set_index("open_time")


def macross(bars_dir: Path, fast: int = 20, slow: int = 50, fee_bps_side: float = 5.5, slippage_bps: float = 1.0, stop_pct: float | None = None) -> dict:
    """The page's baseline: long when the 20 crosses above the 50 with price above both, short on the mirror, exit on the opposite cross.

    Decisions on a bar's close, filled at the next bar's open (no look-ahead); a stop, when given, is checked against the
    next bars' lows/highs and filled at the stop price. Costs per side: the fee plus slippage, both in bps of notional.
    """
    import numpy as np
    import pandas as pd

    df = load_15m(bars_dir)
    c = df["close"]
    f, s = c.rolling(fast).mean(), c.rolling(slow).mean()
    above = (f > s) & (c > f) & (c > s)
    below = (f < s) & (c < f) & (c < s)
    cross_up = (f > s) & (f.shift(1) <= s.shift(1))
    cross_dn = (f < s) & (f.shift(1) >= s.shift(1))
    opens, highs, lows = df["open"].to_numpy(), df["high"].to_numpy(), df["low"].to_numpy()
    cu, cd, ab, bl = cross_up.to_numpy(), cross_dn.to_numpy(), above.to_numpy(), below.to_numpy()
    idx = df.index
    pos = 0
    entry_px = None
    trades = []
    cost = (fee_bps_side + slippage_bps) / 1e4
    pending = None  # ("LONG"|"SHORT"|"FLAT") to execute at the next open
    for i in range(1, len(df) - 1):
        if pending is not None:
            px = opens[i]
            if pos != 0:
                trades.append({"exit_time": idx[i], "side": pos, "entry": entry_px, "exit": px, "ret_gross": pos * (px / entry_px - 1), "reason": pending[1]})
                pos, entry_px = 0, None
            if pending[0] == "LONG":
                pos, entry_px, entry_i = 1, px, i
            elif pending[0] == "SHORT":
                pos, entry_px, entry_i = -1, px, i
            pending = None
        if pos != 0 and stop_pct is not None:
            if pos == 1 and lows[i] <= entry_px * (1 - stop_pct):
                px = entry_px * (1 - stop_pct)
                trades.append({"exit_time": idx[i], "side": pos, "entry": entry_px, "exit": px, "ret_gross": pos * (px / entry_px - 1), "reason": "stop"})
                pos, entry_px = 0, None
            elif pos == -1 and highs[i] >= entry_px * (1 + stop_pct):
                px = entry_px * (1 + stop_pct)
                trades.append({"exit_time": idx[i], "side": pos, "entry": entry_px, "exit": px, "ret_gross": pos * (px / entry_px - 1), "reason": "stop"})
                pos, entry_px = 0, None
        # decide on this bar's close for the next open
        if pos == 1 and cd[i]:
            pending = ("SHORT" if bl[i] else "FLAT", "cross")
        elif pos == -1 and cu[i]:
            pending = ("LONG" if ab[i] else "FLAT", "cross")
        elif pos == 0:
            if cu[i] and ab[i]:
                pending = ("LONG", "entry")
            elif cd[i] and bl[i]:
                pending = ("SHORT", "entry")
    tr = pd.DataFrame(trades)
    if tr.empty:
        return {"trades": 0}
    tr["ret_net"] = tr["ret_gross"] - 2 * cost
    daily = tr.set_index("exit_time")["ret_net"].resample("1D").sum()
    gross_total = float((1 + tr["ret_gross"]).prod() - 1)
    net_total = float((1 + tr["ret_net"]).prod() - 1)
    years = (idx[-1] - idx[0]).days / 365.25
    sharpe = float(daily.mean() / daily.std() * np.sqrt(365)) if daily.std() > 0 else float("nan")
    eq = (1 + tr["ret_net"]).cumprod()
    dd = float((eq / eq.cummax() - 1).min())
    return {"bars": int(len(df)), "from": str(idx[0].date()), "to": str(idx[-1].date()), "years": round(years, 2), "fast": fast, "slow": slow,
            "fee_bps_side": fee_bps_side, "slippage_bps": slippage_bps, "stop_pct": stop_pct,
            "trades": int(len(tr)), "trades_per_year": round(len(tr) / years, 1), "win_rate_net": round(float((tr["ret_net"] > 0).mean()), 3),
            "mean_gross_per_trade_bps": round(float(tr["ret_gross"].mean() * 1e4), 1), "round_trip_cost_bps": 2 * (fee_bps_side + slippage_bps),
            "mean_net_per_trade_bps": round(float(tr["ret_net"].mean() * 1e4), 1),
            "gross_total_return": round(gross_total, 3), "net_total_return": round(net_total, 3), "net_cagr": round((1 + net_total) ** (1 / years) - 1, 3) if net_total > -1 else -1.0,
            "net_sharpe_daily": round(sharpe, 2), "max_drawdown_net": round(dd, 3),
            "exit_reasons": {k: int(v) for k, v in tr["reason"].value_counts().items()}}


# ---------------------------------------------------------------- 3. policy
SCORE_LEVELS = {"conditions": ["Do not quote", "Marginal", "Standard", "Excellent"], "safe": ["Stay out", "Caution", "OK", "Ideal"]}


def policy(answers: dict) -> str:
    """The page's table, in its stated order; score answers are the most likely level (an index)."""
    if answers["cascade"] >= 0.70:
        return "GET OUT"
    if answers["smart_money_flow"] >= 0.60:
        return "GET OUT"
    if answers["thin_book"] >= 0.70:
        return "CAUTION"
    if answers["fake_walls"] >= 0.70:
        return "CAUTION"
    if answers["conditions"] >= 2 and answers["confidence"] >= 0.80 and answers["safe_to_trade"] >= 2:
        return "GREEN LIGHT"
    if answers["conditions"] >= 1:
        return "TRADE SMALL"
    return "SIT OUT"


DESK_15_OCT = {  # what hft.cloud9markets.com displayed at the read on 15 October 2026, 21:15 UTC on its clock
    "regime": "mean_reverting", "regime_probs": {"crisis": 0.02, "high_vol": 0.14, "mean_reverting": 0.44, "trending": 0.39}, "confidence": 0.26,
    "bias_30s": "down", "smart_money_flow": 0.27, "thin_book": 0.62, "conditions": 1, "conditions_score": 1.58, "cascade": 0.18,
    "fake_walls": 0.65, "whale": "quietly_selling", "safe_to_trade": 0, "safe_score": 0.72,
}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("scenario", choices=["wake", "macross", "policy", "all"])
    ap.add_argument("--day", default="2026-09-20")
    ap.add_argument("--symbol", default="BTCUSDT")
    ap.add_argument("--bars", type=Path, default=None, help="directory of Binance monthly 15m kline zips")
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--no-log", action="store_true")
    a = ap.parse_args(argv)
    results = {}
    if a.scenario in ("wake", "all"):
        from qr.config import paths
        results["wake"] = wake(paths().root / "mirror" / "tape", a.day, a.symbol)
        print(json.dumps(results["wake"], indent=1))
    if a.scenario in ("macross", "all"):
        results["macross"] = {
            "taker_5.5bps": macross(a.bars, fee_bps_side=5.5),
            "maker_3.2bps": macross(a.bars, fee_bps_side=3.2),
            "free": macross(a.bars, fee_bps_side=0.0, slippage_bps=0.0),
            "taker_5.5bps_stop_1pct": macross(a.bars, fee_bps_side=5.5, stop_pct=0.01),
        }
        print(json.dumps(results["macross"], indent=1, default=str))
        if not a.no_log:
            from qr.config import paths
            from qr.validate.trial_log import TrialLog

            log = TrialLog(paths().ensure().trial_log)
            rec = log.run("review_cloud9_ma_cross_15m", "ma_cross_review", {"fast": 20, "slow": 50, "bars": "binance futures/um BTCUSDT 15m 2024-01..2026-09", "engine": "scripts/review_cloud9_scenarios.py"},
                          "BTCUSDT", metrics={k: {kk: v.get(kk) for kk in ("trades", "net_sharpe_daily", "net_total_return", "mean_net_per_trade_bps", "max_drawdown_net")} for k, v in results["macross"].items()},
                          variants=4, note="a review replication of a website's baseline, not a registered candidate")
            print("trial log seq", rec.seq)
    if a.scenario in ("policy", "all"):
        action = policy(DESK_15_OCT)
        results["policy"] = {"desk_answers": DESK_15_OCT, "table_says": action, "desk_showed": "TRADE SMALL", "agree": action == "TRADE SMALL"}
        print(json.dumps(results["policy"], indent=1))
    if a.out:
        a.out.write_text(json.dumps(results, indent=1, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
