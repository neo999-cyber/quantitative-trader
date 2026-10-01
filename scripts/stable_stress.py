#!/usr/bin/env python3
"""The stablecoin ladder's loss distributions (`qr/research/stable_stress.py`) as a markdown table for `docs/31`.

    python scripts/stable_stress.py [--principal 1300]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from qr.research.stable_stress import ASSUMPTIONS, REPLAYS, ladder_table


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--principal", type=float, default=1300.0)
    ap.add_argument("--out", type=Path, default=Path("reports/p3/ladder_stress.md"))
    a = ap.parse_args(argv)
    df = ladder_table(a.principal)
    lines = [f"# Stablecoin ladder — one-year loss distributions on ${a.principal:,.0f} (Monte Carlo, 20,000 years, assumptions in `qr/research/stable_stress.py`)", "",
             "| Tier | Instrument | Stated yield | Expected | P(loss) | P(loss > 10%) | CVaR 5% | Worst 1% | Expected $ | CVaR 5% $ |", "|---|---|---|---|---|---|---|---|---|---|"]
    for r in df.itertuples(index=False):
        lines.append(f"| {r.tier} | {r.instrument} | {r.yield_pa*100:.1f}% | **{r.expected_return*100:+.2f}%** | {r.p_loss*100:.1f}% | {r.p_loss_gt_10pct*100:.1f}% | {r.cvar_5*100:+.1f}% | {r.worst_1pct*100:+.1f}% | {r.expected_usd:+,.0f} | {r.cvar_5_usd:+,.0f} |")
    lines += ["", "## Assumptions (edit these, not the code)", "", "| Instrument | Event | Rate / yr | Loss low / mode / high | Applies with prob. | Anchor |", "|---|---|---|---|---|---|"]
    for t in ASSUMPTIONS:
        for e in t.events:
            lines.append(f"| {t.name} | {e.name} | {e.rate_per_year:.3f} | {e.loss_low:.0%} / {e.loss_mode:.0%} / {e.loss_high:.0%} | {e.forced_sale_prob:.0%} | {e.anchor} |")
        if t.price_vol_pa:
            lines.append(f"| {t.name} | price of the staked asset | — | lognormal, vol {t.price_vol_pa:.0%}/yr | 100% | {t.note} |")
    lines += ["", "## Historical replays (deterministic)", ""]
    for name, cases in REPLAYS.items():
        lines.append(f"- **{name}**: " + "; ".join(f"{k}: {v if isinstance(v, str) else f'{v:+.0%}'}" for k, v in cases.items()))
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text("\n".join(lines) + "\n")
    print("\n".join(lines[:12]))
    print(f"\nwrote {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
