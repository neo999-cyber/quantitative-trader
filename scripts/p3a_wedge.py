#!/usr/bin/env python3
"""P3-A kill test: the Polymarket wedge over the options-implied probability (`docs/prereg/p3_threshold_wedge_v1.md`, seq 932).

Reads the frozen catalogue, the mirrored daily YES prices, DVOL and spot
from the lake; computes the model probability per market-day; runs the
registered rule, its four variants and three controls; writes the
per-trade table, the daily book P&L and a summary under `reports/p3/`;
**counts itself in the trial log** (one run record per family/control,
`variants` = grid size). It writes nothing to the catalogue or the mirror
except the spot cache.

    QR_ROOT=~/qr/lake python scripts/p3a_wedge.py            # in-sample only (markets ending before 2026-06-01)
    QR_ROOT=~/qr/lake python scripts/p3a_wedge.py --holdout  # the holdout, once, after the in-sample verdict

Conventions, as registered: a decision on day t fills at day t+1's print;
1-point haircut per fill; settlement at 0/1 with no haircut; one position
per market; one market per asset × end date (largest wedge at entry) for
the per-share population; the book adds the 5-open / $25 caps on a $200
sleeve. Standard errors clustered by asset × end date.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm

from qr.config import paths
from qr.data import polymarket as pm
from qr.data.deribit import load_dvol
from qr.data.lake import Lake
from qr.validate import stats as st
from qr.validate.cscv import cscv
from qr.validate.trial_log import TrialLog

HYP = "p3_threshold_wedge_v1"
FAMILY = "threshold_wedge"
HOLDOUT_START = pd.Timestamp("2026-06-01", tz="UTC")
HOLDOUT_END = pd.Timestamp("2026-09-20", tz="UTC")
HAIRCUT = 0.01
EXIT_X = 0.02
CAP_USD, MAX_OPEN, SLEEVE = 25.0, 5, 200.0
GRID = [{"k": k, "T": T} for k in (0.05, 0.08) for T in ("resolution", 7)]
PPY = 365.0
SPOT = {"BTC": "BTCUSDT", "ETH": "ETHUSDT", "SOL": "SOLUSDT"}


# ---------------------------------------------------------------- inputs
def spot_closes(lake: Lake, mirror: Path) -> pd.DataFrame:
    """Daily spot close per asset from the lake, the September tail from the bucket's daily files (cached)."""
    cache = mirror / "p3" / "spot_daily.parquet"
    if cache.exists():
        return pd.read_parquet(cache)
    from qr.data.binance import BinanceBucket, HttpBucket
    bucket = BinanceBucket(HttpBucket(), market="spot")
    out = {}
    for asset, sym in SPOT.items():
        s = lake.read_klines(sym, "1d")["close"]
        tail = bucket.load_klines(sym, "1d", start=(s.index.max() + pd.Timedelta(days=1)).strftime("%Y-%m-%d"), cadence="daily")["close"]
        out[asset] = pd.concat([s, tail]).sort_index()
        out[asset] = out[asset][~out[asset].index.duplicated(keep="last")]
    df = pd.DataFrame(out)
    df.index = df.index.normalize()
    cache.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(cache)
    return df


def realised_vol(spot: pd.DataFrame, window: int = 30) -> pd.DataFrame:
    """Past-only annualised realised vol in vol points, like DVOL."""
    return np.log(spot).diff().rolling(window).std() * math.sqrt(PPY) * 100.0


# ----------------------------------------------------------------- model
def model_prob(kind: str, S: np.ndarray, X: float, sigma: np.ndarray, tau: np.ndarray) -> np.ndarray:
    """The registered probabilities: Φ(d₂) terminal; reflection-principle touch for barriers."""
    with np.errstate(divide="ignore", invalid="ignore"):
        sig_t = sigma * np.sqrt(tau)
        mu = -0.5 * sigma**2
        if kind == "above":
            d2 = (np.log(S / X) + mu * tau) / sig_t
            return norm.cdf(d2)
        if kind == "reach":
            b = np.log(X / S)
            p = norm.cdf((-b + mu * tau) / sig_t) + np.exp(2 * mu * b / sigma**2) * norm.cdf((-b - mu * tau) / sig_t)
            return np.where(b <= 0, 1.0, p)
        if kind == "dip":
            b = np.log(S / X)
            mu = -mu
            p = norm.cdf((-b + mu * tau) / sig_t) + np.exp(2 * mu * b / sigma**2) * norm.cdf((-b - mu * tau) / sig_t)
            return np.where(b <= 0, 1.0, p)
    raise ValueError(kind)


