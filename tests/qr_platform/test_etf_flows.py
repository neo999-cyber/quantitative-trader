"""The forward collector for ETF creation and redemption flow.

None of these URLs could be reached from the machine the parser was written on,
so what is tested here is everything that does not need the network: that a
plausible payload is read correctly, that an implausible one fails with the
fields it actually saw, and that the record is append-only — which is the
property the whole exercise depends on.
"""
import json

import pandas as pd
import pytest

from qr.data import etf_flows


def screener(**overrides) -> dict:
    """The shape the iShares product screener is documented to return."""
    body = {
        "239710": {
            "localExchangeTicker": "IWM",
            "fundName": "iShares Russell 2000 ETF",
            "sharesOutstanding": {"r": 275_000_000.0, "d": "275,000,000"},
            "totalNetAssets": {"r": 61_000_000_000.0, "d": "61,000,000,000"},
            "navAmount": {"r": 221.82, "d": "221.82"},
        },
        "239726": {
            "localExchangeTicker": "HYG",
            "fundName": "iShares iBoxx High Yield",
            "sharesOutstanding": {"r": 190_000_000.0, "d": "190,000,000"},
            "totalNetAssets": {"r": 15_000_000_000.0, "d": "15,000,000,000"},
            "navAmount": {"r": 78.95, "d": "78.95"},
        },
        "999999": {
            "localExchangeTicker": "IVV",  # not in the basket; must be ignored
            "sharesOutstanding": {"r": 1.0},
        },
    }
    body.update(overrides)
    return body


def test_a_plausible_payload_yields_one_row_per_basket_fund():
    counts = etf_flows.parse_ishares(screener())

    assert {c.ticker for c in counts} == {"IWM", "HYG"}, "a fund outside the basket was kept"
    iwm = next(c for c in counts if c.ticker == "IWM")
    assert iwm.shares_outstanding == 275_000_000.0
    assert iwm.total_net_assets == 61_000_000_000.0
    assert iwm.nav == pytest.approx(221.82)
    assert iwm.source == "ishares_product_screener"
    assert iwm.observed_utc.endswith("+00:00"), "the observation time is the whole point"


def test_a_flat_list_of_records_is_read_too():
    """The endpoint's nesting is one of the things written blind."""
    counts = etf_flows.parse_ishares(list(screener().values()))
    assert {c.ticker for c in counts} == {"IWM", "HYG"}


def test_formatted_strings_are_read_and_placeholders_are_not():
    body = screener()
    body["239710"]["sharesOutstanding"] = "275,000,000"
    body["239710"]["navAmount"] = "$221.82"
    body["239726"]["navAmount"] = "--"

    counts = {c.ticker: c for c in etf_flows.parse_ishares(body)}
    assert counts["IWM"].shares_outstanding == 275_000_000.0
    assert counts["IWM"].nav == pytest.approx(221.82)
    assert counts["HYG"].nav is None, "'--' is not a NAV of zero"


def test_a_payload_without_the_field_says_what_it_did_have():
    """The likeliest failure, and the one that decides whether a run was wasted."""
    body = {"239710": {"localExchangeTicker": "IWM", "fundName": "x", "esgRating": "AA"}}
    with pytest.raises(etf_flows.FlowSourceError) as exc:
        etf_flows.parse_ishares(body)
    assert "IWM" in str(exc.value)
    assert "esgRating" in str(exc.value), "the error must quote the fields that arrived"


def test_a_payload_with_no_funds_at_all_is_a_different_error():
    with pytest.raises(etf_flows.FlowSourceError, match="no fund records"):
        etf_flows.parse_ishares({"message": "forbidden"})


def test_recording_is_append_only(tmp_path):
    """A corrected line would reintroduce exactly the revision problem this avoids."""
    path = tmp_path / "flows.jsonl"
    etf_flows.append(path, etf_flows.parse_ishares(screener()))
    etf_flows.append(path, etf_flows.parse_ishares(screener()))

    lines = path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 4
    assert all(json.loads(line)["ticker"] in {"IWM", "HYG"} for line in lines)


