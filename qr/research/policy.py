"""The research policy: what an unattended run is allowed to spend.

This is the spine of autonomy, and it exists because of an asymmetry that is
easy to state and easy to forget. Stages 1 to 3 — explore the sandbox, write a
mechanism memo, run cheap kill tests — cost nothing when they fail, so a
machine should run them all night. Stage 4 is the opposite: **every variant
that reaches the gates raises gate 4's deflation bar for every family that
comes after it, forever.** The trial log is already at ~1,450.

So an agent that decides what to promote *after seeing results* does two
things, not one. Given enough attempts it eventually promotes noise — the
familiar problem. But it also spends the project's remaining ability to detect
a real edge, which is the problem nobody notices until the edge arrives and
cannot be shown. Searching wider is not the lever. Choosing better is.

The answer is not to keep a human in the loop; a human approving memos at 9am
is a rate limit made of availability, which is no rate limit at all on a bad
week. The answer is to **fix the rule and the quota before any run**, in code,
declared into the hash-chained log the same way the sandbox boundary is. Then
the agent may promote freely, because the thing it cannot do is promote *more*,
or promote on a rule it invented after seeing the numbers.

Three limits, and they do different jobs:

* **The quota** (`max_promotions_per_week`, `max_promotions_per_quarter`) caps
  the rate. This is `docs/10_NEXT.md`'s "three to five candidates a quarter,
  not fifty", made mechanical.
* **The bar** (`min_cost_multiple`) is what a candidate must clear in the
  sandbox before it may be promoted at all: the effect must be worth at least
  three times its trading costs. Not 1.2x — that lesson was expensive and is
  written up in `docs/08`.
* **The stopping rule** (`max_candidates`) is the one that can end the project.
  Eight candidates with genuine, named mechanisms through the full gates, none
  surviving, and the finding is *no edge is accessible at this account size
  with this data* — write it up, stop, hold an index fund. Fixed in advance,
  before anyone is attached to a result, precisely so it cannot be
  renegotiated later.

`counts_from` is the detail that makes the stopping rule mean what it says.
Nine families have already failed and none of them had a mechanism — they were
patterns, which is the whole diagnosis. Counting them would fire the stopping
rule before the mechanism-first plan had tested a single idea. So the count
starts at the log sequence where this policy was declared.
"""
from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone

from qr.validate.trial_log import TrialLog, canonical


class PolicyBreach(RuntimeError):
    """An unattended run asked for more than the policy allows. It does not get it."""


class StoppingRuleReached(RuntimeError):
    """The pre-committed number of mechanisms has been tested and none survived."""


@dataclass(frozen=True)
class ResearchPolicy:
    """The rules an unattended run may not talk its way out of."""

    #: Promotions to Stage 4 — a pre-registration plus a gate run — per window.
    max_promotions_per_week: int = 2
    max_promotions_per_quarter: int = 5
    #: The widest grid a single family may sweep. Gate 4 deflates against the
    #: real count, so a fine grid is not free and a wide one is expensive for
    #: everyone who comes after.
    max_variants_per_family: int = 250
    #: Stage 3's bar: gross effect as a multiple of round-trip costs.
    min_cost_multiple: float = 3.0
    #: The stopping rule. Mechanisms tested, not variants.
    max_candidates: int = 8
    #: Log sequence the candidate count starts from. Set at declaration.
    counts_from: int = 0
    note: str = ""

    def __post_init__(self) -> None:
        if self.max_promotions_per_week < 1 or self.max_promotions_per_quarter < 1:
            raise ValueError("a policy that permits no promotions is a stopped project, not a policy")
        if self.max_promotions_per_week > self.max_promotions_per_quarter:
            raise ValueError(
                f"the weekly cap ({self.max_promotions_per_week}) exceeds the quarterly one "
                f"({self.max_promotions_per_quarter}), so the quarterly cap does nothing"
            )
        if self.min_cost_multiple < 1.0:
            raise ValueError(
                f"min_cost_multiple {self.min_cost_multiple} would promote a candidate that does "
                "not cover its own costs"
            )
        if self.max_candidates < 1:
            raise ValueError("max_candidates must be at least 1")

    def fingerprint(self) -> str:
        return hashlib.sha256(canonical(asdict(self)).encode("utf-8")).hexdigest()

    def describe(self) -> dict:
        return {**asdict(self), "fingerprint": self.fingerprint()}


# ---------------------------------------------------------------- declaration


def declare(log: TrialLog, policy: ResearchPolicy, force: bool = False):
    """Stamp the policy into the log, anchoring the candidate count to now.

    Like the sandbox boundary, once. A quota that can be raised after a
    disappointing week is not a quota, and the one thing a forced change must
    not be is quiet — `supersedes` puts it in the chain where a reader looking
    at a later pass can find it.
    """
    existing = current(log)
    if existing is not None and not force:
        raise PolicyBreach(
            f"a research policy is already in force ({existing.fingerprint()[:12]}…).\n"
            "Raising a quota after seeing results is the thing it exists to prevent.\n"
            "`--force` records the supersession in the log."
        )
    head = log.head()
    anchored = ResearchPolicy(**{**asdict(policy), "counts_from": 0 if head is None else head.seq + 1})
    return log.append(
        "policy",
        "policy/research",
        {"policy": anchored.describe(), "supersedes": existing.fingerprint() if existing else None},
    )


