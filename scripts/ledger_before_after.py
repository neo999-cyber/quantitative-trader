"""Review 22, step 8: the before/after table for a frozen grid re-run on the ledger engine.

Reads two directories of gate reports — the weight-engine originals and the
ledger re-runs — and prints one row per hypothesis: verdict, the gate it
stopped at, best net Sharpe, gross Sharpe, cost drag, turnover, gate 3's t
and gate 6's permutation p, each before → after. Writes nothing to the
trial log; the re-runs themselves are the counted trials.

    python scripts/ledger_before_after.py ~/qr/lake/reports/weights_engine ~/qr/lake/reports/ledger_engine
"""
from __future__ import annotations

import json
import sys
from pathlib import Path


def _load(directory: Path) -> dict[str, dict]:
    out = {}
    for path in sorted(directory.glob("*.json")):
        if path.name.endswith("_external.json"):
            continue
        with path.open() as fh:
            out[path.stem] = json.load(fh)
    return out


def _stat(report: dict, gate: int, key: str):
    for g in report.get("gates", []):
        if g.get("gate") == gate:
            return g.get("stats", {}).get(key)
    return None


def _stopped_at(report: dict) -> str:
    failed = [g["gate"] for g in report.get("gates", []) if g.get("verdict") == "FAIL"]
    return ",".join(str(g) for g in failed) if failed else "—"


def _fmt(value, digits=2) -> str:
    if value is None:
        return "—"
    try:
        return f"{float(value):.{digits}f}"
    except (TypeError, ValueError):
        return str(value)


def row(name: str, before: dict | None, after: dict | None) -> str:
    def pair(get, digits=2):
        return f"{_fmt(get(before) if before else None, digits)} → {_fmt(get(after) if after else None, digits)}"

    cells = [
        name,
        f"{before['verdict'] if before else '—'} → {after['verdict'] if after else '—'}",
        f"{_stopped_at(before) if before else '—'} → {_stopped_at(after) if after else '—'}",
        pair(lambda r: r["tear_sheet"].get("sharpe")),
        pair(lambda r: r["tear_sheet"].get("gross_sharpe")),
        pair(lambda r: r["tear_sheet"].get("cost_drag_ann"), 4),
        pair(lambda r: r["tear_sheet"].get("ann_turnover"), 1),
        pair(lambda r: _stat(r, 3, "hac_tstat")),
        pair(lambda r: _stat(r, 6, "bar_permutation_p_value")),
        f"{(before or {}).get('context', {}).get('engine', 'weights')} → {(after or {}).get('context', {}).get('engine', '?')}",
    ]
    return "| " + " | ".join(cells) + " |"


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print(__doc__, file=sys.stderr)
        return 2
    before, after = _load(Path(argv[1])), _load(Path(argv[2]))
    names = sorted(set(before) | set(after))
    print("| hypothesis | verdict | failed gates | net Sharpe | gross Sharpe | cost drag/yr | turnover/yr | gate 3 t | gate 6 p | engine |")
    print("|---|---|---|---|---|---|---|---|---|---|")
    for name in names:
        print(row(name, before.get(name), after.get(name)))
    missing = [n for n in names if n not in after]
    if missing:
        print(f"\nnot re-run: {', '.join(missing)}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
