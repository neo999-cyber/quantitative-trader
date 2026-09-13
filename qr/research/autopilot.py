"""The overnight loop: Stages 2, 3 and 4, unattended.

    brief -> memo -> triage -> kill test (sandbox) -> quota -> pre-register
          -> twelve gates (validation) -> report

Everything in that line is already built and tested somewhere else. What this
module adds is the *order*, the refusals between the steps, and the property
that matters most for leaving a laptop alone overnight: **every exit is
recorded and no exit is silent.** A candidate that dies at triage, at the kill
test, at the quota or at gate 5 leaves the same kind of trace, so the morning's
question — what happened, and why — is answered from the log rather than from
scrollback.

## The rules it cannot talk its way out of

They are not enforced here. That is deliberate, and it is why this file is
short: each rule lives with the thing it protects, so a future loop that
forgets to call one still cannot break it.

* **The sandbox** (`qr/data/sandbox.py`) refuses a kill test on validation
  data, gate 0 fails a discovery panel, and `write_report` refuses to write
  one.
* **The policy** (`qr/research/policy.py`) raises rather than returns when the
  quota is spent or the stopping rule is reached.
* **The trial log** hash-chains all of it, so a record that was edited or
  dropped stops verifying.

What this loop is trusted with is choosing which briefs to think about, and
being wrong about that is cheap — the funnel is designed so that a bad idea
costs a page of text and a few seconds in the sandbox.

## What "autonomous" does not include

It does not include deciding that something works. The loop ends at a
Hypothesis Report; a family that clears all twelve gates goes to incubation,
which is a paper record gate 10 reads over weeks. Nothing here funds anything,
and nothing here should.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Sequence

import pandas as pd

from qr.data.panel import Panel
from qr.data.sandbox import SandboxSpec, restrict
from qr.execution.costs import CostModel
from qr.research import features, killtest, mechanism
from qr.research.mechanism import MechanismMemo, Triage
from qr.research.policy import (
    PolicyBreach,
    ResearchPolicy,
    StoppingRuleReached,
    check_promotion,
)
from qr.validate.trial_log import TrialLog


def _is_deterministic(exc: Exception) -> bool:
    """Would this failure repeat identically on the next brief?

    A 4xx other than rate limiting is a statement about the request — a schema
    the API will not accept, a model that does not exist, a missing key — and
    no amount of different prose will change it. A 429 or a 5xx is about the
    moment, and the next brief may well succeed.
    """
    status = getattr(exc, "status_code", None)
    if status is None:
        response = getattr(exc, "response", None)
        status = getattr(response, "status_code", None)
    if not isinstance(status, int):
        return False
    return 400 <= status < 500 and status != 429


@dataclass
class CandidateOutcome:
    """One brief, and how far it got."""

    brief: str
    candidate_id: str = ""
    title: str = ""
    stage: str = "memo"          # memo | triage | killtest | promotion | gates
    outcome: str = ""            # killed | blocked | failed | promoted | error
    reason: str = ""
    datasets_needed: tuple[str, ...] = ()
    stats: dict[str, Any] = field(default_factory=dict)

    def row(self) -> dict[str, Any]:
        return {
            "candidate": self.candidate_id or "(none)",
            "title": self.title[:48],
            "stage": self.stage,
            "outcome": self.outcome,
            "reason": self.reason[:90],
        }


@dataclass
class Night:
    """What an unattended run did. The morning's whole answer."""

    outcomes: list[CandidateOutcome] = field(default_factory=list)
    stopped_early: str = ""

    def frame(self) -> pd.DataFrame:
        return pd.DataFrame([o.row() for o in self.outcomes])

    def promoted(self) -> list[CandidateOutcome]:
        return [o for o in self.outcomes if o.outcome == "promoted"]

    def blocked(self) -> list[CandidateOutcome]:
        return [o for o in self.outcomes if o.outcome == "blocked"]

    def shopping_list(self) -> dict[str, int]:
        """Datasets named tonight, and how many candidates named each.

        The most valuable output of a night where nothing ran, and it very
        nearly went in the bin. It used to draw only from `blocked` candidates
        — but triage honours a self-kill first, and a model that notices the
        data is missing says so *by killing its own candidate*. So the first
        two real nights reported "0 blocked on data" and an empty list while
        three of the twelve memos said, in as many words, "blocked on data, not
        on logic".

        Drawing from every candidate that named a missing dataset fixes that
        without touching the verdicts, which are separately right: a killed
        candidate stays killed, because whether the *idea* survives and whether
        the *data* exists are different questions and the shopping list only
        asks the second one. A dataset named by three dead candidates is still
        a dataset three lines of enquiry ran into.
        """
        counts: dict[str, int] = {}
        for outcome in self.outcomes:
            for dataset in outcome.datasets_needed:
                counts[dataset] = counts.get(dataset, 0) + 1
        return dict(sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])))


