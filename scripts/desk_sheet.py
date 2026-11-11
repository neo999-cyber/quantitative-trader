#!/usr/bin/env python3
"""The desk sheet: one page a day from what the box already records, no server, no UI (15 October 2026).

What a terminal would show the owner, as a markdown file and an optional push: the recorders' health, the
Programme 3 recording's progress against its registered minimum, the collectors' freshness, the yield ladder's
current rates against the T-bill and the carry, the dated items and the decisions that are the owner's. Every
number comes from a file on the box or one public read (Binance's premium index, no key). Nothing here reads a
price against a model: the recording's progress is counted, not judged (`docs/31` §16–§18).

The volatility block (11 November 2026, on the owner's word, to learn from) is three more public reads, no key:
Binance's spot daily closes, Deribit's implied-volatility index and CBOE's own VIX history file. It sets what
options price against what the market did, and bitcoin's daily return against the day's change in VIX. It is
descriptive: no rule, no signal, nothing registered (`reports/desk/vol_snapshot_2026-11-11.md`).

The push goes through ntfy, which shows a message as text only up to 4,096 bytes and turns a longer one into a
file attachment, so a page over `PUSH_LIMIT` is pushed in its short form (the file on disk is always the full page).

Standard library only, so it runs on the box after the morning collectors:

    python3 desk_sheet.py --out /root/desk            # writes /root/desk/desk_<date>.md and latest.md
    python3 desk_sheet.py --out /root/desk --push     # also pushes the sheet through ntfy (QR_NTFY_TOPIC)

The dated items and the open decisions are a block of text in this file, kept by hand (`DESK_NOTES`).
"""
from __future__ import annotations

import argparse
import glob
import json
import math
import os
import re
import statistics
import subprocess
import sys
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

V3_START = datetime(2026, 10, 13, 4, 53, tzinfo=timezone.utc)   # the daily ladders admitted (docs/31 §17)
V3_MIN_CLUSTERS = 30
MEASURED = {"perp_maker_bps_side": 3.2, "carry_round_trip_bps": 21.4, "stage1_fill_pct": 94.2}
FUNDING_WINDOWS = (30, 90, 365)                                   # trailing days for the realised-funding lines
VOL_WINDOWS = (7, 30)                                             # trailing days of realised volatility
VIX_JUMP_POINTS = 2.0                                             # a jump day: VIX up by more than this, close to close
LINK_WINDOWS = (20, 250)                                          # sessions for bitcoin's return against the change in VIX
PUSH_LIMIT = 4000                                                 # bytes; ntfy renders a message as text up to 4,096
DESK_NOTES = """\
**Dated (Claude's):** **30 Nov** — mirror both recordings, the v3 read once on 13 Oct–29 Nov, the addendum to `docs/36`. Since 1 Nov: Programme 5 (TimesFM) **FAILED** (2 Nov, `docs/37`) · health alerts push once per failure (10 Nov) · this volatility block (11 Nov).
**Open decisions (owner's):** the carry holding, untimed (`docs/34`): no, not now, or an amount and a leverage; the yield sleeve stays in the bill until then.
**Standing:** no live orders; the live key's futures and spot trading are off; Programmes 2, 4 and 5 closed without a pass; Programme 3's last read is 30 November."""


def _run(cmd: list[str]) -> str:
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=60).stdout
    except Exception:  # noqa: BLE001
        return ""


def _age_h(path: Path) -> float | None:
    try:
        return (datetime.now(timezone.utc).timestamp() - path.stat().st_mtime) / 3600
    except OSError:
        return None


