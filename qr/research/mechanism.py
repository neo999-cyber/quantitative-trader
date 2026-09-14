"""Stage 2 of `docs/10_NEXT.md`: mechanism before code.

The nine families that failed were all *patterns* — "things that went up keep
going up". Nobody pays for a pattern. The ideas that survive are transfers:
someone is **forced to trade** regardless of price, and somebody collects. So
before anything runs, a one-page memo answers six questions:

1. Who is forced to trade, and why?
2. Which market are they forced in, and what **mechanically transmits** their
   flow into the market we actually trade?
3. Why will they keep being forced? *(If the answer is "momentum works", there
   is no mechanism. Kill it here.)*
4. Who is on the other side today, and why has the effect not gone?
5. What would make it stop working?
6. Crudest possible version, and its gross return before costs.

Most candidates die at (2) or (3), on paper, for free. That is the point of the
stage: it is the cheapest filter in the funnel and the only one that looks at
*why* rather than at a number.

## Why question 2 exists

It was added after 26 self-kills (`docs/15`). The kills were right, but the
runs kept circling one ambiguity: is "leveraged longs pay funding on the perp"
a mechanism for a *spot* strategy? The forced trader is real and the payment is
real, and neither of those is a reason for the spot price to move — the perp is
a different instrument, and a memo that skips from one to the other is asserting
a link rather than naming one.

So the bar is now a transfer **plus a named transmission**: which market the
forced trader is forced in, and the arbitrage that carries their flow to ours.
"Funding is high, therefore spot falls" does not clear it. "Liquidations force
perp selling; basis arbitrageurs are long spot against short perp and sell spot
to stay hedged; the spot book is thinner overnight" does — it names a trader who
must act in *our* market, and it is checkable.

The bar is strict and it is not empty. Spot ETF creations and redemptions,
miner treasury selling, token unlocks and spot-margin liquidations are all
forced flow in spot itself, needing no transmission at all.

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
    "funding_tilt": {
        "class": "FundingTilt",
        "module": "qr.strategies.funding",
        "already_failed": False,
        "expresses": (
            "spot positioning from perpetual funding: hold the pairs whose levered crowd is "
            "most one-sided. Reads funding, never collects it — no spot position can"
        ),
    },
    "tsmom": {"class": "TSMOM", "module": "qr.strategies.library", "already_failed": True,
              "expresses": "time-series momentum — tested as tsmom_v1, failed"},
    "xsmom": {"class": "CrossSectionalMomentum", "module": "qr.strategies.library", "already_failed": True,
              "expresses": "cross-sectional momentum — tested as xsmom_v1, failed"},
    "reversal": {"class": "ShortTermReversal", "module": "qr.strategies.library", "already_failed": True,
                 "expresses": "short-term reversal — tested as reversal_v1, failed"},
}

#: JSON Schema keywords structured outputs is known to accept. Deliberately a
#: list of what has been *proven* to pass rather than a claim about the API's
#: full capability: two nights were spent discovering, one rejection at a time,
#: that `additionalProperties: true` and numeric `minimum`/`maximum` are not
#: supported. A test asserts the schema uses nothing outside this set, so the
#: next unsupported keyword is caught by pytest in a second rather than by a
#: run that has already loaded the lake.
SCHEMA_KEYWORDS = frozenset(
    {"type", "properties", "required", "additionalProperties", "description", "enum", "anyOf", "items"}
)

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

#: Stems that name an *agent* in the market being traded. A transmission is a
#: claim about someone's behaviour — an arbitrageur unwinding a hedge, an
#: authorised participant creating shares, a miner selling a treasury — and
#: every honest one names that someone. Two prices moving together does not.
#:
#: A stem list is crude and it fails closed, which is the right direction here:
#: a memo killed for naming no agent can be rewritten to name the agent it
#: meant, and the kill reason says exactly that. The alternative, accepting
#: "spot follows the perp", is how the funding candidates kept getting through.
TRANSMISSION_AGENTS = (
    "arb", "hedg", "market maker", "market-maker", "dealer", "liquidity provider",
    "authoris", "authoriz", "creat", "redem", "issuer", "fund must", "index fund",
    "liquidat", "margin call", "collateral", "mandate", "prospectus",
    "miner", "treasury", "unlock", "vest", "insider", "borrow", "short seller",
    "deliver", "settle", "expiry", "expiri", "basis trad", "cash and carry",
    "cash-and-carry", "in this market", "in spot itself", "forced in spot",
)


def _params_schema() -> dict[str, Any]:
    """The parameter object a crude version may set, built from the real classes.

    An open `additionalProperties: true` object would have been the obvious
    shape and the API refuses it outright — structured outputs require a closed
    schema. The refusal is doing the project a favour: enumerating the union of
    every primitive's constructor arguments means the model cannot invent a
    parameter that does not exist, and the names and types stay correct by
    construction because they are read off the classes rather than copied here.

    Every property is optional. The model is told to set only the ones
    belonging to the primitive it chose, and `CrudeVersion.build()` drops nulls
    before constructing, so a model that emits an irrelevant key as `null`
    rather than omitting it is not punished for the difference.
    """
    import importlib
    import inspect

    types = {int: "integer", float: "number", str: "string", bool: "boolean"}
    properties: dict[str, dict] = {}
    for spec in PRIMITIVES.values():
        cls = getattr(importlib.import_module(spec["module"]), spec["class"])
        for name, param in inspect.signature(cls.__init__).parameters.items():
            if name == "self" or name in properties:
                continue
            kind = types.get(type(param.default))
            if kind is None:
                # A `None` default carries no type, and guessing costs
                # correctness: `rebalance_on: str | None = None` came back as a
                # number until the annotation was read instead.
                annotation = str(param.annotation)
                kind = next(
                    (t for marker, t in (("str", "string"), ("bool", "boolean"),
                                         ("int", "integer"), ("float", "number"))
                     if marker in annotation),
                    "number",
                )
            # `anyOf` with a null branch rather than `"type": [kind, "null"]`:
            # the former is what Pydantic emits for an optional field, and the
            # SDK's own `messages.parse()` path generates Pydantic schemas, so
            # it is the shape the server is certain to accept. Every property
            # is then listed in `required` as well, which the documented
            # examples all do — between them, the request validates whether or
            # not the server insists on a closed, fully-required schema.
            properties[name] = {"anyOf": [{"type": kind}, {"type": "null"}]}
    return {
        "type": "object",
        "properties": properties,
        "required": sorted(properties),
        "additionalProperties": False,
        "description": (
            "Set the parameters belonging to the primitive you chose and null for "
            "every other one."
        ),
    }


SYSTEM_PROMPT = """You are a sceptical quantitative researcher screening trade ideas for a small \
retail account. Your job is to KILL ideas cheaply, not to find one.

