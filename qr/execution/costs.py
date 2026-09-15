"""Cost models. Gate 2 (cost survival) is decided here, so the defaults are
deliberately pessimistic and every number is named and sourced.

A trade pays three things, all expressed in basis points of traded notional:

* **fee** — the venue's schedule, per side. Binance spot is a flat 0.10% for
  VIP0 and drops with 30-day volume or by paying fees in BNB (−25%).
* **spread** — crossing the book costs roughly half the quoted spread per side.
  Taker orders always pay it; a maker order that actually rests earns it back,
  which is why `maker` is a separate, and by default unused, path.
* **impact** — the square-root law, Δ = coef · σ · √(Q/V): pushing size through
  a book moves it, superlinearly in participation. At the sizes this platform
  trades it is small, and it is the term that decides capacity.

A perpetual is the same three things plus **funding**, which is not a cost
in this model's sense at all: it is a transfer between the two sides of the
book, paid or received on what is *held* rather than on what is traded, and
it can be income. It therefore enters the backtest's **gross** return
(`qr.research.runner.funding_pnl`), not its cost drag — a carry family earns
nothing else, and a "cost" that is the whole of the return would make gate
2's net-over-gross ratio meaningless. What this model records is whether the
venue settles funding at all (`funding=True`), so the runner knows to look
for the `funding_rate` feature, and the venue's maker/taker schedule, which
for a perp is a fraction of spot's: Binance USDⓈ-M charges a regular user
2.0 / 5.0 bps, Hyperliquid 1.5 / 4.5. See `binance_perp` and
`hyperliquid_perp`.

The fee schedule below is a snapshot and must be re-verified against
<https://www.binance.com/en/fee/schedule> before a cost model is frozen for a
live strategy — `verified_on` records when it last was, and it travels with the
model into the trial log so a Hypothesis Report can never quietly cite an
unverified fee.

`trial_costs()` is the one the crypto trial runs on: VIP0 with the BNB discount
on, checked against the account's own fee panel on 2026-09-11.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
import numpy as np
import pandas as pd

BPS = 1e-4


@dataclass(frozen=True)
class BinanceSpotFees:
    """Binance spot fee schedule, in basis points per side.

    Snapshot of the public VIP schedule. `bnb_discount` applies the 25% rebate
    for paying fees in BNB; `verified_on` is the date a human last checked it.
    """

    maker_bps: float
    taker_bps: float
    tier: str = "VIP0"
    bnb_discount: bool = False
    verified_on: str = "unverified"

    @classmethod
    def tier_table(cls) -> dict[str, tuple[float, float]]:
        return {
            "VIP0": (10.0, 10.0),
            "VIP1": (9.0, 10.0),
            "VIP2": (8.0, 10.0),
            "VIP3": (7.0, 9.0),
            "VIP4": (7.0, 9.0),
            "VIP5": (6.0, 8.0),
            "VIP6": (5.0, 7.0),
            "VIP7": (4.0, 6.0),
            "VIP8": (2.0, 4.0),
            "VIP9": (2.0, 4.0),
        }

    @classmethod
    def for_tier(cls, tier: str = "VIP0", bnb_discount: bool = False, verified_on: str = "unverified"):
        table = cls.tier_table()
        key = tier.upper()
        if key not in table:
            raise ValueError(f"unknown Binance spot tier {tier!r}; known: {sorted(table)}")
        maker, taker = table[key]
        if bnb_discount:
            maker, taker = maker * 0.75, taker * 0.75
        return cls(maker, taker, key, bnb_discount, verified_on)


@dataclass(frozen=True)
class PerpFees:
    """A perpetual-futures venue's schedule, in basis points per side."""

    maker_bps: float
    taker_bps: float
    venue: str
    tier: str = "base"
    verified_on: str = "unverified"


#: Binance USDⓈ-M perpetuals, "regular user" (under $15M 30-day volume and
#: under 25 BNB): 0.020% maker / 0.050% taker, 10% off when fees are paid in
#: BNB. Binance's fee page shows the schedule only to a logged-in account, so
#: this snapshot is from the public schedule as several fee trackers reported
#: it on 2026-09-15 and stays **unverified** until read off the account's own
#: fee panel, exactly as the spot tier was before it was frozen.
BINANCE_PERP_REGULAR = PerpFees(2.0, 5.0, "binance_perp", "regular", "unverified")
BINANCE_PERP_BNB_DISCOUNT = 0.10

