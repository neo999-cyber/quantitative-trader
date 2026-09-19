"""Perp funding and open interest: the dataset twelve kills asked for.

The paths and column names were written from Binance's published layout without
ever meeting the live bucket, and the first real pull confirmed them. One thing
was wrong: `fundingRate` carries epoch integers, `metrics` carries formatted
datetimes, and the ingest died refusing `create_time` as non-numeric. The
metrics fixture therefore defaults to the *string* shape, so a regression
cannot pass by using the convenient format instead of the real one.

The rest is what does not depend on the bucket at all: that a wrong shape fails
loudly quoting what it received, that the daily aggregation means what it
claims, that the join cannot smuggle a perp into the tradable universe, and
that a strategy needing funding refuses a panel without it rather than holding
nothing.
"""
import io
import zipfile

import numpy as np
import pandas as pd
import pytest

from qr.data.binance import BucketError, LocalBucket
from qr.data.funding import (
    FundingBucket,
    attach,
    combine,
    daily_funding,
    daily_open_interest,
    funding_key,
    metrics_key,
    parse_funding,
    parse_metrics,
)
from qr.data.panel import Panel
from qr.strategies.funding import FundingTilt
from qr.validate.selftest import noise_world


def zipped(text: str, name: str = "f.csv") -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr(name, text)
    return buf.getvalue()


def funding_csv(rows: list[tuple[int, float]]) -> str:
    body = "\n".join(f"{t},8,{r}" for t, r in rows)
    return "calc_time,funding_interval_hours,last_funding_rate\n" + body


def metrics_csv(rows: list[tuple[int, float, float]], as_text: bool = True) -> str:
    """Metrics rows. `as_text` is the shape the real bucket actually ships.

    The first live ingest died here: `fundingRate` carries epoch integers like
    the klines, and `metrics` carries formatted datetimes. The fixture defaults
    to the real shape so a regression cannot pass by using the convenient one.
    """
    header = (
        "create_time,symbol,sum_open_interest,sum_open_interest_value,"
        "count_toptrader_long_short_ratio,sum_toptrader_long_short_ratio,"
        "count_long_short_ratio,sum_taker_long_short_vol_ratio\n"
    )

    def stamp(t):
        if not as_text:
            return t
        return pd.Timestamp(t, unit="ms", tz="UTC").strftime("%Y-%m-%d %H:%M:%S")

    body = "\n".join(f"{stamp(t)},BTCUSDT,{oi},{usd},1,1,1,1" for t, oi, usd in rows)
    return header + body


DAY = 86_400_000
H8 = 8 * 3_600_000


# --------------------------------------------------------------------- parsing


def test_funding_parses_to_utc_and_keeps_the_rate():
    payload = zipped(funding_csv([(DAY, 0.0001), (DAY + H8, -0.0002)]))
    frame = parse_funding(payload, "BTCUSDT")
    assert list(frame.columns) == ["funding_rate", "funding_interval_hours"]  # the interval is kept since 2026-09-15
    assert frame.index.tz is not None
    assert frame["funding_rate"].tolist() == [0.0001, -0.0002]


def test_metrics_parses_open_interest_and_ignores_the_columns_we_do_not_read():
    frame = parse_metrics(zipped(metrics_csv([(DAY, 1000.0, 5e7)])))
    assert frame["open_interest"].iloc[0] == 1000.0
    assert frame["open_interest_usd"].iloc[0] == 5e7


def test_a_missing_column_quotes_the_header_that_actually_arrived():
    """The paths and names here have never met the live bucket."""
    payload = zipped("calc_time,funding_interval_hours,rate\n1000,8,0.0001\n")
    with pytest.raises(BucketError) as exc:
        parse_funding(payload)
    assert "last_funding_rate" in str(exc.value)
    assert "'rate'" in str(exc.value) or "rate" in str(exc.value)
    assert "never been checked against the live bucket" in str(exc.value)


def test_a_headerless_file_is_refused_rather_than_guessed_at():
    with pytest.raises(BucketError, match="no header row"):
        parse_funding(zipped("1000,8,0.0001\n"))


def test_an_empty_file_is_empty_rather_than_an_error():
    assert parse_funding(zipped("")).empty
    assert parse_metrics(zipped("")).empty


def test_a_non_numeric_rate_is_refused():
    with pytest.raises(BucketError, match="non-numeric"):
        parse_funding(zipped(funding_csv([(DAY, 0.0001)]).replace("0.0001", "n/a")))


def test_duplicate_timestamps_keep_the_last():
    frame = parse_funding(zipped(funding_csv([(DAY, 0.0001), (DAY, 0.0009)])))
    assert len(frame) == 1
    assert frame["funding_rate"].iloc[0] == 0.0009


