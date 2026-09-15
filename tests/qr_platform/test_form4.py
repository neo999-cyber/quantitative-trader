"""E5's Form 4 loader: SEC insider-transactions data sets, point-in-time.

Fixtures are built in the bucket's exact TSV layout; no network.
"""
from __future__ import annotations

import io
import zipfile

import pandas as pd
import pytest

from qr.data.form4 import (
    QUALIFYING_RELATIONSHIPS,
    cluster_signals,
    parse_quarter,
    qualifying_purchases,
    with_acceptance_times,
)
from qr.data.pit import AVAILABILITY_COLUMNS, asof_view

SUB = "ACCESSION_NUMBER\tFILING_DATE\tPERIOD_OF_REPORT\tDATE_OF_ORIG_SUB\tNO_SECURITIES_OWNED\tNOT_SUBJECT_SEC16\tFORM3_HOLDINGS_REPORTED\tFORM4_TRANS_REPORTED\tDOCUMENT_TYPE\tISSUERCIK\tISSUERNAME\tISSUERTRADINGSYMBOL\tREMARKS\tAFF10B5ONE\n"
TRANS = "ACCESSION_NUMBER\tNONDERIV_TRANS_SK\tSECURITY_TITLE\tSECURITY_TITLE_FN\tTRANS_DATE\tTRANS_DATE_FN\tDEEMED_EXECUTION_DATE\tDEEMED_EXECUTION_DATE_FN\tTRANS_FORM_TYPE\tTRANS_CODE\tEQUITY_SWAP_INVOLVED\tEQUITY_SWAP_TRANS_CD_FN\tTRANS_TIMELINESS\tTRANS_TIMELINESS_FN\tTRANS_SHARES\tTRANS_SHARES_FN\tTRANS_PRICEPERSHARE\tTRANS_PRICEPERSHARE_FN\tTRANS_ACQUIRED_DISP_CD\tTRANS_ACQUIRED_DISP_CD_FN\tSHRS_OWND_FOLWNG_TRANS\tSHRS_OWND_FOLWNG_TRANS_FN\tVALU_OWND_FOLWNG_TRANS\tVALU_OWND_FOLWNG_TRANS_FN\tDIRECT_INDIRECT_OWNERSHIP\tDIRECT_INDIRECT_OWNERSHIP_FN\tNATURE_OF_OWNERSHIP\tNATURE_OF_OWNERSHIP_FN\n"
OWNER = "ACCESSION_NUMBER\tRPTOWNERCIK\tRPTOWNERNAME\tRPTOWNER_RELATIONSHIP\tRPTOWNER_TITLE\tRPTOWNER_TXT\tRPTOWNER_STREET1\tRPTOWNER_STREET2\tRPTOWNER_CITY\tRPTOWNER_STATE\tRPTOWNER_ZIPCODE\tRPTOWNER_STATE_DESC\tFILE_NUMBER\n"
FOOT = "ACCESSION_NUMBER\tFOOTNOTE_ID\tFOOTNOTE_TXT\n"


def _sub(acc, date, doc, cik, name, sym, b51="0", orig=""):
    return f"{acc}\t{date}\t{date}\t{orig}\t\t\t\t\t{doc}\t{cik}\t{name}\t{sym}\t\t{b51}\n"


def _trans(acc, sk, date, code, shares, price, ad="A", title="Common Stock", di="D", fn=""):
    return (
        f"{acc}\t{sk}\t{title}\t\t{date}\t\t\t\t4\t{code}\t0\t\t\t\t{shares}\t\t{price}\t{fn}\t{ad}\t\t"
        f"{shares}\t\t\t\t{di}\t\t\t\n"
    )


def _owner(acc, cik, name, rel, title=""):
    return f"{acc}\t{cik}\t{name}\t{rel}\t{title}\t\t\t\t\t\t\t\t001-00001\n"


