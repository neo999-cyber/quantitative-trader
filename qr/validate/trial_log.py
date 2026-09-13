"""The trial log: an append-only, hash-chained record of every run.

Gate 4 (multiple-testing deflation) is only honest if the trial count is
honest, and a trial count kept in a mutable file is not evidence of anything.
So every record carries the hash of the record before it; editing or deleting
any line breaks every hash after it and `verify()` says where.

    log = TrialLog(path)
    log.prereg(hypothesis_id="tsmom_v1", doc=Path("docs/prereg/tsmom_v1.md").read_text())
    log.run(hypothesis_id="tsmom_v1", family="tsmom", params={"lookback": 90},
            universe="binance_spot_top30", metrics={"sharpe": 0.8})
    log.verify()          # -> raises TrialLogCorrupt on any edit
    log.trial_count()     # -> every variant ever run, which is what gate 4 needs

The file is JSON Lines so it stays greppable and diffable, and appends stay
cheap when the log has hundreds of thousands of variants in it.
"""
from __future__ import annotations

import hashlib
import json
import os
import socket
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator, Literal

GENESIS = "0" * 64

#: "sandbox" declares a market's discovery/validation boundary. It is a kind
#: rather than a note because the boundary has to be machine-readable: the
#: code that refuses to redraw it reads it back out of the chain.
#: "policy" is the research budget an unattended run may not exceed: the
#: promotion quota, the kill-test bar and the stopping rule, fixed before
#: any run rather than judged after one. See `qr/research/policy.py`.
#: "memo" is a Stage 2 mechanism memo and what triage did to it. The killed
#: ones matter most: they are what stops the same idea being regenerated and
#: re-rejected at the same cost, and they are the evidence that the stopping
#: rule counted eight genuine candidates rather than eight versions of one.
#: "killtest" is Stage 3's verdict on a memo that survived triage.
Kind = Literal[
    "prereg", "run", "gate", "holdout", "forward", "note", "sandbox", "policy",
    "memo", "killtest",
]


class TrialLogCorrupt(RuntimeError):
    """The hash chain does not verify: a record was edited, deleted or reordered."""


def canonical(obj: Any) -> str:
    """A byte-stable JSON rendering, so the same record always hashes the same."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def record_hash(body: dict[str, Any]) -> str:
    return hashlib.sha256(canonical(body).encode("utf-8")).hexdigest()


def content_hash(text: str) -> str:
    """Hash of a pre-registration document (or any other blob) we want stamped."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class TrialRecord:
    seq: int
    ts: str
    kind: str
    hypothesis_id: str
    payload: dict[str, Any]
    prev_hash: str
    hash: str

    def body(self) -> dict[str, Any]:
        """The hashed part of the record: everything except the hash itself."""
        return {
            "seq": self.seq,
            "ts": self.ts,
            "kind": self.kind,
            "hypothesis_id": self.hypothesis_id,
            "payload": self.payload,
            "prev_hash": self.prev_hash,
        }

    def to_json(self) -> str:
        return canonical({**self.body(), "hash": self.hash})

    @classmethod
    def from_json(cls, line: str) -> "TrialRecord":
        raw = json.loads(line)
        try:
            return cls(
                seq=raw["seq"],
                ts=raw["ts"],
                kind=raw["kind"],
                hypothesis_id=raw["hypothesis_id"],
                payload=raw["payload"],
                prev_hash=raw["prev_hash"],
                hash=raw["hash"],
            )
        except KeyError as exc:  # a truncated or hand-written line
            raise TrialLogCorrupt(f"record is missing field {exc}") from exc