# ---------------------------------------------------------------- aggregation


def test_daily_funding_sums_the_settlements_rather_than_averaging_them():
    """What a position paid that day is the sum of what it paid three times."""
    frame = parse_funding(
        zipped(funding_csv([(DAY, 0.0001), (DAY + H8, 0.0001), (DAY + 2 * H8, 0.0001)]))
    )
    daily = daily_funding(frame)
    assert len(daily) == 1
    assert daily.iloc[0] == pytest.approx(0.0003)


def test_a_day_that_settled_twice_is_honestly_cheaper():
    frame = parse_funding(zipped(funding_csv([(DAY, 0.0001), (DAY + H8, 0.0001)])))
    assert daily_funding(frame).iloc[0] == pytest.approx(0.0002)


def test_open_interest_takes_the_last_reading_of_the_day_not_the_sum():
    """A stock, not a flow."""
    frame = parse_metrics(zipped(metrics_csv([(DAY, 100.0, 1e6), (DAY + H8, 140.0, 1.4e6)])))
    daily = daily_open_interest(frame)
    assert len(daily) == 1
    assert daily["open_interest"].iloc[0] == 140.0


def test_combine_produces_one_row_per_day():
    funding = parse_funding(zipped(funding_csv([(DAY, 0.0001), (DAY + H8, 0.0002), (2 * DAY, 0.0003)])))
    metrics = parse_metrics(zipped(metrics_csv([(DAY, 100.0, 1e6), (2 * DAY, 120.0, 1.2e6)])))
    out = combine(funding, metrics)
    assert list(out.index.strftime("%Y-%m-%d")) == ["1970-01-02", "1970-01-03"]
    assert out["funding_rate"].tolist() == [pytest.approx(0.0003), pytest.approx(0.0003)]
    assert out["open_interest"].tolist() == [100.0, 120.0]


# --------------------------------------------------------------------- the join


@pytest.fixture(scope="module")
def panel():
    return noise_world(n_symbols=6, years=2, seed=9)


def _features(panel, symbols=None, value=0.0001):
    return {
        s: pd.DataFrame({"funding_rate": value}, index=panel.index)
        for s in (symbols if symbols is not None else panel.symbols)
    }


def test_the_join_adds_a_field_without_touching_the_price_fields(panel):
    joined = attach(panel, _features(panel))
    assert "funding_rate" in joined.fields
    pd.testing.assert_frame_equal(joined.close, panel.close)
    assert joined.symbols == panel.symbols


def test_a_pair_with_no_perp_carries_nan_rather_than_a_zero(panel):
    """Zero funding is a claim about the market; absence is not."""
    joined = attach(panel, _features(panel, symbols=panel.symbols[:3]))
    funding = joined.get("funding_rate")
    assert funding[panel.symbols[0]].notna().all()
    assert funding[panel.symbols[-1]].isna().all()


def test_the_join_cannot_add_symbols_the_spot_panel_does_not_trade(panel):
    """A feature must never widen the universe to instruments nothing priced."""
    extra = _features(panel)
    extra["PERPONLYUSDT"] = pd.DataFrame({"funding_rate": 0.01}, index=panel.index)
    joined = attach(panel, extra)
    assert joined.symbols == panel.symbols
    assert "PERPONLYUSDT" not in joined.close.columns


def test_a_panel_with_nothing_to_join_is_returned_unchanged(panel):
    assert attach(panel, {}) is panel


# ---------------------------------------------------------------- the strategy


def _funded(panel, seed=0):
    rng = np.random.default_rng(seed)
    return attach(
        panel,
        {
            s: pd.DataFrame(
                {"funding_rate": rng.normal(1e-4, 3e-4, len(panel.index))}, index=panel.index
            )
            for s in panel.symbols
        },
    )


def test_a_funding_strategy_refuses_a_panel_without_funding(panel):
    """Holding nothing and finding nothing must not look the same."""
    with pytest.raises(ValueError, match="no `funding_rate`"):
        FundingTilt().target_weights(panel)


def test_it_holds_exactly_n_long_names(panel):
    weights = FundingTilt(lookback=5, n_long=3, rebalance=7).target_weights(_funded(panel))
    live = weights[weights.abs().sum(axis=1) > 0]
    assert (live > 0).sum(axis=1).max() == 3
    assert live.sum(axis=1).max() == pytest.approx(1.0)