# ------------------------------------------------------------------ pieces
def recorder_health(health_log: Path, pm_dir: Path, surface_dir: Path) -> dict:
    last = ""
    if health_log.exists():
        lines = health_log.read_text().strip().splitlines()
        last = lines[-1] if lines else ""
    today = datetime.now(timezone.utc).date()
    yday = today - timedelta(days=1)
    mb_yday = _run(["du", "-sm", str(pm_dir / "polymarket" / yday.isoformat())]).split("\t")[0].strip() if (pm_dir / "polymarket" / yday.isoformat()).exists() else "0"
    reconnects = _run(["journalctl", "-u", "qr-pm-polymarket", "--since", "24 hours ago", "--no-pager"]).count("reconnect after error")
    surface_yday = len(glob.glob(str(surface_dir / "deribit" / yday.isoformat() / "*.json.gz")))
    disk = _run(["df", "-h", "/"]).strip().splitlines()[-1].split()[3] if _run(["df", "-h", "/"]) else "?"
    return {"last_line": last, "pm_mb_yesterday": mb_yday, "reconnects_24h": reconnects, "surface_files_yesterday": surface_yday, "disk_free": disk,
            "wrong": "WRONG" in last}


def recording_progress(catalogue: Path, now: datetime | None = None) -> dict:
    """Structural counts of the daily ladders in the catalogue since the switch: markets, settlement-date clusters, settled so far."""
    now = now or datetime.now(timezone.utc)
    daily: dict[str, tuple[str, datetime]] = {}
    n_lines = 0
    latest_markets = 0
    latest_daily = 0
    if not catalogue.exists():
        return {"catalogue_lines_since_switch": 0, "daily_markets": 0, "clusters_total": 0, "clusters_settled": 0, "minimum": V3_MIN_CLUSTERS}
    with catalogue.open() as fh:
        for line in fh:
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                continue
            at = datetime.fromtimestamp(float(d.get("at", 0)), tz=timezone.utc)
            if at < V3_START:
                continue
            n_lines += 1
            ms = d.get("markets") or []
            latest_markets = len(ms)
            latest_daily = 0
            for m in ms:
                q = (m.get("question") or "").lower()
                if "above" not in q or not m.get("start") or not m.get("end"):
                    continue
                try:
                    start = datetime.fromisoformat(m["start"].replace("Z", "+00:00"))
                    end = datetime.fromisoformat(m["end"].replace("Z", "+00:00"))
                except ValueError:
                    continue
                if (end - start) > timedelta(days=8):
                    continue
                latest_daily += 1
                asset = "BTC" if "bitcoin" in q else "ETH" if "ethereum" in q else "SOL" if "solana" in q else None
                if asset:
                    daily[m["yes_token"]] = (asset, end)
    clusters = {(a, e.date()) for a, e in daily.values()}
    settled = {c for c in clusters if datetime.combine(c[1], datetime.min.time(), tzinfo=timezone.utc) + timedelta(hours=16) <= now}
    return {"catalogue_lines_since_switch": n_lines, "latest_markets": latest_markets, "latest_daily_markets": latest_daily,
            "daily_markets_seen": len(daily), "clusters_total": len(clusters), "clusters_settled": len(settled), "minimum": V3_MIN_CLUSTERS,
            "days_recorded": round((now - V3_START).total_seconds() / 86400, 1)}


def collectors(flows_dir: Path, yield_dir: Path) -> dict:
    today = datetime.now(timezone.utc).date().isoformat()
    ibit = flows_dir / "ishares" / f"IBIT_{today}.xls"
    etha = flows_dir / "ishares" / f"ETHA_{today}.xls"
    table = flows_dir / "etf_flows_table.jsonl"
    eq = flows_dir / "etf_shares_outstanding.jsonl"
    yfile = yield_dir / "yields" / f"{today}.jsonl"
    latest_yield = sorted(glob.glob(str(yield_dir / "yields" / "*.jsonl")))
    return {"ibit_today": ibit.exists(), "etha_today": etha.exists(), "table_rows": sum(1 for _ in table.open()) if table.exists() else 0,
            "equities_flows_age_h": round(_age_h(eq), 1) if _age_h(eq) is not None else None,
            "yield_today": yfile.exists(), "latest_yield_file": Path(latest_yield[-1]).name if latest_yield else None}


