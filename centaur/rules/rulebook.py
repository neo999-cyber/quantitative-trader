"""THE VETERAN TRADER'S RULEBOOK - the human filter, as code.

Five rules.  A candidate must pass every one.  If it fails even one rule the
verdict is ABORT.  No exceptions.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field

from ..config import AccountConfig
from ..sizing import position_size, PositionSize
from ..screens.regime import RegimeAssessment, Regime
from .candidate import TradeCandidate, SignalCategory


@dataclass
class RuleResult:
    rule: str
    title: str
    passed: bool
    reason: str
    data: dict = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"rule": self.rule, "title": self.title, "passed": self.passed,
                "reason": self.reason, "data": self.data, "warnings": self.warnings}


# --------------------------------------------------------------------------- #
# RULE 1 - The Asymmetry Check (1:3 minimum)
# --------------------------------------------------------------------------- #
def rule_asymmetry(c: TradeCandidate, cfg: AccountConfig, regime=None) -> RuleResult:
    title = "Asymmetry Check (1:3 minimum)"
    problems = c.validate()
    if problems:
        return RuleResult("R1", title, False, "; ".join(problems))
    rr = c.reward_risk
    data = {"risk_per_share": c.risk_per_share, "reward_per_share": c.reward_per_share,
            "reward_risk": rr, "min_reward_risk": cfg.min_reward_risk}
    if rr < cfg.min_reward_risk:
        return RuleResult("R1", title, False,
                          f"reward:risk is 1:{rr:.2f}, below the 1:{cfg.min_reward_risk:g} minimum "
                          f"(risk ${c.risk_per_share:.2f} vs reward ${c.reward_per_share:.2f})", data)

    # Is there a wall between entry and target that caps the *realistic* reward?
    if c.is_long:
        walls = [lv for lv in c.resistance_levels if c.entry < lv < c.target]
    else:
        walls = [lv for lv in c.support_levels if c.target < lv < c.entry]
    if walls:
        nearest = min(walls, key=lambda lv: abs(lv - c.entry))
        realistic_rr = abs(nearest - c.entry) / c.risk_per_share
        data.update({"nearest_wall": nearest, "realistic_reward_risk": realistic_rr})
        if realistic_rr < cfg.min_reward_risk:
            kind = "resistance" if c.is_long else "support"
            return RuleResult("R1", title, False,
                              f"{kind} at {nearest:.2f} sits between entry and target; realistic reward:risk "
                              f"to that level is only 1:{realistic_rr:.2f}", data)
        return RuleResult("R1", title, True,
                          f"1:{rr:.2f}; {'resistance' if c.is_long else 'support'} at {nearest:.2f} still leaves "
                          f"1:{realistic_rr:.2f} to the first wall", data)
    return RuleResult("R1", title, True, f"reward:risk 1:{rr:.2f} (risk ${c.risk_per_share:.2f}, reward ${c.reward_per_share:.2f})", data)


# --------------------------------------------------------------------------- #
# RULE 2 - The Confluence Matrix (Rule of 3)
# --------------------------------------------------------------------------- #
def rule_confluence(c: TradeCandidate, cfg: AccountConfig, regime=None) -> RuleResult:
    title = "Confluence Matrix (Rule of 3)"
    cats = {s.category for s in c.signals}
    data = {"signals": [s.to_dict() for s in c.signals],
            "categories": sorted(k.value for k in cats),
            "n_signals": len(c.signals), "n_categories": len(cats)}
    if len(c.signals) < cfg.min_signals:
        return RuleResult("R2", title, False,
                          f"only {len(c.signals)} signal(s); need {cfg.min_signals}. One indicator is a coincidence.", data)
    if len(cats) < cfg.min_categories:
        return RuleResult("R2", title, False,
                          f"{len(c.signals)} signals but only {len(cats)} independent categor{'y' if len(cats)==1 else 'ies'} "
                          f"({', '.join(sorted(k.value for k in cats))}); need {cfg.min_categories} non-correlated reasons", data)
    core = {SignalCategory.TECHNICAL, SignalCategory.FUNDAMENTAL, SignalCategory.SENTIMENT_FLOW}
    warnings = []
    if not core.issubset(cats):
        missing = sorted(k.value for k in core - cats)
        warnings.append(f"classic matrix wants technical + fundamental + sentiment/flow; missing {missing}")
    return RuleResult("R2", title, True,
                      f"{len(c.signals)} signals across {len(cats)} categories: {', '.join(sorted(k.value for k in cats))}",
                      data, warnings)


# --------------------------------------------------------------------------- #
# RULE 3 - The Macro Regime Filter (don't fight the tide)
# --------------------------------------------------------------------------- #
def rule_macro(c: TradeCandidate, cfg: AccountConfig, regime: RegimeAssessment | None) -> RuleResult:
    title = "Macro Regime Filter"
    if regime is None:
        return RuleResult("R3", title, False, "no regime assessment supplied - run the regime check first")
    data = {"regime": regime.regime.value, "composite": regime.composite, "confidence": regime.confidence}
    against_tide = (c.is_long and regime.regime == Regime.RISK_OFF) or (not c.is_long and regime.regime == Regime.RISK_ON)
    if against_tide:
        if c.defensive and c.conviction == "high":
            return RuleResult("R3", title, True,
                              f"{regime.regime.value} regime, but candidate is flagged defensive + highest conviction "
                              f"(the only long exception); size conservatively", data,
                              ["fighting the tide - expect a 40-60% lower win rate on this side of the tape"])
        side = "long" if c.is_long else "short"
        return RuleResult("R3", title, False,
                          f"market is {regime.regime.value} (confidence {regime.confidence:.0%}); a {side} here fights the tide. "
                          f"Cash is a position.", data)
    warnings = []
    if regime.regime == Regime.NEUTRAL:
        warnings.append("regime is NEUTRAL/transitional - lower conviction, consider half size")
    return RuleResult("R3", title, True,
                      f"{regime.regime.value} (composite {regime.composite:+.2f}, confidence {regime.confidence:.0%}) "
                      f"does not oppose a {c.direction.value}", data, warnings)


# --------------------------------------------------------------------------- #
# RULE 4 - The Catalyst & Liquidity Check
# --------------------------------------------------------------------------- #
def rule_catalyst_liquidity(c: TradeCandidate, cfg: AccountConfig, regime=None,
                            today: dt.date | None = None, size: PositionSize | None = None) -> RuleResult:
    title = "Catalyst & Liquidity Check"
    today = today or dt.date.today()
    data = {}
    if c.avg_dollar_volume is None:
        return RuleResult("R4", title, False, "average dollar volume unknown - cannot verify liquidity")
    data["avg_dollar_volume"] = c.avg_dollar_volume
    if c.avg_dollar_volume < cfg.min_avg_dollar_volume:
        return RuleResult("R4", title, False,
                          f"zombie stock: ${c.avg_dollar_volume/1e6:,.1f}M/day average dollar volume is below the "
                          f"${cfg.min_avg_dollar_volume/1e6:,.0f}M floor - slippage will eat the edge", data)
    if size is not None:
        share = size.position_value / c.avg_dollar_volume if c.avg_dollar_volume else 0.0
        data["position_pct_of_adv"] = share
        if share > cfg.max_position_pct_of_adv:
            return RuleResult("R4", title, False,
                              f"position (${size.position_value:,.0f}) is {share:.2%} of daily dollar volume; "
                              f"limit is {cfg.max_position_pct_of_adv:.1%}", data)
    if not c.catalyst.strip():
        return RuleResult("R4", title, False, "no catalyst - why is this moving NOW? If you can't say, you don't know", data)
    data["catalyst"] = c.catalyst
    horizon = c.holding_days or cfg.default_holding_days
    if c.next_earnings is not None:
        days_to = (c.next_earnings - today).days
        data["days_to_earnings"] = days_to
        if 0 <= days_to <= horizon + cfg.earnings_buffer_days:
            return RuleResult("R4", title, False,
                              f"earnings on {c.next_earnings} is {days_to} day(s) away, inside the {horizon}-day holding "
                              f"window - a binary event. Exit before it or hedge with options; do not hold through it.", data)
    warnings = [] if c.next_earnings is not None else ["next earnings date unknown - confirm it before entry"]
    return RuleResult("R4", title, True,
                      f"${c.avg_dollar_volume/1e6:,.0f}M/day liquidity; catalyst: {c.catalyst.strip()}"
                      + (f"; earnings {c.next_earnings} is outside the window" if c.next_earnings else ""),
                      data, warnings)


# --------------------------------------------------------------------------- #
# RULE 5 - The Sleep Test (position sizing)
# --------------------------------------------------------------------------- #
def rule_sleep_test(c: TradeCandidate, cfg: AccountConfig, regime=None) -> RuleResult:
    title = "Sleep Test (position sizing)"
    if c.validate():
        return RuleResult("R5", title, False, "invalid entry/stop; cannot size")
    try:
        size = position_size(cfg.equity, cfg.risk_pct, c.entry, c.stop)
    except ValueError as exc:
        return RuleResult("R5", title, False, str(exc))
    data = size.to_dict()
    if size.shares < 1:
        return RuleResult("R5", title, False,
                          f"stop is ${size.risk_per_share:.2f} away but max risk is ${size.max_risk_dollars:.2f}: "
                          f"even one share breaks the {cfg.risk_pct:.0%} rule. Tighten the stop or skip.", data)
    if size.position_pct_of_equity > 1.0:
        return RuleResult("R5", title, False, f"position would need {size.position_pct_of_equity:.0%} of equity (leverage)", data)
    warnings = []
    if size.position_pct_of_equity > 0.25:
        warnings.append(f"position is {size.position_pct_of_equity:.0%} of equity - concentrated; stop is tight relative to price")
    return RuleResult("R5", title, True, size.summary(), data, warnings)


RULES = [rule_asymmetry, rule_confluence, rule_macro, rule_catalyst_liquidity, rule_sleep_test]


@dataclass
class GauntletReport:
    candidate: TradeCandidate
    results: list[RuleResult]
    size: PositionSize | None
    verdict: str          # "TAKE" | "ABORT"

    @property
    def passed(self) -> bool:
        return self.verdict == "TAKE"

    def failed_rules(self) -> list[RuleResult]:
        return [r for r in self.results if not r.passed]

    def to_dict(self) -> dict:
        return {"ticker": self.candidate.ticker, "verdict": self.verdict,
                "results": [r.to_dict() for r in self.results],
                "size": self.size.to_dict() if self.size else None,
                "candidate": self.candidate.to_dict()}

    def render(self) -> str:
        c = self.candidate
        lines = [f"=== GAUNTLET: {c.ticker} {c.direction.value.upper()}  entry {c.entry:.2f}  stop {c.stop:.2f}  target {c.target:.2f} ==="]
        for r in self.results:
            mark = "PASS" if r.passed else "FAIL"
            lines.append(f"[{mark}] {r.rule} {r.title}: {r.reason}")
            for w in r.warnings:
                lines.append(f"       warning: {w}")
        if self.passed and self.size:
            lines.append("")
            lines.append(f"EXECUTION PLAN: buy {self.size.shares} shares @ {c.entry:.2f}; hard stop {c.stop:.2f} "
                         f"(set it in the broker immediately); take partial profits at {c.target:.2f} (1:{c.reward_risk:.1f}).")
        lines.append("")
        lines.append(f"VERDICT: {self.verdict}" + ("" if self.passed else
                     f"  - failed {', '.join(r.rule for r in self.failed_rules())}. Abort. No exceptions."))
        return "\n".join(lines)


def run_gauntlet(candidate: TradeCandidate, cfg: AccountConfig, regime: RegimeAssessment | None,
                 today: dt.date | None = None) -> GauntletReport:
    """Run every rule.  All five must pass for a TAKE verdict."""
    r5 = rule_sleep_test(candidate, cfg)
    size = PositionSize(**r5.data) if r5.passed else None
    results = [
        rule_asymmetry(candidate, cfg),
        rule_confluence(candidate, cfg),
        rule_macro(candidate, cfg, regime),
        rule_catalyst_liquidity(candidate, cfg, today=today, size=size),
        r5,
    ]
    verdict = "TAKE" if all(r.passed for r in results) else "ABORT"
    return GauntletReport(candidate, results, size if verdict == "TAKE" else size, verdict)