@dataclass
class TrialLog:
    """Append-only hash-chained trial log backed by a JSON Lines file."""

    path: Path
    _agent: str = field(default="", repr=False)

    def __post_init__(self) -> None:
        self.path = Path(self.path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self._agent:
            self._agent = f"{os.environ.get('USER', 'unknown')}@{socket.gethostname()}"

    # ---------------------------------------------------------------- reading

    def __iter__(self) -> Iterator[TrialRecord]:
        if not self.path.exists():
            return
        with self.path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    yield TrialRecord.from_json(line)

    def records(self, kind: Kind | None = None, hypothesis_id: str | None = None) -> list[TrialRecord]:
        return [
            r
            for r in self
            if (kind is None or r.kind == kind)
            and (hypothesis_id is None or r.hypothesis_id == hypothesis_id)
        ]

    def head(self) -> TrialRecord | None:
        """The last record, read without loading the whole file."""
        if not self.path.exists() or self.path.stat().st_size == 0:
            return None
        last = None
        with self.path.open("rb") as fh:
            # Walk backwards in blocks until a complete final line is in hand.
            size = fh.seek(0, os.SEEK_END)
            block = 4096
            buf = b""
            while size > 0:
                step = min(block, size)
                size -= step
                fh.seek(size)
                buf = fh.read(step) + buf
                lines = [ln for ln in buf.split(b"\n") if ln.strip()]
                if lines and (size == 0 or buf.count(b"\n") >= 1):
                    last = lines[-1]
                    break
        return TrialRecord.from_json(last.decode("utf-8")) if last else None

    def trial_count(self, hypothesis_id: str | None = None) -> int:
        """Every variant ever run — the N that gate 4's deflation consumes."""
        return sum(
            r.payload.get("variants", 1)
            for r in self.records(kind="run", hypothesis_id=hypothesis_id)
        )

    # ---------------------------------------------------------------- writing

    def append(self, kind: Kind, hypothesis_id: str, payload: dict[str, Any]) -> TrialRecord:
        prev = self.head()
        body = {
            "seq": 0 if prev is None else prev.seq + 1,
            "ts": datetime.now(timezone.utc).isoformat(timespec="microseconds"),
            "kind": kind,
            "hypothesis_id": hypothesis_id,
            "payload": {**payload, "agent": self._agent},
            "prev_hash": GENESIS if prev is None else prev.hash,
        }
        rec = TrialRecord(**body, hash=record_hash(body))
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(rec.to_json() + "\n")
            fh.flush()
            os.fsync(fh.fileno())
        return rec

    def prereg(self, hypothesis_id: str, doc: str, **extra: Any) -> TrialRecord:
        """Gate 0: stamp the pre-registration document before any run touches data."""
        return self.append(
            "prereg", hypothesis_id, {"doc_sha256": content_hash(doc), "doc_chars": len(doc), **extra}
        )

    def document_drift(self, root: Path | None = None) -> list[dict[str, Any]]:
        """Pre-registrations whose document no longer hashes to what was logged.

        The chain protects the log, not the files the log points at. A
        pre-registration is a promise that a prediction was fixed before the
        data was seen, and that promise is only checkable while the document
        still hashes to the recorded value — so an edit after the fact, however
        well-meant (appending the outcome is the obvious temptation, and one
        this project's author reached for within an hour of the run), silently
        voids the evidence. Editing is not prevented, because the file is the
        author's; it is made visible.

        Only the latest registration per hypothesis is checked, since an
        amendment before the first run is legitimate and gate 0 polices the
        ordering. A document that is absent is reported separately from one
        that has changed: the first is a missing file, the second is a
        different prediction.

        A hypothesis registered from inline text rather than a file has no
        document to drift from and is skipped — its wording lives in the record
        and nowhere else, so the chain already covers it. Passing `root`
        overrides that and looks for `<hypothesis_id>.md` there regardless.
        """
        from qr.config import REPO_ROOT

        out: list[dict[str, Any]] = []
        by_id: dict[str, TrialRecord] = {}
        for rec in self.records(kind="prereg"):
            by_id[rec.hypothesis_id] = rec  # records() is in sequence order
        for hypothesis_id, rec in sorted(by_id.items()):
            expected = rec.payload.get("doc_sha256")
            if root is not None:
                path = Path(root) / f"{hypothesis_id}.md"
            else:
                source = rec.payload.get("source")
                if not source or source == "inline":
                    continue
                path = Path(source)
                if not path.is_absolute():
                    path = REPO_ROOT / path
            if not path.exists():
                out.append({"hypothesis": hypothesis_id, "state": "MISSING", "path": str(path)})
                continue
            actual = content_hash(path.read_text(encoding="utf-8"))
            if actual != expected:
                out.append(
                    {
                        "hypothesis": hypothesis_id,
                        "state": "CHANGED",
                        "registered": str(expected)[:16],
                        "on_disk": actual[:16],
                        "seq": rec.seq,
                    }
                )
        return out

    def run(
        self,
        hypothesis_id: str,
        family: str,
        params: dict[str, Any],
        universe: str,
        metrics: dict[str, Any] | None = None,
        variants: int = 1,
        manifest_hash: str | None = None,
        **extra: Any,
    ) -> TrialRecord:
        """One backtest run. `variants` > 1 records a whole sweep in a single line."""
        return self.append(
            "run",
            hypothesis_id,
            {
                "family": family,
                "params": params,
                "universe": universe,
                "metrics": metrics or {},
                "variants": int(variants),
                "manifest_hash": manifest_hash,
                **extra,
            },
        )

    def gate(self, hypothesis_id: str, gate: int, name: str, verdict: str, stats: dict[str, Any]) -> TrialRecord:
        """Record one gate's verdict.

        SKIP is a permitted verdict and is recorded like any other: a gate that
        did not run is the most important thing to have on the record, because
        it is the one a reader is most likely to mistake for a pass.
        """
        verdict = verdict.upper()
        if verdict not in {"PASS", "WARN", "FAIL", "SKIP"}:
            raise ValueError(f"verdict must be PASS/WARN/FAIL/SKIP, got {verdict!r}")
        return self.append(
            "gate", hypothesis_id, {"gate": gate, "name": name, "verdict": verdict, "stats": stats}
        )

    def forward(
        self,
        hypothesis_id: str,
        date: str,
        net_return: float,
        cost: float,
        weights: dict[str, float] | None = None,
        expected_weights: dict[str, float] | None = None,
        expected_cost: float | None = None,
        **extra: Any,
    ) -> TrialRecord:
        """One bar of the live paper record.

        It goes in the same hash-chained file as everything else, and that is
        the point. A paper record kept in a spreadsheet is worth nothing: the
        one failure mode of incubation is the operator quietly dropping the
        week it went badly, and a chain makes that visible instead of
        tempting. `expected_weights` and `expected_cost` are what the research
        code said should happen on this bar, so gate 10 can tell a strategy
        that decayed from a strategy that was never wired up correctly.
        """
        return self.append(
            "forward",
            hypothesis_id,
            {
                "date": str(date),
                "net_return": float(net_return),
                "cost": float(cost),
                "weights": {str(k): float(v) for k, v in (weights or {}).items()},
                "expected_weights": (
                    None if expected_weights is None
                    else {str(k): float(v) for k, v in expected_weights.items()}
                ),
                "expected_cost": None if expected_cost is None else float(expected_cost),
                **extra,
            },
        )

    def note(self, hypothesis_id: str, text: str, **extra: Any) -> TrialRecord:
        """A written justification — what a WARN costs you."""
        return self.append("note", hypothesis_id, {"text": text, **extra})

    # ----------------------------------------------------------- verification

    def verify(self) -> int:
        """Walk the chain. Returns the number of records; raises on any break."""
        prev_hash, expected_seq = GENESIS, 0
        count = 0
        for rec in self:
            if rec.seq != expected_seq:
                raise TrialLogCorrupt(f"record {count}: seq {rec.seq}, expected {expected_seq}")
            if rec.prev_hash != prev_hash:
                raise TrialLogCorrupt(
                    f"record {rec.seq}: prev_hash {rec.prev_hash[:12]}…, expected {prev_hash[:12]}…"
                )
            if record_hash(rec.body()) != rec.hash:
                raise TrialLogCorrupt(f"record {rec.seq}: contents do not match its hash (edited)")
            prev_hash, expected_seq = rec.hash, rec.seq + 1
            count += 1
        return count


@dataclass
class SealedTrialLog(TrialLog):
    """A trial log that can be read but never written.

    A sensitivity analysis re-runs strategies that are already on the record
    with one parameter changed. It must read the log — gate 0 needs the
    pre-registration and gate 11 needs the holdout that gate 9 opened — and it
    must not write to it, for two reasons that are not stylistic.

    The trial count gate 4 deflates against is the number of configurations
    ever searched. Re-scoring nine known families at three account sizes
    searches nothing new: the same variants, the same data, one cost parameter
    moved. Logging them as `run` records would treble the count and raise
    gate 4's bar for every future family, which would make honest bookkeeping
    punish a sensitivity check — precisely backwards.

    And the `gate` records `run_gates` writes would be verdicts. These are not
    verdicts; the holdout is spent and a family that looks better at $100,000
    here has earned a place in the next pre-registration, nothing more. A
    reader scanning the log for "did it pass" must not find a row that says so.

    Writes are dropped rather than raised on, so the ordinary gate machinery
    runs unmodified. The record it returns is well-formed and correctly
    chained onto the current head; it simply never reaches the file.
    """

    def append(self, kind: Kind, hypothesis_id: str, payload: dict[str, Any]) -> TrialRecord:
        prev = self.head()
        body = {
            "seq": 0 if prev is None else prev.seq + 1,
            "ts": datetime.now(timezone.utc).isoformat(timespec="microseconds"),
            "kind": kind,
            "hypothesis_id": hypothesis_id,
            "payload": {**payload, "agent": self._agent, "sealed": True},
            "prev_hash": GENESIS if prev is None else prev.hash,
        }
        return TrialRecord(**body, hash=record_hash(body))
