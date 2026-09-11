"""The Evening Brief (AI grind) and the Morning Review (human filter)."""
from __future__ import annotations

import datetime as dt
import json
from dataclasses import dataclass, field
from pathlib import Path

from .config import AccountConfig
from .screens.pattern_matcher import ScanHit, SetupSpec, SetupStats
from .screens.regime import RegimeAssessment
from .screens.options_flow import FlowFlag
from .rules.candidate import TradeCandidate, Signal, Direction


@dataclass
class EveningBrief:
    date: str
    regime: RegimeAssessment
    spec: SetupSpec
    hits: list[ScanHit]
    pooled: SetupStats | None = None
    flow: list[FlowFlag] = field(default_factory=list)
    universe_size: int = 0
    journal_feedback: str = ""
    notes: list[str] = field(default_factory=list)

    def top(self, n: int = 5) -> list[ScanHit]:
        return self.hits[:n]

    def to_dict(self) -> dict:
        return {
            "date": self.date,
            "regime": self.regime.to_dict(),
            "setup": self.spec.describe(),
            "universe_size": self.universe_size,
            "pooled_stats": self.pooled.to_dict() if self.pooled else None,
            "hits": [h.to_dict() for h in self.hits],
            "flow": [f.to_dict() for f in self.flow],
            "notes": self.notes,
        }

    def markdown(self, top_n: int = 5) -> str:
        L = [f"# Evening Brief - {self.date}", ""]
        L += ["## 1. Macro regime (Rule 3 input)", "", "```", self.regime.summary(), "```", ""]
        if self.regime.bearish:
            L += ["> **RISK-OFF.** Longs fight the tide. Sit on hands, trade inversely, or take only the "
                  "highest-conviction defensive setups. Cash is a position.", ""]
        L += [f"## 2. Setup screen: {self.spec.describe()}", "",
              f"Universe: {self.universe_size} tickers. Fired today: {len(self.hits)}.", ""]
        if self.pooled and self.pooled.occurrences:
            p = self.pooled
            L += [f"Pooled history across the universe: {p.summary()}", ""]
        flow_by_ticker: dict[str, list[FlowFlag]] = {}
        for f in self.flow:
            flow_by_ticker.setdefault(f.ticker, []).append(f)
        if self.hits:
            L += ["| # | Ticker | Close | RSI | Streak | RVOL | Move | ADV $M | Hist n | Win | Mean 5d | Edge | Flow |",
                  "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
            for i, h in enumerate(self.top(top_n), 1):
                s = h.stats
                flow = "yes" if h.ticker in flow_by_ticker else ""
                L.append(
                    f"| {i} | **{h.ticker}** | {h.close:.2f} | {h.rsi:.0f} | {h.consecutive_down} | {h.relative_volume:.1f}x | "
                    f"{h.drawdown_pct:+.1%} | {h.avg_dollar_volume/1e6:,.0f} | {s.occurrences} | "
                    f"{'' if not s.occurrences else f'{s.win_rate:.0%}'} | "
                    f"{'' if not s.occurrences else f'{s.mean_return:+.2%}'} | "
                    f"{'' if not s.occurrences else f'{s.edge:+.2%}'} | {flow} |"
                )
            L.append("")
            L += ["### Signals per candidate", ""]
            for h in self.top(top_n):
                L.append(f"- **{h.ticker}**")
                for sig in h.signals:
                    L.append(f"  - {sig}")
                for f in flow_by_ticker.get(h.ticker, [])[:2]:
                    L.append(f"  - sentiment_flow: call volume {f.ratio:.1f}x 30d avg at {f.strike:g} strike exp {f.expiration} ({f.days_to_expiry}d)")
            L.append("")
        else:
            L += ["_Nothing fired today. That is a result, not a failure - do nothing._", ""]
        if self.flow:
            L += ["## 3. Unusual call flow (>=14 DTE filter applied)", "",
                  "| Ticker | Exp | Strike | Vol | 30d avg | Ratio | OI | Note |", "|---|---|---|---|---|---|---|---|"]
            for f in self.flow[:15]:
                L.append(f"| {f.ticker} | {f.expiration} | {f.strike:g} | {f.volume:,.0f} | {f.avg_volume_30d:,.0f} | "
                         f"{f.ratio:.1f}x | {f.open_interest:,.0f} | {f.note} |")
            L.append("")
        L += ["## 4. Morning checklist (the human filter)", "",
              "For each candidate you like, pull up the chart, check the news, fill in a candidate file and run "
              "`centaur gauntlet <file>`. Expect to throw 4 of 5 away.", "",
              "1. **Asymmetry** - where is the logical stop? Is 1:3 realistic before the first wall of resistance?",
              "2. **Confluence** - three independent reasons (technical + fundamental + flow), or wait.",
              "3. **Macro** - see section 1. Fighting the tide costs 40-60% of your win rate.",
              "4. **Catalyst & liquidity** - why now? Earnings inside the holding window? Enough volume to exit?",
              "5. **Sleep test** - `centaur size` gives the share count. The math dictates size, not your gut.", ""]
        if self.notes:
            L += ["## Notes", ""] + [f"- {n}" for n in self.notes] + [""]
        if self.journal_feedback:
            L += ["---", "", self.journal_feedback, ""]
        return "\n".join(L)

    def save(self, briefs_dir: str | Path) -> tuple[Path, Path]:
        d = Path(briefs_dir)
        d.mkdir(parents=True, exist_ok=True)
        md = d / f"{self.date}.md"
        js = d / f"{self.date}.json"
        md.write_text(self.markdown())
        js.write_text(json.dumps(self.to_dict(), indent=2, default=str))
        return md, js


def candidate_template(hit: ScanHit, cfg: AccountConfig, resistance: list[float] | None = None,
                       next_earnings: dt.date | None = None, atr_value: float | None = None) -> TradeCandidate:
    """Pre-fill a candidate file from a scan hit so the human only edits stop/target/catalyst."""
    stop = round(hit.close - 1.5 * atr_value, 2) if atr_value else round(hit.close * 0.96, 2)
    target = round(hit.close + cfg.min_reward_risk * (hit.close - stop), 2)
    return TradeCandidate(
        ticker=hit.ticker, entry=round(hit.close, 2), stop=stop, target=target, direction=Direction.LONG,
        signals=[Signal.parse(s, source="pattern_matcher") for s in hit.signals],
        catalyst="", avg_dollar_volume=hit.avg_dollar_volume,
        resistance_levels=[round(r, 2) for r in (resistance or []) if r > hit.close][:5],
        next_earnings=next_earnings, holding_days=cfg.default_holding_days,
        ai_thesis=f"{hit.consecutive_down}-day capitulation, RSI {hit.rsi:.0f}; historical {hit.stats.summary()}",
        notes="TEMPLATE: verify stop/target on the chart, add the catalyst and any fundamental/flow signals before running the gauntlet.",
    )
