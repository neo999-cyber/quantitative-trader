"""A readable record of every hypothesis this platform has judged.

The research output so far lives in three places that only a terminal can see:
markdown gate reports, a hash-chained JSONL log, and tables printed to stderr
during a run. All of it is accurate and none of it is legible, which is a
problem for the one thing this project produces — a *no*, argued in detail,
that has to be re-readable months later to be worth anything.

`qr site` renders it as one self-contained HTML file. No build step, no CDN, no
JavaScript: the data is already on disk as `reports/*.json`, and a browser can
draw it. Opening the file offline must work, because the lake it reads from is
a directory on a laptop and not a service.

The hero is the gate ladder — every hypothesis as a row of ten cells, one per
gate, coloured by verdict. Six months from now the useful question is not what
any single number was; it is *where each family died*, and that grid answers it
at a glance in a way no table of Sharpe ratios does.
"""
from __future__ import annotations

import html
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from qr.validate.trial_log import TrialLog, TrialLogCorrupt

#: Gate 0 through 9, so a family that stopped early still shows the ladder it
#: never reached rather than a short row that looks like a different shape.
GATE_NAMES = {
    0: "pre-registration",
    1: "data integrity",
    2: "cost survival",
    3: "significance",
    4: "deflation",
    5: "selection",
    6: "permutation",
    7: "cross-validated OOS",
    8: "robustness",
    9: "holdout",
}

VERDICT_ORDER = {"FAIL": 0, "WARN": 1, "SKIP": 2, "PASS": 3}


