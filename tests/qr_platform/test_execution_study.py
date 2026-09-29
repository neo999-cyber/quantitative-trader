"""B13 mandate and B16 runner against the fake venue with a fake clock."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from qr.execution.journal import D, Journal
from qr.execution.study import Session, StudyConfig, preview, resume, start
from qr.execution.venues import FakeVenue, Instrument

T0 = datetime(2026, 10, 6, 8, 0, tzinfo=timezone.utc)


class Clock:
    def __init__(self, t=T0):
        self.t = t

    def __call__(self):
        return self.t

    def advance(self, s):
        self.t += timedelta(seconds=s)


def make(tmp_path):
    fake = FakeVenue(name="fake", instruments={"SUIUSDT": Instrument("fake", "SUIUSDT", D("0.0001"), D("0.1"), D("1"), D("5"))},
                     books={"SUIUSDT": (D("0.7000"), D("0.7001"))})
    journal = Journal(tmp_path / "j.sqlite")  # no cash seeded: `start` imports the venue's balance
    config = StudyConfig(account="acct", symbols={"fake": ["SUIUSDT"]}, hours_utc=(7, 15), session_expires_at=(T0 + timedelta(hours=6)).isoformat())
    return fake, journal, config


def test_the_mandate_is_typed_back_and_starts_only_from_a_flat_paused_account(tmp_path):
    fake, journal, config = make(tmp_path)
    lines = []
    found = preview(config, {"fake": fake}, out=lines.append)
    assert found["config_hash"] == config.digest() and "TESTNET" in lines[0]
    assert found["venues"]["fake"]["instruments"][0]["qty_at_cap"] == "14.2"  # $9.99 / 0.7001, step 0.1
    with pytest.raises(PermissionError):
        start(journal, config, {"fake": fake}, "wrong", now=T0)
    fake.pos["SUIUSDT"] = D("1")
    with pytest.raises(PermissionError, match="not flat"):
        start(journal, config, {"fake": fake}, f"{config.digest()} STUDY", now=T0)
    fake.pos.clear()
    start(journal, config, {"fake": fake}, f"{config.digest()} STUDY", now=T0)
    assert journal.mode() == "STUDY"
    assert journal.cash("acct")[("fake", "USDT")] == D("100")  # the venue's balance became the opening cash
    assert journal.db.execute("SELECT COUNT(*) FROM audit WHERE kind = 'mandate'").fetchone()[0] == 1
    with pytest.raises(PermissionError, match="only from PAUSED"):
        start(journal, config, {"fake": fake}, f"{config.digest()} STUDY", now=T0)


def test_a_slot_places_one_post_only_order_and_the_ttl_cancels_it(tmp_path):
    fake, journal, config = make(tmp_path)
    start(journal, config, {"fake": fake}, f"{config.digest()} STUDY", now=T0)
    clock = Clock()
    s = Session(journal, config, {"fake": fake}, now=clock, log=lambda m: None)
    s.tick()
    assert len(fake.orders) == 1 and list(fake.orders.values())[0].side == "BUY"
    s.tick()  # same slot: nothing new
    assert len(fake.orders) == 1
    clock.advance(900)
    s.tick()  # the entry has rested its TTL: cancelled; a new slot places a SELL
    states = [o.status for o in fake.orders.values()]
    assert states.count("CANCELED") == 1 and states.count("NEW") == 1
    assert [o.side for o in fake.orders.values() if o.status == "NEW"] == ["SELL"]
    outcomes = [r[0] for r in journal.db.execute("SELECT outcome FROM study_attempts").fetchall()]
    assert outcomes == ["placed:ACKED", "placed:ACKED"]


def test_a_fill_is_closed_by_a_maker_exit_then_by_the_taker_after_an_hour_from_the_fill(tmp_path):
    fake, journal, config = make(tmp_path)
    start(journal, config, {"fake": fake}, f"{config.digest()} STUDY", now=T0)
    clock = Clock()
    s = Session(journal, config, {"fake": fake}, now=clock, log=lambda m: None)
    fake.fill_on_place = D("14.2")
    s.tick()  # entry fills at once; a maker exit is posted on the other side
    kinds = sorted(w.kind for w in s.working.values())
    assert kinds == ["entry", "exit_maker"]
    assert journal.positions("acct")[("fake", "SUIUSDT")] == D("14.2")
    clock.advance(5)
    s.tick()  # the +5 s mark
    clock.advance(55)
    s.tick()  # the +60 s mark (the registered one)
    row = journal.db.execute("SELECT mid_at_place, mid_after FROM study_marks").fetchone()
    assert row == ("0.70005", "0.70005")
    assert sorted(h for (h,) in journal.db.execute("SELECT horizon_s FROM study_mark_horizons").fetchall()) == [5, 60]
    # the maker exit rests its TTL and is re-posted, until an hour from the fill the taker takes it
    clock.advance(840)
    s.tick()  # a new slot also places the next scheduled entry (SELL, resting)
    assert sorted(w.kind for w in s.working.values()) == ["entry", "entry", "exit_maker"]
    clock.advance(2700)  # 3,600 s after the fill
    s.tick()
    assert journal.positions("acct") == {}
    assert [w.kind for w in s.working.values() if w.filled_at is not None] == []  # only unfilled scheduled entries remain
    kinds = [r[0] for r in journal.db.execute("SELECT action FROM intents").fetchall()]
    assert kinds.count("EXIT") >= 2  # a maker exit (or more) and the taker


def test_the_session_loss_stop_pauses_entries(tmp_path):
    fake, journal, config = make(tmp_path)
    start(journal, config, {"fake": fake}, f"{config.digest()} STUDY", now=T0)
    clock = Clock()
    s = Session(journal, config, {"fake": fake}, now=clock, log=lambda m: None)
    s.open_nav = D("130")  # pretend the session opened $30 above where the account is now
    s.tick()
    assert journal.mode() == "PAUSED"
    assert journal.db.execute("SELECT outcome, detail FROM study_attempts").fetchone()[1] == "session_loss_stop"


def test_close_all_leaves_the_venue_flat_and_the_journal_paused(tmp_path):
    fake, journal, config = make(tmp_path)
    start(journal, config, {"fake": fake}, f"{config.digest()} STUDY", now=T0)
    clock = Clock()
    s = Session(journal, config, {"fake": fake}, now=clock, log=lambda m: None)
    fake.fill_on_place = D("14.2")
    s.tick()
    problems = s.close_all()
    assert problems == [] and fake.positions() == {} and journal.mode() == "PAUSED"
    assert resume(journal, {"fake": fake}, "acct") == []


def test_resume_refuses_when_the_venue_and_the_journal_disagree(tmp_path):
    fake, journal, config = make(tmp_path)
    journal.cash_event("dep", "acct", "fake", "USDT", "100", "transfer", T0.isoformat())
    fake.pos["SUIUSDT"] = D("3")  # a manual trade outside the harness
    assert resume(journal, {"fake": fake}, "acct") == ["fake SUIUSDT: venue 3, journal 0"]


def test_a_new_session_rebuilds_its_working_set_from_the_journal(tmp_path):
    fake, journal, config = make(tmp_path)
    start(journal, config, {"fake": fake}, f"{config.digest()} STUDY", now=T0)
    clock = Clock()
    s = Session(journal, config, {"fake": fake}, now=clock, log=lambda m: None)
    s.tick()  # one resting entry
    cid = next(iter(s.working))
    fake._exec(fake.orders[cid], D("14.2"))  # it fills while no session is running
    fresh = Session(journal, config, {"fake": fake}, now=clock, log=lambda m: None)
    assert cid in fresh.working and fresh.working[cid].kind == "entry"
    problems = fresh.close_all()  # reconciles the fill, closes the position, verifies flat
    assert problems == [] and fake.positions() == {} and journal.positions("acct") == {}


def test_a_reposted_exit_gets_a_fresh_client_id(tmp_path):
    fake, journal, config = make(tmp_path)
    start(journal, config, {"fake": fake}, f"{config.digest()} STUDY", now=T0)
    clock = Clock()
    s = Session(journal, config, {"fake": fake}, now=clock, log=lambda m: None)
    fake.fill_on_place = D("14.2")
    s.tick()  # entry filled, maker exit posted
    for _ in range(3):  # three TTLs: the maker exit is cancelled and re-posted each time, at a moving price
        clock.advance(900)
        fake.books["SUIUSDT"] = (fake.books["SUIUSDT"][0] + D("0.0001"), fake.books["SUIUSDT"][1] + D("0.0001"))
        s.tick()
    exits = journal.db.execute("SELECT COUNT(*) FROM intents WHERE action = 'EXIT'").fetchone()[0]
    errors = journal.db.execute("SELECT COUNT(*) FROM audit WHERE kind = 'error'").fetchone()[0]
    assert exits >= 3 and errors == 0
