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


def test_finra_short_interest_parses_days_to_cover_and_settlement_dates_land_on_business_days():
    from qr.data.short_data import parse_finra_si, si_settlement_days

    text = "accountingYearMonthNumber|symbolCode|issueName|issuerServicesGroupExchangeCode|marketClassCode|currentShortPositionQuantity|previousShortPositionQuantity|stockSplitFlag|averageDailyVolumeQuantity|daysToCoverQuantity|revisionFlag|changePercent|changePreviousNumber|settlementDate\n20250630|A|Agilent Technologies Inc.|A|NYSE|3354818|4110706||1749336|1.92||-18.39|-755888|2025-06-30\n"
    frame = parse_finra_si(text.encode())
    assert frame["days_to_cover"].iloc[0] == 1.92 and frame["settlement_date"].iloc[0] == pd.Timestamp("2025-06-30")
    days = si_settlement_days("2025-06-01", "2025-07-31")
    assert days == ["20250613", "20250630", "20250715", "20250731"]  # 15 June 2025 is a Sunday