def test_side_selects_the_opposite_end_of_the_ranking(panel):
    funded = _funded(panel)
    low = FundingTilt(lookback=5, n_long=2, rebalance=7, side=1).target_weights(funded)
    high = FundingTilt(lookback=5, n_long=2, rebalance=7, side=-1).target_weights(funded)
    overlap = ((low > 0) & (high > 0)).sum().sum()
    assert overlap < (low > 0).sum().sum() / 2, "the two sides must not pick the same names"


def test_it_buys_the_most_negative_funding_when_side_is_positive(panel):
    """A known answer rather than a plausible one."""
    index = panel.index
    crowded_short, crowded_long = panel.symbols[0], panel.symbols[1]
    features = {s: pd.DataFrame({"funding_rate": 0.0}, index=index) for s in panel.symbols}
    features[crowded_short] = pd.DataFrame({"funding_rate": -0.01}, index=index)
    features[crowded_long] = pd.DataFrame({"funding_rate": 0.01}, index=index)
    funded = attach(panel, features)

    weights = FundingTilt(lookback=2, n_long=1, rebalance=1, side=1).target_weights(funded)
    held = weights[weights.abs().sum(axis=1) > 0]
    assert (held[crowded_short] > 0).all()
    assert (held[crowded_long] == 0).all()


def test_the_floor_keeps_it_flat_when_nobody_is_paying_much(panel):
    """A mechanism about paying to stay has nothing to say where nobody pays."""
    flat = attach(
        panel,
        {s: pd.DataFrame({"funding_rate": 1e-6}, index=panel.index) for s in panel.symbols},
    )
    weights = FundingTilt(lookback=5, n_long=3, rebalance=7, min_abs_funding=1e-3).target_weights(flat)
    assert float(weights.abs().sum().sum()) == 0.0


def test_a_side_that_is_not_a_side_is_refused():
    with pytest.raises(ValueError, match="side must be"):
        FundingTilt(side=0)


# ------------------------------------------------------------------ the bucket


def test_the_bucket_reads_a_mirror_laid_out_the_way_the_puller_writes_it(tmp_path):
    mirror = LocalBucket(tmp_path)
    mirror.write(funding_key("BTCUSDT", "2024-01"), zipped(funding_csv([(DAY, 0.0001)])))
    mirror.write(funding_key("BTCUSDT", "2024-02"), zipped(funding_csv([(2 * DAY, 0.0002)])))
    mirror.write(metrics_key("BTCUSDT", "2024-01-02"), zipped(metrics_csv([(DAY, 100.0, 1e6)])))

    bucket = FundingBucket(mirror)
    assert bucket.symbols() == ["BTCUSDT"]
    assert bucket.periods("BTCUSDT") == ["2024-01", "2024-02"]
    assert len(bucket.load_funding("BTCUSDT")) == 2
    assert len(bucket.load_metrics("BTCUSDT")) == 1


def test_a_symbol_with_no_files_loads_empty_rather_than_raising(tmp_path):
    assert FundingBucket(LocalBucket(tmp_path)).load_funding("NOPEUSDT").empty


# ----------------------------------------------- the timestamp the bucket ships


def test_metrics_timestamps_are_datetime_strings_not_epochs():
    """The first live ingest died on exactly this.

    The paths and the columns were right; `create_time` is a formatted datetime
    while `fundingRate`'s `calc_time` is an epoch integer, and `to_utc` refused
    it as non-numeric.
    """
    frame = parse_metrics(zipped(metrics_csv([(DAY, 100.0, 1e6)])))
    assert len(frame) == 1
    assert frame.index[0] == pd.Timestamp("1970-01-02", tz="UTC")
    assert frame["open_interest"].iloc[0] == 100.0


def test_an_epoch_metrics_file_still_parses():
    """Whichever shape arrives, both are legitimate bucket formats."""
    frame = parse_metrics(zipped(metrics_csv([(DAY, 100.0, 1e6)], as_text=False)))
    assert frame.index[0] == pd.Timestamp("1970-01-02", tz="UTC")


def test_a_timestamp_that_is_neither_is_refused_with_the_value_quoted():
    """A NaT is a row silently dropped from a feature; stopping is better."""
    body = metrics_csv([(DAY, 100.0, 1e6)]).replace("1970-01-02 00:00:00", "not-a-date")
    with pytest.raises(BucketError, match="not-a-date"):
        parse_metrics(zipped(body))


def test_daily_aggregation_survives_the_string_timestamps():
    frame = parse_metrics(zipped(metrics_csv([(DAY, 100.0, 1e6), (DAY + H8, 140.0, 1.4e6)])))
    daily = daily_open_interest(frame)
    assert len(daily) == 1
    assert daily["open_interest"].iloc[0] == 140.0
