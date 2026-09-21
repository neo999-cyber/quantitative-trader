"""Polymarket / Deribit loaders (Programme 3, P3-A): classification, eligibility, history parsing. No network."""
from __future__ import annotations

import json

import pandas as pd
import pytest

from qr.data import deribit, polymarket


@pytest.mark.parametrize(
    "q, expected",
    [
        ("Will Bitcoin reach $150,000 in January?", ("BTC", "reach", 150_000.0)),
        ("Will Ethereum dip to $2,000 by March 31?", ("ETH", "dip", 2_000.0)),
        ("Will Bitcoin be above $100k on December 31?", ("BTC", "above", 100_000.0)),
        ("Will Solana hit $300 in 2026?", ("SOL", "reach", 300.0)),
        ("Will the price of Bitcoin be above $95,000 on September 21, 4AM ET?", None),  # dated-hour market: excluded
        ("Bitcoin Up or Down - September 21, 3PM ET", None),
        ("Will Trump mention Bitcoin?", None),  # no strike
        ("Will Apple close above $200?", None),  # not a crypto asset
        ("Will Bitcoin hit $70k or $90k first?", None),  # two strikes, a race: not a threshold market
    ],
)
def test_classify(q, expected):
    c = polymarket.classify(q)
    if expected is None:
        assert c is None
    else:
        assert (c["asset"], c["kind"], c["strike"]) == expected


def test_eligible_filters_by_rule():
    df = pd.DataFrame({
        "market_id": ["1", "2", "3", "4", "5"],
        "kind": ["reach", "reach", None, "dip", "reach"],
        "closed": [True, True, True, True, False],
        "horizon_days": [30, 3, 30, 30, 30],
        "volume": [50_000.0, 50_000.0, 50_000.0, 100.0, 50_000.0],
        "yes_token": ["a", "b", "c", "d", "e"],
        "end": pd.to_datetime(["2025-01-01"] * 5, utc=True),
    })
    out = polymarket.eligible(df)
    assert list(out["market_id"]) == ["1"]  # short horizon, unclassified, thin, and open markets all drop


def test_price_history_reads_mirror_and_collapses_to_days(tmp_path):
    token = "123"
    d = tmp_path / "polymarket" / "prices"
    d.mkdir(parents=True)
    t0 = int(pd.Timestamp("2026-01-02", tz="UTC").timestamp())
    hist = [{"t": t0, "p": 0.10}, {"t": t0 + 3600, "p": 0.12}, {"t": t0 + 86400, "p": 0.20}]
    (d / f"{token}.json").write_text(json.dumps({"history": hist}))
    s = polymarket.price_history(tmp_path, token)
    assert len(s) == 2
    assert s.iloc[0] == pytest.approx(0.12)  # last print of the day
    assert s.iloc[1] == pytest.approx(0.20)


def test_dvol_to_frame_dedups_and_sorts():
    t1 = int(pd.Timestamp("2026-01-02", tz="UTC").timestamp() * 1000)
    t0 = t1 - 86_400_000
    rows = [[t1, 50, 52, 49, 51], [t0, 48, 49, 47, 48.5], [t1, 50, 52, 49, 51]]
    df = deribit.to_frame(rows)
    assert len(df) == 2
    assert list(df["close"]) == [48.5, 51.0]
    assert df["date"].iloc[0] < df["date"].iloc[1]
