import numpy as np
import pandas as pd
import pytest

from qr.data.qa import check_klines, report_markdown, summarise


@pytest.fixture()
def clean(frames):
    return frames["BTCUSDT"]


def test_clean_bars_pass_every_check(clean):
    report = check_klines(clean, "BTCUSDT")
    assert report.verdict == "PASS"
    assert report.failures == []
    assert report.rows == len(clean)


def test_a_high_below_the_close_is_a_failure(clean):
    bad = clean.copy()
    bad.iloc[10, bad.columns.get_loc("high")] = bad["low"].iloc[10] * 0.5
    names = {c.name for c in check_klines(bad).failures}
    assert "high_is_highest" in names


def test_a_missing_bar_inside_the_window_is_a_warning(clean):
    gapped = clean.drop(clean.index[20:23])
    report = check_klines(gapped)
    gaps = next(c for c in report.checks if c.name == "calendar_gaps")
    assert gaps.verdict == "WARN"
    assert gaps.count == 3
    assert report.verdict == "WARN"


def test_bars_in_the_wrong_timestamp_unit_break_the_spacing_check(clean):
    broken = clean.copy()
    index = broken.index.to_list()
    index[30] = index[30] + pd.Timedelta(hours=7)
    broken.index = pd.DatetimeIndex(index)
    names = {c.name for c in check_klines(broken).failures}
    assert "bar_spacing" in names


def test_duplicate_timestamps_fail(clean):
    doubled = pd.concat([clean, clean.iloc[[5]]]).sort_index()
    assert "unique_index" in {c.name for c in check_klines(doubled).failures}


def test_a_naive_index_fails_the_timezone_check(clean):
    naive = clean.copy()
    naive.index = naive.index.tz_localize(None)
    assert "timezone_utc" in {c.name for c in check_klines(naive).failures}


def test_zero_volume_bars_are_flagged_as_untradable(clean):
    quiet = clean.copy()
    quiet.iloc[40:45, quiet.columns.get_loc("volume")] = 0.0
    check = next(c for c in check_klines(quiet).checks if c.name == "zero_volume_bars")
    assert (check.verdict, check.count) == ("WARN", 5)


def test_quote_volume_in_the_wrong_units_is_caught(clean):
    wrong = clean.copy()
    wrong["quote_volume"] = wrong["volume"]  # base units where quote units belong
    assert "quote_volume_consistent" in {c.name for c in check_klines(wrong).failures}


def test_taker_volume_above_total_volume_is_caught(clean):
    wrong = clean.copy()
    wrong["taker_buy_base"] = wrong["volume"] * 1.5
    assert "taker_buy_within_volume" in {c.name for c in check_klines(wrong).failures}


def test_a_frozen_feed_is_flagged(clean):
    stuck = clean.copy()
    stuck.iloc[50:65, [stuck.columns.get_loc(c) for c in ("open", "high", "low", "close")]] = 100.0
    check = next(c for c in check_klines(stuck).checks if c.name == "frozen_price")
    assert check.verdict == "WARN"


def test_an_empty_frame_fails_rather_than_passing_vacuously(clean):
    report = check_klines(clean.iloc[:0], "EMPTY")
    assert report.verdict == "FAIL"
    assert [c.name for c in report.failures] == ["non_empty"]


def test_report_renders_a_summary_and_the_offenders(frames):
    reports = [check_klines(f, s) for s, f in sorted(frames.items())]
    text = report_markdown(reports)
    assert "# Data QA report" in text
    assert "BTCUSDT" in text
    assert len(summarise(reports)) == len(frames)
