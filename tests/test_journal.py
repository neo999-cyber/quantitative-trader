from centaur.journal import Journal


def test_open_close_stats_feedback(tmp_path):
    j = Journal(tmp_path / "t.jsonl")
    a = j.open("AAPL", "long", 150, 145, 165, 20, ai_thesis="capitulation bounce", why_taken="3 signals, risk-on")
    b = j.open("MSFT", "long", 400, 390, 430, 10)
    assert len(j.entries()) == 2 and all(e.is_open for e in j.entries())
    j.close(a.id, 165, "target", lessons="partial at 1:3 worked")
    j.close(b.id, 390, "stop")
    entries = {e.ticker: e for e in j.entries()}
    assert entries["AAPL"].r_multiple == 3.0 and entries["AAPL"].pnl == 300.0
    assert entries["MSFT"].r_multiple == -1.0 and entries["MSFT"].pnl == -100.0
    s = j.stats()
    assert s["closed_trades"] == 2 and s["win_rate"] == 0.5 and abs(s["expectancy_r"] - 1.0) < 1e-9
    fb = j.feedback_markdown()
    assert "capitulation bounce" in fb and "+3.00R" in fb and "partial at 1:3 worked" in fb


def test_short_pnl_sign(tmp_path):
    j = Journal(tmp_path / "t.jsonl")
    e = j.open("TSLA", "short", 200, 210, 170, 5)
    e = j.close(e.id, 180, "target")
    assert e.pnl == 100.0 and e.r_multiple == 2.0