def test_a_flow_is_a_change_and_the_first_observation_has_none(tmp_path):
    path = tmp_path / "flows.jsonl"
    rows = [
        {"observed_utc": "2026-09-14T00:00:00+00:00", "ticker": "IWM",
         "shares_outstanding": 275_000_000.0, "total_net_assets": None, "nav": 200.0,
         "source": "t"},
        {"observed_utc": "2026-09-15T00:00:00+00:00", "ticker": "IWM",
         "shares_outstanding": 276_000_000.0, "total_net_assets": None, "nav": 200.0,
         "source": "t"},
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")

    flow = etf_flows.daily_flow(etf_flows.load(path))
    assert pd.isna(flow["shares_change"].iloc[0]), "day one is unknown, not zero"
    assert flow["shares_change"].iloc[1] == 1_000_000.0
    assert flow["flow_usd"].iloc[1] == 200_000_000.0


def test_an_empty_record_loads_rather_than_raising(tmp_path):
    """Everything downstream must cope with collection not having started."""
    frame = etf_flows.load(tmp_path / "nothing.jsonl")
    assert frame.empty
    assert etf_flows.daily_flow(frame).empty


# ------------------------------------------------------------------- the CLI


def _args(tmp_path, **overrides):
    import types

    body = {"root": str(tmp_path / "lake"), "url": None, "out": None,
            "dump": None, "dry_run": False}
    body.update(overrides)
    return types.SimpleNamespace(**body)


def test_a_missing_share_count_is_derived_from_net_assets_over_nav():
    """What the live screener actually returns: net assets and NAV, no count.

    It does not need one. Net assets *are* shares times NAV by definition, so
    the count is a division rather than an estimate — and which of the two a
    row came from is recorded, because they fail differently.
    """
    body = screener()
    for record in body.values():
        record.pop("sharesOutstanding", None)
    body["239710"]["totalNetAssets"] = {"r": 61_000_000_000.0}
    body["239710"]["navAmount"] = {"r": 200.0}

    iwm = next(c for c in etf_flows.parse_ishares(body) if c.ticker == "IWM")
    assert iwm.shares_outstanding == pytest.approx(305_000_000.0)
    assert iwm.shares_basis == "derived"


def _live(ticker: str, shares: float) -> "etf_flows.ShareCount":
    return etf_flows.ShareCount("t", ticker, shares, None, None, "s", "derived")


def test_the_live_counts_land_on_the_creation_unit():
    """The first real payload, and the number that decides the dataset.

    Every fund's derived count is a multiple of 50,000 shares — the iShares
    creation unit — with a sub-share remainder from dividing net assets by a
    four-decimal NAV. The source is therefore exactly as precise as the process
    it describes: creations happen in whole units, and whole units are what it
    reports.
    """
    counts = [
        _live("EFA", 739_199_999.43), _live("EEM", 464_850_001.75),
        _live("IWM", 271_200_000.46), _live("TLT", 586_899_998.83),
        _live("IEF", 458_700_000.36), _live("LQD", 269_100_001.26),
        _live("HYG", 184_599_999.59),
    ]
    assert etf_flows.share_quantum(counts) == 50_000.0
    assert etf_flows.precision_warning(counts) == "", "the live source is fine"


def test_a_source_too_coarse_to_show_a_day_is_called_out_on_day_one():
    """No amount of collecting fixes a step the source never published below."""
    # Both counts divide by 100,000, so that is the step the source is moving
    # in — the finder reports the coarsest one consistent with the data, which
    # is the conservative reading.
    coarse = [_live("HYG", 184_600_000.0), _live("XYZ", 1_000_000.0)]
    warning = etf_flows.precision_warning(coarse)
    assert "XYZ" in warning and "100,000" in warning
    assert "does not fix" in warning
    # The big fund in the same list is unaffected: 100,000 of 184.6m is 0.05%.
    assert "HYG" not in warning


def test_significant_digits_on_net_assets_was_the_wrong_question():
    """It answered 17 on the live payload — an all-clear for a bad reason.

    The screener publishes a share count; net assets are that count times a
    four-decimal NAV. The trailing digits are arithmetic, not information, so a
    check reading them is measuring its own multiplication.
    """
    shares, nav = 184_600_000.0, 78.7110
    # Nine digits: a clean pass of any "does the source publish enough
    # precision" test, on a figure whose last five digits are multiplication.
    assert etf_flows.significant_digits(shares * nav) > 6
    # One count divides by 100,000, so on its own it cannot distinguish a
    # 50,000 step from a 100,000 one — which is why the check reads the whole
    # set. Either way it is orders of magnitude below the nine digits above.
    assert etf_flows.share_quantum([_live("HYG", shares)]) == 100_000.0


def test_the_dry_run_prints_what_it_would_record(tmp_path, capsys, monkeypatch):
    """The first live run reached the issuer, parsed seven funds, and then died
    formatting them: `table()` takes a frame and was handed a list. The fetch
    and the parse were the risky parts and the printing was the one that broke,
    so it gets a test of its own."""
    from qr.cli import cmd_data_flows_collect
    from qr.data import etf_flows as module

    monkeypatch.setattr(module, "fetch", lambda *a, **k: screener())
    assert cmd_data_flows_collect(_args(tmp_path, dry_run=True)) == 0

    out = capsys.readouterr().out
    assert "IWM" in out and "HYG" in out
    assert "275,000,000.00" in out, "full precision, not the 4-sig-fig table format"
    assert "nothing was written" in out
    assert not (tmp_path / "lake" / "flows").exists(), "--dry-run wrote to the lake"


def test_a_real_run_appends_and_says_how_much_history_there_is(tmp_path, capsys, monkeypatch):
    from qr.cli import cmd_data_flows_collect
    from qr.data import etf_flows as module

    monkeypatch.setattr(module, "fetch", lambda *a, **k: screener())
    assert cmd_data_flows_collect(_args(tmp_path)) == 0

    out = capsys.readouterr().out
    assert "recorded 2 funds" in out
    assert "1 day(s)" in out
    # The warning that matters on day one: a flow is a change between two
    # observations, so the first run records a level and no flow at all.
    assert "One day is not a flow" in out