def run_night(
    briefs: Sequence[str],
    log: TrialLog,
    policy: ResearchPolicy,
    sandbox: SandboxSpec,
    panel: Panel,
    *,
    costs: CostModel | None = None,
    universe: pd.DataFrame | None = None,
    equity: float | None = None,
    propose: Callable[[str], MechanismMemo] | None = None,
    promote: Callable[[MechanismMemo, KillTestLike], None] | None = None,
    progress: Callable[[str], None] | None = None,
    now: datetime | None = None,
) -> Night:
    """Work through the briefs until they run out or the policy says stop.

    `propose` and `promote` are injected rather than imported so the loop can
    be tested without an API key and without running the twelve gates — the
    order and the refusals are what needs testing here, and they are the same
    whether the memo came from Claude or from a fixture.
    """
    propose = propose or mechanism.propose
    costs = costs or CostModel.trial()
    now = now or datetime.now(timezone.utc)
    say = progress or (lambda _line: None)

    discovery = restrict(panel, sandbox, "discovery")
    night = Night()

    for brief in briefs:
        outcome = CandidateOutcome(brief=brief)
        night.outcomes.append(outcome)

        # The quota is checked BEFORE the memo, not after the kill test. A
        # candidate that survives everything and is then refused for want of
        # budget has cost a night's compute to learn something known at the
        # start, and — worse — leaves a promotable idea sitting in a log where
        # the next run will find it already validated and be tempted.
        try:
            check_promotion(log, policy, now=now)
        except StoppingRuleReached as exc:
            night.stopped_early = str(exc)
            outcome.stage, outcome.outcome, outcome.reason = "promotion", "stopped", str(exc)
            say("stopping rule reached; no further candidates")
            break
        except PolicyBreach as exc:
            night.stopped_early = str(exc)
            outcome.stage, outcome.outcome, outcome.reason = "promotion", "quota", str(exc)
            say(f"quota spent: {exc}")
            break

        say(f"memo: {brief[:70]}")
        try:
            memo = propose(brief)
        except Exception as exc:
            outcome.stage, outcome.outcome = "memo", "error"
            outcome.reason = f"{type(exc).__name__}: {exc}"
            say(f"  memo failed: {outcome.reason}")
            if _is_deterministic(exc):
                # A 400 is a statement about the request, not about the brief.
                # The next brief builds the same request and fails identically,
                # so continuing only buys the same error once per brief — which
                # is exactly what a live run did, three times, before anyone
                # read the first one. Stop and say so.
                night.stopped_early = (
                    "the request itself was rejected, so every brief would fail the same "
                    f"way: {outcome.reason}"
                )
                say("  this is a request error, not a brief error — stopping the night")
                break
            continue

        outcome.candidate_id, outcome.title = memo.candidate_id, memo.title
        verdict = mechanism.triage(memo)
        mechanism.record(log, memo, verdict)
        outcome.stage = "triage"
        # Recorded whatever the verdict turns out to be. What a candidate
        # needed is a fact about the data, and it stays true when the idea is
        # rejected for some other reason entirely.
        outcome.datasets_needed = tuple(features.datasets_needed(memo.required_features))

        if verdict.verdict == "blocked":
            outcome.outcome, outcome.reason = "blocked", verdict.reason
            say(f"  {memo.candidate_id}: blocked on data")
            continue
        if not verdict.proceed:
            outcome.outcome, outcome.reason = "killed", verdict.reason
            say(f"  {memo.candidate_id}: killed at triage")
            continue

        say(f"  {memo.candidate_id}: kill tests")
        outcome.stage = "killtest"
        try:
            test = killtest.run(memo, discovery, policy, costs, universe, equity)
        except Exception as exc:
            outcome.outcome = "error"
            outcome.reason = f"{type(exc).__name__}: {exc}"
            say(f"  kill test failed to run: {outcome.reason}")
            continue

        killtest.record(log, test)
        outcome.stats = test.stats
        if not test.passed:
            outcome.outcome = "failed"
            outcome.reason = f"{test.failed_at}: {test.reason}"
            say(f"  {memo.candidate_id}: died at {test.failed_at}")
            continue

        outcome.stage = "gates"
        if promote is None:
            outcome.outcome, outcome.reason = "ready", test.reason
            say(f"  {memo.candidate_id}: survived the sandbox; no promoter wired up")
            continue

        try:
            promote(memo, test)
        except Exception as exc:
            outcome.outcome = "error"
            outcome.reason = f"{type(exc).__name__}: {exc}"
            say(f"  promotion failed: {outcome.reason}")
            continue

        outcome.outcome, outcome.reason = "promoted", test.reason
        say(f"  {memo.candidate_id}: promoted, pre-registered and gated")

    return night


