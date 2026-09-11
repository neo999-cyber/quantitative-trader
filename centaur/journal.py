"""Step 5 of the daily workflow - The Journal.

    "Win or lose, you log the trade.  'AI suggested X, I took it because of
     Y, I exited because of Z.'  You feed this journal back to the AI to
     refine future prompts."

Entries are appended to a JSONL file; `feedback_markdown()` produces the
block you paste into the next evening prompt.
"""
from __future__ import annotations

import datetime as dt
import json
import uuid
from dataclasses import dataclass, field, asdict
from pathlib import Path


@dataclass
class JournalEntry:
    id: str
    ticker: str
    direction: str
    opened: str
    entry: float
    stop: float
    target: float
    shares: int
    ai_thesis: str = ""              # what the AI suggested
    why_taken: str = ""              # why the human took it
    signals: list[str] = field(default_factory=list)
    gauntlet: dict | None = None     # rule-by-rule outcome at entry
    regime: str = ""
    closed: str | None = None
    exit_price: float | None = None
    exit_reason: str = ""            # "stop", "target", "time", "discretionary", "news"
    pnl: float | None = None
    r_multiple: float | None = None
    lessons: str = ""
    tags: list[str] = field(default_factory=list)

    @property
    def is_open(self) -> bool:
        return self.closed is None

    @property
    def risk_per_share(self) -> float:
        return abs(self.entry - self.stop)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "JournalEntry":
        known = set(cls.__dataclass_fields__)
        return cls(**{k: v for k, v in d.items() if k in known})


class Journal:
    def __init__(self, path: str | Path = "journal/trades.jsonl"):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    # -- storage --------------------------------------------------------- #
    def entries(self) -> list[JournalEntry]:
        if not self.path.is_file():
            return []
        out: dict[str, JournalEntry] = {}
        with open(self.path) as fh:
            for line in fh:
                line = line.strip()
                if line:
                    e = JournalEntry.from_dict(json.loads(line))
                    out[e.id] = e  # later lines supersede earlier ones for the same id
        return list(out.values())

    def _append(self, e: JournalEntry) -> None:
        with open(self.path, "a") as fh:
            fh.write(json.dumps(e.to_dict()) + "\n")

    def get(self, entry_id: str) -> JournalEntry:
        for e in self.entries():
            if e.id == entry_id or e.id.startswith(entry_id):
                return e
        raise KeyError(f"no journal entry {entry_id}")

    # -- workflow -------------------------------------------------------- #
    def open(self, ticker: str, direction: str, entry: float, stop: float, target: float, shares: int,
             ai_thesis: str = "", why_taken: str = "", signals: list[str] | None = None,
             gauntlet: dict | None = None, regime: str = "", opened: dt.date | None = None,
             tags: list[str] | None = None) -> JournalEntry:
        e = JournalEntry(
            id=uuid.uuid4().hex[:8], ticker=ticker.upper(), direction=direction, opened=str(opened or dt.date.today()),
            entry=entry, stop=stop, target=target, shares=shares, ai_thesis=ai_thesis, why_taken=why_taken,
            signals=list(signals or []), gauntlet=gauntlet, regime=regime, tags=list(tags or []),
        )
        self._append(e)
        return e

    def close(self, entry_id: str, exit_price: float, exit_reason: str, lessons: str = "",
              closed: dt.date | None = None) -> JournalEntry:
        e = self.get(entry_id)
        sign = 1.0 if e.direction == "long" else -1.0
        e.closed = str(closed or dt.date.today())
        e.exit_price = exit_price
        e.exit_reason = exit_reason
        e.pnl = sign * (exit_price - e.entry) * e.shares
        e.r_multiple = sign * (exit_price - e.entry) / e.risk_per_share if e.risk_per_share else None
        e.lessons = lessons
        self._append(e)
        return e

    # -- analytics ------------------------------------------------------- #
    def stats(self) -> dict:
        closed = [e for e in self.entries() if not e.is_open and e.r_multiple is not None]
        if not closed:
            return {"closed_trades": 0}
        rs = [e.r_multiple for e in closed]
        wins = [r for r in rs if r > 0]
        losses = [r for r in rs if r <= 0]
        win_rate = len(wins) / len(rs)
        avg_win = sum(wins) / len(wins) if wins else 0.0
        avg_loss = sum(losses) / len(losses) if losses else 0.0
        expectancy = win_rate * avg_win + (1 - win_rate) * avg_loss
        by_reason: dict[str, int] = {}
        for e in closed:
            by_reason[e.exit_reason or "unspecified"] = by_reason.get(e.exit_reason or "unspecified", 0) + 1
        return {
            "closed_trades": len(closed),
            "open_trades": sum(1 for e in self.entries() if e.is_open),
            "win_rate": win_rate,
            "avg_win_r": avg_win,
            "avg_loss_r": avg_loss,
            "expectancy_r": expectancy,
            "total_pnl": sum(e.pnl or 0.0 for e in closed),
            "total_r": sum(rs),
            "best_r": max(rs),
            "worst_r": min(rs),
            "exit_reasons": by_reason,
        }

    def feedback_markdown(self, last_n: int = 20) -> str:
        """The block you paste back into the AI prompt so it learns from your trades."""
        closed = [e for e in self.entries() if not e.is_open][-last_n:]
        s = self.stats()
        lines = ["## Trade journal feedback", ""]
        if s.get("closed_trades"):
            lines += [
                f"Closed trades: {s['closed_trades']}, win rate {s['win_rate']:.0%}, "
                f"avg win {s['avg_win_r']:+.2f}R, avg loss {s['avg_loss_r']:+.2f}R, expectancy {s['expectancy_r']:+.2f}R per trade.",
                "",
            ]
        for e in closed:
            lines.append(
                f"- {e.opened} {e.ticker} {e.direction}: AI suggested \"{e.ai_thesis or '-'}\"; "
                f"I took it because \"{e.why_taken or '-'}\"; exited {e.closed} on {e.exit_reason or '-'} "
                f"at {e.exit_price} ({e.r_multiple:+.2f}R)."
                + (f" Lesson: {e.lessons}" if e.lessons else "")
            )
        if not closed:
            lines.append("_No closed trades yet._")
        lines += ["", "Use this history to refine tomorrow's screen: favour setups that produced the winners, "
                        "flag the conditions that produced the losers, and say explicitly when a setup resembles a past loser."]
        return "\n".join(lines)
