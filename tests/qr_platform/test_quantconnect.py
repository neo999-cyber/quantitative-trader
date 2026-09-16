import pandas as pd

from qr.data.quantconnect import daily_equity, statistics


def test_daily_equity_keeps_each_sessions_last_sample_and_assigns_midnight_to_the_session_before():
    ny = "America/New_York"
    stamps = [pd.Timestamp("2024-03-05 09:31", tz=ny), pd.Timestamp("2024-03-05 16:00", tz=ny),
              pd.Timestamp("2024-03-06 00:00", tz=ny), pd.Timestamp("2024-03-06 12:00", tz=ny),
              pd.Timestamp("2024-03-09 00:00", tz=ny)]  # Saturday midnight: Friday's close
    vals = [[int(s.timestamp()), 1000.0, 1000.0, 1000.0, v] for s, v in zip(stamps, [1000.0, 1010.0, 1010.0, 1005.0, 1020.0])]
    result = {"equity_chart": {"chart": {"series": {"Equity": {"values": vals}}}}, "backtest": {"backtest": {"statistics": {"Sharpe Ratio": "0.5"}}}}
    eq = daily_equity(result)
    assert list(eq.index.tz_convert(ny).date.astype(str)) == ["2024-03-05", "2024-03-06", "2024-03-08"]
    assert eq.tolist() == [1010.0, 1005.0, 1020.0]
    assert statistics(result)["Sharpe Ratio"] == "0.5"
