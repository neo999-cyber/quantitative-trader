import json

import pytest

from qr.validate.trial_log import GENESIS, TrialLog, TrialLogCorrupt, content_hash


@pytest.fixture()
def log(tmp_path):
    return TrialLog(tmp_path / "trial_log.jsonl")


def test_empty_log_verifies_and_counts_nothing(log):
    assert log.verify() == 0
    assert log.trial_count() == 0
    assert log.head() is None


def test_chain_links_records_in_order(log):
    a = log.prereg("tsmom_v1", "mechanism: trends persist")
    b = log.run("tsmom_v1", "tsmom", {"lookback": 90}, "binance_spot_top30")
    c = log.run("tsmom_v1", "tsmom", {"lookback": 120}, "binance_spot_top30")

    assert a.prev_hash == GENESIS
    assert (a.seq, b.seq, c.seq) == (0, 1, 2)
    assert b.prev_hash == a.hash and c.prev_hash == b.hash
    assert log.verify() == 3
    assert log.head().hash == c.hash


def test_prereg_stamps_the_document_hash(log):
    doc = "universe: top 30 by quote volume\nhorizon: 20 days\n"
    rec = log.prereg("tsmom_v1", doc)
    assert rec.payload["doc_sha256"] == content_hash(doc)
    assert rec.payload["doc_chars"] == len(doc)


def test_trial_count_sums_variants_not_lines(log):
    log.run("h", "tsmom", {"lookback": 30}, "u", variants=200)
    log.run("h", "tsmom", {"lookback": 60}, "u")
    log.run("other", "xsmom", {"lookback": 60}, "u", variants=7)

    assert log.trial_count() == 208
    assert log.trial_count(hypothesis_id="h") == 201


def test_gate_records_require_a_known_verdict(log):
    log.gate("h", 3, "single-strategy significance", "pass", {"t_stat": 3.4})
    assert log.records(kind="gate")[0].payload["verdict"] == "PASS"
    with pytest.raises(ValueError):
        log.gate("h", 3, "significance", "probably fine", {})


def test_a_skipped_gate_is_recorded_rather_than_dropped(log):
    """A gate that did not run is the one most easily mistaken for a pass."""
    log.gate("h", 9, "true holdout", "SKIP", {"reason": "no holdout supplied"})
    assert log.records(kind="gate")[0].payload["verdict"] == "SKIP"
    assert log.verify() == 1


def test_editing_a_record_breaks_the_chain(log):
    log.run("h", "tsmom", {"lookback": 30}, "u", {"sharpe": 0.2})
    log.run("h", "tsmom", {"lookback": 60}, "u", {"sharpe": 2.9})
    lines = log.path.read_text().splitlines()
    doctored = json.loads(lines[0])
    doctored["payload"]["metrics"]["sharpe"] = 2.9
    lines[0] = json.dumps(doctored, sort_keys=True, separators=(",", ":"))
    log.path.write_text("\n".join(lines) + "\n")

    with pytest.raises(TrialLogCorrupt, match="do not match its hash"):
        log.verify()


def test_deleting_a_record_breaks_the_chain(log):
    for lb in (30, 60, 90):
        log.run("h", "tsmom", {"lookback": lb}, "u")
    lines = log.path.read_text().splitlines()
    log.path.write_text("\n".join(lines[:1] + lines[2:]) + "\n")

    with pytest.raises(TrialLogCorrupt, match="seq"):
        log.verify()


def test_head_survives_a_log_longer_than_one_read_block(log):
    for lb in range(200):
        log.run("h", "tsmom", {"lookback": lb, "pad": "x" * 200}, "u")
    assert log.path.stat().st_size > 4096
    assert log.head().seq == 199
    assert log.verify() == 200


def test_an_edited_preregistration_is_reported_even_though_the_chain_is_intact(tmp_path):
    """The chain protects the log, not the documents the log points at.

    Appending the outcome to a pre-registration after the run is the obvious
    temptation — and it silently voids the one thing the stamp was for, because
    the document no longer hashes to what was promised. The log itself stays
    perfectly valid, which is exactly why this needs saying out loud.
    """
    prereg = tmp_path / "prereg"
    prereg.mkdir()
    doc = prereg / "h1.md"
    doc.write_text("the prediction, written before the data was seen", encoding="utf-8")

    log = TrialLog(tmp_path / "trial_log.jsonl")
    log.prereg("h1", doc.read_text(encoding="utf-8"))
    assert log.document_drift(prereg) == []

    doc.write_text(doc.read_text(encoding="utf-8") + "\n\nOutcome: it failed.", encoding="utf-8")
    drift = log.document_drift(prereg)
    assert log.verify() > 0  # the chain is still sound
    assert [d["hypothesis"] for d in drift] == ["h1"]
    assert drift[0]["state"] == "CHANGED"