#: Hyperliquid perps, base tier (14-day volume under $5M): 0.015% maker /
#: 0.045% taker; maker rebates begin at 0.5% of 14-day maker volume share.
#: Read from https://hyperliquid.gitbook.io/hyperliquid-docs/trading/fees on
#: 2026-09-15.
HYPERLIQUID_PERP_BASE = PerpFees(1.5, 4.5, "hyperliquid_perp", "base", "2026-09-15")


#: The account's own fee panel, read on this date: 30-day volume 0.00 USD, so
#: VIP0, with the BNB fee discount switched on -> 0.07500% maker and taker.
TRIAL_FEE_TIER = "VIP0"
TRIAL_BNB_DISCOUNT = True
TRIAL_FEES_VERIFIED_ON = "2026-09-11"

#: Half the quoted spread, per side. 2 bps is a deliberately pessimistic stand-in
#: for the top-30 USDT pairs, which mostly quote inside 1 bp; it is the number to
#: replace first once the bucket's 1h bars give a real intrabar spread estimate.
#: The ETF trial models the account that exists, not a comfortable one. See
#: `CostModel.etf_trial` for why this single number decides what gate 2 means.
ETF_TRIAL_EQUITY = 1_000.0

#: The long-short trial prices against $10,000, not $1,000: a US margin account
#: may not short below $2,000 of equity, so the account the ETF trial models
#: cannot hold a short book at all.
LONG_SHORT_TRIAL_EQUITY = 10_000.0

TRIAL_HALF_SPREAD_BPS = 2.0


