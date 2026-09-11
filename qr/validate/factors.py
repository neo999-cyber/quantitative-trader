"""Factor decomposition: is this an edge, or is it beta wearing a hat?

The row that belongs at the top of every Hypothesis Report. A long-only crypto
strategy in a bull sample posts a fine Sharpe by holding coins while coins went
up, and every gate downstream will happily certify that as real — because it
*is* real, it is just not the strategy's. Regressing the strategy's returns on
BTC (and whatever else) separates the two:

    r_strategy(t) = alpha + beta . r_factors(t) + e(t)

What matters is the **alpha t-statistic**, HAC-corrected, not the R-squared.
A strategy with beta 0.9 to BTC and an alpha t of 0.4 has discovered that BTC
went up. One with beta 0.2 and an alpha t of 3.5 has found something.

`information_ratio` is alpha divided by the volatility of e(t), annualised:
what the strategy earns per unit of the risk the factors do not explain, and
the number to size on. (Note it is *not* the Sharpe of the residuals — OLS
residuals have zero mean by construction, so that quantity is always zero and
means nothing.)
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
import pandas as pd


@dataclass
class Decomposition:
    """One regression of a strategy on a set of factors."""

    alpha_per_period: float
    alpha_annual: float
    alpha_tstat: float
    alpha_pvalue: float
    betas: dict[str, float]
    beta_tstats: dict[str, float]
    r_squared: float
    information_ratio: float
    residual_vol_annual: float
    n_obs: int
    hac_lags: int
    periods_per_year: float

    @property
    def dominant_factor(self) -> str:
        if not self.betas:
            return ""
        return max(self.betas, key=lambda k: abs(self.betas[k]))

    def verdict(self, min_alpha_t: float = 2.0) -> str:
        """Gate-8 style read: does anything survive the factors?"""
        if not np.isfinite(self.alpha_tstat):
            return "FAIL"
        if self.alpha_tstat >= min_alpha_t + 1.0:
            return "PASS"
        return "WARN" if self.alpha_tstat >= min_alpha_t else "FAIL"

    def summary(self) -> dict[str, float]:
        out = {
            "alpha_annual": self.alpha_annual,
            "alpha_tstat": self.alpha_tstat,
            "alpha_pvalue": self.alpha_pvalue,
            "r_squared": self.r_squared,
            "information_ratio": self.information_ratio,
            "residual_vol_annual": self.residual_vol_annual,
            "n_obs": float(self.n_obs),
        }
        out.update({f"beta_{k}": v for k, v in self.betas.items()})
        return out

    def to_frame(self) -> pd.DataFrame:
        rows = [
            {
                "term": "alpha (annualised)",
                "estimate": self.alpha_annual,
                "t_stat": self.alpha_tstat,
                "p_value": self.alpha_pvalue,
            }
        ]
        for name, beta in self.betas.items():
            rows.append(
                {"term": f"beta to {name}", "estimate": beta, "t_stat": self.beta_tstats.get(name, float("nan")), "p_value": float("nan")}
            )
        return pd.DataFrame(rows)


def decompose(
    strategy_returns: pd.Series,
    factors: pd.Series | pd.DataFrame,
    periods_per_year: float = 365.0,
    hac_lags: int | None = None,
) -> Decomposition:
    """Regress a strategy on its factors with HAC standard errors.

    Aligned on the intersection of their indices and dropped where either is
    missing — never filled, because a filled factor return is a fabricated one.
    """
    import statsmodels.api as sm

    y = pd.Series(strategy_returns).astype(float)
    x = factors.to_frame() if isinstance(factors, pd.Series) else factors.copy()
    x = x.astype(float)
    if isinstance(factors, pd.Series) and factors.name is None:
        x.columns = ["factor"]

    joined = pd.concat([y.rename("_y"), x], axis=1, join="inner").dropna()
    if len(joined) < 30:
        raise ValueError(f"need at least 30 overlapping observations, got {len(joined)}")

    y_clean = joined["_y"]
    x_clean = joined.drop(columns=["_y"])
    design = sm.add_constant(x_clean, has_constant="add")

    n = len(joined)
    if hac_lags is None:
        hac_lags = int(math.floor(4 * (n / 100.0) ** (2.0 / 9.0)))
    hac_lags = max(0, min(hac_lags, n - len(design.columns) - 1))

    model = sm.OLS(y_clean, design).fit(
        cov_type="HAC", cov_kwds={"maxlags": hac_lags, "use_correction": True}
    )
    residuals = pd.Series(model.resid, index=joined.index)
    residual_sd = residuals.std(ddof=1)

    names = [c for c in design.columns if c != "const"]
    return Decomposition(
        alpha_per_period=float(model.params["const"]),
        alpha_annual=float(model.params["const"] * periods_per_year),
        alpha_tstat=float(model.tvalues["const"]),
        alpha_pvalue=float(model.pvalues["const"]),
        betas={name: float(model.params[name]) for name in names},
        beta_tstats={name: float(model.tvalues[name]) for name in names},
        r_squared=float(model.rsquared),
        # alpha / residual volatility, annualised. Using the residuals' own
        # mean here would always give zero: OLS puts it in the constant.
        information_ratio=(
            float(model.params["const"] / residual_sd * math.sqrt(periods_per_year))
            if residual_sd > 0
            else float("nan")
        ),
        residual_vol_annual=float(residual_sd * math.sqrt(periods_per_year)),
        n_obs=n,
        hac_lags=hac_lags,
        periods_per_year=periods_per_year,
    )


def benchmark_returns(panel, symbol: str = "BTCUSDT") -> pd.Series:
    """The market factor for a crypto book: BTC's own close-to-close returns.

    Falls back to an equal-weighted average of the panel when BTC is absent,
    which is the right proxy for a universe that does not contain it.
    """
    returns = panel.returns()
    if symbol in returns.columns:
        return returns[symbol].rename(symbol)
    return returns.mean(axis=1, skipna=True).rename("equal_weight")


def factor_table(panel, extra: pd.DataFrame | None = None, btc: str = "BTCUSDT") -> pd.DataFrame:
    """The standard factor set for the crypto trial: BTC, plus anything supplied.

    Kept deliberately small. Every factor added is another chance to explain a
    real edge away, and the report's job is to show what survives the obvious
    one, not to regress alpha into nothing.
    """
    factors = benchmark_returns(panel, btc).to_frame()
    if extra is not None and not extra.empty:
        factors = factors.join(extra, how="left")
    return factors