def ladder(yield_dir: Path, top: int = 8) -> dict:
    files = sorted(glob.glob(str(yield_dir / "yields" / "*.jsonl")))
    if not files:
        return {}
    rec = None
    with open(files[-1]) as fh:
        for line in fh:
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                pass
    if not rec:
        return {}
    pools = [p for p in rec.get("pools") or [] if p.get("stablecoin") and p.get("apy") is not None]
    pools.sort(key=lambda p: -(p.get("tvlUsd") or 0))
    out = {"recorded_at": rec.get("recorded_at"), "pools": [{"name": f"{p.get('project')} {p.get('symbol')} ({p.get('chain')})", "apy": p.get("apy"), "apy30": p.get("apyMean30d"), "tvl_musd": round((p.get("tvlUsd") or 0) / 1e6)} for p in pools[:top]]}
    # the T-bill: the latest snapshot that has one (FRED times out from the box some mornings), as a number and its date
    for f in reversed(files[-7:]):
        try:
            with open(f) as fh:
                last_line = [ln for ln in fh.read().splitlines() if ln.strip()][-1]   # a day's file may hold several runs; the last one counts
            r = json.loads(last_line)
        except (OSError, IndexError, json.JSONDecodeError):
            continue
        t = r.get("tbill") if r.get("tbill") is not None else r.get("dtb3")
        if t is None:
            continue
        if isinstance(t, dict):
            out["dtb3"] = t.get("dtb3") if t.get("dtb3") is not None else t.get("value")
            out["dtb3_date"] = f"{t.get('date') or ''} {t.get('source') or ''}".strip()
        else:
            out["dtb3"] = t
            out["dtb3_date"] = Path(f).stem
        break
    return out


def funding_now(symbols=("BTCUSDT", "ETHUSDT")) -> dict:
    out = {}
    for s in symbols:
        try:
            with urllib.request.urlopen(urllib.request.Request(f"https://fapi.binance.com/fapi/v1/premiumIndex?symbol={s}", headers={"User-Agent": "Mozilla/5.0"}), timeout=20) as r:
                d = json.loads(r.read())
            rate = float(d["lastFundingRate"])
            out[s] = {"rate_8h": rate, "annualised_pct": round(rate * 3 * 365 * 100, 2)}
        except Exception as exc:  # noqa: BLE001
            out[s] = {"error": f"{type(exc).__name__}"}
    return out


def _fetch_funding(symbol: str, start_ms: int, limit: int = 1000) -> list[dict]:
    """Every funding settlement for `symbol` since `start_ms`, paged through the public endpoint (no key, like `funding_now`)."""
    rows: list[dict] = []
    for _ in range(6):
        url = f"https://fapi.binance.com/fapi/v1/fundingRate?symbol={symbol}&startTime={start_ms}&limit={limit}"
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=20) as r:
            page = json.loads(r.read())
        rows += page
        if len(page) < limit:
            break
        start_ms = int(page[-1]["fundingTime"]) + 1
    return rows


def funding_trailing(symbols=("BTCUSDT", "ETHUSDT"), windows=FUNDING_WINDOWS, now: datetime | None = None, fetch=_fetch_funding) -> dict:
    """What a short perp held every day actually collected over the trailing windows, annualised: gross, and on the capital a 1×
    holding ties up (the spot notional plus the full perp margin, one round trip of costs taken once a year). The morning rate in
    `funding_now` is read on one day and overstates this (`docs/34`, the decision section); this is the number against the bill."""
    now = now or datetime.now(timezone.utc)
    now_ms = now.timestamp() * 1000
    rt = MEASURED["carry_round_trip_bps"] / 100.0
    out: dict = {}
    for s in symbols:
        try:
            rows = fetch(s, int((now - timedelta(days=max(windows) + 1)).timestamp() * 1000))
            pts = sorted((int(r["fundingTime"]), float(r["fundingRate"])) for r in rows if int(r["fundingTime"]) <= now_ms)
            res: dict = {}
            for w in windows:
                since = now_ms - w * 86_400_000
                sel = [(t, rate) for t, rate in pts if t >= since]
                if not sel:
                    continue
                covered = any(t < since for t, _ in pts)                          # data reaches past the window's start
                days = float(w) if covered else max((now_ms - sel[0][0]) / 86_400_000, 1.0)
                gross = sum(rate for _, rate in sel) * 365 / days * 100
                res[w] = {"days": round(days, 1), "n": len(sel), "gross_pct": round(gross, 2), "on_capital_1x_pct": round((gross - rt) / 2, 2)}
            out[s] = res
        except Exception as exc:  # noqa: BLE001
            out[s] = {"error": type(exc).__name__}
    return out


