"""Gate 6: permutation tests.

The question a permutation test answers is the one a t-stat cannot: *given this
data's own distribution, how often would a search like mine find something this
good in data with no structure in it?* It needs no distributional assumption,
it prices the search rather than the winner, and it is very hard to fool.

Three tests, weakest to strongest:

* **Signal shuffle** — keep the prices, shuffle the strategy's weights in time.
  Asks whether the *timing* carries information, holding the book's composition
  and turnover fixed. Cheap, and catches a signal that is really just an
  exposure.
* **Random-entry percentile** — compare against seeded random books. Asks
  whether the strategy beats an equally active coin toss on the same universe.
* **Masters bar permutation with re-optimisation** — permute the bar-to-bar
  returns, rebuild a consistent price series, and re-run **the whole variant
  grid**, keeping the best. This is the strong one: it tests the entire
  procedure, search included, so a strategy that only looks good because 200
  variants were tried will fail it. Nothing else in the pipeline prices the
  search this directly.

Permutation preserves the return distribution, the intrabar shape and the
cross-sectional correlation structure; it destroys serial dependence, which is
where every trend, reversal and momentum edge lives. A strategy that survives
it is claiming something about time ordering, which is exactly the claim.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Sequence

import numpy as np
import pandas as pd

from qr.data.panel import Panel


@dataclass
class PermutationResult:
    """One permutation test: observed statistic against its null distribution."""

    name: str
    observed: float
    null: np.ndarray
    n_permutations: int

    @property
    def p_value(self) -> float:
        """One-sided p, with the +1 correction that keeps it from ever being 0.

        Without it, 1,000 permutations none of which beat the observed value
        would report p = 0, which claims more certainty than 1,000 draws can
        carry. The floor is 1 / (n + 1).
        """
        if len(self.null) == 0 or not np.isfinite(self.observed):
            return float("nan")
        at_least_as_good = int(np.sum(self.null >= self.observed))
        return float((1 + at_least_as_good) / (1 + len(self.null)))

    @property
    def percentile(self) -> float:
        """Where the observed value sits in the null, 0-100."""
        if len(self.null) == 0 or not np.isfinite(self.observed):
            return float("nan")
        return float(100.0 * np.mean(self.null < self.observed))

    def verdict(self, pass_below: float = 0.05, fail_above: float = 0.10) -> str:
        p = self.p_value
        if not np.isfinite(p):
            return "FAIL"
        if p < pass_below:
            return "PASS"
        return "WARN" if p <= fail_above else "FAIL"

    def summary(self) -> dict[str, float]:
        return {
            "observed": self.observed,
            "p_value": self.p_value,
            "percentile": self.percentile,
            "null_median": float(np.median(self.null)) if len(self.null) else float("nan"),
            "null_95th": float(np.percentile(self.null, 95)) if len(self.null) else float("nan"),
            "permutations": float(self.n_permutations),
        }


# --------------------------------------------------------------- permuting data


def permute_panel(panel: Panel, seed: int = 0, same_permutation: bool = True) -> Panel:
    """A panel with its time ordering destroyed and everything else preserved.

    The bar-to-bar close returns are permuted and the close series rebuilt from
    the first price; open, high and low are carried as ratios to their own
    close, so each bar keeps its shape; volume travels with its bar.

    `same_permutation` applies one ordering to every symbol, which **preserves
    the cross-sectional correlation structure**. That is the null a timing
    strategy should be tested against: shuffling each symbol independently also
    destroys co-movement, making the null far easier to beat and the test far
    too kind.

    One caveat, and it is inherent rather than a shortcoming here: the shared
    ordering is filtered down to each symbol's own live bars, so two pairs with
    **different listing windows** cannot receive the identical permutation and
    their correlation is preserved only approximately. Pairs sharing a window —
    which is most of a top-30 universe over a chosen sample — are exact. Where
    that matters, restrict the panel to a common window before permuting.
    """
    rng = np.random.default_rng(seed)
    close = panel.close
    n = len(close)
    if n < 3:
        raise ValueError("cannot permute fewer than three bars")

    returns = close.pct_change(fill_method=None)
    ratios = {
        field_name: (panel[field_name] / close)
        for field_name in ("open", "high", "low")
        if field_name in panel.fields
    }

    order = rng.permutation(n - 1)
    permuted_returns = pd.DataFrame(index=close.index, columns=close.columns, dtype=float)
    permuted_ratios = {k: pd.DataFrame(index=close.index, columns=close.columns, dtype=float) for k in ratios}

    for symbol in close.columns:
        col = returns[symbol].to_numpy()[1:]
        # Permute only within the bars this symbol actually traded, so its
        # listing window survives. Filtering one global ordering down to each
        # symbol's live bars keeps the relative ordering consistent across
        # symbols — two pairs with the same live window get the identical
        # permutation, which is what preserves their correlation exactly.
        live = np.flatnonzero(np.isfinite(col))
        source = order if same_permutation else rng.permutation(n - 1)
        col_order = source[np.isin(source, live)]

        shuffled = np.full(n - 1, np.nan)
        shuffled[live] = col[col_order]
        permuted_returns[symbol] = np.concatenate([[np.nan], shuffled])

        for name, frame in ratios.items():
            shape = frame[symbol].to_numpy()[1:]
            moved = shape.copy()
            moved[live] = shape[col_order]
            permuted_ratios[name][symbol] = np.concatenate([[frame[symbol].to_numpy()[0]], moved])

    # Rebuild prices from the first observed close of each symbol. NaN returns
    # (a pair that had not listed) stay NaN, so listing windows are preserved.
    first = close.ffill().bfill().iloc[0]
    new_close = (1.0 + permuted_returns.fillna(0.0)).cumprod().mul(first, axis=1)
    new_close = new_close.where(close.notna())

    fields: dict[str, pd.DataFrame] = {"close": new_close}
    for name, frame in permuted_ratios.items():
        fields[name] = (new_close * frame).where(close.notna())
    live_returns = returns.to_numpy()[1:]
    for name in ("volume", "quote_volume", "trades"):
        if name in panel.fields:
            original = panel[name].to_numpy()
            rebuilt = original.copy()
            for j in range(len(close.columns)):
                live = np.flatnonzero(np.isfinite(live_returns[:, j]))
                source = order if same_permutation else rng.permutation(n - 1)
                col_order = source[np.isin(source, live)]
                column = original[1:, j].copy()
                column[live] = original[1:, j][col_order]
                rebuilt[1:, j] = column
            fields[name] = pd.DataFrame(rebuilt, index=close.index, columns=close.columns)
    return Panel(fields, panel.interval)


def shuffle_weights(weights: pd.DataFrame, seed: int = 0) -> pd.DataFrame:
    """Reorder a book's rows in time, keeping every position it ever held.

    Composition, gross exposure and the number of rebalances are untouched;
    only *when* each book was held changes.
    """
    rng = np.random.default_rng(seed)
    order = rng.permutation(len(weights))
    return pd.DataFrame(weights.to_numpy()[order], index=weights.index, columns=weights.columns)


# ------------------------------------------------------------------- the tests


def signal_shuffle_test(
    evaluate: Callable[[pd.DataFrame], float],
    weights: pd.DataFrame,
    observed: float,
    n_permutations: int = 1000,
    seed: int = 0,
) -> PermutationResult:
    """Does the timing matter? Shuffle the book in time and re-score it."""
    null = np.array(
        [evaluate(shuffle_weights(weights, seed=seed + i)) for i in range(n_permutations)]
    )
    return PermutationResult("signal_shuffle", observed, null, n_permutations)


def bar_permutation_test(
    panel: Panel,
    evaluate: Callable[[Panel], float],
    observed: float,
    n_permutations: int = 1000,
    seed: int = 0,
    same_permutation: bool = True,
) -> PermutationResult:
    """Masters' test. `evaluate` should re-run the **whole grid** and return its best.

    Passing a single fixed variant tests only that variant; passing the search
    tests the search, which is the version that prices the 200 configurations
    someone tried before settling on this one.
    """
    null = np.array(
        [
            evaluate(permute_panel(panel, seed=seed + i, same_permutation=same_permutation))
            for i in range(n_permutations)
        ]
    )
    return PermutationResult("bar_permutation", observed, null, n_permutations)


def random_entry_test(
    evaluate: Callable[[int], float],
    observed: float,
    n_permutations: int = 1000,
    seed: int = 0,
) -> PermutationResult:
    """Does it beat an equally busy coin toss? `evaluate` takes a seed."""
    null = np.array([evaluate(seed + i) for i in range(n_permutations)])
    return PermutationResult("random_entry", observed, null, n_permutations)


@dataclass
class PermutationSuite:
    """All three tests together, as gate 6 reports them."""

    results: list[PermutationResult] = field(default_factory=list)

    @property
    def verdict(self) -> str:
        verdicts = {r.verdict() for r in self.results}
        if not verdicts:
            return "FAIL"
        if "FAIL" in verdicts:
            return "FAIL"
        return "WARN" if "WARN" in verdicts else "PASS"

    def to_frame(self) -> pd.DataFrame:
        return pd.DataFrame(
            [{"test": r.name, "verdict": r.verdict(), **r.summary()} for r in self.results]
        )


def shuffle_columns(weights: pd.DataFrame, seed: int = 0) -> pd.DataFrame:
    """Reassign each bar's weights to different symbols, keeping the shape.

    The shuffled-ticker placebo. Every bar keeps exactly the same *set* of
    weights — same gross exposure, same concentration, same turnover profile —
    but they are attached to the wrong coins.

    A signal that genuinely picks symbols collapses. A signal that is really
    market timing wearing a cross-sectional costume does **not**, because which
    coin it held never mattered: it was long when the market rose. That
    distinction is invisible in a Sharpe ratio and decisive for whether the
    strategy is what its author thinks it is.
    """
    rng = np.random.default_rng(seed)
    values = weights.to_numpy().copy()
    for row in range(values.shape[0]):
        values[row] = values[row][rng.permutation(values.shape[1])]
    return pd.DataFrame(values, index=weights.index, columns=weights.columns)


def shuffled_ticker_test(
    evaluate: Callable[[pd.DataFrame], float],
    weights: pd.DataFrame,
    observed: float,
    n_permutations: int = 200,
    seed: int = 0,
) -> PermutationResult:
    """Does it matter *which* symbols the strategy picked?"""
    null = np.array(
        [evaluate(shuffle_columns(weights, seed=seed + i)) for i in range(n_permutations)]
    )
    return PermutationResult("shuffled_ticker", observed, null, n_permutations)
