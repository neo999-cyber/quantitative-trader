import datetime as dt

import pytest

from centaur.rules.candidate import TradeCandidate, Signal, SignalCategory, Direction
from centaur.rules.rulebook import run_gauntlet, rule_asymmetry, rule_confluence, rule_macro, rule_catalyst_liquidity, rule_sleep_test
from centaur.config import AccountConfig


def good_candidate(**kw) -> TradeCandidate:
    base = dict(
        ticker="AAPL", entry=150.0, stop=145.0, target=165.0,
        signals=[
            Signal(SignalCategory.TECHNICAL, "bouncing off the 200-day moving average"),
            Signal(SignalCategory.FUNDAMENTAL, "massive buyback announced"),
            Signal(SignalCategory.SENTIMENT_FLOW, "unusual institutional call buying"),
        ],
        catalyst="buyback announcement + oversold bounce",
        avg_dollar_volume=5e9, resistance_levels=[170.0, 180.0],
        next_earnings=dt.date(2026, 10, 30), holding_days=10,
    )
    base.update(kw)
    return TradeCandidate(**base)


def test_full_pass_yields_take_and_20_shares(cfg, risk_on, today):
    report = run_gauntlet(good_candidate(), cfg, risk_on, today=today)
    assert report.verdict == "TAKE", report.render()
    assert report.size.shares == 20            # $100 risk / $5 per share
    assert all(r.passed for r in report.results)
    assert "20 shares" in report.render()


def test_rule1_rejects_poor_asymmetry(cfg):
    r = rule_asymmetry(good_candidate(target=157.0), cfg)   # 1:1.4
    assert not r.passed and "below the 1:3" in r.reason


def test_rule1_rejects_resistance_wall(cfg):
    # 1:3 on paper, but massive resistance at 158 caps the realistic reward at 1:1.6
    r = rule_asymmetry(good_candidate(resistance_levels=[158.0]), cfg)
    assert not r.passed and "resistance at 158.00" in r.reason


def test_rule1_short_uses_support_levels(cfg):
    c = good_candidate(direction=Direction.SHORT, entry=150.0, stop=155.0, target=130.0, support_levels=[146.0])
    r = rule_asymmetry(c, cfg)
    assert not r.passed and "support at 146.00" in r.reason


def test_rule1_rejects_inverted_levels(cfg):
    r = rule_asymmetry(good_candidate(stop=155.0), cfg)
    assert not r.passed and "stop must be below entry" in r.reason


def test_rule2_requires_three_independent_categories(cfg):
    one = good_candidate(signals=[Signal(SignalCategory.TECHNICAL, "MA bounce")])
    assert not rule_confluence(one, cfg).passed
    correlated = good_candidate(signals=[Signal(SignalCategory.TECHNICAL, s) for s in ("MA bounce", "RSI < 30", "hammer candle")])
    r = rule_confluence(correlated, cfg)
    assert not r.passed and "only 1 independent categor" in r.reason
    assert rule_confluence(good_candidate(), cfg).passed


def test_rule3_blocks_longs_in_risk_off(cfg, risk_off, risk_on):
    r = rule_macro(good_candidate(), cfg, risk_off)
    assert not r.passed and "fights the tide" in r.reason
    assert rule_macro(good_candidate(), cfg, risk_on).passed
    # shorts are the ones fighting the tide in risk-on
    short = good_candidate(direction=Direction.SHORT, entry=150.0, stop=155.0, target=130.0)
    assert not rule_macro(short, cfg, risk_on).passed
    assert rule_macro(short, cfg, risk_off).passed


def test_rule3_defensive_high_conviction_exception(cfg, risk_off):
    r = rule_macro(good_candidate(defensive=True, conviction="high"), cfg, risk_off)
    assert r.passed and r.warnings


def test_rule3_requires_a_regime(cfg):
    assert not rule_macro(good_candidate(), cfg, None).passed


def test_rule4_zombie_stock(cfg, today):
    r = rule_catalyst_liquidity(good_candidate(avg_dollar_volume=5e6), cfg, today=today)
    assert not r.passed and "zombie" in r.reason


def test_rule4_earnings_inside_holding_window(cfg, today):
    r = rule_catalyst_liquidity(good_candidate(next_earnings=today + dt.timedelta(days=4)), cfg, today=today)
    assert not r.passed and "binary event" in r.reason
    ok = rule_catalyst_liquidity(good_candidate(next_earnings=today + dt.timedelta(days=30)), cfg, today=today)
    assert ok.passed


def test_rule4_requires_catalyst(cfg, today):
    r = rule_catalyst_liquidity(good_candidate(catalyst="  "), cfg, today=today)
    assert not r.passed and "catalyst" in r.reason


def test_rule4_warns_on_unknown_earnings(cfg, today):
    r = rule_catalyst_liquidity(good_candidate(next_earnings=None), cfg, today=today)
    assert r.passed and any("earnings date unknown" in w for w in r.warnings)


def test_rule5_math_dictates_size(cfg):
    r = rule_sleep_test(good_candidate(), cfg)
    assert r.passed and r.data["shares"] == 20 and r.data["actual_risk_dollars"] == 100.0


def test_rule5_rejects_when_one_share_breaks_the_rule():
    tiny = AccountConfig(equity=1_000.0, risk_pct=0.01)   # $10 max risk, $50 stop distance
    r = rule_sleep_test(good_candidate(entry=1000.0, stop=950.0, target=1150.0), tiny)
    assert not r.passed and "even one share" in r.reason


def test_single_failure_aborts(cfg, risk_on, today):
    report = run_gauntlet(good_candidate(target=157.0), cfg, risk_on, today=today)
    assert report.verdict == "ABORT"
    assert [r.rule for r in report.failed_rules()] == ["R1"]
    assert "Abort. No exceptions." in report.render()


def test_config_rejects_reckless_risk():
    with pytest.raises(ValueError):
        AccountConfig(equity=1e4, risk_pct=0.05)
        from centaur.config import load_config
        load_config(risk_pct=0.05)
