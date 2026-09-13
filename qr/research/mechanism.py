"""Stage 2 of `docs/10_NEXT.md`: mechanism before code.

The nine families that failed were all *patterns* — "things that went up keep
going up". Nobody pays for a pattern. The ideas that survive are transfers:
someone is **forced to trade** regardless of price, and somebody collects. So
before anything runs, a one-page memo answers five questions:

1. Who is forced to trade, and why?
2. Why will they keep being forced? *(If the answer is "momentum works", there
   is no mechanism. Kill it here.)*
3. Who is on the other side today, and why has the effect not gone?
4. What would make it stop working?
5. Crudest possible version, and its gross return before costs.

Most candidates die at (2), on paper, for free. That is the point of the stage:
it is the cheapest filter in the funnel and the only one that looks at *why*
rather than at a number.

## Why the harness does not trust the memo

Claude writes the memo, and Claude also answers "is this a real mechanism?",
which is a conflict of interest with a well-known direction. A model asked to
generate eight candidates and judge them will judge its own work kindly — not
dishonestly, just optimistically, the same way a person does.

So `triage()` re-decides, deterministically, from the memo's structured fields
and without reference to the model's own verdict:

* **A crude version that compiles to one of the nine failed families is
  killed.** If the best expression of "index funds must rebalance" is
  `CrossSectionalMomentum`, then the idea is cross-sectional momentum, which
  has been tested, which failed, and which re-testing would cost the trial
  count for nothing.
* **A memo whose features are not in the lake is `blocked`, not `killed`.**
  Those are different and the difference is the whole value of a blocked
  night's work: a wrong idea should be forgotten, a blocked one should be
  parked with the name of the dataset that unblocks it.
* **A memo that cannot name a payer is killed**, whatever it says about
  itself, because that is question 1 and everything else rests on it.

The model may also kill its own candidate, and when it does that is honoured
immediately — a self-kill is the outcome this stage is *trying* to produce, and
there is no incentive to overturn one.

## What it may propose

Only primitives that exist. A memo does not write code: it names a family from
`PRIMITIVES` and the parameters for the crudest version of itself, which
Stage 3 then runs in the sandbox. That constraint is doing real work — it keeps
every candidate immediately runnable and auditable, and it means the autopilot
never executes anything a person has not already reviewed as code.

The cost is that today only one primitive can express a genuine mechanism
(`calendar_event`), because the rest of the list needs data the lake does not
have. That is not a limitation of this module; it is the state of the data, and
`qr/research/features.py` names what to go and get.
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import asdict, dataclass, field
from typing import Any, Sequence

from qr.research import features
from qr.validate.trial_log import TrialLog, content_hash

DEFAULT_MODEL = os.environ.get("QR_CLAUDE_MODEL", "claude-opus-5")

#: Families a memo may compile its crude version to. The three marked
#: `already_failed` are here so a restatement of a tested pattern can be
#: *recognised* and killed, not so it can be run again.
PRIMITIVES: dict[str, dict[str, Any]] = {
    "calendar_event": {
        "class": "CalendarEvent",
        "module": "qr.strategies.calendar",
        "already_failed": False,
        "expresses": "a forced trade on a knowable date: month/quarter end, turn of month, year end",
    },
    "tsmom": {"class": "TSMOM", "module": "qr.strategies.library", "already_failed": True,
              "expresses": "time-series momentum — tested as tsmom_v1, failed"},
    "xsmom": {"class": "CrossSectionalMomentum", "module": "qr.strategies.library", "already_failed": True,
              "expresses": "cross-sectional momentum — tested as xsmom_v1, failed"},
    "reversal": {"class": "ShortTermReversal", "module": "qr.strategies.library", "already_failed": True,
                 "expresses": "short-term reversal — tested as reversal_v1, failed"},
}

#: Phrases that are a pattern wearing a mechanism's clothes. Question 2 asks
#: why the forced trader keeps being forced; an answer drawn from this list is
#: an answer about price behaviour, which is the thing being explained rather
#: than an explanation of it.
NON_MECHANISMS = (
    "momentum works",
    "trends persist",
    "trends tend to continue",
    "mean reversion works",
    "the pattern repeats",
    "historically it has worked",
    "it has worked in the past",
    "prices tend to",
    "the market tends to",
    "investors are irrational",
    "behavioural bias",
    "fear and greed",
)

SYSTEM_PROMPT = """You are a sceptical quantitative researcher screening trade ideas for a small \
retail account. Your job is to KILL ideas cheaply, not to find one.

The bar is a transfer, not a pattern. A real candidate names someone who is FORCED to trade \
regardless of price — a mandate, a deadline, a margin call, a redemption, a tax year end — and \
names who collects the other side. "Momentum works" is not a mechanism; it is the thing that \
would need explaining. If the honest answer to "why will they keep being forced?" is a statement \
about price behaviour rather than about an obligation, kill the candidate and say so.

Most good screening ends in a kill. A night that kills eight candidates for named reasons is a \
success. Inventing a mechanism to keep a candidate alive is the failure mode; say "killed" freely.

