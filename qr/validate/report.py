"""The Hypothesis Report: the validation engine's output, and the only thing
allowed to promote an idea.

Markdown for a human, JSON for the machine, both from one `GateReport`. It
carries the eleven rows with their verdicts, the trial count at the time, the
data manifest hash, the frozen cost model, the factor decomposition and the
tear sheet — so a report read a year later can be checked against the exact
bytes and the exact fee schedule it was computed on.

Two conventions the report enforces rather than describes:

* **An unjustified WARN counts as a FAIL.** A WARN requires a written note in
  the trial log for the same hypothesis; without one, the headline verdict is
  degraded. Waving a warning through silently is how thresholds stop meaning
  anything.
* **The headline is the deflated number, not the backtest number.** The
  in-sample Sharpe appears, but below the deflated Sharpe and the holdout, so
  the first figure anyone's eye lands on is the honest one.
"""
from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from qr.report import table
from qr.validate.gates import FAIL, PASS, SKIP, WARN, GateReport
from qr.validate.trial_log import TrialLog

VERDICT_MARK = {PASS: "PASS", WARN: "WARN", FAIL: "**FAIL**", SKIP: "skip"}

#: The full eleven, so the report shows what was not run as well as what was.
GATE_NAMES = {
    0: "Pre-registration",
    1: "Data integrity",
    2: "Cost survival",
    3: "Single-strategy significance",
    4: "Multiple-testing deflation",
    5: "Selection overfitting",
    6: "Permutation",
    7: "Cross-validated OOS distribution",
    8: "Robustness and regime",
    9: "True holdout",
    10: "Incubation",
    11: "Sizing",
}


def justified_warnings(report: GateReport, trial_log: TrialLog | None) -> dict[int, bool]:
    """Which WARNs have a written justification in the trial log."""
    if trial_log is None:
        return {r.number: False for r in report.warnings}
    notes = trial_log.records(kind="note", hypothesis_id=report.hypothesis_id)
    text = " ".join(str(n.payload.get("text", "")).lower() for n in notes)
    return {r.number: (f"gate {r.number}" in text) for r in report.warnings}


def headline_verdict(report: GateReport, trial_log: TrialLog | None = None) -> tuple[str, str]:
    """The verdict and one sentence of why, with unjustified WARNs counted as FAIL."""
    stopped = report.stopped_at
    if stopped is not None:
        return FAIL, f"stopped at gate {stopped.number} ({stopped.name}): {stopped.detail}"
    justified = justified_warnings(report, trial_log)
    unjustified = [n for n, ok in justified.items() if not ok]
    if unjustified:
        gates = ", ".join(str(n) for n in sorted(unjustified))
        return FAIL, f"warnings at gate(s) {gates} with no written justification in the trial log"
    if report.warnings:
        gates = ", ".join(str(r.number) for r in report.warnings)
        return WARN, f"passed with justified warnings at gate(s) {gates}"
    return PASS, "every gate run returned PASS"


def to_json(report: GateReport, trial_log: TrialLog | None = None, extra: dict | None = None) -> dict[str, Any]:
    verdict, reason = headline_verdict(report, trial_log)
    justified = justified_warnings(report, trial_log)
    return {
        "hypothesis_id": report.hypothesis_id,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "verdict": verdict,
        "reason": reason,
        "gates": [
            {
                "gate": r.number,
                "name": r.name,
                "verdict": r.verdict,
                "detail": r.detail,
                "justified": justified.get(r.number),
                "stats": _jsonable(r.stats),
            }
            for r in report.results
        ],
        "context": _jsonable(report.context),
        **(extra or {}),
    }


