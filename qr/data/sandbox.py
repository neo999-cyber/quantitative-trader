"""Stage 1 of `docs/10_NEXT.md`: the discovery sandbox.

The problem it solves is a self-inflicted trap. Every gate in this platform
exists to stop a searcher fooling themselves, and they work — which means every
exploratory look at the data costs something, because anything seen is
something the validation set can no longer be innocent of. Browsing is
therefore expensive, and expensive browsing is exactly why nine of nine
families so far have been textbook strategies. Nobody went looking, because
looking had a price.

So: carve off a permanent slice where looking is **free**, and from which
nothing is ever reported. Validation happens on the untouched remainder.

Three properties make this worth having rather than a comment in a README.

**The split is decided by a hash, not by a person.** `assign()` is
`sha256(salt + symbol)`, so which symbols land in the sandbox is fixed before
anyone knows what is in them and cannot be nudged afterwards. A split chosen
by judgement is a split that can be re-chosen when the result is
disappointing.

**It is declared once, into the hash-chained trial log.** `declare()` refuses
to overwrite an existing declaration for a market. Re-drawing the boundary
after seeing a result is the single failure this whole idea exists to prevent,
so it is not a discouraged action, it is a refused one — and a forced
redeclaration writes a record saying so, which no later reader can miss.

**Nothing computed here is reportable.** `restrict()` stamps the side onto the
panel, gate 0 FAILs a discovery run, and `write_report` refuses to write one.
Three layers, because the whole value of the sandbox is the promise that its
results never leak into the record, and a promise enforced in one place is a
promise one refactor from being broken.

Two split modes, because the two markets are not alike:

* **symbols** — 734 Binance pairs can spare a quarter of themselves. The
  sandbox gets its own names and the validation set keeps the rest, so a
  finding has to survive on instruments it was never fitted to.
* **period** — twelve ETFs cannot spare three. There the boundary is a date:
  the sandbox gets the early years and validation the later ones.

`both` applies the symbol rule and the date rule together, and is the
strictest: the sandbox is a rectangle, and everything outside it is validation.
"""
from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass, field
from typing import Iterable, Literal, Sequence

import pandas as pd

from qr.data.panel import Panel
from qr.validate.trial_log import TrialLog, canonical

Side = Literal["discovery", "validation"]
Mode = Literal["symbols", "period", "both"]

#: Where the sandbox's side is recorded on a panel, so it travels with the data
#: instead of with the caller's intentions.
SIDE_ATTR = "sandbox_side"


@dataclass(frozen=True)
class SandboxSpec:
    """One market's discovery/validation boundary. Declared once, never redrawn.

    `salt` is what makes the symbol assignment reproducible and unguessable at
    the same time: the same salt always produces the same split, and a
    different salt produces a different one, so "try another salt until the
    sandbox looks interesting" leaves a trail of declarations in the log rather
    than a quietly better-looking answer.
    """

    market: str
    mode: Mode = "symbols"
    #: Share of symbols that go to the sandbox, in `symbols` and `both` modes.
    symbol_fraction: float = 0.25
    #: The sandbox gets bars up to and including this date, in `period` and
    #: `both` modes. ISO date, or None.
    period_end: str | None = None
    salt: str = "qr-sandbox-v1"
    note: str = ""

    def __post_init__(self) -> None:
        if self.mode not in ("symbols", "period", "both"):
            raise ValueError(f"mode must be symbols, period or both; got {self.mode!r}")
        if self.mode in ("symbols", "both") and not 0.0 < self.symbol_fraction < 1.0:
            raise ValueError(
                f"symbol_fraction must be strictly between 0 and 1; got {self.symbol_fraction}. "
                "A sandbox of everything is not a sandbox, and one of nothing is not either."
            )
        if self.mode in ("period", "both") and not self.period_end:
            raise ValueError(f"mode {self.mode!r} needs a period_end")

    def fingerprint(self) -> str:
        """The declaration's identity. Any change to the boundary changes it."""
        return hashlib.sha256(canonical(asdict(self)).encode("utf-8")).hexdigest()

    # ------------------------------------------------------------ assignment

    def assign(self, symbol: str) -> Side:
        """Which side a symbol falls on. A hash, so nobody chose it.

        In `period` mode every symbol is on both sides — the boundary is the
        date — so this answers "validation", which is the side that decides
        whether a result may be reported.
        """
        if self.mode == "period":
            return "validation"
        digest = hashlib.sha256(f"{self.salt}:{symbol}".encode("utf-8")).digest()
        draw = int.from_bytes(digest[:8], "big") / float(1 << 64)
        return "discovery" if draw < self.symbol_fraction else "validation"

    def split_symbols(self, symbols: Iterable[str]) -> tuple[list[str], list[str]]:
        names = list(symbols)
        discovery = [s for s in names if self.assign(s) == "discovery"]
        return discovery, [s for s in names if s not in set(discovery)]

    def date_mask(self, index: pd.DatetimeIndex, side: Side) -> pd.Series:
        """Bars belonging to `side` on the time axis."""
        if self.mode == "symbols" or self.period_end is None:
            return pd.Series(True, index=index)
        cutoff = pd.Timestamp(self.period_end, tz="UTC")
        early = pd.Series(index <= cutoff, index=index)
        return early if side == "discovery" else ~early

    def describe(self) -> dict:
        return {**asdict(self), "fingerprint": self.fingerprint()}


