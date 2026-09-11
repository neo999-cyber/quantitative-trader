"""Prompt #2 - The Catalyst Synthesizer.

    "Here is the transcript of $XYZ's latest earnings call.  Summarize the
     top 3 bullish and top 3 bearish points.  Then cross-reference this with
     recent insider buying/selling data from the last 30 days."

`summarize_transcript` sends the transcript to Claude and gets back a strict
JSON structure (structured outputs, so no parsing heuristics).  The insider
cross-reference is plain pandas and works without an API key.
"""
from __future__ import annotations

import datetime as dt
import json
import logging
import os
from dataclasses import dataclass, field, asdict

import pandas as pd

log = logging.getLogger(__name__)

DEFAULT_MODEL = os.environ.get("CENTAUR_CLAUDE_MODEL", "claude-opus-5")

SYSTEM_PROMPT = """You are a sell-side equity analyst preparing a pre-trade brief for a discretionary swing trader.
You read earnings-call transcripts and extract what actually moves the stock: guidance changes, margin
trajectory, demand commentary, capital allocation, and anything management is dodging.
Be concrete: quote numbers and the speaker where possible. Never invent figures that are not in the transcript.
Rate the overall tone from -1 (very bearish) to +1 (very bullish)."""

CATALYST_SCHEMA = {
    "type": "object",
    "properties": {
        "ticker": {"type": "string"},
        "bullish": {
            "type": "array",
            "minItems": 3, "maxItems": 3,
            "items": {
                "type": "object",
                "properties": {
                    "point": {"type": "string"},
                    "evidence": {"type": "string"},
                    "category": {"type": "string", "enum": ["guidance", "demand", "margins", "capital_return", "product", "balance_sheet", "other"]},
                },
                "required": ["point", "evidence", "category"],
                "additionalProperties": False,
            },
        },
        "bearish": {
            "type": "array",
            "minItems": 3, "maxItems": 3,
            "items": {
                "type": "object",
                "properties": {
                    "point": {"type": "string"},
                    "evidence": {"type": "string"},
                    "category": {"type": "string", "enum": ["guidance", "demand", "margins", "capital_return", "product", "balance_sheet", "other"]},
                },
                "required": ["point", "evidence", "category"],
                "additionalProperties": False,
            },
        },
        "tone": {"type": "number", "minimum": -1, "maximum": 1},
        "key_catalysts_ahead": {"type": "array", "items": {"type": "string"}},
        "one_line_thesis": {"type": "string"},
    },
    "required": ["ticker", "bullish", "bearish", "tone", "key_catalysts_ahead", "one_line_thesis"],
    "additionalProperties": False,
}


@dataclass
class CatalystSummary:
    ticker: str
    bullish: list[dict]
    bearish: list[dict]
    tone: float
    key_catalysts_ahead: list[str]
    one_line_thesis: str
    model: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict, model: str = "") -> "CatalystSummary":
        return cls(
            ticker=d["ticker"], bullish=d["bullish"], bearish=d["bearish"], tone=float(d["tone"]),
            key_catalysts_ahead=list(d.get("key_catalysts_ahead", [])), one_line_thesis=d["one_line_thesis"],
            model=model,
        )

    def markdown(self) -> str:
        lines = [f"### {self.ticker} earnings call - tone {self.tone:+.2f}", "", f"_{self.one_line_thesis}_", "", "**Bullish**"]
        for b in self.bullish:
            lines.append(f"- [{b['category']}] {b['point']} - _{b['evidence']}_")
        lines += ["", "**Bearish**"]
        for b in self.bearish:
            lines.append(f"- [{b['category']}] {b['point']} - _{b['evidence']}_")
        if self.key_catalysts_ahead:
            lines += ["", "**Catalysts ahead**"] + [f"- {c}" for c in self.key_catalysts_ahead]
        return "\n".join(lines)


def summarize_transcript(ticker: str, transcript: str, model: str = DEFAULT_MODEL, client=None) -> CatalystSummary:
    """Ask Claude for the top-3 bullish / top-3 bearish points as strict JSON.

    Uses streaming (transcripts are long) and server-side refusal fallbacks so
    a policy decline on the primary model is retried on a fallback model
    inside the same call.
    """
    import anthropic

    client = client or anthropic.Anthropic()
    user = (
        f"Ticker: {ticker}\n\nHere is the latest earnings call transcript. Summarize the top 3 bullish and "
        f"top 3 bearish points, rate the tone, and list the dated catalysts management mentioned.\n\n"
        f"<transcript>\n{transcript}\n</transcript>"
    )
    with client.beta.messages.stream(
        model=model,
        max_tokens=16000,
        system=SYSTEM_PROMPT,
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        output_config={"format": {"type": "json_schema", "schema": CATALYST_SCHEMA}},
        messages=[{"role": "user", "content": user}],
    ) as stream:
        response = stream.get_final_message()

    if response.stop_reason == "refusal":
        details = getattr(response, "stop_details", None)
        raise RuntimeError(f"model declined the request: {getattr(details, 'explanation', 'no explanation')}")
    if response.stop_reason == "max_tokens":
        raise RuntimeError("response truncated (max_tokens); shorten the transcript or raise max_tokens")
    text = next(b.text for b in response.content if b.type == "text")
    return CatalystSummary.from_dict(json.loads(text), model=response.model)