The bar is a transfer, not a pattern. A real candidate names someone who is FORCED to trade \
regardless of price — a mandate, a deadline, a margin call, a redemption, a tax year end — and \
names who collects the other side. "Momentum works" is not a mechanism; it is the thing that \
would need explaining. If the honest answer to "why will they keep being forced?" is a statement \
about price behaviour rather than about an obligation, kill the candidate and say so.

The bar has a second half that is just as strict: TRANSMISSION. Name the market the forced \
trader is forced in, and — if that is not the market being traded here — the arbitrage that \
mechanically carries their flow into it. Someone must be obliged to trade OUR instrument. \
"Funding on the perpetual is high, therefore spot falls" does not clear the bar: the perp and \
the spot are different instruments and the sentence asserts the link instead of naming it. \
"Liquidations force perp selling; basis arbitrageurs hold long spot against short perp and must \
sell spot to stay hedged" does clear it, because it names a trader forced in spot and can be \
checked. And the transmitting agent must itself be OBLIGED — a hedge that must be maintained, a \
margin call, a mandate. An arbitrageur who unwinds a delta-neutral book when the carry stops \
paying is not forced: nothing fixes the date, the size or the price, so they transmit nothing. \
A profit motive is not an obligation. If you cannot name the transmission, kill the candidate \
— that is the honest outcome, \
and forced flow that happens in our own market (creations and redemptions, treasury selling, \
vesting unlocks, margin liquidations in the spot book) needs no transmission at all.

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
        "transmission": {
            "type": "string",
            "description": (
                "Q2: which market is the forced trader forced in, and what mechanically "
                "carries their flow into the market traded here? Name the arbitrageur or "
                "the hedge that links the two instruments, or say that the forced flow is "
                "in this market already. The agent doing the carrying must itself be obliged "
                "— a hedge to maintain, a margin call, a mandate. A discretionary trader "
                "acting on a profit motive transmits nothing, and a statement about prices "
                "moving together is not a transmission."
            ),
        },
        "persistence": {"type": "string", "description": "Q3: why will they KEEP being forced"},
        "other_side": {"type": "string", "description": "Q4: who collects, and why has it not gone"},
        "what_breaks_it": {"type": "string", "description": "Q5"},
        "crude_version": {
            "type": "object",
            "properties": {
                "primitive": {"type": "string"},
                "params": _params_schema(),
                "expected_sign": {"type": "string", "enum": ["positive", "negative"]},
                "rationale": {"type": "string"},
            },
            "required": ["primitive", "params", "expected_sign", "rationale"],
            "additionalProperties": False,
        },
        "required_features": {"type": "array", "items": {"type": "string"}},
        "self_verdict": {"type": "string", "enum": ["proceed", "killed"]},
        "kill_reason": {"type": "string"},
        # No `minimum`/`maximum`: structured outputs rejects numeric bounds
        # ("For 'number' type, properties maximum, minimum are not supported"),
        # which cost a second night. The range lives in the description and
        # `from_dict` clamps it, because a confidence of 7 is a malformed memo
        # rather than a very confident one.
        "confidence": {
            "type": "number",
            "description": "Between 0 and 1. Low is the honest answer for most candidates.",
        },
    },
    "required": [
        "candidate_id", "title", "forced_trader", "transmission", "persistence", "other_side",
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
        # A null is "not specified", not "specified as nothing": the schema has
        # to offer every primitive's parameters at once, so a model naming the
        # irrelevant ones explicitly is being tidy rather than wrong. Anything
        # else the class does not accept still raises, and triage kills the
        # memo for it — a parameter that was meant and is not understood must
        # not be dropped in silence.
        params = {k: v for k, v in self.params.items() if v is not None}
        return getattr(module, spec["class"])(**params)


@dataclass(frozen=True)
class MechanismMemo:
    """One page, six questions, and a machine-runnable crude version."""

    candidate_id: str
    title: str
    forced_trader: str
    transmission: str
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
            transmission=raw.get("transmission", ""),
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
            confidence=min(1.0, max(0.0, float(raw.get("confidence", 0.0)))),
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
                "\n## 2. Which market are they forced in, and what transmits it to ours?\n",
                self.transmission,
                "\n## 3. Why will they keep being forced?\n",
                self.persistence,
                "\n## 4. Who is on the other side, and why has the effect not gone?\n",
                self.other_side,
                "\n## 5. What would make it stop working?\n",
                self.what_breaks_it,
                "\n## 6. Crudest version\n",
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


def triage(memo: MechanismMemo, panel=None) -> Triage:
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

    transmission = memo.transmission.strip()
    if not transmission:
        return Triage(
            "killed",
            "question 2 is unanswered: the memo does not say which market the forced trader is "
            "forced in, or what carries their flow into the one traded here",
        )

    phrase = _reads_as_a_pattern(transmission)
    if phrase is not None:
        return Triage(
            "killed",
            f"question 2 answers with a statement about prices ({phrase!r}). A transmission is "
            "an obligation somebody has in this market, not an observation that two prices move "
            "together.",
        )

    lowered = " ".join(transmission.lower().split())
    if not any(stem in lowered for stem in TRANSMISSION_AGENTS):
        return Triage(
            "killed",
            "question 2 names no agent in the market traded here. A transmission has to say who "
            "is obliged to trade this instrument — the arbitrageur unwinding a hedge, the issuer "
            "creating or redeeming, the holder being liquidated — or that the forced flow is in "
            "this market already. An asserted link between two instruments is not one.",
        )

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
            "the mechanism is coherent but this project has no source for the data: "
            + ", ".join(f.key for f in blocked),
            tuple(features.datasets_needed(memo.required_features)),
        )

    # The registry says what this project *can* have; the panel says what this
    # lake *does* have. Conflating them sends a memo whose mechanism is fine to
    # a kill test with no data, where it produces a strategy holding nothing —
    # which reads exactly like a strategy that found nothing.
    if panel is not None:
        absent = features.satisfied_by(panel, memo.required_features)
        if absent:
            return Triage(
                "blocked",
                "the data exists but has not been pulled into this lake: "
                + ", ".join(absent)
                + ". Run the ingestor and this candidate is ready.",
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

    return Triage(
        "proceed",
        "a named payer, a named transmission into this market, an obligation that persists, "
        "and a runnable crude version",
    )


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
        f"Answer the six questions for ONE candidate.\n\n"
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