def restrict(panel: Panel, spec: SandboxSpec, side: Side) -> Panel:
    """The half of `panel` that belongs to `side`, stamped with which half it is.

    The stamp is the point. A panel that has been through here knows what it
    is, so the code that refuses to report a discovery result does not have to
    trust its caller to have remembered — see `sandbox_side`.
    """
    if side not in ("discovery", "validation"):
        raise ValueError(f"side must be discovery or validation; got {side!r}")

    out = panel
    if spec.mode in ("symbols", "both"):
        discovery, validation = spec.split_symbols(panel.symbols)
        wanted = discovery if side == "discovery" else validation
        if not wanted:
            raise ValueError(
                f"the {side} side of {spec.market} is empty: none of the {len(panel.symbols)} "
                f"symbols in this panel fall on it. Check the market and the symbol_fraction."
            )
        out = out.select(wanted)
    if spec.mode in ("period", "both"):
        mask = spec.date_mask(out.index, side)
        if not bool(mask.any()):
            raise ValueError(
                f"the {side} side of {spec.market} is empty: no bars fall "
                f"{'on or before' if side == 'discovery' else 'after'} {spec.period_end}."
            )
        out = Panel({k: v.loc[mask.to_numpy()] for k, v in out.fields.items()}, out.interval)

    for frame in out.fields.values():
        frame.attrs[SIDE_ATTR] = side
    return out


def sandbox_side(panel: Panel | None) -> Side | None:
    """What `restrict` stamped on this panel, or None if it never went through."""
    if panel is None:
        return None
    for frame in panel.fields.values():
        stamped = frame.attrs.get(SIDE_ATTR)
        if stamped:
            return stamped  # type: ignore[return-value]
    return None


# ---------------------------------------------------------------- the record


class SandboxRedeclared(RuntimeError):
    """A market's boundary already exists and was not drawn again."""


def declare(log: TrialLog, spec: SandboxSpec, force: bool = False):
    """Stamp the boundary into the trial log. Once.

    `force` exists because a genuine mistake — the wrong market name, a
    fraction of 0.9 — has to be fixable. It is deliberately not quiet: the
    forced record carries `supersedes`, so the chain shows a boundary that was
    moved and when, and any reader can ask what had already been seen when it
    happened. That is the whole defence, and it is a social one rather than a
    technical one. Nothing can stop someone redrawing a line; the log can make
    it impossible to do so invisibly.
    """
    existing = current(log, spec.market)
    if existing is not None and not force:
        raise SandboxRedeclared(
            f"{spec.market} already has a sandbox, declared as {existing.fingerprint()[:12]}…\n"
            f"Redrawing it after seeing results is the one thing this is here to prevent.\n"
            f"If it is genuinely wrong, `--force` records the supersession in the log."
        )
    payload = {
        "spec": spec.describe(),
        "supersedes": existing.fingerprint() if existing is not None else None,
    }
    return log.append("sandbox", f"sandbox/{spec.market}", payload)


def current(log: TrialLog, market: str) -> SandboxSpec | None:
    """The boundary in force for a market, or None if none was ever drawn."""
    records = [
        r for r in log.records(kind="sandbox") if r.payload.get("spec", {}).get("market") == market
    ]
    if not records:
        return None
    spec = dict(records[-1].payload["spec"])
    spec.pop("fingerprint", None)
    return SandboxSpec(**spec)


def require(log: TrialLog, market: str) -> SandboxSpec:
    """The boundary, or an error that says how to draw one."""
    spec = current(log, market)
    if spec is None:
        raise SandboxRedeclared(
            f"no discovery sandbox has been declared for {market}.\n"
            f"Nothing may be explored until one exists, because an undeclared boundary is "
            f"one that can be drawn after the fact.\n"
            f"  qr sandbox declare --market {market}"
        )
    return spec
