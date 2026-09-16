# Pre-registration: `p2_late_day_momentum_v1` — late-day hedging momentum, long-only, QQQ

*Written 16 September 2026, before any run. Registered after the
`intraday-xnas` panel was built and its unconditional QA read (2,094
sessions, 2018-05-01 → 2026-08-31, mean last-half-hour move +0.43 bps a
session), and before any conditional number was looked at.*

## Mechanism

Leveraged ETFs must rebalance to their target leverage at the close, and
they rebalance in the direction of the day: a +1% day makes a 3× fund buy
before the bell, a −1% day makes it sell, and inverse funds trade the same
way. Option market-makers short gamma hedge the same way in the last half
hour. Baltussen, Da, Lammers and Martens ("Hedging demand and market
intraday momentum", JFE 2021) show the last half hour goes with the day
across 60+ futures markets over decades, scaled by leveraged-ETF assets and
the day's move, and reverting over the following days. The forced party is
the fund, whose order is a function of the day's return and its AUM, not of
price. QQQ carries the largest leveraged-ETF complex of any single index
(TQQQ, SQQQ, QLD, QID), so the demand is largest there.

Long-only here (the account cannot short below $2,000): the family buys
at the decision time on up days and sells at the close; the down-day short
is the natural pair, pre-registered for later, not claimed here.

## Predicted sign and size

**Positive against cash, with a small gross number and a costs verdict.**
Gross last-half-hour return on days the rule fires **2 to 6 bps per trade**
(the paper's unconditional 1–2 bps, larger on large-move days), rising with
the threshold `k`; net of the frozen 6-bps round trip **the base variant
(k = 0) loses money** and only the high-threshold variants can be positive;
net Sharpe of the best variant **between −0.5 and +0.5**. This is a family
that the cost model is expected to kill; the mechanism's existence is what
the gross numbers test, and its tradeability at $0 commission and a
2-bps half-spread is what gate 2 tests. A net Sharpe above 1.5 is a reason
to look for a leak (a minute bar stamped before its time).

## Data and instrument

Databento `XNAS.ITCH` `ohlcv-1m` for QQQ (bought 16 September 2026 as part
of the 31-name pull, $21.94), regular hours only. Market `intraday-xnas`,
two bars a session: the **day bar** (09:30 → decision time) whose
`ret_to_decision` is the signal, and the **late bar** (decision → 16:00)
whose return the position earns. The synthetic price is continuous across
both and drops the overnight gap, which the rule never holds. Decision
price = close of the last minute bar at or before the decision time; exit
= the last regular minute's close, executed as MOC. Early-close sessions
yield no bars.

## Universe

`qqq`: QQQ alone (a fixed basket). SPY and IWM are the extension once
their minute bars are bought (~$1.50); not in this hypothesis.

## Rule and parameters

On the day bar: if `ret_to_decision ≥ k`, target 1.0 (the whole $1,000
book, whole shares; QQQ at $400–700 is one or two shares); else 0. On the
late bar: target 0. The runner's shift holds the day-bar target over the
late bar and nothing overnight.

| Parameter | Range | Swept? |
|---|---|---|
| `k` (day's return to the decision) | 0, 0.0025, 0.005, 0.01 | yes |
| `decision` | 15:30 (panel as built); 15:00 as a second panel if 15:30 passes gate 2 | fixed here |
| `side` | long | fixed |

**4 variants.**

    qr gates --family late_day_momentum --hypothesis p2_late_day_momentum_v1 \
      --market intraday-xnas --costs alpaca --basket qqq --equity 1000 \
      --benchmark cash --risk-free fred --end 2025-08-31 \
      --grid 'k=[0,0.0025,0.005,0.01]' --param side=long --all-gates --upto 8

then once, `--holdout-start 2025-09-01 --upto 11`, only if gates 1–8 pass.
The benchmark is **cash**: the book holds the market for half an hour a
day at most; exposure-matched buy-and-hold at ~3% invested is cash within
rounding, and the pre-registered comparator is stated as cash to be plain.

## Cost model

`CostModel.alpaca_zero()`: 3 bps a side, 6 bps a round trip, 12 stressed.
Every fire is a round trip.

## Controls

- **Reverse-day control** (`side=reverse`, registered as
  `p2_late_day_momentum_v1_reverse`): buy on days *down* by at least `k`.
  The mechanism says this loses; if it earns as much, the family is the
  last half hour's drift, not the hedging demand.
- Hold cash: the benchmark itself.

## Out-of-sample period

1 September 2025 → 31 August 2026, opened once after gates 1–8.

## What would falsify this

- Gross return per fire below 2 bps → the mechanism is not measurable
  here at this resolution.
- Net negative at 1× costs for every variant → gate 2: a real but
  untradeable effect at this account (the expected outcome).
- No monotone relation between `k` and the gross return per fire → the
  day's move is not the driver.
- The reverse control earning as much gross as the family.

## Prior

**FAIL at gate 2**: the effect exists at a few basis points, the 6-bps
round trip takes it; the finding worth keeping is the gross number per
fire and whether it grows with `k`, for the day shorting exists.
