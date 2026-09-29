"""The results page, and the two promises it makes.

It must work offline — the lake is a directory on a laptop, not a service, and
a page that needs a CDN to render a verdict is a page that stops working the
day the research matters. And it must not lie about its own evidence: if the
hash chain is broken or a pre-registration no longer matches its stamp, that
belongs on the page rather than in a terminal nobody will re-open.
"""
import json
import re

import pytest

from qr.site import GATE_NAMES, collect, integrity, render, write_site
from qr.validate.trial_log import TrialLog


def a_run(hypothesis_id="h1", gates=None, verdict="FAIL", **extra):
    gates = gates or [
        {"gate": 0, "name": "pre-registration", "verdict": "PASS", "detail": "registered", "stats": {}},
        {"gate": 1, "name": "data integrity", "verdict": "WARN", "detail": "a warning", "stats": {"x": 1.5}},
        {"gate": 2, "name": "cost survival", "verdict": "FAIL", "detail": "costs ate it", "stats": {}},
    ]
    return {
        "hypothesis_id": hypothesis_id,
        "verdict": verdict,
        "reason": "stopped at gate 2",
        "gates": gates,
        "context": {"trials": 30, "symbols": ["A", "B"], "start": "2007-01-01", "end": "2022-12-31"},
        "tear_sheet": {"sharpe": 0.678, "net_over_gross": 0.733, "max_drawdown": -0.31},
        **extra,
    }


@pytest.fixture()
def lake(tmp_path):
    reports = tmp_path / "reports"
    reports.mkdir()
    for i, hid in enumerate(["etf_tsmom_v1", "etf_buyhold_v1"]):
        (reports / f"{hid}.json").write_text(json.dumps(a_run(hid)), encoding="utf-8")
    log = TrialLog(tmp_path / "trial_log.jsonl")
    log.prereg("etf_tsmom_v1", "a document", source="inline")
    return tmp_path, reports, log


# ------------------------------------------------------------------ collecting


def test_a_missing_reports_directory_is_empty_rather_than_an_error(tmp_path):
    assert collect(tmp_path / "nope") == []


def test_a_corrupt_report_is_skipped_and_the_rest_still_render(tmp_path):
    """One unreadable file must not cost you the whole record."""
    reports = tmp_path / "reports"
    reports.mkdir()
    (reports / "good.json").write_text(json.dumps(a_run("good")), encoding="utf-8")
    (reports / "bad.json").write_text("{not json", encoding="utf-8")
    runs = collect(reports)
    assert [r["hypothesis_id"] for r in runs] == ["good"]


# -------------------------------------------------------------------- the page


def test_the_page_needs_nothing_from_the_network(lake):
    """The offline promise, asserted rather than intended.

    No script tags, no stylesheet links, no image or font hosts. Everything the
    browser needs is in the file, because the file lives next to a Parquet lake
    on someone's laptop.
    """
    _, reports, log = lake
    page = render(collect(reports), integrity(log))
    assert "<script" not in page.lower()
    assert not re.search(r'(src|href)\s*=\s*["\']https?://', page, re.I)
    assert "@import" not in page


def test_every_family_shows_every_gate_even_the_ones_it_never_reached(lake):
    """A family stopped at gate 2 still shows every gate it never reached.

    Otherwise a short row reads as a different shape rather than as an early
    death, and the one thing this page exists to show is where each family
    stopped.
    """
    _, reports, log = lake
    page = render(collect(reports), integrity(log))
    ladders = re.findall(r'<div class="ladder">(.*?)</div>\s*</td>', page, re.S)
    assert ladders, "no ladders rendered"
    for ladder in ladders:
        assert ladder.count('class="cell') == len(GATE_NAMES) == 12


def test_an_unreached_gate_is_drawn_as_absence_not_as_a_verdict(lake):
    _, reports, log = lake
    page = render(collect(reports), integrity(log))
    assert "not reached" in page
    assert 'class="cell NONE"' in page


def test_the_verdict_and_the_gate_that_produced_it_both_appear(lake):
    _, reports, log = lake
    page = render(collect(reports), integrity(log))
    assert "etf_tsmom_v1" in page and "etf_buyhold_v1" in page
    assert "costs ate it" in page          # the gate's own sentence, verbatim
    assert "stopped at gate 2" in page     # and the headline reason


def test_content_is_escaped_rather_than_interpolated(tmp_path):
    """Gate details are generated text, but the universe is not: the crypto
    lake contains a pair literally named `币安人生USDT`, and a symbol list
    reaches this page. Escape everything; interpolate nothing."""
    reports = tmp_path / "reports"
    reports.mkdir()
    hostile = a_run("h<script>alert(1)</script>")
    hostile["reason"] = "5 < 6 & 7 > 2"
    (reports / "h.json").write_text(json.dumps(hostile), encoding="utf-8")
    page = render(collect(reports), {"chain": "verified", "path": "x"})
    assert "<script>alert(1)</script>" not in page
    assert "&lt;script&gt;" in page
    assert "5 &lt; 6 &amp; 7 &gt; 2" in page


def test_an_empty_record_still_renders_and_says_so():
    page = render([], {"chain": "no trial log", "path": "nowhere"})
    assert "qr families" in page
    assert "<html" in page


# ------------------------------------------------------------------ integrity


def test_the_page_reports_a_verified_chain(lake):
    _, reports, log = lake
    page = render(collect(reports), integrity(log))
    assert "chain verified" in page
    assert "documents match their stamps" in page


def test_a_broken_chain_reaches_the_page(lake):
    """A results page that cannot say its evidence is broken is a brochure."""
    tmp_path, reports, log = lake
    lines = log.path.read_text(encoding="utf-8").splitlines()
    record = json.loads(lines[0])
    record["payload"]["doc_sha256"] = "0" * 64
    log.path.write_text(json.dumps(record) + "\n", encoding="utf-8")

    audit = integrity(TrialLog(log.path))
    assert audit["chain"].startswith("CORRUPT")
    assert "CORRUPT" in render(collect(reports), audit)


def test_a_drifted_preregistration_reaches_the_page(tmp_path):
    prereg = tmp_path / "prereg"
    prereg.mkdir()
    (prereg / "h1.md").write_text("the prediction", encoding="utf-8")
    log = TrialLog(tmp_path / "trial_log.jsonl")
    log.prereg("h1", "the prediction", source=str(prereg / "h1.md"))
    (prereg / "h1.md").write_text("a different prediction", encoding="utf-8")

    audit = integrity(log)
    assert audit["drift"] and audit["drift"][0]["state"] == "CHANGED"
    assert "no longer match" in render([a_run()], audit)


# ----------------------------------------------------------------- the command


def test_write_site_creates_the_file_and_its_parent(lake):
    tmp_path, reports, log = lake
    out = write_site(reports, log, tmp_path / "site" / "index.html")
    assert out.exists() and out.stat().st_size > 2_000
    assert out.read_text(encoding="utf-8").startswith("<!doctype html>")


def test_the_cli_refuses_when_there_is_nothing_to_render(tmp_path, capsys):
    from qr.cli import main

    code = main(["--root", str(tmp_path), "site"])
    assert code == 2
    assert "qr families" in capsys.readouterr().err