# --------------------------------------------------------------------------- #
# Insider transactions (Form 4) - last N days
# --------------------------------------------------------------------------- #
@dataclass
class InsiderSummary:
    ticker: str
    days: int
    buys: int = 0
    sells: int = 0
    buy_value: float = 0.0
    sell_value: float = 0.0
    transactions: list[dict] = field(default_factory=list)

    @property
    def net_value(self) -> float:
        return self.buy_value - self.sell_value

    @property
    def bias(self) -> str:
        if self.buys == 0 and self.sells == 0:
            return "none"
        if self.buy_value > 2 * self.sell_value and self.buys >= 1:
            return "buying"
        if self.sell_value > 2 * self.buy_value and self.sells >= 1:
            return "selling"
        return "mixed"

    def to_dict(self) -> dict:
        d = asdict(self)
        d["net_value"] = self.net_value
        d["bias"] = self.bias
        return d

    def summary(self) -> str:
        if self.bias == "none":
            return f"no insider transactions in the last {self.days} days"
        return (
            f"insiders {self.bias}: {self.buys} buys (${self.buy_value:,.0f}) vs "
            f"{self.sells} sells (${self.sell_value:,.0f}) in the last {self.days} days"
        )


def _classify(text: str) -> str | None:
    t = (text or "").lower()
    if "purchase" in t or "buy" in t:
        return "buy"
    if "sale" in t or "sell" in t or "sold" in t:
        return "sell"
    return None


def summarize_insider_activity(ticker: str, df: pd.DataFrame, days: int = 30,
                               as_of: dt.date | None = None) -> InsiderSummary:
    """Reduce a yfinance-style `insider_transactions` frame to buys vs sells.

    Expected columns (yfinance): Shares, Value, Text, Insider, Position,
    Transaction, Start Date.  Option exercises, gifts and tax withholdings are
    ignored - only open-market purchases and sales count.
    """
    out = InsiderSummary(ticker=ticker, days=days)
    if df is None or df.empty:
        return out
    today = as_of or dt.date.today()
    cutoff = pd.Timestamp(today) - pd.Timedelta(days=days)
    date_col = "Start Date" if "Start Date" in df.columns else df.columns[-1]
    frame = df.copy()
    frame[date_col] = pd.to_datetime(frame[date_col], errors="coerce")
    frame = frame[frame[date_col] >= cutoff]
    for _, row in frame.iterrows():
        kind = _classify(str(row.get("Text", "")) + " " + str(row.get("Transaction", "")))
        if kind is None:
            continue
        value = float(pd.to_numeric(row.get("Value"), errors="coerce") or 0.0)
        shares = float(pd.to_numeric(row.get("Shares"), errors="coerce") or 0.0)
        rec = {
            "date": str(row[date_col].date()) if not pd.isna(row[date_col]) else None,
            "insider": row.get("Insider"), "position": row.get("Position"),
            "kind": kind, "shares": shares, "value": value,
        }
        out.transactions.append(rec)
        if kind == "buy":
            out.buys += 1
            out.buy_value += abs(value)
        else:
            out.sells += 1
            out.sell_value += abs(value)
    return out


def cross_reference(summary: CatalystSummary | None, insiders: InsiderSummary) -> dict:
    """Do the words (call tone) and the money (insider trades) agree?"""
    tone = summary.tone if summary else None
    bias = insiders.bias
    if tone is None:
        verdict, note = "unknown", "no transcript summary available"
    elif bias == "none":
        verdict, note = "unconfirmed", "no insider activity to confirm or contradict the call"
    elif (tone > 0.2 and bias == "buying") or (tone < -0.2 and bias == "selling"):
        verdict, note = "confirms", "insider activity agrees with management's tone"
    elif (tone > 0.2 and bias == "selling") or (tone < -0.2 and bias == "buying"):
        verdict, note = "contradicts", "insiders are trading against management's tone - weigh the money, not the words"
    else:
        verdict, note = "neutral", "no clear agreement or disagreement"
    signals: list[str] = []
    if summary is not None and abs(summary.tone) >= 0.3:
        signals.append(f"fundamental: earnings call tone {summary.tone:+.2f} - {summary.one_line_thesis}")
    if bias in ("buying", "selling"):
        signals.append(f"sentiment_flow: {insiders.summary()}")
    return {"verdict": verdict, "note": note, "tone": tone, "insider_bias": bias, "signals": signals}
