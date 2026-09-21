import json

import pandas as pd
import pytest

from qr.data.feargreed import CLASSIFICATIONS, LocalFearGreed, as_feature, fetch, normalised, parse


def payload(rows):
    return json.dumps({"name": "Fear and Greed Index", "data": rows}).encode()


@pytest.fixture()
def history():
    # The API returns newest first; timestamps are seconds, UTC.
    return parse(
        payload(
            [
                {"value": "71", "value_classification": "Greed", "timestamp": "1735689600"},
                {"value": "40", "value_classification": "Neutral", "timestamp": "1735603200"},
                {"value": "12", "value_classification": "Extreme Fear", "timestamp": "1735516800"},
            ]
        )
    )


def test_parsing_sorts_oldest_first_and_indexes_by_utc_day(history):
    assert list(history.index.strftime("%Y-%m-%d")) == ["2024-12-30", "2024-12-31", "2025-01-01"]
    assert str(history.index.tz) == "UTC"
    assert list(history["fng_value"]) == [12.0, 40.0, 71.0]


def test_values_are_not_silently_lost_to_index_alignment(history):
    assert history["fng_value"].notna().all()


def test_classifications_are_an_ordered_category(history):
    assert list(history["fng_class"].cat.categories) == CLASSIFICATIONS
    assert history["fng_class"].iloc[0] < history["fng_class"].iloc[-1]


def test_the_feature_is_lagged_by_one_bar_by_default(history):
    index = pd.date_range("2024-12-30", "2025-01-01", freq="D", tz="UTC")
    lagged = as_feature(history, index)
    assert pd.isna(lagged.iloc[0])
    assert list(lagged.iloc[1:]) == [12.0, 40.0]
    assert list(as_feature(history, index, lag=0)) == [12.0, 40.0, 71.0]


def test_a_negative_lag_is_refused(history):
    index = pd.date_range("2024-12-30", "2025-01-01", freq="D", tz="UTC")
    with pytest.raises(ValueError, match="reads the future"):
        as_feature(history, index, lag=-1)


def test_the_lag_is_counted_in_bars_not_publications(history):
    # A panel bar after the last publication must see the newest value, not an
    # extra-stale one: the lag is one bar, not one publication.
    index = pd.date_range("2024-12-30", "2025-01-03", freq="D", tz="UTC")
    assert as_feature(history, index).loc[pd.Timestamp("2025-01-02", tz="UTC")] == 71.0


def test_bars_before_the_index_existed_stay_missing(history):
    index = pd.date_range("2017-01-01", "2017-01-03", freq="D", tz="UTC")
    assert as_feature(history, index).isna().all()


def test_normalisation_maps_the_range_to_minus_one_and_one(history):
    index = pd.date_range("2024-12-31", "2025-01-01", freq="D", tz="UTC")
    values = normalised(history, index, lag=0)
    assert values.iloc[0] == pytest.approx(-0.2)
    assert values.iloc[1] == pytest.approx(0.42)


def test_an_empty_response_parses_to_an_empty_frame():
    frame = parse(payload([]))
    assert frame.empty
    assert str(frame.index.tz) == "UTC"


def test_a_cached_file_reads_the_same_as_the_api(tmp_path, history):
    path = tmp_path / "fng.json"
    path.write_bytes(
        payload([{"value": "50", "value_classification": "Neutral", "timestamp": "1735689600"}])
    )
    frame = fetch(LocalFearGreed(path))
    assert frame["fng_value"].iloc[0] == 50.0