def market_panel(row, mirror: Path, spot: pd.DataFrame, vol: pd.DataFrame) -> pd.DataFrame | None:
    """Per-day frame for one market: price, spot, sigma, tau, p_model, wedge. None when there is no history."""
    px = pm.price_history(mirror, row.yes_token)
    if px.empty:
        return None
    end = row.end.normalize()
    days = px.index[(px.index < end)]
    if len(days) < 2:
        return None
    px = px.reindex(days)
    S = spot[row.asset].reindex(days)
    sig = vol[row.asset].reindex(days) / 100.0
    tau = ((end - days).days.to_numpy()) / PPY
    p = model_prob(row.kind, S.to_numpy(), float(row.strike), sig.to_numpy(), tau)
    f = pd.DataFrame({"price": px.to_numpy(), "spot": S.to_numpy(), "sigma": sig.to_numpy(), "tau": tau, "p_model": p}, index=days)
    f["wedge"] = f["price"] - f["p_model"]
    return f.dropna(subset=["price", "p_model"])


# ------------------------------------------------------------------ rule
def simulate(panels: dict, cat: pd.DataFrame, k: float, T, side: str, naive: bool = False) -> tuple[pd.DataFrame, pd.Series]:
    """All markets, chronologically; returns the trade table (per-share population, one per asset×end) and the capped book's daily return.

    side="sell": short YES on wedge >= k (the family / placebo). side="buy": the mirror. naive: short every
    YES <= 0.20 at first sight, hold to resolution.
    """
    # candidate entries: (decision day, market, wedge)
    cands = []
    for mid, f in panels.items():
        r = cat.loc[mid]
        if naive:
            first = f.index[0]
            if f["price"].iloc[0] <= 0.20:
                cands.append((first, mid, -f["price"].iloc[0]))
            continue
        w = f["wedge"] if side == "sell" else -f["wedge"]
        hit = w[w >= k]
        if len(hit):
            t0 = hit.index[0]
            cands.append((t0, mid, float(hit.iloc[0])))
    cands.sort(key=lambda c: (c[0], -c[2]))
    taken_group: set = set()
    trades = []
    open_until: dict[str, pd.Timestamp] = {}
    daily = {}
    for t0, mid, w in cands:
        r = cat.loc[mid]
        f = panels[mid]
        group = (r.asset, r.end.normalize())
        if group in taken_group:
            continue
        pos = f.index.get_loc(t0)
        if pos + 1 >= len(f):
            continue  # no next-day print to fill on
        t_fill = f.index[pos + 1]
        p_fill = f["price"].iloc[pos + 1]
        fill = p_fill - HAIRCUT if side == "sell" else p_fill + HAIRCUT
        if not (0.0 < fill < 1.0):
            continue
        taken_group.add(group)
        # exit search from the day after the fill
        exit_day, exit_px, reason = None, None, "resolution"
        if not naive:
            for u in range(pos + 2, len(f)):
                day = f.index[u]
                w_u = f["wedge"].iloc[u] if side == "sell" else -f["wedge"].iloc[u]
                held = (day - t_fill).days
                if w_u <= EXIT_X or (T != "resolution" and held >= T):
                    if u + 1 < len(f):
                        exit_day = f.index[u + 1]
                        exit_px = f["price"].iloc[u + 1] + HAIRCUT if side == "sell" else f["price"].iloc[u + 1] - HAIRCUT
                        reason = "wedge_closed" if w_u <= EXIT_X else "max_hold"
                    break
        if exit_day is None:
            exit_day = r.end.normalize()
            exit_px = float(round(r.resolved_yes))
        edge = (fill - exit_px) if side == "sell" else (exit_px - fill)
        per_share_capital = (1 - fill) if side == "sell" else fill
        trades.append({"market_id": mid, "asset": r.asset, "kind": r.kind, "end": r.end.normalize(), "decision": t0, "fill_day": t_fill,
                       "fill": fill, "exit_day": exit_day, "exit": exit_px, "reason": reason, "edge": edge, "wedge_at_entry": w,
                       "capital_per_share": per_share_capital, "hold_days": (exit_day - t_fill).days})
    tr = pd.DataFrame(trades)
    if tr.empty:
        return tr, pd.Series(dtype=float)
    # the capped book: chronological, ≤ MAX_OPEN open, $CAP each, mark-to-market daily from the mirrored prints
    tr = tr.sort_values(["fill_day", "wedge_at_entry"], ascending=[True, False]).reset_index(drop=True)
    open_pos: list[tuple[pd.Timestamp, int]] = []
    in_book = np.zeros(len(tr), dtype=bool)
    for i, row in tr.iterrows():
        open_pos = [(d, j) for d, j in open_pos if d > row.fill_day]
        if len(open_pos) < MAX_OPEN:
            open_pos.append((row.exit_day, i))
            in_book[i] = True
    tr["in_book"] = in_book
    pnl = {}
    for i, row in tr[tr.in_book].iterrows():
        f = panels[row.market_id]
        n = CAP_USD / row.capital_per_share
        path = f["price"][(f.index > row.fill_day) & (f.index < row.exit_day)]
        marks = pd.concat([pd.Series([row.fill], index=[row.fill_day]), path, pd.Series([row.exit], index=[row.exit_day])])
        d = marks.diff().dropna() * n * (-1.0 if side == "sell" else 1.0)
        for day, v in d.items():
            pnl[day] = pnl.get(day, 0.0) + float(v)
    ret = pd.Series(pnl).sort_index() / SLEEVE
    idx = pd.date_range(ret.index.min(), ret.index.max(), freq="D", tz="UTC")
    return tr, ret.reindex(idx).fillna(0.0)