You may only propose a crude version using a primitive from the list you are given. If no \
primitive fits, or the idea needs data that is not available, say so plainly rather than \
substituting something that does fit — a candidate that is blocked on data is a useful output."""

MEMO_SCHEMA = {
    "type": "object",
    "properties": {
        "candidate_id": {"type": "string", "description": "snake_case, e.g. month_end_rebalance_v1"},
        "title": {"type": "string"},
        "forced_trader": {"type": "string", "description": "Q1: who is forced to trade, and why"},
        "persistence": {"type": "string", "description": "Q2: why will they KEEP being forced"},
        "other_side": {"type": "string", "description": "Q3: who collects, and why has it not gone"},
        "what_breaks_it": {"type": "string", "description": "Q4"},
        "crude_version": {
            "type": "object",
            "properties": {
                "primitive": {"type": "string"},
                "params": {"type": "object", "additionalProperties": True},
                "expected_sign": {"type": "string", "enum": ["positive", "negative"]},
                "rationale": {"type": "string"},
            },
            "required": ["primitive", "params", "expected_sign", "rationale"],
            "additionalProperties": False,
        },
        "required_features": {"type": "array", "items": {"type": "string"}},
        "self_verdict": {"type": "string", "enum": ["proceed", "killed"]},
        "kill_reason": {"type": "string"},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
    },
    "required": [
        "candidate_id", "title", "forced_trader", "persistence", "other_side",
        "what_breaks_it", "crude_version", "required_features", "self_verdict",
        "kill_reason", "confidence",
    ],
    "additionalProperties": False,
}


@dataclass(frozen=True)
class CrudeVersion:
    primitive: str
    params: dict[str, Any]
    expected_sign: str
    rationale: str = ""

    def build(self):
        """The strategy object Stage 3 runs. Raises if the primitive is unknown."""
        import importlib

        spec = PRIMITIVES.get(self.primitive)
        if spec is None:
            raise ValueError(f"unknown primitive {self.primitive!r}; known: {sorted(PRIMITIVES)}")
        module = importlib.import_module(spec["module"])
        return getattr(module, spec["class"])(**self.params)


@dataclass(frozen=True)
class MechanismMemo:
    """One page, five questions, and a machine-runnable crude version."""

    candidate_id: str
    title: str
    forced_trader: str
    persistence: str
    other_side: str
    what_breaks_it: str
    crude_version: CrudeVersion
    required_features: tuple[str, ...] = ()
    self_verdict: str = "proceed"
    kill_reason: str = ""
    confidence: float = 0.0
    model: str = ""

    @classmethod
    def from_dict(cls, raw: dict, model: str = "") -> "MechanismMemo":
        crude = dict(raw["crude_version"])
        return cls(
            candidate_id=raw["candidate_id"],
            title=raw["title"],
            forced_trader=raw["forced_trader"],
            persistence=raw["persistence"],
            other_side=raw["other_side"],
            what_breaks_it=raw["what_breaks_it"],
            crude_version=CrudeVersion(
                primitive=crude["primitive"],
                params=dict(crude.get("params") or {}),
                expected_sign=crude["expected_sign"],
                rationale=crude.get("rationale", ""),
            ),
            required_features=tuple(raw.get("required_features") or ()),
            self_verdict=raw.get("self_verdict", "proceed"),
            kill_reason=raw.get("kill_reason", ""),
            confidence=float(raw.get("confidence", 0.0)),
            model=model,
        )

    def to_dict(self) -> dict:
        body = asdict(self)
        body["crude_version"] = asdict(self.crude_version)
        body["required_features"] = list(self.required_features)
        return body

    def as_markdown(self) -> str:
        """The one page a human reads, and the document gate 0 hashes."""
        return "\n".join(
            [
                f"# {self.title}",
                f"\n*Candidate `{self.candidate_id}`. Mechanism memo, Stage 2.*\n",
                "## 1. Who is forced to trade, and why?\n",
                self.forced_trader,
                "\n## 2. Why will they keep being forced?\n",
                self.persistence,
                "\n## 3. Who is on the other side, and why has the effect not gone?\n",
                self.other_side,
                "\n## 4. What would make it stop working?\n",
                self.what_breaks_it,
                "\n## 5. Crudest version\n",
                f"`{self.crude_version.primitive}` with "
                f"`{json.dumps(self.crude_version.params, sort_keys=True)}`, "
                f"expected sign **{self.crude_version.expected_sign}**.\n",
                self.crude_version.rationale,
                f"\nFeatures required: {', '.join(self.required_features) or 'none'}.",
            ]
        )


# --------------------------------------------------------------------- triage


@dataclass(frozen=True)
class Triage:
    """The harness's own verdict, reached without reference to the model's."""

    verdict: str  # "proceed" | "killed" | "blocked"
    reason: str
    missing_datasets: tuple[str, ...] = ()

    @property
    def proceed(self) -> bool:
        return self.verdict == "proceed"


def _reads_as_a_pattern(text: str) -> str | None:
    lowered = " ".join(text.lower().split())
    for phrase in NON_MECHANISMS:
        if phrase in lowered:
            return phrase
    return None


def triage(memo: MechanismMemo) -> Triage:
    """Decide what happens to a memo. Deterministic, and deliberately harsh.

    Order matters. A self-kill is honoured first because it is the outcome the
    stage exists to produce and there is no reason to argue with one. After
    that the checks run cheapest-first, and every one of them can only kill or
    block — nothing here can revive a candidate.
    """
    if memo.self_verdict == "killed":
        return Triage("killed", f"killed by the memo itself: {memo.kill_reason or 'no reason given'}")

    if not memo.forced_trader.strip():
        return Triage("killed", "question 1 is unanswered: no payer is named")

    phrase = _reads_as_a_pattern(memo.persistence)
    if phrase is not None:
        return Triage(
            "killed",
            f"question 2 answers with a statement about prices ({phrase!r}), not an obligation. "
            "That is the pattern being restated rather than explained.",
        )

    unknown = features.unknown_keys(memo.required_features)
    if unknown:
        return Triage("killed", f"asks for features that do not exist: {', '.join(unknown)}")

    blocked = features.missing(memo.required_features)
    if blocked:
        return Triage(
            "blocked",
            "the mechanism is coherent but the data is not in the lake: "
            + ", ".join(f.key for f in blocked),
            tuple(features.datasets_needed(memo.required_features)),
        )

    spec = PRIMITIVES.get(memo.crude_version.primitive)
    if spec is None:
        return Triage("killed", f"crude version names no known primitive ({memo.crude_version.primitive!r})")
    if spec["already_failed"]:
        return Triage(
            "killed",
            f"the crudest version is {memo.crude_version.primitive}, which has already been "
            "pre-registered and failed. Whatever the memo says, the thing being proposed is "
            "that family, and re-running it would spend the trial count for nothing.",
        )

    try:
        memo.crude_version.build()
    except Exception as exc:  # the params are the model's; they may not fit
        return Triage("killed", f"crude version does not build: {type(exc).__name__}: {exc}")

    return Triage("proceed", "a named payer, an obligation that persists, and a runnable crude version")


# ------------------------------------------------------------------ the call


def propose(
    brief: str,
    model: str = DEFAULT_MODEL,
    client=None,
    max_tokens: int = 8_000,
) -> MechanismMemo:
    """Ask Claude for one memo, as strict JSON.

    `brief` is the seed — a market, a class of forced trader, a question. The
    prompt carries the primitive list and the feature registry so the model
    cannot propose something unrunnable without being told it is doing so.
    """
    import anthropic

    client = client or anthropic.Anthropic()
    catalogue = "\n".join(
        f"- `{key}`: {spec['expresses']}"
        for key, spec in PRIMITIVES.items()
    )
    have = ", ".join(f"`{k}`" for k, f in features.REGISTRY.items() if f.available)
    havent = "\n".join(
        f"- `{f.key}`: {f.what} — NOT AVAILABLE, would need {f.needs_dataset}"
        for f in features.REGISTRY.values()
        if not f.available
    )
    user = (
        f"{brief}\n\n"
        f"Answer the five questions for ONE candidate.\n\n"
        f"Primitives you may use for the crude version:\n{catalogue}\n\n"
        f"Features available in the lake: {have}\n\n"
        f"Features NOT available (propose one only if the idea genuinely needs it; "
        f"it will be parked, not run):\n{havent}\n"
    )
    with client.beta.messages.stream(
        model=model,
        max_tokens=max_tokens,
        system=SYSTEM_PROMPT,
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        output_config={"format": {"type": "json_schema", "schema": MEMO_SCHEMA}},
        messages=[{"role": "user", "content": user}],
    ) as stream:
        response = stream.get_final_message()

    if response.stop_reason == "refusal":
        details = getattr(response, "stop_details", None)
        raise RuntimeError(f"model declined: {getattr(details, 'explanation', 'no explanation')}")
    if response.stop_reason == "max_tokens":
        raise RuntimeError("memo truncated (max_tokens)")
    text = next(b.text for b in response.content if b.type == "text")
    return MechanismMemo.from_dict(json.loads(text), model=response.model)


def record(log: TrialLog, memo: MechanismMemo, verdict: Triage):
    """Put the memo and its triage in the chain — including the killed ones.

    Especially the killed ones. A record of what was considered and rejected,
    with the reason, is what stops the same idea being generated and rejected
    again next week at the same cost; and if the stopping rule is ever reached,
    it is the evidence that the eight candidates were genuine rather than eight
    variations on one.
    """
    return log.append(
        "memo",
        memo.candidate_id,
        {
            "memo": memo.to_dict(),
            "doc_sha256": content_hash(memo.as_markdown()),
            "triage": asdict(verdict),
        },
    )


def considered(log: TrialLog) -> list[dict]:
    """Every memo ever written, with what happened to it."""
    return [
        {
            "candidate_id": r.hypothesis_id,
            "title": r.payload["memo"].get("title", ""),
            "verdict": r.payload["triage"]["verdict"],
            "reason": r.payload["triage"]["reason"],
            "ts": r.ts[:19],
        }
        for r in log.records(kind="memo")
    ]
