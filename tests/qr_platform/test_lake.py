import pandas as pd
import pytest

from qr.config import paths
from qr.data.lake import Lake


@pytest.fixture()
def lake(tmp_path):
    return Lake(paths(tmp_path / "lake"))


@pytest.fixture()
def filled(lake, frames, bucket):
    for symbol, frame in frames.items():
        lake.write_klines(symbol, frame)
    lake.write_reference("instruments", bucket.instruments())
    return lake


def test_writing_records_rows_and_span_in_the_manifest(filled, frames):
    manifest = filled.manifest().set_index("symbol")
    assert manifest.loc["BTCUSDT", "rows"] == len(frames["BTCUSDT"])
    assert manifest.loc["BTCUSDT", "last_ts"] == pd.Timestamp("2024-06-30", tz="UTC")
    assert len(manifest.loc["BTCUSDT", "sha256"]) == 64


def test_reading_back_round_trips_the_bars(filled, frames):
    stored = filled.read_klines("BTCUSDT")
    pd.testing.assert_frame_equal(stored, frames["BTCUSDT"], check_freq=False)


def test_reading_a_range_clips_to_it(filled):
    frame = filled.read_klines("ETHUSDT", start="2023-04-01", end="2023-04-30")
    assert frame.index[0] == pd.Timestamp("2023-04-01", tz="UTC")
    assert frame.index[-1] == pd.Timestamp("2023-04-30", tz="UTC")


def test_load_panel_returns_every_symbol_in_the_lake(filled, frames):
    panel = filled.load_panel()
    assert panel.symbols == sorted(frames)
    assert str(panel.index.tz) == "UTC"


def test_manifest_hash_is_stable_and_changes_with_the_data(filled, frames):
    before = filled.manifest_hash()
    assert before == filled.manifest_hash()
    filled.write_klines("BTCUSDT", frames["BTCUSDT"].iloc[:-1])
    assert filled.manifest_hash() != before


def test_rewriting_a_symbol_replaces_its_manifest_row(filled, frames):
    rows_before = len(filled.manifest())
    filled.write_klines("BTCUSDT", frames["BTCUSDT"].iloc[:-1])
    assert len(filled.manifest()) == rows_before
    assert filled.manifest().set_index("symbol").loc["BTCUSDT", "rows"] == len(frames["BTCUSDT"]) - 1


def test_a_symbol_that_was_never_written_raises(filled):
    with pytest.raises(FileNotFoundError, match="not in the lake"):
        filled.read_klines("NOPEUSDT")


def test_the_lake_is_laid_out_hive_partitioned(filled):
    path = filled.kline_path("BTCUSDT", "1d")
    assert path.parts[-3:] == ("interval=1d", "symbol=BTCUSDT", "data.parquet")
    assert path.exists()
