import hashlib

import pandas as pd
import pytest

from qr.data.binance import (
    BinanceBucket,
    BucketError,
    KLINE_COLUMNS,
    kline_key,
    parse_klines,
    period_of,
    to_utc,
    verify_checksum,
)
from qr.data.fixtures import SyntheticPair, build_mirror, kline_csv, make_klines, zip_bytes


def test_milliseconds_and_microseconds_both_land_on_the_right_day():
    # 2024-11-01 in ms (pre-switch) and 2025-01-01 in us (post-switch).
    out = to_utc(pd.Series([1_730_419_200_000, 1_735_689_600_000_000]))
    assert list(out.strftime("%Y-%m-%d")) == ["2024-11-01", "2025-01-01"]
    assert str(out.tz) == "UTC"


def test_a_history_spanning_the_switch_has_no_jump(bucket, tmp_path):
    mirror = build_mirror(tmp_path / "m2", [SyntheticPair("XUSDT", "2024-12-20", "2025-01-10", seed=7)])
    frame = BinanceBucket(mirror).load_klines("XUSDT")
    spacing = frame.index.to_series().diff().dropna().unique()
    assert list(spacing) == [pd.Timedelta(days=1)]
    assert frame.index[0] == pd.Timestamp("2024-12-20", tz="UTC")
    assert frame.index[-1] == pd.Timestamp("2025-01-10", tz="UTC")


def test_headerless_and_headered_files_parse_the_same():
    frame = make_klines(SyntheticPair("XUSDT", "2024-03-01", "2024-03-05", seed=3))
    bare = parse_klines(kline_csv(frame, header=False))
    headed = parse_klines(kline_csv(frame, header=True))
    pd.testing.assert_frame_equal(bare, headed)
    assert len(bare) == len(frame)


def test_a_header_row_is_never_parsed_as_a_bar():
    frame = make_klines(SyntheticPair("XUSDT", "2024-03-01", "2024-03-05", seed=3))
    parsed = parse_klines(kline_csv(frame, header=True))
    assert parsed.notna().all().all()
    assert len(parsed) == 5


def test_round_trip_preserves_prices_and_volume():
    frame = make_klines(SyntheticPair("XUSDT", "2024-03-01", "2024-03-10", seed=11))
    parsed = parse_klines(kline_csv(frame))
    for col in ("open", "high", "low", "close", "volume", "quote_volume"):
        pd.testing.assert_series_equal(parsed[col], frame[col], check_names=False, check_freq=False, rtol=1e-9)


def test_a_file_with_the_wrong_column_count_is_rejected():
    with pytest.raises(BucketError, match="columns"):
        parse_klines(b"1,2,3\n4,5,6\n")


def test_checksums_are_verified_and_a_tampered_archive_is_caught(tmp_path):
    mirror = build_mirror(tmp_path / "m", [SyntheticPair("XUSDT", "2024-03-01", "2024-03-10", seed=1)])
    key = kline_key("XUSDT", "1d", "2024-03")
    assert verify_checksum(mirror.read(key), mirror.read(key + ".CHECKSUM"))

    tampered = make_klines(SyntheticPair("XUSDT", "2024-03-01", "2024-03-10", seed=999))
    mirror.write(key, zip_bytes("XUSDT-1d-2024-03.csv", kline_csv(tampered)))
    with pytest.raises(BucketError, match="checksum"):
        BinanceBucket(mirror).load_klines("XUSDT")


def test_the_universe_comes_from_the_bucket_and_keeps_delisted_pairs(bucket):
    assert "DEADUSDT" in bucket.symbols()
    instruments = bucket.instruments().set_index("symbol")
    assert instruments.loc["DEADUSDT", "last_data"] < pd.Timestamp("2023-09-01", tz="UTC")
    assert instruments.loc["LATEUSDT", "listed_on"] == pd.Timestamp("2024-01-01", tz="UTC")
    assert instruments.loc["BTCUSDT", "quote_asset"] == "USDT"
    assert instruments.loc["BTCUSDT", "base_asset"] == "BTC"


def test_a_delisted_pair_loads_only_up_to_its_last_bar(bucket):
    frame = bucket.load_klines("DEADUSDT")
    assert frame.index[-1] == pd.Timestamp("2023-08-15", tz="UTC")
    assert frame.index[0] == pd.Timestamp("2023-01-01", tz="UTC")


def test_loading_a_date_range_clips_to_it(bucket):
    frame = bucket.load_klines("BTCUSDT", start="2023-05-10", end="2023-06-20")
    assert frame.index[0] == pd.Timestamp("2023-05-10", tz="UTC")
    assert frame.index[-1] == pd.Timestamp("2023-06-20", tz="UTC")


def test_an_unknown_symbol_loads_empty_rather_than_raising(bucket):
    assert bucket.load_klines("NOPEUSDT").empty


def test_period_parsing_covers_monthly_and_daily_keys():
    assert period_of("data/spot/monthly/klines/BTCUSDT/1d/BTCUSDT-1d-2024-03.zip") == "2024-03"
    assert period_of("data/spot/daily/klines/BTCUSDT/1d/BTCUSDT-1d-2024-03-05.zip") == "2024-03-05"
    with pytest.raises(BucketError):
        period_of("data/spot/monthly/klines/BTCUSDT/1d/index.html")


def test_a_futures_kline_header_is_read_under_the_spot_names():
    """`futures/um` files carry a header with `count`, `taker_buy_volume`,
    `taker_buy_quote_volume`; the fields are the spot fields under other names."""
    from qr.data.binance import parse_klines

    body = (
        b"open_time,open,high,low,close,volume,close_time,quote_volume,count,taker_buy_volume,taker_buy_quote_volume,ignore\n"
        b"1785542400000,62859.90,63126.60,62228.80,62792.30,54738.143,1785628799999,3435251324.17280,1084259,26052.710,1635229029.00870,0\n"
    )
    frame = parse_klines(body, "BTCUSDT")
    assert len(frame) == 1
    assert frame["trades"].iloc[0] == 1084259
    assert frame["taker_buy_base"].iloc[0] == pytest.approx(26052.710)
    assert frame["taker_buy_quote"].iloc[0] == pytest.approx(1635229029.0087)
    assert str(frame.index[0]) == "2026-08-01 00:00:00+00:00"