@pytest.fixture()
def quarter(tmp_path):
    sub = SUB + "".join(
        [
            _sub("A-1", "03-MAR-2025", "4", "0000000001", "ACME CORP", "ACME"),
            _sub("A-2", "05-MAR-2025", "4", "0000000001", "ACME CORP", "ACME"),
            _sub("A-3", "06-MAR-2025", "4", "0000000001", "ACME CORP", "ACME", b51="1"),
            _sub("A-4", "09-MAR-2025", "4/A", "0000000001", "ACME CORP", "ACME", orig="03-MAR-2025"),
            _sub("B-1", "04-MAR-2025", "4", "0000000002", "BOLT INC", "BOLT"),
            _sub("B-2", "04-MAR-2025", "4", "0000000002", "BOLT INC", "BOLT"),
        ]
    )
    trans = TRANS + "".join(
        [
            _trans("A-1", 1, "01-MAR-2025", "P", 10000, 25.0),  # officer, $250k open market
            _trans("A-2", 2, "04-MAR-2025", "P", 2000, 25.0),  # director, $50k
            _trans("A-3", 3, "05-MAR-2025", "P", 4000, 25.0),  # 10b5-1 plan: excluded
            _trans("A-4", 4, "01-MAR-2025", "P", 1000, 25.0),  # amendment of A-1: $25k
            _trans("B-1", 5, "03-MAR-2025", "A", 5000, 0.0),  # grant: excluded
            _trans("B-2", 6, "03-MAR-2025", "P", 3000, 10.0),  # ten-percent owner: excluded
        ]
    )
    owners = OWNER + "".join(
        [
            _owner("A-1", "0000000101", "Jane Officer", "Officer", "CEO"),
            _owner("A-2", "0000000102", "John Director", "Director"),
            _owner("A-3", "0000000103", "Kim Officer", "Director,Officer", "CFO"),
            _owner("A-4", "0000000101", "Jane Officer", "Officer", "CEO"),
            _owner("B-1", "0000000201", "Bo Director", "Director"),
            _owner("B-2", "0000000202", "Big Fund LP", "TenPercentOwner"),
        ]
    )
    foot = FOOT + "A-2\tF1\tOpen market purchase.\n"
    path = tmp_path / "2025q1_form345.zip"
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("SUBMISSION.tsv", sub)
        z.writestr("NONDERIV_TRANS.tsv", trans)
        z.writestr("REPORTINGOWNER.tsv", owners)
        z.writestr("FOOTNOTES.tsv", foot)
    return path


def test_parse_quarter_joins_the_three_tables_and_carries_availability_columns(quarter):
    frame = parse_quarter(quarter)
    assert len(frame) == 6
    for column in AVAILABILITY_COLUMNS:
        assert column in frame.columns
    assert frame["published_at"].isna().all()  # no acceptance times yet
    assert frame["event_time"].dt.tz is not None
    row = frame.set_index("accession").loc["A-1"]
    assert row["owner_relationship"] == "Officer" and row["is_officer"] and not row["is_director"]
    assert row["value_usd"] == pytest.approx(250_000.0)
    assert row["document_type"] == "4" and not row["is_amendment"]
    assert frame.set_index("accession").loc["A-4", "is_amendment"]
    assert frame.set_index("accession").loc["A-3", "plan_10b5_1"]
    assert len(set(frame["source_hash"])) == 1 and len(frame["source_hash"].iloc[0]) == 64


def test_acceptance_times_become_published_at_and_missing_ones_stay_missing(quarter):
    frame = parse_quarter(quarter)
    times = {
        "A-1": "2025-03-03T17:10:00.000Z",
        "A-2": "2025-03-05T16:05:00.000Z",
        "A-3": "2025-03-06T09:00:00.000Z",
        "A-4": "2025-03-09T09:00:00.000Z",
        "B-1": "2025-03-04T12:00:00.000Z",
    }
    out = with_acceptance_times(frame, times)
    assert out.set_index("accession").loc["A-1", "published_at"] == pd.Timestamp("2025-03-03T17:10:00Z")
    assert pd.isna(out.set_index("accession").loc["B-2", "published_at"])
    # a filing with no acceptance time is never visible
    visible = asof_view(out, pd.Timestamp("2030-01-01", tz="UTC"), key="accession")
    assert "B-2" not in set(visible["accession"])


def test_qualifying_purchases_keep_open_market_buys_by_officers_and_directors_only(quarter):
    frame = with_acceptance_times(parse_quarter(quarter), {"A-1": "2025-03-03T17:10:00Z", "A-2": "2025-03-05T16:05:00Z",
                                                            "A-3": "2025-03-06T09:00:00Z", "A-4": "2025-03-09T09:00:00Z",
                                                            "B-1": "2025-03-04T12:00:00Z", "B-2": "2025-03-04T12:00:00Z"})
    q = qualifying_purchases(frame, min_each_usd=25_000.0)
    assert sorted(q["accession"]) == ["A-1", "A-2", "A-4"]
    assert QUALIFYING_RELATIONSHIPS == ("Officer", "Director")


