"""The iShares fund-workbook history (`qr/data/etf_flows.py`, 14 October 2026) and the box collector that mirrors it."""
import importlib.util
import json
from pathlib import Path

import pandas as pd
import pytest

from qr.data import etf_flows

XLS = """<?xml version="1.0"?>
<ss:Workbook xmlns:ss="urn:schemas-microsoft-com:office:spreadsheet">
<ss:Worksheet ss:Name="Disclaimers"><ss:Table><ss:Row><ss:Cell><ss:Data ss:Type="String">x</ss:Data></ss:Cell></ss:Row></ss:Table></ss:Worksheet>
<ss:Worksheet ss:Name="Historical"><ss:Table>
<ss:Row><ss:Cell><ss:Data ss:Type="String">As Of</ss:Data></ss:Cell><ss:Cell><ss:Data ss:Type="String">NAV per Share</ss:Data></ss:Cell><ss:Cell><ss:Data ss:Type="String">Ex-Dividends</ss:Data></ss:Cell><ss:Cell><ss:Data ss:Type="String">Shares Outstanding</ss:Data></ss:Cell></ss:Row>
<ss:Row><ss:Cell><ss:Data ss:Type="String">Oct 13, 2026</ss:Data></ss:Cell><ss:Cell><ss:Data ss:Type="Number">47.060864</ss:Data></ss:Cell><ss:Cell><ss:Data ss:Type="String">--</ss:Data></ss:Cell><ss:Cell><ss:Data ss:Type="Number">1420680000</ss:Data></ss:Cell></ss:Row>
<ss:Row><ss:Cell><ss:Data ss:Type="String">Oct 12, 2026</ss:Data></ss:Cell><ss:Cell><ss:Data ss:Type="Number">46.7146</ss:Data></ss:Cell><ss:Cell><ss:Data ss:Type="String">--</ss:Data></ss:Cell><ss:Cell><ss:Data ss:Type="Number">1422080000</ss:Data></ss:Cell></ss:Row>
<ss:Row><ss:Cell><ss:Data ss:Type="String">Oct 09, 2026</ss:Data></ss:Cell><ss:Cell><ss:Data ss:Type="Number">46.6253</ss:Data></ss:Cell><ss:Cell><ss:Data ss:Type="String">--</ss:Data></ss:Cell><ss:Cell><ss:Data ss:Type="Number">1421600000</ss:Data></ss:Cell></ss:Row>
<ss:Row><ss:Cell><ss:Data ss:Type="String">bad date</ss:Data></ss:Cell><ss:Cell><ss:Data ss:Type="Number">1</ss:Data></ss:Cell><ss:Cell><ss:Data ss:Type="String">--</ss:Data></ss:Cell><ss:Cell><ss:Data ss:Type="Number">1</ss:Data></ss:Cell></ss:Row>
</ss:Table></ss:Worksheet>
</ss:Workbook>"""

spec = importlib.util.spec_from_file_location("collect_btc_etf", Path(__file__).resolve().parents[2] / "scripts" / "collect_btc_etf_standalone.py")
standalone = importlib.util.module_from_spec(spec)
spec.loader.exec_module(standalone)


def test_historical_sheet_rows_oldest_first_and_junk_dropped():
    rows = etf_flows.parse_ishares_fund_xls(XLS)
    assert [r["date"] for r in rows] == ["2026-10-09", "2026-10-12", "2026-10-13"]
    assert rows[-1]["shares_outstanding"] == 1420680000 and rows[-1]["nav"] == pytest.approx(47.060864)
    with pytest.raises(etf_flows.FlowSourceError, match="no 'Historical'"):
        etf_flows.parse_ishares_fund_xls(XLS.replace('Name="Historical"', 'Name="Other"'))
    with pytest.raises(etf_flows.FlowSourceError, match="not a SpreadsheetML"):
        etf_flows.parse_ishares_fund_xls("<!DOCTYPE html><html></html>")


def test_the_standalone_parser_agrees_with_the_package():
    assert standalone.parse_ishares_fund_xls(XLS) == etf_flows.parse_ishares_fund_xls(XLS)
    assert standalone.FUNDS == etf_flows.ISHARES_CRYPTO_FUNDS
    assert standalone.ISHARES_FUND_DOWNLOAD == etf_flows.ISHARES_FUND_DOWNLOAD


def test_history_frame_derives_the_flow_at_the_settlement_day_nav(tmp_path):
    d = tmp_path / "etf_flows" / "ishares"
    d.mkdir(parents=True)
    (d / "IBIT_2026-10-13.xls").write_text(XLS.replace("1420680000", "1420000000"))   # an older snapshot
    (d / "IBIT_2026-10-14.xls").write_text(XLS)                                       # the latest wins
    f = etf_flows.ishares_history(tmp_path, "IBIT")
    assert list(f["date"].dt.strftime("%Y-%m-%d")) == ["2026-10-09", "2026-10-12", "2026-10-13"]
    assert pd.isna(f["flow_usd"].iloc[0])
    assert f["flow_usd"].iloc[1] == pytest.approx(480000 * 46.7146)         # +480k shares at the 12 Oct NAV
    assert f["flow_usd"].iloc[2] == pytest.approx(-1400000 * 47.060864)     # −1.4 M shares at the 13 Oct NAV
    assert (f["snapshot"] == "IBIT_2026-10-14.xls").all()
    assert etf_flows.ishares_history(tmp_path, "ETHA").empty


def test_build_writes_the_reference(tmp_path, monkeypatch):
    from qr.config import paths
    from qr.data.lake import Lake

    d = tmp_path / "mirror" / "etf_flows" / "ishares"
    d.mkdir(parents=True)
    (d / "IBIT_2026-10-14.xls").write_text(XLS)
    lake = Lake(paths(tmp_path / "lake"))
    panel = etf_flows.build_crypto_etf_flows(lake, tmp_path / "mirror", funds={"IBIT": 333011, "ETHA": 348532})
    assert set(panel["ticker"]) == {"IBIT"} and len(panel) == 3
    with pytest.raises(etf_flows.FlowSourceError):
        etf_flows.build_crypto_etf_flows(lake, tmp_path / "nowhere")


def test_flow_table_rows_skip_the_summary_lines():
    page = """<html><table><tr><th>Date</th><th>IBIT</th><th>FBTC</th><th>Totals</th></tr>
    <tr><td>Oct 12, 2026</td><td>-66.1</td><td>-3.6</td><td>-68.7</td></tr>
    <tr><td>Oct 09, 2026</td><td>22.6</td><td>-201.3</td><td>-187.5</td></tr>
    <tr><td>Total</td><td>308.5</td><td>x</td><td>-622.5</td></tr></table></html>"""
    rows = standalone.parse_flow_table(page)
    assert len(rows) == 6 and rows[0] == {"date": "2026-10-12", "ticker": "IBIT", "flow_musd": -66.1}
    assert {r["ticker"] for r in rows} == {"IBIT", "FBTC", "Totals"}
    with pytest.raises(ValueError):
        standalone.parse_flow_table("<html>no table</html>")