def current(log: TrialLog) -> ResearchPolicy | None:
    records = log.records(kind="policy")
    if not records:
        return None
    body = dict(records[-1].payload["policy"])
    body.pop("fingerprint", None)
    return ResearchPolicy(**body)


def require(log: TrialLog) -> ResearchPolicy:
    policy = current(log)
    if policy is None:
        raise PolicyBreach(
            "no research policy has been declared, so an unattended run has no budget and no "
            "stopping rule.\n  qr policy declare"
        )
    return policy


# ------------------------------------------------------------------ the checks


def _promotions_since(log: TrialLog, cutoff: datetime, counts_from: int = 0) -> int:
    """Pre-registrations stamped since `cutoff`, under this policy.

    `counts_from` matters as much here as it does for the stopping rule, and
    for a reason a test found rather than a reviewer: without it, declaring a
    policy in the week after a busy one starts the agent already over its
    quota, blocked by work the policy did not govern. A rate limit that
    retroactively charges for the past is not a rate limit, it is an outage.
    """
    total = 0
    for record in log.records(kind="prereg"):
        if record.seq < counts_from:
            continue
        try:
            stamped = datetime.fromisoformat(record.ts)
        except ValueError:
            continue
        if stamped.tzinfo is None:
            stamped = stamped.replace(tzinfo=timezone.utc)
        if stamped >= cutoff:
            total += 1
    return total


def candidates_tested(log: TrialLog, policy: ResearchPolicy) -> int:
    """Distinct hypotheses pre-registered since the policy was declared.

    Counted from `counts_from` rather than from the beginning of the chain,
    because the nine families that already failed had no mechanism — they are
    the diagnosis, not the first nine attempts at the cure.
    """
    return len(
        {
            r.hypothesis_id
            for r in log.records(kind="prereg")
            if r.seq >= policy.counts_from
        }
    )


def check_promotion(log: TrialLog, policy: ResearchPolicy | None = None, now: datetime | None = None) -> None:
    """May an unattended run promote one more candidate to the gates?

    Raises rather than returning a boolean, because the only correct response
    to "no" is to stop, and a boolean is something a caller can accidentally
    ignore.
    """
    policy = policy or require(log)
    now = now or datetime.now(timezone.utc)

    tested = candidates_tested(log, policy)
    if tested >= policy.max_candidates:
        raise StoppingRuleReached(
            f"{tested} candidates with named mechanisms have been through the gates and the "
            f"pre-committed limit is {policy.max_candidates}.\n"
            "The finding is: no edge is accessible at this account size with this data. "
            "Write it up, stop, hold an index fund.\n"
            "This was fixed in advance so it could not be renegotiated here."
        )

    week = _promotions_since(log, now - timedelta(days=7), policy.counts_from)
    if week >= policy.max_promotions_per_week:
        raise PolicyBreach(
            f"{week} promotions in the last seven days; the weekly cap is "
            f"{policy.max_promotions_per_week}. Choosing better is the lever, not searching wider."
        )
    quarter = _promotions_since(log, now - timedelta(days=91), policy.counts_from)
    if quarter >= policy.max_promotions_per_quarter:
        raise PolicyBreach(
            f"{quarter} promotions in the last quarter; the cap is "
            f"{policy.max_promotions_per_quarter}."
        )


def check_grid(policy: ResearchPolicy, n_variants: int, hypothesis_id: str = "") -> None:
    """Is this grid within what the policy permits a single family to spend?"""
    if n_variants > policy.max_variants_per_family:
        raise PolicyBreach(
            f"{hypothesis_id or 'this family'} sweeps {n_variants} variants; the cap is "
            f"{policy.max_variants_per_family}. Gate 4 deflates against the real count, so "
            "a finer grid is paid for by every family that comes after."
        )


def clears_the_bar(policy: ResearchPolicy, gross_edge_bps: float, round_trip_cost_bps: float) -> bool:
    """Stage 3's kill test: is the effect worth at least `min_cost_multiple` of its costs?"""
    if round_trip_cost_bps <= 0:
        raise ValueError("a round-trip cost of zero is not a cost model, it is a missing one")
    return gross_edge_bps >= policy.min_cost_multiple * round_trip_cost_bps


def budget(log: TrialLog, policy: ResearchPolicy | None = None, now: datetime | None = None) -> dict:
    """What is left, for a run that wants to report its own headroom."""
    policy = policy or require(log)
    now = now or datetime.now(timezone.utc)
    tested = candidates_tested(log, policy)
    return {
        "candidates_tested": tested,
        "candidates_remaining": max(0, policy.max_candidates - tested),
        "promotions_this_week": _promotions_since(log, now - timedelta(days=7), policy.counts_from),
        "weekly_cap": policy.max_promotions_per_week,
        "promotions_this_quarter": _promotions_since(log, now - timedelta(days=91), policy.counts_from),
        "quarterly_cap": policy.max_promotions_per_quarter,
        "stopping_rule_reached": tested >= policy.max_candidates,
    }