def test_cluster_signals_count_distinct_insiders_and_stamp_the_completing_filing(quarter):
    frame = with_acceptance_times(parse_quarter(quarter), {"A-1": "2025-03-03T17:10:00Z", "A-2": "2025-03-05T16:05:00Z",
                                                            "A-3": "2025-03-06T09:00:00Z", "A-4": "2025-03-09T09:00:00Z",
                                                            "B-1": "2025-03-04T12:00:00Z", "B-2": "2025-03-04T12:00:00Z"})
    # as of 8 March the cluster is Jane ($250k) + John ($50k): two insiders, $300k
    q = qualifying_purchases(asof_view(frame, pd.Timestamp("2025-03-08", tz="UTC"), key=["issuer_cik", "owner_cik", "trans_date", "trans_code", "security_title"]), 25_000.0)
    s = cluster_signals(q, window_days=10, min_insiders=2, min_combined_usd=100_000.0)
    assert len(s) == 1
    row = s.iloc[0]
    assert row["symbol"] == "ACME" and row["n_insiders"] == 2 and row["combined_usd"] == pytest.approx(300_000.0)
    assert row["signal_time"] == pd.Timestamp("2025-03-05T16:05:00Z")  # the filing that completed it
    assert row["completing_accession"] == "A-2"
    # as of 10 March the amendment has cut Jane to $25k: $75k combined, no signal
    q2 = qualifying_purchases(asof_view(frame, pd.Timestamp("2025-03-10", tz="UTC"), key=["issuer_cik", "owner_cik", "trans_date", "trans_code", "security_title"]), 25_000.0)
    assert cluster_signals(q2, 10, 2, 100_000.0).empty
    # three insiders required: not met
    assert cluster_signals(q, 10, 3, 100_000.0).empty


def test_one_insider_buying_twice_is_one_insider(quarter):
    frame = with_acceptance_times(parse_quarter(quarter), {"A-1": "2025-03-03T17:10:00Z", "A-2": "2025-03-05T16:05:00Z"})
    q = qualifying_purchases(frame, 25_000.0)
    q = pd.concat([q, q[q["accession"] == "A-1"].assign(accession="A-1b", trans_date=q["trans_date"].iloc[0])])
    only_jane = q[q["owner_cik"] == "0000000101"]
    assert cluster_signals(only_jane, 10, 2, 100_000.0).empty


def test_the_audits_exclusion_rules_each_fire_on_their_own_case(tmp_path):
    """One filing per rule found by the 2025 Q1 labelling audit
    (docs/audit/e5_form4_labels_2025q1.csv), and one clean control."""
    from qr.data.form4 import exclusion_reasons

    cases = [
        ("C-0", "Jane Officer", "Officer", "ACME", "D", "", "", "", "0"),  # clean
        ("C-1", "Jane Officer", "Officer", "NONE", "D", "", "", "", "0"),  # not traded
        ("C-2", "Jane Officer", "Officer", "ACME", "D", "", "", "", "1"),  # 10b5-1 flag
        ("C-3", "EcoR1 Capital, LLC", "Director,TenPercentOwner", "ACME", "I", "See note", "", "", "0"),  # entity
        ("C-4", "Rich Holder", "Director,TenPercentOwner", "ACME", "I", "By Fund", "", "", "0"),  # 10% indirect
        ("C-5", "Jane Officer", "Officer", "ACME", "D", "", "Shares purchased in a private placement under Regulation D.", "", "0"),
        ("C-6", "Jane Officer", "Officer", "ACME", "D", "", "Includes shares held under the ESPP.", "Shares were purchased as part of the Company's ESPP plan.", "0"),
        ("C-7", "Jane Officer", "Officer", "ACME", "D", "", "Includes shares acquired under the employee stock purchase plan.", "", "0"),  # holdings note only: kept
        ("C-8", "Gerber Living Trust", "Director,Officer", "ACME", "D", "", "", "", "0"),  # a trust is a person's
    ]
    frame = pd.DataFrame(
        [
            {
                "accession": acc, "owner_name": owner, "owner_relationship": rel, "symbol": sym,
                "direct_indirect": di, "nature_of_ownership": nature, "footnotes": notes,
                "row_footnotes": row_notes, "plan_10b5_1": flag == "1",
            }
            for acc, owner, rel, sym, di, nature, notes, row_notes, flag in cases
        ]
    )
    reasons = exclusion_reasons(frame).tolist()
    assert reasons == [
        "", "issuer_not_traded", "10b5-1_flag", "entity_reporting_owner", "ten_percent_owner_indirect",
        "not_open_market_footnote", "plan_purchase", "", "",
    ]


def test_a_quarter_without_the_10b5_1_column_parses_with_the_flag_off(quarter, tmp_path):
    # AFF10B5ONE exists only from 2023; 2006q1 has no such column.
    import zipfile as _zf

    src = _zf.ZipFile(quarter)
    out = tmp_path / "2006q1_form345.zip"
    with _zf.ZipFile(out, "w") as z:
        for name in src.namelist():
            text = src.read(name).decode()
            if name == "SUBMISSION.tsv":
                lines = [line.rsplit("\t", 1)[0] for line in text.splitlines()]
                text = "\n".join(lines) + "\n"
            z.writestr(name, text)
    frame = parse_quarter(out)
    assert len(frame) == 6 and not frame["plan_10b5_1"].any()


def test_a_mistyped_transaction_year_is_missing_not_a_crash():
    from qr.data.form4 import _sec_date

    out = _sec_date(pd.Series(["03-AUG-0012", "03-AUG-2012", ""]))
    assert pd.isna(out.iloc[0]) and out.iloc[1] == pd.Timestamp("2012-08-03") and pd.isna(out.iloc[2])
