# Pre-registration: `p2_insider_cluster_v1` — insider cluster purchases, long-only, exposure-matched

*Drafted 15 September 2026, before any run. Register only after the 100-filing
labelling audit passes and the exposure-matched benchmark exists in the
engine, and before any backtest of this family.*

## Mechanism

Officers and directors buy their own stock with their own money for two
reasons: on a calendar (routine), or because they know something (opportunistic).
Cohen, Malloy and Pomorski (Journal of Finance, 2012) show the routine half
predicts nothing and the opportunistic half carried 82 bps a month of
value-weighted abnormal return in their sample. The information is public the
moment the Form 4 is accepted by EDGAR, which the SEC requires within two
business days of the trade; the drift after publication is what is tested. A
cluster — several insiders buying in the same window — is the cheapest filter
for "something", and it is a rule that a deterministic parser can apply.

## Predicted sign and size

**Positive against exposure-matched buy-and-hold.** Gross event advantage of
**30 to 60 bps per month** over the 60-session hold on the matched-control
event study; net of the frozen cost model, alpha t-statistic **above 2**
against the market factor in gate 8; a $1,000 four-position book with a net
Sharpe **0.3 to 0.6 above** its exposure-matched benchmark. Any net Sharpe
above 2.5 is a reason to look for a publication-time leak, not to celebrate.

## Universe

US common stocks (no ADRs, funds or SPACs) listed on the signal date, price
above $5 and trailing 20-session median dollar volume above $5 million,
resolved point-in-time from QuantConnect's survivorship-free security master.
The eligible set is kept as data, not reconstructed from today's listings.

## Signal

At least **two distinct** officers or directors of the same issuer with
qualifying **open-market purchases** (transaction code P, non-derivative,
not a grant, exercise, gift or 10b5-1 plan transaction, amendments resolved
to the final record) of at least **$25,000 each and $100,000 combined**,
disclosed within **10 trading days**. Routine insiders — those with a
purchase in the same calendar month in each of the prior three years — are
excluded from the count, following the paper. The cluster's time is the
**EDGAR acceptance time** of the filing that completes it.

## Horizon and timing

Enter at the next regular-session open after at least one complete session
has passed since acceptance. Hold **60 sessions**; **20 sessions** is the one
declared variant. Exit on corporate events per the security master.

## Parameter ranges

| Parameter | Range | Swept? |
|---|---|---|
| `hold_sessions` | 20, 60 | yes |
| `min_combined_usd` | 100,000; 250,000 | yes |
| `min_insiders` | 2, 3 | yes |
| `min_each_usd` | 25,000 | fixed |
| `window_days` | 10 | fixed |
| `max_positions` ($1,000 book) | 4 at 25% each | fixed |

**8 variants.** A separate 20-position book is reported for a larger account
so diversification available only at scale does not flatter the $1,000 result.

## Cost model

`alpaca_zero` (to be built before registration): $0 commission, half the
quoted spread from minute quotes, 1 bp of slippage for payment-for-order-flow
routing, whole shares. Gate 2 additionally requires survival at 2× costs. Cost
is a small number here by construction; the binding test is the benchmark.

## Benchmark

**Exposure-matched buy-and-hold** of the eligible universe: equal weight,
scaled bar by bar to the strategy's average gross exposure, remainder in
cash. Not cash alone — a long-only stock book benchmarked to cash passes on
beta in a rising market, which is Programme 1's error in mirror image.

## Labelling audit (before registration)

100 filings sampled without looking at subsequent returns, hand-labelled as
qualifying or not; the parser must reach **95% precision** on qualifying
signals, and every timestamp or amendment ambiguity in the retained sample
must be resolved. The parser decides; any language-model extraction keeps its
supporting text and an uncertainty flag and never trades.

## Out-of-sample period

The final 12 months of the available sample, opened exactly once, after gates
1–8 are complete.

## What would falsify this

- Matched-control event advantage below 15 bps a month, or not distinguishable
  from zero with issuer- and date-clustered errors → the mechanism is not
  there in this period.
- Alpha t-statistic below 2 against the market factor → gate 8: the return is
  beta.
- SPA *p* against the exposure-matched benchmark above 0.5 → gate 5.
- Holdout Sharpe negative or below half the deflated Sharpe → gate 9.
- Incubation (gate 10, at least 63 observations): more than one in ten
  signals skipped for reasons the backtest did not model → the rule is not
  executable as written.

## Prior

The most likely outcome: **a real but small event advantage that the
four-position $1,000 book cannot diversify**, so the event study passes and
the account-level book warns at gate 8 on concentration. That would be a
finding about size, and the 20-position book would say so.

## Amendment, 15 September 2026 — before registration, before any run

1. **The labelling audit passed**: `docs/audit/e5_form4_audit.md`. On 100
   filings from 2025 Q1 labelled without any price data, the parser as
   registered (`qr/data/form4.py`, rules in `exclusion_reasons`) retains 73
   and is right on 72 — precision 98.6%, recall 94.7%. The four dropped true
   positives are 10%-owners buying through their own holding vehicles; the
   rule that drops them (TenPercentOwner buying indirectly) is part of the
   definition and is not to be relaxed after a run. The definition of
   "qualifying" above is extended by the audit's mechanical rules: the
   issuer must carry a trading symbol; institutional reporting owners are
   excluded by name; filing footnotes naming a placement, offering,
   negotiated purchase, exchange or 10b5-1 plan exclude the row; the
   transaction row's own footnotes naming an ESPP, DRIP or 401(k) exclude it.
2. **Cost model**: `CostModel.alpaca_zero()` exists. Its half-spread is a
   stated placeholder of 2 bps until measured from quotes; 1 bp PFOF
   slippage; whole shares, which the runner enforces by flooring each
   position to what $1,000 buys at the previous close (so a $700 share
   cannot be held at 25%). Gate 2's stress doubles both.
3. **Benchmark**: `--benchmark exposure` exists (`exposure_benchmark`): the
   costed equal-weight eligible universe scaled to the best variant's mean
   gross exposure, the remainder compounding at FRED DTB3.
4. **Cluster window**: the loader's `cluster_signals` measures the 10-day
   window on transaction dates in calendar days; the pre-registered 10
   *trading* days is applied at the security master when the prices are
   joined. One signal per issuer per window: a third buyer inside a window
   that already fired does not fire again.
5. **Prices**: QuantConnect's free tier is the venue and needs the owner's
   account (`docs/20` §4.1). No price series for US stocks exists in the
   lake and none will be substituted. The registration stands; the run
   waits for the account.
