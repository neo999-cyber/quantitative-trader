import io
import zipfile

import pandas as pd

from qr.data.short_data import ftd_periods, parse_ftd, parse_regsho


def test_ftd_zip_parses_in_the_secs_own_layout():
    text = "SETTLEMENT DATE|CUSIP|SYMBOL|QUANTITY (FAILS)|DESCRIPTION|PRICE\n20250602|B38564108|CMBT|51003|CMB.TECH NV (BEL)|8.83\n20250602|D1668R123|MBGAF|332|MERCEDES BENZ GROUP AG COMMON |59.80\n"
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("cnsfails202506a.txt", text)
    frame = parse_ftd(buf.getvalue())
    assert len(frame) == 2 and frame["symbol"].tolist() == ["CMBT", "MBGAF"]
    assert frame["fails"].tolist() == [51003, 332] and frame["settlement_date"].iloc[0] == pd.Timestamp("2025-06-02")


def test_regsho_daily_parses_and_computes_the_short_ratio():
    text = "Date|Symbol|ShortVolume|ShortExemptVolume|TotalVolume|Market\n20250602|A|465874|100|703318|B,Q,N\n20250602|AA|1260393|100|3451219|B,Q,N\n"
    frame = parse_regsho(text.encode())
    assert len(frame) == 2 and abs(frame["short_ratio"].iloc[0] - 465874 / 703318) < 1e-9


def test_ftd_periods_are_two_a_month():
    assert ftd_periods("2024-01", "2024-02") == ["202401a", "202401b", "202402a", "202402b"]