#: Only used in a type hint above; kept loose so this module does not import
#: `KillTest` purely to name it in a callable signature.
KillTestLike = Any


# ---------------------------------------------------------------- promotion

#: How a memo's single crude parameter set becomes a pre-registered grid.
#:
#: Fixed here, in code, before any run — which is the only thing that makes an
#: autonomous promotion honest. A grid chosen after seeing the kill test is a
#: search conducted with knowledge of the answer, and gate 4 cannot deflate for
#: a search it was not told about. The memo commits to the event and the side;
#: the expansion varies only the window, which is the parameter nobody has a
#: prior about.
#:
#: Twelve variants is deliberate: enough for CSCV to have splits to work with
#: at gate 5, far below the policy's cap, and small enough that gate 4's bar
#: does not move much for the families that come after.
GRID_EXPANSION: dict[str, dict[str, list]] = {
    "calendar_event": {"before": [1, 2, 3, 5], "after": [0, 1, 2]},
}


def family_spec(memo: MechanismMemo, prereg_dir=None):
    """The FamilySpec a promoted memo becomes.

    The memo's own parameters are the fixed ones; `GRID_EXPANSION` supplies the
    swept ones. Anything the memo fixed that the expansion also names is the
    expansion's, so a memo cannot narrow its own grid to the variant that
    happened to work in the sandbox.
    """
    from qr.research.families import FamilySpec

    spec = PRIMITIVES_FOR_SPEC.get(memo.crude_version.primitive)
    if spec is None:
        raise ValueError(f"no family spec for primitive {memo.crude_version.primitive!r}")
    grid = {k: [v] for k, v in memo.crude_version.params.items()}
    grid.update(GRID_EXPANSION.get(memo.crude_version.primitive, {}))
    return FamilySpec(
        hypothesis_id=memo.candidate_id,
        strategy_class=spec,
        grid=grid,
        summary=memo.title,
    )


def _strategy_classes() -> dict[str, type]:
    import importlib

    out = {}
    for key, spec in mechanism.PRIMITIVES.items():
        module = importlib.import_module(spec["module"])
        out[key] = getattr(module, spec["class"])
    return out


PRIMITIVES_FOR_SPEC = _strategy_classes()


def promoter(
    log: TrialLog,
    panel: Panel,
    sandbox: SandboxSpec,
    policy: ResearchPolicy,
    *,
    costs: CostModel | None = None,
    universe: pd.DataFrame | None = None,
    reports_dir=None,
    prereg_dir=None,
    manifest_hash: str | None = None,
    equity: float | None = None,
    permutations: int = 200,
    progress: Callable[[str], None] | None = None,
):
    """Build the callable `run_night` uses to take a survivor through Stage 4.

    The order inside is the part that matters and it is the same order a person
    would have to follow: write the pre-registration **first**, stamp it into
    the log, and only then touch the validation data. Gate 0 compares the two
    sequence numbers and fails a hypothesis registered after its first run, so
    doing this in the wrong order does not produce a subtly optimistic result,
    it produces a FAIL.
    """
    from pathlib import Path

    from qr.research.families import run_family
    from qr.research.policy import check_grid
    from qr.validate.report import write_report

    costs = costs or CostModel.trial()
    validation = restrict(panel, sandbox, "validation")

    def promote(memo: MechanismMemo, test) -> None:
        spec = family_spec(memo)
        check_grid(policy, spec.n_variants, memo.candidate_id)

        document = memo.as_markdown()
        if prereg_dir is not None:
            path = Path(prereg_dir) / f"{memo.candidate_id}.md"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(document, encoding="utf-8")
        # Before the data. Always.
        log.prereg(
            memo.candidate_id,
            document,
            source="autopilot",
            primitive=memo.crude_version.primitive,
            grid={k: list(v) for k, v in spec.grid.items()},
            killtest_reason=getattr(test, "reason", ""),
        )

        run = run_family(
            spec,
            validation,
            costs,
            universe,
            "sandbox_validation",
            trial_log=log,
            manifest_hash=manifest_hash,
            permutations=permutations,
            equity=equity,
            upto=11,
            stop_on_fail=True,
            progress=progress,
        )
        if reports_dir is not None:
            write_report(
                run.report,
                reports_dir,
                log,
                run.sweep.results[run.best_variant].stats(),
            )

    return promote
