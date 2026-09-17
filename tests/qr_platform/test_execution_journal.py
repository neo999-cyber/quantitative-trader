"""B10 journal and B12 limits for the maker-fill study's stage 1 (docs/27)."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from qr.execution.journal import D, Intent, Journal, NavUncertain
from qr.execution.limits import StudyPolicy, check_entry, check_exit, gross_open_usd

NOW = datetime(2026, 10, 6, 10, 0, tzinfo=timezone.utc)
LATER = (NOW + timedelta(minutes=15)).isoformat()


def intent(symbol="SUIUSDT", side="BUY", qty="10", limit="0.7", action="ENTRY", signal="s1", venue="binance", **kw):
    return Intent(
        account="acct", venue=venue, symbol=symbol, side=side, qty=qty, limit=limit,
        post_only=kw.get("post_only", action == "ENTRY"), reduce_only=kw.get("reduce_only", action == "EXIT"),
        strategy_version="stage1-v1", signal_id=signal, action=action, expires_at=kw.get("expires_at", LATER),
    )


@pytest.fixture()
def journal(tmp_path):
    j = Journal(tmp_path / "journal.sqlite")
    j.set_mode("STUDY", "test mandate")
    j.cash_event("dep-1", "acct", "binance", "USDT", "100", "transfer", NOW.isoformat())
    j.cash_event("dep-2", "acct", "bybit", "USDT", "100", "transfer", NOW.isoformat())
    return j


@pytest.fixture()
def policy():
    return StudyPolicy(eligible=("binance:SUIUSDT", "binance:DOGEUSDT", "bybit:SUIUSDT"))


# -- B10 ---------------------------------------------------------------------


def test_the_journal_opens_paused_whatever_it_was_closed_as(tmp_path):
    j = Journal(tmp_path / "j.sqlite")
    assert j.mode() == "PAUSED"
    j.set_mode("STUDY", "mandate")
    j.close()
    assert Journal(tmp_path / "j.sqlite").mode() == "PAUSED"


def test_staging_is_idempotent_and_refuses_a_changed_payload(journal):
    i = intent()
    assert journal.stage(i) == "STAGED"
    assert journal.stage(i) == "STAGED"  # a retry is a no-op
    with pytest.raises(ValueError, match="different payload"):
        journal.stage(intent(limit="0.71"))  # same client id (same signal/side/action), different price
    assert journal.reserved("acct") == (D(0), D("7.0"))


def test_unknown_leaves_only_by_reconciliation_and_never_by_a_resend(journal):
    i = intent()
    journal.stage(i)
    journal.transition(i.client_id, "SUBMITTING", "sending")
    journal.transition(i.client_id, "UNKNOWN", "timeout after 5s; request may have reached the venue")
    with pytest.raises(ValueError, match="reconciliation"):
        journal.transition(i.client_id, "ACKED", "resent and acked")
    with pytest.raises(ValueError, match="not a permitted transition"):
        journal.transition(i.client_id, "SUBMITTING", "reconciled: resend")
    journal.transition(i.client_id, "ACKED", "reconciled: venue lists order 123 open", venue_order_id="123")
    assert journal.state(i.client_id) == "ACKED"


def test_an_execution_posts_once_and_a_conflicting_duplicate_is_an_error(journal):
    i = intent()
    journal.stage(i)
    journal.transition(i.client_id, "SUBMITTING", "sending")
    journal.transition(i.client_id, "ACKED", "ack")
    assert journal.execution("x1", i.client_id, "4", "0.7", "0.0006", "USDT", NOW.isoformat())
    assert not journal.execution("x1", i.client_id, "4", "0.7", "0.0006", "USDT", NOW.isoformat())  # replayed callback
    with pytest.raises(ValueError, match="different content"):
        journal.execution("x1", i.client_id, "5", "0.7", "0.0006", "USDT", NOW.isoformat())
    assert journal.positions("acct") == {("binance", "SUIUSDT"): D("4")}
    assert journal.cash("acct")[("binance", "USDT")] == D("100") - D("2.8") - D("0.0006")
    with pytest.raises(ValueError, match="overfills"):
        journal.execution("x2", i.client_id, "7", "0.7", "0", "USDT", NOW.isoformat())


def test_a_partial_fill_then_cancel_releases_only_the_reservation_and_replay_reproduces_state(journal, tmp_path):
    i = intent()
    journal.stage(i)
    journal.transition(i.client_id, "SUBMITTING", "sending")
    journal.transition(i.client_id, "PARTIAL", "fill 4")
    journal.execution("x1", i.client_id, "4", "0.7", "0", "USDT", NOW.isoformat())
    journal.transition(i.client_id, "CANCEL_REQUESTED", "cancel sent")
    assert journal.reserved("acct")[1] == D("7.0")  # still working: nothing released
    journal.transition(i.client_id, "CANCELLED", "venue confirms cancel, filled 4 of 10")
    assert journal.reserved("acct")[1] == D(0)
    cash_before, pos_before = journal.cash("acct"), journal.positions("acct")
    journal.rebuild()
    assert journal.cash("acct") == cash_before and journal.positions("acct") == pos_before


def test_nav_is_uncertain_without_a_valid_mark_and_the_holding_is_kept(journal):
    i = intent()
    journal.stage(i)
    journal.transition(i.client_id, "SUBMITTING", "s")
    journal.transition(i.client_id, "FILLED", "f")
    journal.execution("x1", i.client_id, "10", "0.7", "0", "USDT", NOW.isoformat())
    with pytest.raises(NavUncertain):
        journal.nav("acct")
    assert journal.positions("acct")[("binance", "SUIUSDT")] == D("10")  # not liquidated
    journal.mark("binance", "SUIUSDT", "0.75", NOW.isoformat())
    assert journal.nav("acct", now=NOW) == D("100") - D("7") + D("100") + D("7.5")
    with pytest.raises(NavUncertain, match="old"):
        journal.nav("acct", max_mark_age_s=30, now=NOW + timedelta(minutes=5))


# -- B12 ---------------------------------------------------------------------


def test_entry_limits_refuse_what_the_study_forbids(journal, policy):
    ok = intent()
    assert check_entry(journal, ok, policy, D("200"), NOW) == []
    assert "order_over_cap" in check_entry(journal, intent(qty="20"), policy, D("200"), NOW)  # $14
    assert "symbol_not_eligible" in check_entry(journal, intent(symbol="BTCUSDT"), policy, D("200"), NOW)
    assert "entry_must_be_post_only" in check_entry(journal, intent(post_only=False), policy, D("200"), NOW)
    assert "intent_expired" in check_entry(journal, intent(expires_at=NOW.isoformat()), policy, D("200"), NOW)
    journal.pause("operator")
    assert "mode_paused" in check_entry(journal, ok, policy, D("200"), NOW)


def test_pending_orders_count_toward_the_gross_cap_across_venues(journal):
    # $50 cap: seven $7 orders is $49 pending; the eighth is refused, on either venue
    policy = StudyPolicy(eligible=("binance:SUIUSDT", "binance:DOGEUSDT", "bybit:SUIUSDT"), max_open_per_symbol=4)
    for k in range(7):
        i = intent(signal=f"s{k}", symbol="SUIUSDT" if k % 2 else "DOGEUSDT", venue="binance")
        assert check_entry(journal, i, policy, D("200"), NOW) == [], k
        journal.stage(i)
    assert gross_open_usd(journal, "acct", policy, NOW) == D("49.0")
    assert "gross_cap" in check_entry(journal, intent(signal="s9", venue="bybit"), policy, D("200"), NOW)
    strict = StudyPolicy(eligible=policy.eligible, max_open_per_symbol=1)
    assert "entry_already_working" in check_entry(journal, intent(signal="s99", symbol="SUIUSDT"), strict, D("200"), NOW)


def test_no_leverage_and_the_session_loss_stop(journal, policy):
    small = intent(qty="10", limit="0.7", venue="bybit", symbol="SUIUSDT")
    journal.cash_event("w-1", "acct", "bybit", "USDT", "-95", "transfer", NOW.isoformat())
    assert "insufficient_unreserved_cash" not in check_entry(journal, small, policy, D("200"), NOW)  # binance cash still counts at 1x
    assert "session_loss_stop" in check_entry(journal, small, policy, D("140"), NOW)  # NAV 105 <= 140 - 25


def test_exits_must_reduce_and_cannot_double_close(journal, policy):
    i = intent()
    journal.stage(i)
    journal.transition(i.client_id, "SUBMITTING", "s")
    journal.transition(i.client_id, "FILLED", "f")
    journal.execution("x1", i.client_id, "10", "0.7", "0", "USDT", NOW.isoformat())
    assert "exit_does_not_reduce" in check_exit(journal, intent(side="BUY", action="EXIT", signal="e1"), policy)
    full = intent(side="SELL", action="EXIT", signal="e1", qty="10")
    assert check_exit(journal, full, policy) == []
    journal.stage(full)
    again = intent(side="SELL", action="EXIT", signal="e2", qty="1")
    assert "exit_exceeds_unclaimed_holding" in check_exit(journal, again, policy)
    journal.pause("operator")
    assert check_exit(journal, intent(side="SELL", action="EXIT", signal="e3", qty="10", reduce_only=True), policy) == ["exit_exceeds_unclaimed_holding"]
    assert "exit_must_be_reduce_only" in check_exit(journal, intent(side="SELL", action="EXIT", signal="e4", reduce_only=False), policy)
