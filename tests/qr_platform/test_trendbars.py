"""The `trend_reset` instruments (`qr/data/trendbars.py`) and the family reading its inputs from a panel; fixtures only."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from qr.config import paths
from qr.data import trendbars as tb
from qr.data.lake import Lake
from qr.data.panel import FIELDS, Panel
from qr.data.qa import check_klines
from qr.strategies import trend as tr
from qr.strategies.trend import TrendReset, features

NY = "America/New_York"


def _minutes(day: str, rows: list[tuple[str, float, float, float, float, float]]) -> pd.DataFrame:
    """Minute bars for one New York date: (HH:MM, open, high, low, close, volume), stamped in UTC."""
    idx = pd.DatetimeIndex([pd.Timestamp(f"{day} {hm}", tz=NY) for hm, *_ in rows]).tz_convert("UTC")
    return pd.DataFrame([r[1:] for r in rows], index=idx, columns=["open", "high", "low", "close", "volume"])


def _session(day: str, close_hm: str = "16:00", cross: float | None = 105.0) -> pd.DataFrame:
    rows = [("08:00", 90.0, 91.0, 89.0, 90.5, 10.0),                       # before the open: ignored
            ("09:30", 100.0, 101.0, 99.5, 100.5, 50.0),
            ("09:31", 100.5, 102.0, 100.0, 101.0, 20.0),
            ("12:59", 101.0, 103.0, 98.0, 102.0, 30.0)]
    if close_hm == "16:00":
        rows.append(("15:59", 102.0, 104.0, 101.5, 104.0, 40.0))
    if cross is not None:
        rows.append((close_hm, cross, 106.0, 104.5, 105.5, 500.0))        # the auction prints as this minute's first trade
    rows.append(("17:00", 107.0, 108.0, 106.0, 107.5, 5.0))                # after the close: ignored
    return _minutes(day, rows)


def test_session_bars_take_the_auction_print_and_respect_the_early_close():
    winter, summer, early, bare = "2024-01-17", "2024-06-12", "2024-11-29", "2024-06-13"
    minutes = pd.concat([_session(winter), _session(summer), _session(early, "13:00", cross=102.5), _session(bare, cross=None)])
    bars = tb.session_bars(minutes)
    assert [d.date().isoformat() for d in bars.index] == [winter, summer, bare, early] and str(bars.index.tz) == "UTC"
    for day in (winter, summer):                                           # the same local hours in winter and summer time
        b = bars.loc[pd.Timestamp(day, tz="UTC")]
        assert (b["open"], b["close"], b["high"], b["low"]) == (100.0, 105.0, 105.0, 98.0)
        assert b["volume"] == 50 + 20 + 30 + 40 + 500 and b["has_cross"] == 1.0 and b["early_close"] == 0.0 and b["minutes"] == 4
        assert b["quote_volume"] == pytest.approx(50 * 100.5 + 20 * 101 + 30 * 102 + 40 * 104 + 500 * 105.0)
        assert b["cross_share"] == pytest.approx(500 / 640)
    e = bars.loc[pd.Timestamp(early, tz="UTC")]
    assert (e["close"], e["early_close"], e["minutes"]) == (102.5, 1.0, 3) and e["volume"] == 50 + 20 + 30 + 500   # the 13:00 print; nothing after it
    n = bars.loc[pd.Timestamp(bare, tz="UTC")]
    assert (n["close"], n["has_cross"]) == (104.0, 0.0)                    # no auction minute: the last regular minute's close


def _daily(closes, opens=None, volume=1000.0):
    idx = pd.date_range("2024-01-02", periods=len(closes), freq="B", tz="UTC")
    opens = closes if opens is None else opens
    return pd.DataFrame({"open": opens, "high": np.maximum(opens, closes), "low": np.minimum(opens, closes), "close": closes,
                         "volume": volume, "quote_volume": np.asarray(closes) * volume}, index=idx, dtype=float)


def test_split_adjust_reads_the_ratio_and_never_guesses():
    bars = _daily([396.0, 400.0, 102.0, 103.0], opens=[395.0, 398.0, 101.0, 102.5])     # a 4:1 split before the third session
    out, events = tb.split_adjust(bars)
    assert events == [{"date": "2024-01-04", "ratio": 4, "gap": round(101.0 / 400.0, 4)}]
    assert out["close"].tolist() == [99.0, 100.0, 102.0, 103.0] and out["split_factor"].tolist() == [0.25, 0.25, 1.0, 1.0]
    assert out["volume"].tolist() == [4000.0, 4000.0, 1000.0, 1000.0] and out["close_unadjusted"].tolist() == [396.0, 400.0, 102.0, 103.0]
    assert out["open"].iloc[2] / out["close"].iloc[1] - 1 == pytest.approx(0.01)       # the night is a 1% move, not −75%
    crash, events = tb.split_adjust(_daily([100.0, 100.0, 58.0], opens=[100.0, 100.0, 57.0]))
    assert events == [{"date": "2024-01-04", "ratio": 0, "gap": 0.57}]                  # −43% fits no split within 10%: left alone, reported
    assert crash["close"].tolist() == [100.0, 100.0, 58.0] and crash["split_factor"].tolist() == [1.0, 1.0, 1.0]
    reverse, events = tb.split_adjust(_daily([10.0, 10.0, 101.0], opens=[10.0, 10.0, 100.0]))
    assert events[0]["ratio"] == -10 and reverse["close"].tolist() == [100.0, 100.0, 101.0]
    quiet, events = tb.split_adjust(_daily([100.0, 70.0, 71.0], opens=[100.0, 70.0, 70.5]))  # a −30% night is a return
    assert events == [] and quiet["close"].tolist() == [100.0, 70.0, 71.0]


def _walk(n=700, seed=5, drift=0.0008):
    r = np.random.default_rng(seed).normal(drift, 0.015, n)
    return 100 * np.exp(np.cumsum(r))


def test_builders_write_bars_with_the_rule_inputs(tmp_path, monkeypatch):
    lake = Lake(paths(tmp_path / "lake").ensure())
    days = pd.bdate_range("2021-01-04", periods=420)
    px = _walk(len(days))
    px[300:] /= 5.0                                                        # a 5:1 split before session 300
    minutes = pd.concat([_minutes(d.date().isoformat(), [("09:30", p, p, p, p, 100.0), ("15:59", p, p, p, p, 100.0), ("16:00", p, p, p, p, 300.0)])
                         for d, p in zip(days, px)])
    minutes["quote_volume"] = minutes["volume"] * minutes["close"]
    lake.write_klines("AAA", minutes, "1m", source="databento", market="xnas")
    summary = tb.build_trend_xnas(lake, ["AAA"])
    row = summary.iloc[0]
    assert row["sessions"] == 420 and row["splits"] == f"5:1@{days[300].date().isoformat()}" and row["unexplained"] == 0
    assert (row["early"], row["no_cross"]) == (1, 1)                       # 26 November 2021 closed at 13:00, and this fixture has no 13:00 minute
    frame = lake.read_klines("AAA", "1d", source="databento", market="trend-xnas")
    assert {"close", "close_unadjusted", "split_factor", "above_ma", "trend_ok", "zroc_21", "zprior_21", "zroc_63", "zprior_63"} <= set(frame.columns)
    assert np.allclose(frame["close"].to_numpy()[:300], px[:300] / 5.0) and np.allclose(frame["close"].to_numpy()[300:], px[300:])
    f = features(frame[["close"]])
    for name in ("above_ma", "trend_ok", "zroc_21", "zprior_21", "zroc_63", "zprior_63"):
        pd.testing.assert_series_equal(frame[name], f[name]["close"], check_names=False)
    assert frame["zroc_63"].first_valid_index() == frame.index[tr.VOL]     # the volatility needs 252 returns
    monkeypatch.setattr(tb, "SYMBOL_START", {"AAA": days[100].date().isoformat()})   # a ticker that meant something else before
    assert tb.build_trend_xnas(lake, ["AAA"]).iloc[0]["sessions"] == 320
    etf = _daily(_walk(500, seed=9)); etf["close_unadjusted"] = etf["close"] * 1.4; etf["dividend"] = 0.0
    etf["quote_volume"] = etf["volume"] * etf["close_unadjusted"]         # as the lake held it until 12 November: adjusted prices, shares as traded, true dollars
    lake.write_klines("SPY", etf, "1d", source="tiingo", market="etf")
    assert not lake.load_panel(["SPY"], "1d", source="tiingo", market="etf").tradable().any().any()   # which the engine refuses
    assert "quote_volume_consistent" in {c.name for c in check_klines(etf, "SPY", calendar="xnys").failures}   # and QA with it
    assert tb.build_trend_etf(lake, ["SPY"]).iloc[0]["sessions"] == 500
    out = lake.read_klines("SPY", "1d", source="tiingo", market="trend-etf")
    assert "dividend" not in out.columns and np.allclose(out["close"], etf["close"]) and out["trend_ok"].notna().all()
    assert np.allclose(out["volume"] * out["close"], out["quote_volume"])
    assert lake.load_panel(["SPY"], "1d", source="tiingo", market="trend-etf").tradable().all().all()
    # QA asks the engine's question: until 12 November it moved dollars over shares by close / close_unadjusted a second
    # time, and failed both instruments before every split or distribution on bars the engine trades (gate 1 reads that
    # as a data failure on a held name).
    assert not check_klines(out, "SPY", "1d", calendar="xnys").failures
    assert not check_klines(frame, "AAA", "1d", calendar="xnys").failures
    panel = lake.load_panel(["AAA"], "1d", source="databento", market="trend-xnas")
    assert panel.get("zprior_63") is not None and panel.get("trend_ok") is not None


def test_a_panel_that_carries_the_inputs_needs_no_warm_up():
    idx = pd.date_range("2020-01-01", periods=900, freq="D", tz="UTC")
    n, base, run = 900, 400, 21
    alt = np.array([0.002 if k % 2 else -0.002 for k in range(n)])
    r = np.zeros(n); r[1:base] = 0.001 + alt[1:base]; r[base:base + run] = 0.02; r[base + run:] = alt[base + run:]
    close = pd.DataFrame({"UP": 100 * np.exp(np.cumsum(r)), "CHOP": _walk(n, seed=7, drift=0.0004)}, index=idx)
    rule = TrendReset(roc=21, hold=10)
    full = rule.target_weights(Panel({"close": close}, "1d"))
    first = int(np.flatnonzero(full.to_numpy().sum(axis=1))[0])
    cut = first - 5                                                       # the book is flat here, so nothing is lost at the cut
    carried = Panel({"close": close, **features(close)}, "1d").slice(start=idx[cut].date().isoformat())
    assert rule.target_weights(carried).equals(full.iloc[cut:])
    bare = Panel({"close": close.iloc[cut:]}, "1d")
    assert rule.target_weights(bare).iloc[:tr.VOL].to_numpy().sum() == 0.0   # without the inputs the same cut spends a year warming up
    assert rule.target_weights(carried).iloc[:tr.VOL].to_numpy().sum() > 0.0
    with pytest.raises(ValueError, match="roc=42"):
        TrendReset(roc=42).target_weights(carried)
    for control in ("trend", "mirror"):
        c = TrendReset(roc=21, hold=10, control=control)
        assert c.target_weights(Panel({"close": close, **features(close)}, "1d")).equals(c.target_weights(Panel({"close": close}, "1d")))


def test_the_command_line_knows_the_markets_the_basket_and_the_fractional_costs():
    from qr import cli
    from qr.execution.costs import CostModel

    assert cli._source_of("trend-xnas") == "databento" and cli._source_of("trend-etf") == "tiingo" and cli._source_of("spot") == "binance"
    assert cli._basket_symbols("etf12") == tb.ETF12 and len(tb.ETF12) == 12 and len(cli._basket_symbols("nasdaq31")) == 31
    assert {"above_ma", "trend_ok", "zroc_21", "zprior_21", "zroc_63", "zprior_63"} <= set(FIELDS)
    args = cli.build_parser().parse_args(["gates", "--family", "trend_reset", "--market", "trend-etf", "--basket", "etf12", "--costs", "alpaca_frac",
                                          "--benchmark", "exposure", "--grid", "roc=[21,63]", "--param", "control=trend"])
    frac, whole = cli._costs(args), CostModel.alpaca_zero()
    assert frac.whole_shares is False and whole.whole_shares is True
    assert (frac.fee_bps, frac.half_spread_bps, frac.slippage_bps) == (whole.fee_bps, whole.half_spread_bps, whole.slippage_bps)
    assert len(cli._build_grid(cli._family_class("trend_reset"), args.grid, args.param)) == 2
    assert all(pd.Timestamp(d).weekday() < 5 for d in tb.EARLY_CLOSES)