@dataclass(frozen=True)
class CostModel:
    """Per-side transaction costs in basis points of traded notional.

    `charge()` takes a turnover matrix — the absolute change in each position's
    weight at each bar — and returns the portfolio return drag per bar.
    """

    fee_bps: float = 10.0
    half_spread_bps: float = 2.0
    #: Per-share commission in dollars, with a per-order floor and a cap as a
    #: share of notional. Zero means a purely proportional venue, which is what
    #: a crypto exchange is; a US equity broker is not, and the difference
    #: decides whether a small account can trade a basket at all. See
    #: `commission_bps`.
    per_share_usd: float = 0.0
    min_commission_usd: float = 0.0
    max_commission_pct: float = 0.0
    #: Annual stock-borrow fee charged on the *short* side, in basis points of
    #: short notional. Zero for a long-only book and for crypto spot, where
    #: there is nothing to borrow. A short leg costs money to hold even when it
    #: never trades, which is a cost with no turnover behind it — the one kind
    #: this model could not previously express.
    borrow_bps_per_year: float = 0.0
    impact_coef: float = 1.0
    #: Charge impact only for what it costs *beyond* crossing the spread,
    #: which `linear_bps` already charges. See `impact_bps`. False restores the
    #: unmodified square-root law, which double-counts.
    net_impact_against_spread: bool = True
    use_maker: bool = False
    #: Whether the venue settles funding on held positions. True for a
    #: perpetual; False for spot, where nothing is paid for holding. The
    #: runner reads this to decide whether the panel's `funding_rate` feature
    #: is a cash flow (perp) or merely a feature (spot). Funding is **not**
    #: charged by `charge()` — see the module docstring for why it is gross.
    funding: bool = False
    #: Execution slippage beyond the quoted half-spread, in basis points per
    #: side: what a payment-for-order-flow wholesaler's fill gives up against
    #: the NBBO midpoint. Zero everywhere except `alpaca_zero`, where it is the
    #: only execution cost a $0-commission broker has left. Reported in the
    #: `spread` component: it is a spread cost by nature, and it stresses
    #: with it.
    slippage_bps: float = 0.0
    #: Whether orders are placed in whole shares. True for a venue whose
    #: on-close (`cls`) orders must be whole shares (Alpaca); the runner then
    #: floors every held position to what the account can actually buy at
    #: that bar's price, so a $250 slice of a $700 share is not held at all.
    whole_shares: bool = False
    multiplier: float = 1.0
    name: str = "binance_spot_vip0_taker"
    verified_on: str = "unverified"

    @classmethod
    def binance_spot(
        cls,
        tier: str = "VIP0",
        bnb_discount: bool = False,
        half_spread_bps: float = 2.0,
        impact_coef: float = 1.0,
        verified_on: str = "unverified",
    ) -> "CostModel":
        fees = BinanceSpotFees.for_tier(tier, bnb_discount, verified_on)
        suffix = "_bnb" if bnb_discount else ""
        return cls(
            fee_bps=fees.taker_bps,
            half_spread_bps=half_spread_bps,
            impact_coef=impact_coef,
            name=f"binance_spot_{fees.tier.lower()}{suffix}_taker",
            verified_on=verified_on,
        )

    @classmethod
    def binance_perp(
        cls,
        bnb_discount: bool = True,
        half_spread_bps: float = 1.0,
        use_maker: bool = False,
        impact_coef: float = 1.0,
        verified_on: str | None = None,
    ) -> "CostModel":
        """Binance USDⓈ-M perpetuals for a regular user. **Verify before freezing.**

        Taker by default: a maker order that rests is cheaper and earns the
        spread back, but a backtest that assumes every order rests is
        assuming fills it was never promised. `use_maker=True` is the
        pre-registered exception for a family whose entries are limit orders
        by construction and whose gate 10 forward record will show its actual
        fill rate.

        1 bp of half-spread is the top-30 USDT perps, which quote inside that
        most of the day; it is pessimistic for BTC and ETH and about right for
        rank 30. Funding is settled (`funding=True`) and enters gross.
        """
        fees = BINANCE_PERP_REGULAR
        maker, taker = fees.maker_bps, fees.taker_bps
        if bnb_discount:
            maker, taker = maker * (1 - BINANCE_PERP_BNB_DISCOUNT), taker * (1 - BINANCE_PERP_BNB_DISCOUNT)
        suffix = "_bnb" if bnb_discount else ""
        side = "maker" if use_maker else "taker"
        return cls(
            fee_bps=maker if use_maker else taker,
            half_spread_bps=half_spread_bps,
            impact_coef=impact_coef,
            use_maker=use_maker,
            funding=True,
            name=f"binance_perp_{fees.tier}{suffix}_{side}",
            verified_on=verified_on or fees.verified_on,
        )

    @classmethod
    def hyperliquid_perp(
        cls,
        half_spread_bps: float = 1.0,
        use_maker: bool = False,
        impact_coef: float = 1.0,
        verified_on: str | None = None,
    ) -> "CostModel":
        """Hyperliquid perps at the base tier, taker by default. Funding enters gross."""
        fees = HYPERLIQUID_PERP_BASE
        side = "maker" if use_maker else "taker"
        return cls(
            fee_bps=fees.maker_bps if use_maker else fees.taker_bps,
            half_spread_bps=half_spread_bps,
            impact_coef=impact_coef,
            use_maker=use_maker,
            funding=True,
            name=f"hyperliquid_perp_{fees.tier}_{side}",
            verified_on=verified_on or fees.verified_on,
        )

    @classmethod
    def carry_pair(cls, spot: "CostModel | None" = None, perp: "CostModel | None" = None) -> "CostModel":
        """One unit of long spot / short perp (`qr/data/carry.py`).

        A unit's turnover trades both legs for the same notional, so its
        proportional cost is the two legs' costs added: fee plus fee, half-
        spread plus half-spread. The perp leg settles funding, the spot leg
        does not, and the unit's panel already carries the rate with the
        short leg's sign, so `funding=True` here means "settle what the
        panel says". Impact is charged once, on the thinner leg's volume,
        which is what the unit panel's `quote_volume` is.
        """
        spot = spot or cls.trial()
        perp = perp or cls.binance_perp()
        if spot.per_share_usd or perp.per_share_usd:
            raise ValueError("a carry unit is priced on two proportional venues, not per share")
        return cls(
            fee_bps=spot.fee_bps + perp.fee_bps,
            half_spread_bps=spot.half_spread_bps + perp.half_spread_bps,
            impact_coef=max(spot.impact_coef, perp.impact_coef),
            use_maker=False,
            funding=True,
            name=f"carry[{spot.name}+{perp.name}]",
            verified_on=min(spot.verified_on, perp.verified_on, key=lambda v: (v != "unverified", v)),
        )

    @classmethod
    def alpaca_zero(
        cls,
        half_spread_bps: float = 2.0,
        slippage_bps: float = 1.0,
        impact_coef: float = 1.0,
        verified_on: str | None = None,
    ) -> "CostModel":
        """Alpaca for US equities at $0 commission (`docs/20`, §2 and §6).

        No commission, no per-order floor, no per-share charge: the cost that
        decided Programme 1's ETF families (42 bps a leg on an $83 order) is
        not there. What remains is the half-spread, 1 bp of PFOF slippage
        against the midpoint, and impact. The 2 bps half-spread is a stated
        placeholder for large-cap US stocks until it is measured from quotes
        (the plan's "half-spread from quotes"); it is pessimistic for SPY and
        the megacaps and optimistic below the top 500, and every family that
        runs on it says so in its pre-registration. Whole shares for on-close
        orders (`cls`, whole shares, before 15:50 ET per Alpaca's order docs,
        read 2026-09-15); fractional is allowed for other orders but the
        model takes the whole-share constraint as binding because the stock
        families trade at the close. Alpaca's fee schedule ($0) and the
        `cls` rule were read on 2026-09-15; the slippage figure is the
        plan's, not measured — hence `verified_on` says so.
        """
        return cls(
            fee_bps=0.0,
            half_spread_bps=half_spread_bps,
            slippage_bps=slippage_bps,
            per_share_usd=0.0,
            min_commission_usd=0.0,
            max_commission_pct=0.0,
            impact_coef=impact_coef,
            whole_shares=True,
            name="alpaca_us_equity_zero_commission",
            verified_on=verified_on or "2026-09-15 (commission and cls rule; spread and slippage unmeasured)",
        )

    @classmethod
    def etf_trial(cls, equity: float = ETF_TRIAL_EQUITY) -> "CostModel":
        """The ETF trial's frozen cost model. Every gate is judged against this.

        IBKR Tiered against the account that actually exists: **$1,000**. That
        choice is the trial's most consequential one and it is deliberate. At
        this size the $0.35 per-order minimum, not the spread and not impact,
        is the binding cost — one leg of a twelve-ETF basket is an $83 order
        paying 42 bps, four times what a Binance taker pays. At $100,000 the
        same trade costs 0.42 bps and the basket is twenty times cheaper than
        crypto.

        So gate 2 is being asked a different question from the crypto trial's.
        There it was "does the edge survive the venue"; here it is "does the
        edge survive *this account*". A family that fails gate 2 at $1,000 and
        would pass at $10,000 has not been shown to lack an edge — it has been
        shown to be unaffordable, and the report must say which. The capacity
        ladder in gate 2 reports both, so the crossover is visible rather than
        inferred.
        """
        return replace(cls.ibkr_etf(), name=f"ibkr_us_etf_tiered_{int(equity)}usd")

    @classmethod
    def etf_long_short(
        cls, equity: float = LONG_SHORT_TRIAL_EQUITY, borrow_bps_per_year: float = 50.0
    ) -> "CostModel":
        """The long-short ETF trial's frozen cost model.

        `etf_trial()` plus a stock-borrow fee, and priced against **$10,000**
        rather than $1,000 for a reason that is a constraint and not a
        preference: a US margin account requires $2,000 of equity before it may
        short at all, so the $1,000 the trial models cannot hold this book in
        any size. Pricing it at the account that exists would be pricing a
        trade that cannot be placed.

        50 bps a year is a general-collateral rate for liquid US ETFs and is
        **unverified**, like the commission schedule beside it. Two of this
        basket — HYG and DBC — are periodically harder to borrow than that, and
        a fee that moves is a cost this model treats as a constant. Where the
        verdict turns on borrow rather than on commission, say so rather than
        reporting the number.
        """
        model = cls.ibkr_etf()
        return replace(
            model,
            borrow_bps_per_year=borrow_bps_per_year,
            name=f"ibkr_etf_long_short_{int(equity)}",
        )

    @classmethod
    def ibkr_etf(
        cls,
        per_share_usd: float = 0.0035,
        min_commission_usd: float = 0.35,
        max_commission_pct: float = 0.01,
        half_spread_bps: float = 1.0,
        verified_on: str = "unverified",
    ) -> "CostModel":
        """IBKR US equities/ETFs, Tiered. **Verify before freezing a trial.**

        The snapshot is Tiered pricing: $0.0035 a share, a $0.35 order minimum
        and a 1% of notional cap, plus about 1 bp of half-spread on a liquid US
        ETF. `verified_on` stays "unverified" until a human has checked it
        against their own account, exactly as the Binance tier was — an
        unverified cost model must never reach a Hypothesis Report.

        The structure matters more than the level here, and it is the opposite
        of crypto's. A Binance taker pays a fixed 7.5 bps whether the order is
        $10 or $10,000. IBKR charges per *share* with a floor per *order*, so
        the cost in basis points depends on the share price and collapses or
        explodes with order size: 0.05 bps on a $700 slice of SPY, and 42 bps
        on the same trade at $83 — which is what one leg of a twelve-ETF
        basket looks like in a $1,000 account. The commission minimum, not the
        spread and not impact, is the binding cost at that size.
        """
        return cls(
            fee_bps=0.0,
            half_spread_bps=half_spread_bps,
            per_share_usd=per_share_usd,
            min_commission_usd=min_commission_usd,
            max_commission_pct=max_commission_pct,
            name="ibkr_us_etf_tiered",
            verified_on=verified_on,
        )

    @classmethod
    def trial(cls, half_spread_bps: float = TRIAL_HALF_SPREAD_BPS, impact_coef: float = 1.0) -> "CostModel":
        """The crypto trial's frozen cost model. Every gate is judged against this.

        VIP0 + BNB discount = 7.5 bps of fee per side, plus the half-spread, so
        9.5 bps per side and 19 bps for a round trip. Gate 2 additionally
        requires the edge to survive `stressed(2.0)`, i.e. 38 bps a round trip.
        """
        return cls.binance_spot(
            tier=TRIAL_FEE_TIER,
            bnb_discount=TRIAL_BNB_DISCOUNT,
            half_spread_bps=half_spread_bps,
            impact_coef=impact_coef,
            verified_on=TRIAL_FEES_VERIFIED_ON,
        )

    @property
    def linear_bps(self) -> float:
        """Everything that does not depend on size: fee, half-spread, slippage."""
        fee = self.fee_bps  # taker; a maker path would net the spread back
        return self.multiplier * (fee + (0.0 if self.use_maker else self.half_spread_bps) + self.slippage_bps)

    def stressed(self, multiplier: float) -> "CostModel":
        """Gate 2 asks whether the edge survives 2x costs. This is that knob."""
        return replace(self, multiplier=self.multiplier * float(multiplier))

    def impact_bps(
        self,
        turnover_notional: pd.DataFrame | np.ndarray,
        adv_notional: pd.DataFrame | np.ndarray,
        volatility: pd.DataFrame | np.ndarray,
    ) -> np.ndarray:
        """Square-root impact: coef · σ · √(traded / ADV), in basis points.

        `volatility` is a per-bar return standard deviation (a fraction, not
        bps). Bars with no ADV get no impact charge and no free lunch either:
        they should have been filtered out by the liquidity screen upstream.

        **The half-spread is netted off**, because `linear_bps` has already
        charged it and the √-law's small-order regime *is* the spread. Without
        that, the law is extrapolated to participations a thousandfold below
        anything it was fitted over, where its concavity makes the marginal
        cost of the first dollar traded unbounded: at p = 1e-5 it still asks
        σ·0.003, about 2 bps on a 5%/day coin, for an order a thousand times
        smaller than the top of book. A $500 market order in BTCUSDT does not
        move the price; it pays the spread, and it pays it once. Charging both
        is what made the trial's first capacity estimate read $10,000 for a
        book trading pairs that turn over nine figures a day.

        So:

            impact(p) = max(0, coef · σ · √p − half_spread)

        Zero for any order small enough to sit inside the quoted spread,
        continuous and monotone through the point where it stops being zero,
        and asymptotically the √-law itself once the term that matters is
        large. It introduces no new parameter — `half_spread_bps` is already
        named, sourced and used — and it can only ever lower the charge, so no
        gate is made easier to pass than the unmodified model would have it.

        What it does **not** fix is `impact_coef`, which is 1.0 because that is
        the round number the literature clusters around and not because
        anything here was fitted to a fill. Everything this function returns
        scales with it, and so does every capacity figure downstream.
        """
        traded = np.asarray(turnover_notional, dtype=float)
        adv = np.asarray(adv_notional, dtype=float)
        sigma = np.asarray(volatility, dtype=float)
        with np.errstate(divide="ignore", invalid="ignore"):
            participation = np.where(adv > 0, traded / adv, 0.0)
        participation = np.nan_to_num(participation, nan=0.0, posinf=0.0)
        sigma = np.nan_to_num(sigma, nan=0.0, posinf=0.0)

        law = self.impact_coef * sigma * np.sqrt(np.maximum(participation, 0.0)) / BPS
        if self.net_impact_against_spread and not self.use_maker:
            law = np.maximum(law - self.half_spread_bps, 0.0)
        return self.multiplier * law

    def commission_bps(
        self,
        turnover: pd.DataFrame,
        equity: pd.Series | float,
        prices: pd.DataFrame,
    ) -> pd.DataFrame:
        """Per-order commission, in basis points of that order's notional.

            commission = clip(per_share x shares, min_per_order, max_pct x notional)

        This is the cost structure of a share-traded venue and it does not
        reduce to a basis-point fee, which is why it needs prices and an equity
        level rather than a rate. Two consequences the crypto trial never had
        to face:

        * **Cheap in basis points when the share price is high.** $0.0035 on a
          $700 share of SPY is 0.05 bps, twenty times cheaper than Binance's
          taker fee.
        * **Ruinous when the order is small.** The per-order minimum is a fixed
          dollar amount, so rebalancing an $83 position — one leg of a
          twelve-name basket in a $1,000 account — pays 42 bps whatever the
          share price is. A strategy that rebalances weekly pays that 52 times
          a year on every leg.

        The 1% cap is the broker's, and it bites exactly where the minimum does.
        """
        eq = pd.Series(equity, index=turnover.index) if np.isscalar(equity) else equity.reindex(turnover.index)
        notional = turnover.mul(eq, axis=0)
        price = prices.reindex_like(turnover)
        with np.errstate(divide="ignore", invalid="ignore"):
            shares = notional.div(price.where(price > 0))
        commission = (shares.abs() * self.per_share_usd).fillna(0.0)
        if self.min_commission_usd > 0:
            commission = commission.clip(lower=self.min_commission_usd)
        if self.max_commission_pct > 0:
            commission = np.minimum(commission, notional.abs() * self.max_commission_pct)
        commission = pd.DataFrame(
            np.asarray(commission), index=turnover.index, columns=turnover.columns
        )
        # No order, no commission. Without this the minimum is charged on every
        # bar for every symbol the strategy is merely holding.
        commission = commission.where(turnover.abs() > 1e-12, 0.0)
        with np.errstate(divide="ignore", invalid="ignore"):
            out = commission.div(notional.abs().where(notional.abs() > 0)) / BPS
        return out.fillna(0.0) * self.multiplier

    def charge(
        self,
        turnover: pd.DataFrame,
        equity: pd.Series | float | None = None,
        adv_notional: pd.DataFrame | None = None,
        volatility: pd.DataFrame | None = None,
        prices: pd.DataFrame | None = None,
        short_exposure: pd.Series | None = None,
        periods_per_year: float = 365.0,
    ) -> pd.Series:
        """Return drag per bar, as a positive fraction of equity.

        `turnover` is |Δweight| per asset per bar. With `equity`, `adv_notional`
        and `volatility` supplied, the square-root impact term is added on top
        of the linear one; without them the model is linear, which is the right
        default while position sizes are small relative to Binance's book.

        With `prices` and a per-share schedule, the proportional fee is replaced
        by a real per-order commission — see `commission_bps`. A model with no
        per-share schedule ignores `prices` entirely, so the crypto path is
        untouched.
        """
        return self.components(
            turnover, equity, adv_notional, volatility, prices, short_exposure, periods_per_year
        ).sum(axis=1).rename("cost")

    def components(
        self,
        turnover: pd.DataFrame,
        equity: pd.Series | float | None = None,
        adv_notional: pd.DataFrame | None = None,
        volatility: pd.DataFrame | None = None,
        prices: pd.DataFrame | None = None,
        short_exposure: pd.Series | None = None,
        periods_per_year: float = 365.0,
    ) -> pd.DataFrame:
        """The same drag, split into the four things it is made of.

        `charge` is this, summed. Gate 2 can say "costs eat 62% of gross return"
        and nothing more, which stopped being a sufficient answer the moment
        there was more than one kind of cost: a per-order commission floor, a
        spread and a borrow fee fail for different reasons and have different
        remedies — a bigger account, a more liquid instrument, and a cheaper
        short respectively. Naming the dominant one turns a verdict into a
        direction.
        """
        index = turnover.index
        zero = pd.Series(0.0, index=index)
        traded = turnover.sum(axis=1)
        if self.per_share_usd > 0 and prices is not None and equity is not None:
            spread = traded * self.multiplier * (self.half_spread_bps + self.slippage_bps) * BPS
            commission = (turnover * self.commission_bps(turnover, equity, prices)).sum(axis=1) * BPS
        else:
            # A proportional venue: `linear_bps` is the fee and the half-spread
            # together, and they are separable here only because both are rates.
            fee_bps = self.multiplier * self.fee_bps
            spread_bps = (0.0 if self.use_maker else self.multiplier * self.half_spread_bps) + (
                self.multiplier * self.slippage_bps
            )
            commission = traded * fee_bps * BPS
            spread = traded * spread_bps * BPS

        impact = zero.copy()
        if adv_notional is not None and volatility is not None and equity is not None:
            eq = pd.Series(equity, index=index) if np.isscalar(equity) else equity.reindex(index)
            traded_notional = turnover.mul(eq, axis=0)
            imp_bps = self.impact_bps(
                traded_notional, adv_notional.reindex_like(turnover), volatility.reindex_like(turnover)
            )
            frame = pd.DataFrame(imp_bps, index=index, columns=turnover.columns)
            impact = (turnover * frame).sum(axis=1) * BPS

        borrow = self.borrow_cost(short_exposure, periods_per_year).reindex(index).fillna(0.0)
        return pd.DataFrame(
            {"commission": commission, "spread": spread, "impact": impact, "borrow": borrow},
            index=index,
        )

    def borrow_cost(
        self, short_exposure: pd.Series | None, periods_per_year: float = 365.0
    ) -> pd.Series:
        """Per-bar drag from holding a short book, as a fraction of equity.

        `short_exposure` is the gross short weight held on each bar — the sum
        of the negative weights, unsigned. The fee accrues on the position
        rather than on the trade, so a long-short book that never rebalances
        still pays every day it is open: the first cost in this model with no
        turnover behind it.

        Short proceeds earning interest is deliberately **not** modelled. A
        real short credit would offset part of this, so omitting it makes the
        strategy look slightly worse than it is, which is the direction an
        unverified cost assumption should err in.
        """
        if not self.borrow_bps_per_year or short_exposure is None or periods_per_year <= 0:
            return pd.Series(dtype=float)
        per_bar = self.borrow_bps_per_year * BPS / periods_per_year
        return short_exposure.abs() * per_bar

    def describe(self) -> dict[str, float | str | bool]:
        return {
            "name": self.name,
            "fee_bps": self.fee_bps,
            "half_spread_bps": self.half_spread_bps,
            "impact_coef": self.impact_coef,
            "per_share_usd": self.per_share_usd,
            "min_commission_usd": self.min_commission_usd,
            "max_commission_pct": self.max_commission_pct,
            "net_impact_against_spread": self.net_impact_against_spread,
            "use_maker": self.use_maker,
            "settles_funding": self.funding,
            "multiplier": self.multiplier,
            "linear_bps_per_side": self.linear_bps,
            "fees_verified_on": self.verified_on,
        }
