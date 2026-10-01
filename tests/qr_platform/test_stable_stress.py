"""The ladder stress simulator: tier 0 is riskless, tails order by tier, the table is complete."""
from __future__ import annotations

import numpy as np

from qr.research.stable_stress import ASSUMPTIONS, ladder_table, simulate, summarise


def test_tbill_is_riskless_and_earns_its_yield():
    r = simulate(ASSUMPTIONS[0], 1000)
    assert np.allclose(r, 0.04)


def test_tails_worsen_with_tier():
    df = ladder_table(principal=1000.0, n_years=20_000)
    by_tier = df.groupby("tier").cvar_5.min()
    assert by_tier[0] > by_tier[1] > by_tier[3]  # CVaR gets more negative as the tier rises


def test_summary_fields_and_bounds():
    s = summarise(simulate(ASSUMPTIONS[4], 5000), 1300.0)
    assert -1.0 <= s["worst_1pct"] <= s["cvar_5"] <= s["expected_return"] <= 0.1
    assert 0 <= s["p_loss_gt_10pct"] <= s["p_loss"] <= 1