def test_a_missing_document_is_reported_separately_from_a_changed_one(tmp_path):
    """One is a lost file; the other is a different prediction."""
    prereg = tmp_path / "prereg"
    prereg.mkdir()
    (prereg / "h1.md").write_text("a prediction", encoding="utf-8")
    log = TrialLog(tmp_path / "trial_log.jsonl")
    log.prereg("h1", "a prediction")
    (prereg / "h1.md").unlink()
    assert log.document_drift(prereg)[0]["state"] == "MISSING"


def test_an_amendment_before_the_first_run_is_checked_against_the_latest_stamp(tmp_path):
    """Gate 0 polices ordering; drift only asks whether the live text is stamped."""
    prereg = tmp_path / "prereg"
    prereg.mkdir()
    doc = prereg / "h1.md"
    log = TrialLog(tmp_path / "trial_log.jsonl")
    doc.write_text("first draft", encoding="utf-8")
    log.prereg("h1", "first draft")
    doc.write_text("second draft, still before any run", encoding="utf-8")
    log.prereg("h1", "second draft, still before any run")
    assert log.document_drift(prereg) == []


def test_a_hypothesis_registered_inline_has_no_document_to_drift_from(tmp_path):
    """Its wording lives in the record, so the chain already covers it."""
    log = TrialLog(tmp_path / "trial_log.jsonl")
    log.prereg("h1", "typed straight in", source="inline")
    log.prereg("h2", "no source recorded at all")
    assert log.document_drift() == []


# ------------------------------------------------- a record larger than a block


def test_head_reads_a_record_larger_than_one_block(tmp_path):
    """The chain broke the first time a record exceeded 4 KB.

    `head()` walked backwards in blocks and accepted the buffer as soon as it
    held any newline — but the file's own terminating newline satisfies that on
    the first read, so a long record came back as a fragment and the decoder
    raised "Extra data". Nothing was big enough until Stage 2 wrote a mechanism
    memo, and then every append after one failed.
    """
    log = TrialLog(tmp_path / "trial.jsonl")
    log.note("small_v1", "short")
    log.note("huge_v1", "y" * 20_000)

    head = log.head()
    assert head is not None
    assert head.hypothesis_id == "huge_v1"
    assert head.payload["text"] == "y" * 20_000


def test_appending_after_a_large_record_keeps_the_chain(tmp_path):
    log = TrialLog(tmp_path / "trial.jsonl")
    log.note("small_v1", "short")
    log.note("huge_v1", "y" * 50_000)
    log.note("after_v1", "short again")

    assert log.verify() == 3
    assert log.head().hypothesis_id == "after_v1"
    assert [r.seq for r in log] == [0, 1, 2]


def test_head_handles_a_file_that_is_one_very_long_record(tmp_path):
    log = TrialLog(tmp_path / "trial.jsonl")
    log.note("only_v1", "z" * 30_000)
    assert log.head().hypothesis_id == "only_v1"
    assert log.verify() == 1


def test_a_memo_sized_record_round_trips(tmp_path):
    """The real shape that found this: six prose answers and a triage verdict."""
    from qr.research.mechanism import CrudeVersion, MechanismMemo, record, triage

    log = TrialLog(tmp_path / "trial.jsonl")
    prose = "A balanced fund must rebalance to fixed weights. " * 60
    memo = MechanismMemo(
        candidate_id="month_end_v1",
        title="Balanced funds rebalance at month end",
        forced_trader=prose,
        transmission=prose,
        persistence=prose,
        other_side=prose,
        what_breaks_it=prose,
        crude_version=CrudeVersion("calendar_event", {"event": "month_end"}, "positive", prose),
        required_features=("close", "calendar"),
    )
    assert len(memo.as_markdown()) > 4096, "the fixture must exceed one block to be a test"

    record(log, memo, triage(memo))
    record(log, memo, triage(memo))
    assert log.verify() == 2
    assert log.head().payload["memo"]["candidate_id"] == "month_end_v1"


def test_a_void_note_takes_a_miscounted_run_out_of_the_trial_count_but_not_out_of_the_log(tmp_path):
    from qr.validate.trial_log import TrialLog

    log = TrialLog(tmp_path / "log.jsonl")
    ok = log.run("h", "fam", {}, "u", variants=8)
    bad = log.run("h", "fam", {}, "u", variants=4084)
    assert log.trial_count() == 4092
    log.note("h", "seq recorded the session count by mistake", void_seq=bad.seq)
    assert log.trial_count() == 8
    assert log.trial_count("h") == 8
    assert len(list(log.records(kind="run"))) == 2  # nothing deleted
    log.verify()