# ------------------------------------------------------------------ volatility: priced against actual
def _get(url: str, timeout: int = 20) -> bytes:
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=timeout) as r:
        return r.read()


def _fetch_closes(symbol: str, now: datetime, limit: int = 500) -> list[tuple]:
    """Binance spot daily closes as (UTC date, close), oldest first; the day still open is left out."""
    now_ms = now.timestamp() * 1000
    rows = json.loads(_get(f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval=1d&limit={limit}"))
    return [(datetime.fromtimestamp(int(r[0]) / 1000, tz=timezone.utc).date(), float(r[4])) for r in rows if int(r[6]) < now_ms]


def _fetch_dvol(currency: str, now: datetime, days: int = 400) -> list[tuple]:
    """Deribit's 30-day implied-volatility index as (UTC date, value), oldest first; the last value is the current one."""
    end = int(now.timestamp() * 1000)
    url = f"https://www.deribit.com/api/v2/public/get_volatility_index_data?currency={currency}&start_timestamp={end - days * 86_400_000}&end_timestamp={end}&resolution=1D"
    return [(datetime.fromtimestamp(int(r[0]) / 1000, tz=timezone.utc).date(), float(r[4])) for r in json.loads(_get(url))["result"]["data"]]


def _fetch_vix(now: datetime, sessions: int = 400) -> list[tuple]:
    """CBOE's own VIX history file as (session date, close), oldest first."""
    rows = _get("https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv").decode().strip().splitlines()[1:]
    out = []
    for ln in rows[-sessions:]:
        d, _o, _h, _l, c = ln.split(",")[:5]
        out.append((datetime.strptime(d.strip(), "%m/%d/%Y").date(), float(c)))
    return out


def _ann_vol(rets: list[float]) -> float:
    """Close-to-close volatility of these daily log returns, a year of 365 days (crypto trades every day), in percent."""
    return statistics.stdev(rets) * math.sqrt(365) * 100


def _pct_rank(values: list[float], v: float) -> int | None:
    """The share of `values` at or below `v`, as a whole percentile."""
    return round(100 * sum(1 for x in values if x <= v) / len(values)) if values else None


def _corr(x: list[float], y: list[float]) -> float | None:
    try:
        return statistics.correlation(x, y)
    except statistics.StatisticsError:
        return None


def volatility(now: datetime | None = None, closes=_fetch_closes, dvol=_fetch_dvol, vix=_fetch_vix) -> dict:
    """What options price against what the market did, the stock market's gauge, and how closely bitcoin moved with it.

    Per asset: the implied volatility now, a month ago and its percentile in the last year; the realised volatility of the
    last 7 and 30 closed days and the percentile of the week's; the price change. Stocks: VIX's last close, its level 21
    sessions ago, its 30-session high, its median and percentile over 252 sessions, and the days it rose by more than
    `VIX_JUMP_POINTS`. The link: the correlation of bitcoin's log return between consecutive VIX sessions (its UTC-day
    close on each session's date, so the day covers that US session) with the change in VIX over the same sessions.
    A source that fails leaves an `error` in its place and the rest stands. Descriptive only: nothing here is a signal."""
    now = now or datetime.now(timezone.utc)
    out: dict = {"assets": {}, "stocks": {}, "link": {}}
    btc: dict = {}
    for cur in ("BTC", "ETH"):
        a: dict = {}
        try:
            cs = closes(cur + "USDT", now)
            if cur == "BTC":
                btc = dict(cs)
            px = [c for _, c in cs]
            rets = [math.log(b / a_) for a_, b in zip(px, px[1:])]
            a["as_of"] = cs[-1][0].isoformat()
            a["ret_pct"] = {n: (px[-1] / px[-1 - n] - 1) * 100 for n in VOL_WINDOWS if len(px) > n}
            a["realised"] = {n: _ann_vol(rets[-n:]) for n in VOL_WINDOWS if len(rets) >= n}
            w = min(VOL_WINDOWS)
            roll = [_ann_vol(rets[i - w:i]) for i in range(w, len(rets) + 1)][-365:]
            a["realised_week_pctile"] = _pct_rank(roll, roll[-1]) if roll else None
        except Exception as exc:  # noqa: BLE001
            a["price_error"] = type(exc).__name__
        try:
            vals = [v for _, v in dvol(cur, now)]
            a["implied"] = vals[-1]
            a["implied_month_ago"] = vals[-31] if len(vals) > 30 else None
            a["implied_pctile"] = _pct_rank(vals[-365:], vals[-1])
        except Exception as exc:  # noqa: BLE001
            a["implied_error"] = type(exc).__name__
        out["assets"][cur] = a
    try:
        vx = vix(now)
        vals = [v for _, v in vx]
        hi = max(vx[-30:], key=lambda r: r[1])
        last31 = vx[-31:]                                                    # 30 close-to-close changes
        out["stocks"] = {"vix": vals[-1], "as_of": vx[-1][0].isoformat(), "vix_month_ago": vals[-22] if len(vals) > 21 else None,
                         "high_30": hi[1], "high_30_date": hi[0].isoformat(), "median_252": statistics.median(vals[-252:]),
                         "pctile_252": _pct_rank(vals[-252:], vals[-1]),
                         "jump_days_30": sum(1 for (_, v0), (_, v1) in zip(last31, last31[1:]) if v1 - v0 > VIX_JUMP_POINTS)}
        pairs = [(math.log(btc[d1] / btc[d0]), v1 - v0) for (d0, v0), (d1, v1) in zip(vx, vx[1:]) if d0 in btc and d1 in btc]
        out["link"] = {n: _corr([r for r, _ in pairs[-n:]], [dv for _, dv in pairs[-n:]]) for n in LINK_WINDOWS if len(pairs) >= n}
    except Exception as exc:  # noqa: BLE001
        out["stocks"] = {"error": type(exc).__name__}
    return out


def _ord(n: int | None) -> str:
    if n is None:
        return "n/a"
    return f"{n}{'th' if 10 <= n % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"


def _signed(x: float) -> str:
    return f"{'+' if x >= 0 else '−'}{abs(x):.0f}"


def _day(iso: str) -> str:
    d = datetime.fromisoformat(iso)
    return f"{d.day} {d.strftime('%b')}"


def _vol_lines(v: dict, short: int = 0) -> list[str]:
    lines = ["## Volatility — priced by options for the next 30 days against actual (yearly rates, percentiles within the last year; to learn from, not a signal)"]
    for cur, a in v.get("assets", {}).items():
        if "implied" in a:
            ago = f"; {a['implied_month_ago']:.0f}% a month ago" if a.get("implied_month_ago") is not None else ""
            priced = f"priced **{a['implied']:.0f}%** ({_ord(a.get('implied_pctile'))} percentile{ago})"
        else:
            priced = f"priced: unavailable ({a.get('implied_error')})"
        rv = a.get("realised") or {}
        if 7 in rv and 30 in rv:
            actual = f"Actual **{rv[7]:.0f}%** over 7 days ({_ord(a.get('realised_week_pctile'))} percentile), {rv[30]:.0f}% over 30"
            gap = f" Priced minus actual: {_signed(a['implied'] - rv[7])} on the week, {_signed(a['implied'] - rv[30])} on the month." if "implied" in a else ""
            ret = a.get("ret_pct") or {}
            move = f" Price {_signed_pct(ret[30])} in 30 days." if 30 in ret else ""
            lines += [f"- {cur}: {priced}. {actual}.{gap}{move}"]
        else:
            lines += [f"- {cur}: {priced}. Actual: unavailable ({a.get('price_error', 'too little history')})."]
    s = v.get("stocks") or {}
    if "vix" in s:
        ago = f"; {s['vix_month_ago']:.1f} a month ago" if s.get("vix_month_ago") is not None else ""
        lines += [f"- Stocks: VIX **{s['vix']:.1f}** on {_day(s['as_of'])} ({_ord(s.get('pctile_252'))} percentile, median {s['median_252']:.1f}{ago}); "
                  f"30-session high {s['high_30']:.1f} on {_day(s['high_30_date'])}, {s['jump_days_30']} jumps of more than {VIX_JUMP_POINTS:.0f} points."]
    else:
        lines += [f"- Stocks: VIX unavailable ({s.get('error', 'no data')})."]
    k = v.get("link") or {}
    got = [(n, k[n]) for n in LINK_WINDOWS if k.get(n) is not None]
    if got:
        first = f"**{_signed2(got[0][1])}** over {got[0][0]} sessions"
        rest = "".join(f", {_signed2(c)} over {n}" for n, c in got[1:])
        lines += [f"- Bitcoin against stock fear (daily return against the day's change in VIX): {first}{rest}; nearer −1 means it falls as fear rises."]
    if not short:
        lines += ["- Reading it: priced a few points over the month's actual is the usual insurance premium; actual far above priced means options expect the swings to fade; "
                  "priced above its 80th percentile is a volatile regime. Size, never direction."]
    return lines + [""]


def _signed_pct(x: float) -> str:
    return f"{'+' if x >= 0 else '−'}{abs(x):.1f}%"


def _signed2(x: float) -> str:
    return f"{'+' if x >= 0 else '−'}{abs(x):.2f}"


# ------------------------------------------------------------------ the page
def render(h: dict, p: dict, c: dict, l: dict, f: dict, now: datetime, t: dict | None = None, vol: dict | None = None, short: int = 0) -> str:
    """The page. `short` is for the push when the full page is over `PUSH_LIMIT`: 1 leaves out the volatility block's reading
    line, 2 also cuts the notes to the dated item and a pointer to the file."""
    def yn(b): return "yes" if b else "**no**"
    lines = [f"# Desk sheet — {now.strftime('%Y-%m-%d %H:%M')} UTC", ""]
    lines += ["## Recorders", f"- Health: {'**WRONG** — ' if h['wrong'] else 'clean — '}`{h['last_line'] or 'no health line yet'}`",
              f"- Polymarket yesterday: {h['pm_mb_yesterday']} MB; reconnects last 24 h: {h['reconnects_24h']}; surface snapshots yesterday: {h['surface_files_yesterday']}/24; disk free {h['disk_free']}", ""]
    lines += ["## Programme 3 recording (v3 daily ladders — the 1 Nov read had 23 clusters with a fill vs 30; next read 30 November)",
              f"- Days recorded since the switch: {p.get('days_recorded', 0)}; catalogue refreshes: {p.get('catalogue_lines_since_switch', 0)}; markets in the latest list: {p.get('latest_markets', 0)}, of which daily ladders {p.get('latest_daily_markets', 0)}",
              f"- Daily-ladder markets seen so far: {p.get('daily_markets_seen', 0)} in **{p.get('clusters_total', 0)} asset × settlement-date clusters**, {p.get('clusters_settled', 0)} settled — the memo's minimum is {p['minimum']} clusters *with a fill*, so this is the ceiling, not the count", ""]
    lines += ["## Collectors", f"- ETF workbooks today: IBIT {yn(c['ibit_today'])}, ETHA {yn(c['etha_today'])}; flow-table rows {c['table_rows']}; equities share counts last touched {c['equities_flows_age_h']} h ago",
              f"- Yield snapshot today: {yn(c['yield_today'])} (latest {c['latest_yield_file']})", ""]
    lines += ["## The ladder, this morning"]
    if l.get("pools"):
        lines += [f"- DefiLlama stablecoin pools at {str(l.get('recorded_at', ''))[:16]} (APY now / 30-day mean / TVL):"]
        lines += [f"  - {x['name']}: {x['apy']:.2f}% / {x['apy30'] if x['apy30'] is None else round(x['apy30'], 2)}% / ${x['tvl_musd']:,}M" for x in l["pools"]]
    if l.get("dtb3") is not None:
        lines += [f"- T-bill, 3-month discount basis ({l.get('dtb3_date', '')}): {l['dtb3']}%"]
    else:
        lines += ["- T-bill (DTB3): no value in the last seven snapshots"]
    for s, v in f.items():
        lines += [f"- {s} funding now: {v.get('rate_8h', '?')} per 8 h = {v.get('annualised_pct', '?')}%/yr at today's rate" if "rate_8h" in v else f"- {s} funding: {v['error']}"]
    for s, v in (t or {}).items():
        if "error" in v:
            lines += [f"- {s} funding realised: {v['error']}"]
            continue
        parts = [f"{w} d {x['gross_pct']}% / {x['on_capital_1x_pct']}%" + (f" ({x['days']} d of data)" if x["days"] < w - 1 else "") for w, x in sorted(v.items())]
        lines += [f"- {s} funding realised, annualised (gross / at 1× on the capital it ties up): " + "; ".join(parts)]
    if t and l.get("dtb3") is not None:
        gaps = []
        for s, v in t.items():
            x = v.get(max(FUNDING_WINDOWS)) if "error" not in v else None
            if x:
                d = x["on_capital_1x_pct"] - float(l["dtb3"])
                gaps.append(f"{s[:3]} {'+' if d >= 0 else '−'}{abs(d):.1f}")
        if gaps:
            lines += [f"- The carry at 1× against the bill ({l['dtb3']}%), last {max(FUNDING_WINDOWS)} days, in points: " + ", ".join(gaps) + " — the rate above is one morning's; this is what the days held paid"]
    lines += [f"- Measured costs: perp maker {MEASURED['perp_maker_bps_side']} bps a side (stage 1, {MEASURED['stage1_fill_pct']}% fill); a carry round trip ≈ {MEASURED['carry_round_trip_bps']} bps", ""]
    if vol:                                                                 # not `v`: the funding loops above reuse that name
        lines += _vol_lines(vol, short)
    if short >= 2:
        lines += ["## Notes", "Next dated: **30 Nov**, the v3 read. The full notes are in `latest.md` on the box.", ""]
    else:
        lines += ["## Notes", DESK_NOTES, ""]
    return "\n".join(lines)


def push_body(page_at, limit: int = PUSH_LIMIT) -> str:
    """The fullest form of the page that ntfy will show as text: the full page, else without the reading line, else with the notes cut."""
    body = ""
    for short in (0, 1, 2):
        body = page_at(short)
        if len(body.encode()) <= limit:
            break
    return body


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=Path("/root/desk"))
    ap.add_argument("--health-log", type=Path, default=Path("/root/pm/health.log"))
    ap.add_argument("--pm", type=Path, default=Path("/root/pm/data"))
    ap.add_argument("--surface", type=Path, default=Path("/root/surface/data"))
    ap.add_argument("--flows", type=Path, default=Path("/root/flows"))
    ap.add_argument("--yield-dir", type=Path, default=Path("/root/yield/data"))
    ap.add_argument("--push", action="store_true")
    ap.add_argument("--no-net", action="store_true", help="skip the funding read (tests)")
    a = ap.parse_args(argv)
    now = datetime.now(timezone.utc)
    h = recorder_health(a.health_log, a.pm, a.surface)
    p = recording_progress(a.pm / "polymarket" / "catalogue.jsonl", now)
    c = collectors(a.flows, a.yield_dir)
    l = ladder(a.yield_dir)
    f = {} if a.no_net else funding_now()
    t = {} if a.no_net else funding_trailing()
    vol = {} if a.no_net else volatility(now)
    page = render(h, p, c, l, f, now, t, vol)
    a.out.mkdir(parents=True, exist_ok=True)
    (a.out / f"desk_{now.date().isoformat()}.md").write_text(page)
    (a.out / "latest.md").write_text(page)
    print(page)
    topic = os.environ.get("QR_NTFY_TOPIC")
    if a.push and topic:
        try:
            body = push_body(lambda short: render(h, p, c, l, f, now, t, vol, short))
            req = urllib.request.Request(f"https://ntfy.sh/{topic}", data=body.encode(), method="POST",
                                         headers={"Title": f"desk sheet {now.date().isoformat()}", "Markdown": "yes", "Priority": "low"})
            urllib.request.urlopen(req, timeout=20).read()
        except Exception as exc:  # noqa: BLE001
            print(f"push failed: {type(exc).__name__}", file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
