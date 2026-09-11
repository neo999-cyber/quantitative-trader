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
