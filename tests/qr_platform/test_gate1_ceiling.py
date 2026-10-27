"""Gate 1's plausibility ceiling reads the forecast, not the income.

On 27 October 2026 the ceiling (8.0) failed the 2020–24 carry holding — gross
Sharpe 9.343 at lags 0, 1 and 2, spike z 0.0, funding 101% of gross — with the
message "the signal is reading the bar it predicts" (`docs/35` §8). A hedged
unit's funding over years of near-zero variance is a yield, not a leak, and the
lag probe had found none. These tests build that book on a synthetic unit
(`test_cot.py`, `test_carry.py`), on both engines, and check the three cases
the gate now tells apart: income over the ceiling, a price peek on the same
venue, and a flat profile with no funding at all.
"""
import numpy as np
import pandas as pd
import pytest

from qr.data.carry import carry_frames
from qr.data.panel import Panel
from qr.execution.costs import CostModel
from qr.research.runner import leakage_probe, run_backtest
from qr.strategies.base import Strategy
from qr.strategies.cot import CarryCrowdingTimer
from qr.strategies.library import BuyAndHold
from qr.validate.gates import FAIL, WARN, GateContext, gate_1_data_integrity

UTC = "UTC"
ENGINES = ("weights", "ledger")


def _bars(index, px):
    return pd.DataFrame(
        {"open": px, "high": px * 1.001, "low": px * 0.999, "close": px, "volume": 1e3, "quote_volume": 1e3 * px, "trades": 10},
        index=index,
    )


def _yield_unit(days=730, funding=5e-4, basis_noise=2e-4, seed=0) -> Panel:
    """A spot-long/perp-short unit whose only return is its funding.

    The spot leg never moves and the basis wanders by a few basis points, so
    the unit's price component is noise and its gross is the funding: 18% a
    year on a book with well under 1% of volatility, which is a gross Sharpe
    far above the ceiling at every lag — the 2020–24 holding, exaggerated.
    """
    rng = np.random.default_rng(seed)
    index = pd.date_range("2023-01-01", periods=days, freq="D", tz=UTC)
    spot = np.full(days, 100.0)
    perp = spot * (1.001 + rng.normal(0.0, basis_noise, days))
    unit = carry_frames(
        _bars(index, spot), _bars(index, perp), pd.DataFrame({"funding_rate": np.full(days, funding)}, index=index)
    )
    unit["cot_crowd"] = 0.1
    unit["cot_pct_52"] = 50.0
    unit["cot_pct_26"] = 50.0
    unit.index.name = "open_time"
    return Panel.from_frames({"BTCUSDT": unit})


class PricePeek(Strategy):
    """Holds the unit on the bars whose price goes up: a leak inside the signal."""

    family = "oracle"

    def target_weights(self, panel, universe=None):
        tomorrow = panel.returns().shift(-1)
        return self.normalise(self.mask_to_universe((tomorrow > 0).astype(float), panel, universe))


def _context(panel, strategy, costs, engine="weights") -> GateContext:
    kwargs = {"engine": engine} if engine != "weights" else {}
    return GateContext(
        hypothesis_id="h",
        panel=panel,
        strategy=strategy,
        costs=costs,
        result=run_backtest(panel, strategy, costs, None, **kwargs),
        permutations=5,
        **kwargs,
    )


@pytest.mark.parametrize("engine", ENGINES)
def test_a_yield_book_over_the_ceiling_warns_and_is_not_called_a_leak(engine):
    holding = CarryCrowdingTimer(control="always_in")
    result = gate_1_data_integrity(_context(_yield_unit(), holding, CostModel.carry_pair(), engine))

    # The measurement the old rule failed on is still there, and still over the ceiling.
    assert result.stats["lag1_gross_sharpe"] > 8.0
    assert abs(result.stats["spike_z"]) < 1.0
    # ...but the forecast is nothing and the gross is the funding.
    assert abs(result.stats["lag1_price_sharpe"]) < 1.0
    assert result.stats["carry_share_of_gross"] == pytest.approx(1.0, abs=0.02)

    assert result.verdict == WARN
    assert "above the 8.0 ceiling" in result.detail
    assert "funding income" in result.detail and "yield book" in result.detail
    assert "reading the bar it predicts" not in result.detail
    assert "no lag spike" in result.detail


@pytest.mark.parametrize("engine", ENGINES)
def test_a_price_peek_on_the_same_venue_still_fails_the_ceiling(engine):
    """Taking the funding out of the ceiling must not let a leak hide behind it."""
    panel = _yield_unit(basis_noise=1e-3)
    result = gate_1_data_integrity(_context(panel, PricePeek(), CostModel.carry_pair(), engine))

    assert result.verdict == FAIL
    assert result.stats["lag1_price_sharpe"] > 8.0
    assert result.stats["spike_z"] > 3.0
    # The message names the number the ceiling read and the shape the probe found.
    assert result.detail.startswith("price-return Sharpe")
    assert "above the 8.0 ceiling" in result.detail
    assert "reading the bar it predicts" in result.detail


def test_a_flat_profile_over_the_ceiling_fails_without_claiming_a_leak():
    """No funding, a deterministic drift: the Sharpe is implausible at every lag.

    The ceiling still blocks — the 18 September 2026 cash-interest case was
    exactly this shape and was real — but the gate can only report what it
    measured: the ceiling, and a lag profile with no spike in it.
    """
    rng = np.random.default_rng(1)
    index = pd.date_range("2023-01-01", periods=730, freq="D", tz=UTC)
    px = 100.0 * np.cumprod(1.0 + 5e-4 + rng.normal(0.0, 1e-4, 730))
    frame = _bars(index, px)
    frame.index.name = "open_time"
    panel = Panel.from_frames({"XUSDT": frame})

    result = gate_1_data_integrity(_context(panel, BuyAndHold(), CostModel.trial()))

    assert result.verdict == FAIL
    assert result.stats["lag1_gross_sharpe"] > 8.0
    assert abs(result.stats["spike_z"]) < 1.0
    # No funding settles here, so the forecast is the whole gross.
    assert result.stats["lag1_price_sharpe"] == result.stats["lag1_gross_sharpe"]
    assert np.isnan(result.stats["carry_share_of_gross"])
    assert result.detail.startswith("gross Sharpe")
    assert "above the 8.0 ceiling" in result.detail
    assert "places no leak inside the signal" in result.detail
    assert "reading the bar it predicts" not in result.detail


def test_the_probe_reports_the_price_sharpe_beside_gross():
    """`price_sharpe` is gross with the funding taken back out, per lag."""
    panel = _yield_unit()
    probe = leakage_probe(panel, CarryCrowdingTimer(control="always_in"), CostModel.carry_pair())
    assert list(probe.columns) == ["sharpe", "gross_sharpe", "price_sharpe"]
    assert (probe["gross_sharpe"] > 8.0).all()
    assert (probe["price_sharpe"].abs() < 1.0).all()
    assert probe.attrs["honest_price_sharpe"] == probe.loc[1, "price_sharpe"]
    assert probe.attrs["carry_share_of_gross"] == pytest.approx(1.0, abs=0.02)

    # On a venue that settles no funding the two columns are the same number.
    spot_only = leakage_probe(panel, CarryCrowdingTimer(control="always_in"), CostModel(fee_bps=0.0, half_spread_bps=0.0))
    assert spot_only["price_sharpe"].equals(spot_only["gross_sharpe"])
    assert np.isnan(spot_only.attrs["carry_share_of_gross"])
