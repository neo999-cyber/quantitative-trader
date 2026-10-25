#!/usr/bin/env python3
"""The desk sheet: one page a day from what the box already records, no server, no UI (15 October 2026).

What a terminal would show the owner, as a markdown file and an optional push: the recorders' health, the
Programme 3 recording's progress against its registered minimum, the collectors' freshness, the yield ladder's
current rates against the T-bill and the carry, the dated items and the decisions that are the owner's. Every
number comes from a file on the box or one public read (Binance's premium index, no key). Nothing here reads a
price against a model: the recording's progress is counted, not judged (`docs/31` §16–§18).

Standard library only, so it runs on the box after the morning collectors:

    python3 desk_sheet.py --out /root/desk            # writes /root/desk/desk_<date>.md and latest.md
    python3 desk_sheet.py --out /root/desk --push     # also pushes the sheet through ntfy (QR_NTFY_TOPIC)

The dated items and the open decisions are a block of text in this file, kept by hand (`DESK_NOTES`).
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
import subprocess
import sys
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

V3_START = datetime(2026, 10, 13, 4, 53, tzinfo=timezone.utc)   # the daily ladders admitted (docs/31 §17)
V3_MIN_CLUSTERS = 30
MEASURED = {"perp_maker_bps_side": 3.2, "carry_round_trip_bps": 21.4, "stage1_fill_pct": 94.2}
DESK_NOTES = """\
**Dated (Claude's):** 25 Oct counts-only check of the daily-ladder recording done (`reports/p3/p3a_v3_counts_2026-10-25.md`) · 27 Oct the v2 deferral note, no run · 31 Oct mirror, the v3 read once, the Programme 3 report.
**Open decisions (owner's):** the ladder / carry holding (`docs/34`) · whether to open the data-expansion programme (the ETF-flow series is in the lake).
**Standing:** no live orders; the live key's futures and spot trading are off; Programme 3 counter four of four; Programme 2 twelve for twelve."""


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


# ------------------------------------------------------------------ the page
def render(h: dict, p: dict, c: dict, l: dict, f: dict, now: datetime) -> str:
    def yn(b): return "yes" if b else "**no**"
    lines = [f"# Desk sheet — {now.strftime('%Y-%m-%d %H:%M')} UTC", ""]
    lines += ["## Recorders", f"- Health: {'**WRONG** — ' if h['wrong'] else 'clean — '}`{h['last_line'] or 'no health line yet'}`",
              f"- Polymarket yesterday: {h['pm_mb_yesterday']} MB; reconnects last 24 h: {h['reconnects_24h']}; surface snapshots yesterday: {h['surface_files_yesterday']}/24; disk free {h['disk_free']}", ""]
    lines += ["## Programme 3 recording (v3, daily ladders, registered read 31 October)",
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
    lines += [f"- Measured costs: perp maker {MEASURED['perp_maker_bps_side']} bps a side (stage 1, {MEASURED['stage1_fill_pct']}% fill); a carry round trip ≈ {MEASURED['carry_round_trip_bps']} bps", ""]
    lines += ["## Notes", DESK_NOTES, ""]
    return "\n".join(lines)


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
    page = render(h, p, c, l, f, now)
    a.out.mkdir(parents=True, exist_ok=True)
    (a.out / f"desk_{now.date().isoformat()}.md").write_text(page)
    (a.out / "latest.md").write_text(page)
    print(page)
    topic = os.environ.get("QR_NTFY_TOPIC")
    if a.push and topic:
        try:
            req = urllib.request.Request(f"https://ntfy.sh/{topic}", data=page.encode(), method="POST",
                                         headers={"Title": f"desk sheet {now.date().isoformat()}", "Markdown": "yes", "Priority": "low"})
            urllib.request.urlopen(req, timeout=20).read()
        except Exception as exc:  # noqa: BLE001
            print(f"push failed: {type(exc).__name__}", file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