def _jsonable(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {str(k): _jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_jsonable(v) for v in obj]
    if isinstance(obj, (np.floating, np.integer)):
        obj = obj.item()
    if isinstance(obj, float) and not np.isfinite(obj):
        return None
    if isinstance(obj, (pd.Timestamp, datetime)):
        return str(obj)
    if isinstance(obj, np.ndarray):
        return _jsonable(obj.tolist())
    return obj


def _fmt(value: Any) -> str:
    if value is None or (isinstance(value, float) and not np.isfinite(value)):
        return "—"
    if isinstance(value, float):
        return f"{value:,.4g}"
    return str(value)


def to_markdown(
    report: GateReport,
    trial_log: TrialLog | None = None,
    tear_sheet: dict[str, float] | None = None,
) -> str:
    verdict, reason = headline_verdict(report, trial_log)
    justified = justified_warnings(report, trial_log)
    context = report.context
    strategy = context.get("strategy", {})

    lines: list[str] = [
        f"# Hypothesis Report — `{report.hypothesis_id}`",
        "",
        f"## Verdict: **{verdict}**",
        "",
        reason,
        "",
        "| | |",
        "|---|---|",
        f"| Strategy | `{strategy.get('name', '?')}` (family `{strategy.get('family', '?')}`) |",
        f"| Parameters | `{strategy.get('params', {})}` |",
        f"| Universe | {len(context.get('symbols', []))} symbols, {context.get('start', '?')} → {context.get('end', '?')} |",
        f"| **Trials counted** | **{context.get('trials', '?')}** |",
        f"| Data manifest | `{(context.get('manifest_hash') or 'not stamped')[:32]}` |",
        f"| Cost model | `{context.get('costs', {}).get('name', '?')}` at "
        f"{_fmt(context.get('costs', {}).get('linear_bps_per_side'))} bps/side, "
        f"fees verified {context.get('costs', {}).get('fees_verified_on', '?')} |",
        f"| Generated | {datetime.now(timezone.utc).isoformat(timespec='seconds')} |",
        "",
        "## The gates",
        "",
        "| # | Gate | Verdict | Detail |",
        "|---|---|---|---|",
    ]

    run_numbers = {r.number for r in report.results}
    for number in sorted(GATE_NAMES):
        found = next((r for r in report.results if r.number == number), None)
        if found is None:
            note = "not reached" if number <= 9 and run_numbers and number > max(run_numbers) else "after the trial"
            lines.append(f"| {number} | {GATE_NAMES[number]} | — | _{note}_ |")
            continue
        mark = VERDICT_MARK.get(found.verdict, found.verdict)
        detail = found.detail
        if found.verdict == WARN:
            detail += " — _justified_" if justified.get(number) else " — **UNJUSTIFIED**"
        lines += [f"| {number} | {GATE_NAMES[number]} | {mark} | {detail} |"]

    lines += ["", "## What the numbers were", ""]

    headline = _headline_table(report, tear_sheet)
    lines += [table(headline), ""]

    factor_row = _factor_row(report)
    if factor_row is not None:
        lines += ["### Factor decomposition", "", factor_row, ""]

    lines += ["### Per gate", ""]
    for result in report.results:
        if not result.stats:
            continue
        lines += [f"**Gate {result.number} — {result.name}**", ""]
        rows = pd.DataFrame(
            [{"statistic": k, "value": _fmt(v)} for k, v in result.stats.items() if not isinstance(v, dict)]
        )
        lines += [table(rows), ""]

    lines += [
        "## How to read this",
        "",
        "The in-sample Sharpe is the least informative number here and appears last for that "
        "reason. The deflated Sharpe prices the search; the holdout is the only figure computed "
        "on data the strategy had never seen. A strategy is worth trading when those two agree "
        "with each other, not when the backtest is impressive.",
        "",
        f"Reproduce: the data manifest hash pins the bytes, the trial log pins the "
        f"{context.get('trials', '?')} variants that were run, and the cost model above pins the "
        "fee schedule. Change any of the three and this report no longer applies.",
        "",
    ]
    return "\n".join(lines)


def _headline_table(report: GateReport, tear_sheet: dict[str, float] | None) -> pd.DataFrame:
    """Deflated and out-of-sample first; the backtest number last."""
    by_gate = {r.number: r.stats for r in report.results}
    rows = [
        ("Deflated Sharpe (gate 4)", by_gate.get(4, {}).get("dsr")),
        ("Holdout Sharpe (gate 9)", by_gate.get(9, {}).get("holdout_sharpe")),
        ("Median CPCV path Sharpe (gate 7)", by_gate.get(7, {}).get("median_path_sharpe")),
        ("Probability of backtest overfitting (gate 5)", by_gate.get(5, {}).get("pbo")),
        ("Bar-permutation p (gate 6)", by_gate.get(6, {}).get("bar_permutation_p_value")),
        # Reported, not binding: the plain null is what the pre-registrations
        # name. See `docs/07_ENGINE_FIXES.md` §3.
        (
            "…with volatility preserved (reported, not binding)",
            by_gate.get(6, {}).get("bar_permutation_vol_preserved_p_value"),
        ),
        ("HAC t-statistic (gate 3)", by_gate.get(3, {}).get("hac_tstat")),
        ("Probabilistic Sharpe (gate 3)", by_gate.get(3, {}).get("psr")),
        ("Net / gross return (gate 2)", by_gate.get(2, {}).get("net_over_gross")),
        ("In-sample net Sharpe (the backtest number)", by_gate.get(2, {}).get("net_sharpe")),
    ]
    if tear_sheet:
        for key in ("cagr", "ann_vol", "max_drawdown", "ann_turnover", "round_trips", "time_in_market", "carry_share_of_gross"):
            if key in tear_sheet and not (isinstance(tear_sheet[key], float) and np.isnan(tear_sheet[key])):
                rows.append((key.replace("_", " "), tear_sheet[key]))
    return pd.DataFrame([{"metric": name, "value": _fmt(value)} for name, value in rows])


def _factor_row(report: GateReport) -> str | None:
    stats = next((r.stats for r in report.results if r.number == 8), None)
    if not stats or "alpha_tstat" not in stats:
        return None
    betas = {k[len("beta_") :]: v for k, v in stats.items() if k.startswith("beta_")}
    rows = [
        {"term": "alpha (annualised)", "value": _fmt(stats.get("alpha_annual")), "t-stat": _fmt(stats.get("alpha_tstat"))},
        *[{"term": f"beta to {name}", "value": _fmt(value), "t-stat": "—"} for name, value in betas.items()],
        {"term": "information ratio", "value": _fmt(stats.get("information_ratio")), "t-stat": "—"},
        {"term": "R²", "value": _fmt(stats.get("r_squared")), "t-stat": "—"},
    ]
    return table(pd.DataFrame(rows))


def write_report(
    report: GateReport,
    directory: Path | str,
    trial_log: TrialLog | None = None,
    tear_sheet: dict[str, float] | None = None,
) -> tuple[Path, Path]:
    """Write `<id>.md` and `<id>.json` side by side. Returns both paths.

    Refuses a run computed on the discovery sandbox. Gate 0 already fails such
    a run, but a report is the artefact that leaves this machine — it is what
    gets read, quoted and remembered — so the refusal is repeated at the point
    of writing rather than trusted to a gate somebody might have skipped with
    `--upto`. The sandbox's entire value is the promise that nothing from it
    reaches the record; a promise with one enforcement point is a promise one
    refactor from being broken.
    """
    if (report.context or {}).get("sandbox_side") == "discovery":
        raise ValueError(
            f"{report.hypothesis_id} was run on the discovery sandbox, which is not reportable. "
            "Exploration there is free precisely because nothing leaves it — re-run against "
            "the validation side if this is a candidate rather than a look."
        )
    out = Path(directory)
    out.mkdir(parents=True, exist_ok=True)
    stem = report.hypothesis_id.replace("/", "_")
    md_path = out / f"{stem}.md"
    json_path = out / f"{stem}.json"
    md_path.write_text(to_markdown(report, trial_log, tear_sheet), encoding="utf-8")
    json_path.write_text(
        json.dumps(to_json(report, trial_log, {"tear_sheet": _jsonable(tear_sheet or {})}), indent=2),
        encoding="utf-8",
    )
    return md_path, json_path