def clustered(tr: pd.DataFrame) -> dict:
    """Mean edge per share, SE clustered by asset × end date, t."""
    e = tr["edge"].to_numpy()
    g = (tr["asset"].astype(str) + "|" + tr["end"].astype(str)).to_numpy()
    N, mean = len(e), e.mean()
    df = pd.DataFrame({"e": e - mean, "g": g}).groupby("g")["e"].sum()
    G = len(df)
    se = math.sqrt((df**2).sum()) / N * math.sqrt(G / max(G - 1, 1))
    return {"n_trades": int(N), "n_clusters": int(G), "mean_edge": float(mean), "se": float(se), "t": float(mean / se) if se > 0 else float("nan"),
            "win_rate": float((e > 0).mean()), "mean_hold_days": float(tr["hold_days"].mean())}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--holdout", action="store_true", help="markets ending in the holdout window instead of before it")
    ap.add_argument("--no-log", action="store_true")
    a = ap.parse_args(argv)
    p = paths().ensure()
    lake = Lake(p)
    mirror = p.root / "mirror"
    cat = pd.read_parquet(mirror / "polymarket" / "catalogue.parquet")
    cat["end"] = pd.to_datetime(cat["end"], utc=True)
    if a.holdout:
        cat = cat[(cat.end >= HOLDOUT_START) & (cat.end <= HOLDOUT_END)]
    else:
        cat = cat[cat.end < HOLDOUT_START]
    cat = cat.set_index("market_id")
    spot = spot_closes(lake, mirror)
    dvol = pd.DataFrame({c: load_dvol(lake, c) for c in ("BTC", "ETH")})
    rv = realised_vol(spot)
    # SOL: BTC DVOL scaled by the past-only realised-vol ratio (registered approximation)
    dvol["SOL"] = dvol["BTC"] * (rv["SOL"] / rv["BTC"]).reindex(dvol.index)
    panels_dvol, panels_rv = {}, {}
    n_nohist = 0
    for mid, row in cat.iterrows():
        f = market_panel(row, mirror, spot, dvol)
        if f is None:
            n_nohist += 1
            continue
        panels_dvol[mid] = f
        panels_rv[mid] = market_panel(row, mirror, spot, rv)
    print(f"{'holdout' if a.holdout else 'in-sample'}: {len(cat)} markets, {len(panels_dvol)} with usable history, {n_nohist} without", flush=True)
    tag = "holdout" if a.holdout else "insample"
    out_dir = p.root / "reports" / "p3"
    out_dir.mkdir(parents=True, exist_ok=True)
    results, book = {}, {}
    runs = [(f"k{int(v['k']*100)}_T{v['T']}", panels_dvol, v["k"], v["T"], "sell", False) for v in GRID]
    runs += [(f"mirror_k{int(v['k']*100)}_T{v['T']}", panels_dvol, v["k"], v["T"], "buy", False) for v in GRID]
    runs += [(f"placebo_k{int(v['k']*100)}_T{v['T']}", panels_rv, v["k"], v["T"], "sell", False) for v in GRID]
    runs += [("naive_le20c", panels_dvol, 0.0, "resolution", "sell", True)]
    all_trades = []
    for name, panels, k, T, side, naive in runs:
        tr, ret = simulate(panels, cat, k, T, side, naive)
        if tr.empty:
            results[name] = {"n_trades": 0}
            continue
        c = clustered(tr)
        c["by_kind"] = {kd: clustered(g) for kd, g in tr.groupby("kind") if len(g) >= 10}
        c["by_asset"] = {asx: clustered(g) for asx, g in tr.groupby("asset") if len(g) >= 10}
        c["book_sharpe"] = st.annualised_sharpe(ret, PPY) if len(ret) > 30 else float("nan")
        c["book_days"] = int(len(ret))
        c["book_total_return"] = float(ret.sum())
        c["book_trades"] = int(tr.in_book.sum())
        results[name] = c
        book[name] = ret
        tr.insert(0, "run", name)
        all_trades.append(tr)
        print(f"{name:28s} n={c['n_trades']:5d} clusters={c['n_clusters']:5d} edge={c['mean_edge']*100:6.2f}pt t={c['t']:6.2f} win={c['win_rate']:.2f} hold={c['mean_hold_days']:.1f}d book_sharpe={c['book_sharpe']:.2f} book_ret={c['book_total_return']*100:.1f}%", flush=True)
    pd.concat(all_trades).to_parquet(out_dir / f"{HYP}_{tag}_trades.parquet", index=False)
    B = pd.DataFrame(book).fillna(0.0)
    B.to_parquet(out_dir / f"{HYP}_{tag}_book_returns.parquet")
    # gates over the four family variants
    fam = [n for n in B.columns if not n.startswith(("mirror", "placebo", "naive"))]
    gates = {}
    if len(fam) >= 2 and len(B) > 64:
        F = B[fam]
        sharpes = {n: st.annualised_sharpe(F[n], PPY) for n in fam}
        best = max(sharpes, key=sharpes.get)
        per_period = np.array([st.moments(F[n]).sharpe for n in fam])
        dsr, bench = st.deflated_sharpe(F[best], n_trials=len(fam), trial_sharpes=per_period)
        t, pv, lags = st.hac_tstat(F[best])
        res = cscv(F, n_blocks=16)
        gates = {"best": best, "net_sharpe": sharpes, "hac_t": t, "hac_p": pv, "dsr": dsr, "dsr_benchmark_per_period": bench, "pbo": res.pbo}
        print(f"best {best}: sharpe {sharpes[best]:.2f} HAC t {t:.2f} DSR {dsr:.3f} PBO {res.pbo:.2f}")
    summary = {"hypothesis": HYP, "sample": tag, "markets": int(len(cat)), "with_history": len(panels_dvol), "results": results, "gates": gates,
               "grid": GRID, "haircut": HAIRCUT, "exit_x": EXIT_X, "cap_usd": CAP_USD, "max_open": MAX_OPEN, "sleeve": SLEEVE}
    (out_dir / f"{HYP}_{tag}_summary.json").write_text(json.dumps(summary, indent=1, default=str))
    if not a.no_log:
        log = TrialLog(p.trial_log)
        rec = log.run(HYP, FAMILY, {"grid": GRID, "sample": tag, "engine": "scripts/p3a_wedge.py", "haircut": HAIRCUT}, "polymarket_crypto_threshold_eligible",
                      metrics={n: {kk: results[n].get(kk) for kk in ("n_trades", "mean_edge", "t", "book_sharpe")} for n in results} | {"gates": gates},
                      variants=len(GRID), controls=[n for n in results if n.startswith(("mirror", "placebo", "naive"))])
        print("trial log seq", rec.seq)
    return 0


if __name__ == "__main__":
    sys.exit(main())