def collect(reports_dir: Path | str) -> list[dict[str, Any]]:
    """Every `<hypothesis>.json` a run has written, newest generation first."""
    directory = Path(reports_dir)
    if not directory.exists():
        return []
    runs = []
    for path in sorted(directory.glob("*.json")):
        try:
            runs.append(json.loads(path.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, OSError):
            continue
    return sorted(runs, key=lambda r: r.get("hypothesis_id", ""))


def integrity(trial_log: TrialLog) -> dict[str, Any]:
    """The audit line: is the chain sound and do the documents still match?

    Reported rather than assumed. A results page that cannot say whether its
    own evidence is intact is a brochure.
    """
    out: dict[str, Any] = {"path": str(trial_log.path)}
    try:
        out["records"] = trial_log.verify()
        out["trials"] = trial_log.trial_count()
        out["chain"] = "verified"
    except TrialLogCorrupt as exc:
        out["chain"] = f"CORRUPT: {exc}"
        return out
    except FileNotFoundError:
        out["chain"] = "no trial log"
        return out
    drift = trial_log.document_drift()
    out["drift"] = drift
    return out


def _stopped_at(run: dict[str, Any]) -> int | None:
    for gate in run.get("gates", []):
        if gate.get("verdict") == "FAIL":
            return int(gate["gate"])
    return None


def _stat(run: dict[str, Any], key: str) -> float | None:
    value = run.get("tear_sheet", {}).get(key)
    return value if isinstance(value, (int, float)) else None


def _num(value: float | None, digits: int = 3, suffix: str = "") -> str:
    if value is None or value != value:  # None or NaN
        return "—"
    return f"{value:,.{digits}f}{suffix}"


def _esc(value: Any) -> str:
    return html.escape(str(value), quote=True)


# ----------------------------------------------------------------- rendering


STYLE = """
:root{
  --ink:#1a1815; --ink-soft:#55504a; --ink-faint:#8a837a;
  --paper:#faf8f4; --card:#ffffff; --rule:#e4dfd6;
  --pass:#2f7a4f; --warn:#a8761a; --fail:#a63d3d; --skip:#9a948b;
  --pass-bg:#e6f1e9; --warn-bg:#f7efdf; --fail-bg:#f6e5e5; --skip-bg:#eeebe6;
  --accent:#3d5a80;
}
@media (prefers-color-scheme: dark){ :root:not([data-theme="light"]){
  --ink:#ece7e0; --ink-soft:#a9a29a; --ink-faint:#7b746c;
  --paper:#16150f; --card:#201e18; --rule:#33302a;
  --pass:#6fbe8e; --warn:#d9a441; --fail:#e07a7a; --skip:#7b746c;
  --pass-bg:#1c2b22; --warn-bg:#2e2618; --fail-bg:#2e1d1d; --skip-bg:#26241f;
  --accent:#8fb0d4;
}}
:root[data-theme="dark"]{
  --ink:#ece7e0; --ink-soft:#a9a29a; --ink-faint:#7b746c;
  --paper:#16150f; --card:#201e18; --rule:#33302a;
  --pass:#6fbe8e; --warn:#d9a441; --fail:#e07a7a; --skip:#7b746c;
  --pass-bg:#1c2b22; --warn-bg:#2e2618; --fail-bg:#2e1d1d; --skip-bg:#26241f;
  --accent:#8fb0d4;
}
*{box-sizing:border-box}
a{color:var(--accent);text-decoration-thickness:1px;text-underline-offset:2px}
a:hover{text-decoration:none}
a:focus-visible{outline:2px solid var(--accent);outline-offset:2px;border-radius:2px}
body{margin:0;background:var(--paper);color:var(--ink);
  font:15px/1.55 ui-serif,Georgia,"Times New Roman",serif;}
.wrap{max-width:1080px;margin:0 auto;padding-block:48px 96px;padding-left:16px;padding-right:16px}
h1{font-size:30px;line-height:1.15;margin:0 0 6px;letter-spacing:-.01em;text-wrap:balance}
h2{font-size:20px;margin:48px 0 14px;padding-bottom:6px;border-bottom:1px solid var(--rule)}
h3{font-size:17px;margin:0 0 2px}
p{margin:0 0 12px;max-width:66ch}
.sub{color:var(--ink-soft);margin-bottom:28px}
.mono{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:12.5px}
.tabular{font-variant-numeric:tabular-nums}
.grid{display:grid;gap:14px}
.cards{grid-template-columns:repeat(auto-fit,minmax(150px,1fr));margin-bottom:8px}
.card{background:var(--card);border:1px solid var(--rule);border-radius:8px;padding:14px 16px}
.card .k{font-size:11px;letter-spacing:.09em;text-transform:uppercase;color:var(--ink-faint)}
.card .v{font-size:26px;line-height:1.2;margin-top:4px;font-variant-numeric:tabular-nums}
table{width:100%;border-collapse:collapse;font-size:14px}
th{text-align:left;font-weight:600;font-size:11px;letter-spacing:.08em;
  text-transform:uppercase;color:var(--ink-faint);padding:0 10px 8px 0;white-space:nowrap}
td{padding:9px 10px 9px 0;border-top:1px solid var(--rule);vertical-align:top}
td.num{text-align:right;font-variant-numeric:tabular-nums;padding-right:18px}
.scroll{overflow-x:auto}
.ladder{display:flex;gap:3px}
.cell{width:26px;height:26px;border-radius:4px;display:grid;place-items:center;
  font:600 11px/1 ui-monospace,monospace;border:1px solid transparent}
.PASS{background:var(--pass-bg);color:var(--pass);border-color:var(--pass)}
.WARN{background:var(--warn-bg);color:var(--warn);border-color:var(--warn)}
.FAIL{background:var(--fail-bg);color:var(--fail);border-color:var(--fail)}
.SKIP{background:var(--skip-bg);color:var(--skip)}
.NONE{background:transparent;color:var(--ink-faint);border:1px dashed var(--rule)}
.badge{display:inline-block;padding:2px 9px;border-radius:999px;font:600 11px/1.6 ui-monospace,monospace;
  letter-spacing:.05em}
.legend{display:flex;flex-wrap:wrap;gap:16px;margin:10px 0 0;font-size:12px;color:var(--ink-soft)}
.legend span{display:flex;align-items:center;gap:6px}
.dot{width:10px;height:10px;border-radius:3px;display:inline-block;border:1px solid transparent}
.dot.PASS{background:var(--pass)} .dot.WARN{background:var(--warn)}
.dot.FAIL{background:var(--fail)} .dot.SKIP{background:var(--skip)}
.dot.NONE{background:transparent;border:1px dashed var(--ink-faint)}
.fam{background:var(--card);border:1px solid var(--rule);border-radius:10px;
  padding:18px 20px;margin-bottom:18px}
.fam header{display:flex;flex-wrap:wrap;gap:10px;align-items:baseline;justify-content:space-between;
  margin-bottom:4px}
.why{color:var(--ink-soft);margin:2px 0 14px;max-width:none}
.gate{display:grid;grid-template-columns:26px 1fr;gap:11px;padding:9px 0;border-top:1px solid var(--rule)}
.gate .name{font-weight:600;font-size:13px}
.gate .detail{color:var(--ink-soft);font-size:13.5px}
details{margin-top:6px}
summary{cursor:pointer;font-size:12px;color:var(--accent)}
summary:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
.stats{margin-top:8px;display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:2px 18px}
.stats div{display:flex;justify-content:space-between;gap:12px;font-size:12px;
  font-family:ui-monospace,monospace;border-bottom:1px dotted var(--rule);padding:3px 0}
.stats .sk{color:var(--ink-faint)}
footer{margin-top:56px;padding-top:18px;border-top:1px solid var(--rule);
  color:var(--ink-faint);font-size:12.5px}
@media (max-width:560px){
  h1{font-size:24px} .card .v{font-size:22px} .cell{width:22px;height:22px}
}
"""


def _ladder(run: dict[str, Any]) -> str:
    by_gate = {int(g["gate"]): g for g in run.get("gates", [])}
    cells = []
    for number in range(10):
        gate = by_gate.get(number)
        verdict = gate["verdict"] if gate else "NONE"
        title = (
            f"gate {number} {GATE_NAMES[number]}: {verdict}"
            if gate
            else f"gate {number} {GATE_NAMES[number]}: not reached"
        )
        cells.append(f'<div class="cell {_esc(verdict)}" title="{_esc(title)}">{number}</div>')
    return f'<div class="ladder">{"".join(cells)}</div>'


def _overview(runs: list[dict[str, Any]]) -> str:
    rows = []
    for run in runs:
        stopped = _stopped_at(run)
        rows.append(
            "<tr>"
            f'<td><a href="#{_esc(run["hypothesis_id"])}">{_esc(run["hypothesis_id"])}</a></td>'
            f"<td>{_ladder(run)}</td>"
            f'<td><span class="badge {_esc(run.get("verdict", "SKIP"))}">'
            f'{_esc(run.get("verdict", "—"))}</span></td>'
            f'<td class="num">{"gate " + str(stopped) if stopped is not None else "—"}</td>'
            f'<td class="num">{_num(_stat(run, "sharpe"))}</td>'
            f'<td class="num">{_num(_stat(run, "net_over_gross"))}</td>'
            f'<td class="num">{_num(_stat(run, "max_drawdown"), 2)}</td>'
            f'<td class="num">{_num(run.get("context", {}).get("trials"), 0)}</td>'
            "</tr>"
        )
    head = (
        "<tr><th>hypothesis</th><th>gates 0–9</th><th>verdict</th><th>stopped</th>"
        "<th>sharpe</th><th>net/gross</th><th>max dd</th><th>variants</th></tr>"
    )
    # `NONE` has no colour of its own — an unreached gate is an absence, drawn
    # as the same dashed outline the ladder uses rather than a fifth hue.
    legend = "".join(
        f'<span><i class="dot {v}"></i>{label}</span>'
        for v, label in [("PASS", "passed"), ("WARN", "warned"), ("FAIL", "failed"),
                         ("SKIP", "not applicable"), ("NONE", "not reached")]
    )
    return (
        f'<div class="scroll"><table>{head}{"".join(rows)}</table></div>'
        f'<div class="legend">{legend}</div>'
    )


def _family(run: dict[str, Any]) -> str:
    gates = []
    for gate in run.get("gates", []):
        number = int(gate["gate"])
        stats = gate.get("stats") or {}
        detail = _esc(gate.get("detail") or "")
        rows = "".join(
            f'<div><span class="sk">{_esc(k)}</span><span>{_esc(_short(v))}</span></div>'
            for k, v in stats.items()
            if not isinstance(v, (dict, list))
        )
        more = (
            f"<details><summary>{len(stats)} statistics</summary>"
            f'<div class="stats">{rows}</div></details>'
            if rows
            else ""
        )
        gates.append(
            '<div class="gate">'
            f'<div class="cell {_esc(gate["verdict"])}">{number}</div>'
            f'<div><div class="name">{number} · {_esc(gate.get("name", GATE_NAMES.get(number, "")))}'
            f'</div><div class="detail">{detail}</div>{more}</div>'
            "</div>"
        )
    context = run.get("context", {})
    meta = " · ".join(
        part
        for part in [
            f'{context.get("trials", "?")} variants',
            f'{context.get("start", "")[:10]} → {context.get("end", "")[:10]}'
            if context.get("start")
            else "",
            f'{len(context.get("symbols") or [])} symbols',
        ]
        if part
    )
    return (
        f'<section class="fam" id="{_esc(run["hypothesis_id"])}">'
        f"<header><h3>{_esc(run['hypothesis_id'])}</h3>"
        f'<span class="badge {_esc(run.get("verdict", "SKIP"))}">{_esc(run.get("verdict", "—"))}</span>'
        f"</header>"
        f'<p class="why">{_esc(run.get("reason") or "")}</p>'
        f'<p class="mono" style="color:var(--ink-faint);margin:0 0 10px">{_esc(meta)}</p>'
        f"{''.join(gates)}</section>"
    )


def _short(value: Any) -> str:
    if isinstance(value, float):
        if value != value:
            return "nan"
        return f"{value:,.4g}"
    text = str(value)
    return text if len(text) <= 48 else text[:45] + "…"


def render(runs: list[dict[str, Any]], audit: dict[str, Any], title: str = "Trial Record") -> str:
    """One self-contained page. No scripts, no network, no build step."""
    verdicts = [r.get("verdict") for r in runs]
    passed = sum(1 for v in verdicts if v == "PASS")
    cards = [
        ("hypotheses judged", str(len(runs))),
        ("passed every gate", str(passed)),
        ("variants searched", f'{sum(int(r.get("context", {}).get("trials") or 0) for r in runs):,}'),
        ("log records", f'{audit.get("records", "—"):,}' if audit.get("records") else "—"),
    ]
    card_html = "".join(
        f'<div class="card"><div class="k">{_esc(k)}</div><div class="v">{_esc(v)}</div></div>'
        for k, v in cards
    )
    drift = audit.get("drift") or []
    audit_line = (
        f'chain {_esc(audit.get("chain", "?"))}'
        + (f' · {audit["trials"]:,} trials counted' if audit.get("trials") else "")
        + (
            " · pre-registration documents match their stamps"
            if audit.get("chain") == "verified" and not drift
            else f" · {len(drift)} document(s) no longer match" if drift else ""
        )
    )
    body = (
        "<div class='wrap'>"
        f"<h1>{_esc(title)}</h1>"
        f'<p class="sub">Every hypothesis this platform has judged, and the gate that stopped it. '
        f'Generated {datetime.now(timezone.utc):%d %B %Y}.</p>'
        f'<div class="grid cards">{card_html}</div>'
        "<h2>Where each family died</h2>"
        + (_overview(runs) if runs else "<p>No reports yet. Run <code>qr families</code>.</p>")
        + ("<h2>The gates, one family at a time</h2>" if runs else "")
        + "".join(_family(run) for run in runs)
        + f'<footer><div class="mono">{_esc(audit_line)}</div>'
        f'<div class="mono" style="margin-top:4px">{_esc(audit.get("path", ""))}</div></footer>'
        "</div>"
    )
    return (
        "<!doctype html><html lang='en'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        f"<title>{_esc(title)}</title><style>{STYLE}</style></head>"
        f"<body>{body}</body></html>"
    )


def write_site(reports_dir: Path | str, trial_log: TrialLog, out: Path | str) -> Path:
    """Render the site to `out` and return the path written."""
    path = Path(out)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render(collect(reports_dir), integrity(trial_log)), encoding="utf-8")
    return path
