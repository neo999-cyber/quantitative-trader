# Brief for the build session (Claude Opus 5)

*Written 15 September 2026 by the Programme 2 planning session. Paste this
whole file as the first message of a new session opened in
`~/quantitative-trader`. It is the only context that session needs.*

## Who you are and what this is

You are running **Programme 2** of `quantitative-trader`: a pre-registered,
gate-validated search for a tradeable edge from a small account. Programme 1
finished with nine failed families and a handover (`docs/19_HANDOVER.md`,
verdict in `docs/18`). Programme 2's plan, the owner's decisions, the
week-1 log and the plain-steps list are in **`docs/20_PROGRAMME_2.md` — read
it first, all of it.** Then `CLAUDE.md` for the repo's conventions.

The owner is Anoop, in Dubai, non-technical, watching token spend. Keep
every reply short, factual, and free of hedging. Report outcomes as they
are: a failed gate is a result, not a problem.

## Environment facts (verified 15 Sep 2026)

- Repo: `~/quantitative-trader`, branch `claude/funny-faraday-nizzck`,
  pushed to GitHub. Commit after every stage with author
  `neo999-cyber <276883747+neo999-cyber@users.noreply.github.com>`
  (use `git -c user.email=... -c user.name=neo999-cyber commit`); push to
  the same branch after each commit.
- Python: `.venv/bin/python` (3.14), `.venv/bin/qr`, tests with
  `.venv/bin/python -m pytest -q` (no network; ~770 tests, all green).
- **The real lake is `~/qr/lake`.** Your shell does not inherit the owner's
  `~/.zshrc`, so every command that touches data must start with
  `export QR_ROOT=~/qr/lake`. `qr doctor` prints which root is in use; if
  it says the checkout's `lake/`, you are in the wrong place.
- The trial log is `~/qr/lake/trial_log.jsonl` (hash-chained, 1,541
  trials); `qr trial verify` before any report.
- macOS: no `timeout` command; `split -n` is not supported (use `-l`).
- Binance's futures websocket connects but streams nothing from Dubai or
  from the Hetzner box; OKX and Bybit stream fine. Binance REST and the
  `data.binance.vision` bucket work.
- Hetzner box: `ssh 91.98.172.9` (root). Runs the ETF share-count collector
  (cron) and two liquidation recorders (`qr-liq-okx`, `qr-liq-bybit`,
  systemd, data in `/root/liq/data/<venue>/`). Do not stop or change them.
- Do not run agent fan-outs; a three-agent fan-out exhausted the usage
  limit once. Work sequentially in this session.

## What already exists (do not rebuild)

- Gate 5 comparators: `--benchmark buyhold|cash`, `--risk-free fred`
  (`qr data riskfree-pull` already stored FRED DTB3 in the lake).
- Cost models: `CostModel.binance_perp()`, `hyperliquid_perp()`,
  `carry_pair()`; funding enters **gross** via `runner.funding_pnl`.
- The carry unit: `qr data carry-build` writes market `carry-um` from spot
  bars, `futures/um` bars and the funding feature (`futures-um`).
  `qr/strategies/carry.py::FundingCarry` is family `funding_carry`;
  `qr gates --market carry-um --costs carry` runs it. The universe's
  volatility floor reads `spot_close` there (`UniverseSpec.vol_field`).
- In the lake: 734 spot series, 864 `futures/um` series, funding features
  for 40 symbols (`futures-um`); the funding **mirror** for the 471
  both-leg symbols was downloading when this brief was written.
- Pre-registration drafts, not yet registered:
  `docs/prereg/p2_funding_carry_v1.md` (C1) and
  `docs/prereg/p2_insider_cluster_v1.md` (E5).
- Tests for all of the above: `tests/qr_platform/test_programme2.py`,
  `test_carry.py`, and one case in `test_binance.py`.

## Hard rules

1. **Never register a pre-registration after a run of that hypothesis.**
   Gate 0 fails it, and it should. Register, then run.
2. **Every backtest is counted in the trial log.** No exploratory runs
   outside the sandbox.
3. **Do not loosen anything**: 3× cost bar, 250 variants a family, 2
   promotions a week, 5 a quarter, hard stop at 8 gated mechanism
   candidates for Programme 2. Gate 4 deflates per hypothesis; do not
   change that either way.
4. **No live orders, no money movement, no funded-evaluation purchase, no
   data spend.** Those are the owner's decisions, each on evidence.
5. **Do not run `qr autopilot` nights.** The brief space is exhausted;
   Programme 2's ideas come from the literature registry in `docs/20` §14.
6. Do not touch `centaur/`. Do not delete or rewrite anything you did not
   write; append or patch, and prove it with `git diff --numstat`.
7. Re-derive every figure you report from the trial log or the gate report
   JSON; never quote a previous report's number as a fact.

## The work, in order

**Step 1 — finish the data.**
```
export QR_ROOT=~/qr/lake
pgrep -fl "funding-pull" || echo "shards done"
ls ~/qr/lake/mirror/binance/data/futures/um/monthly/fundingRate | wc -l
comm -12 <(ls ~/qr/lake/mirror/binance/data/spot/monthly/klines | sort) \
        <(ls ~/qr/lake/mirror/binance/data/futures/um/monthly/klines | sort) > /tmp/both_syms.txt
.venv/bin/qr data funding-ingest --symbols $(cat /tmp/both_syms.txt)
.venv/bin/qr data carry-build
```
If shards are still running, wait for them (`pgrep`), do not relaunch. If
any both-leg symbol has no funding files after the shards end, pull just
those with `qr data funding-pull --no-metrics --symbols ...`.

**Step 2 — read the universe, then register and run C1.**
Run the check in the pre-registration's spirit: load the `carry-um` panel,
`UniverseSpec(n=40, lookback=30, min_history=180, vol_field="spot_close",
name="carry_top40")`, print members per bar over time and the top-40 on a
few dates, and the mean perp funding of members by year. If a peg, fiat or
leveraged token appears, fix the exclusion **before** registering and say
so in the document's amendment section. Then:
```
.venv/bin/qr trial prereg p2_funding_carry_v1 --file docs/prereg/p2_funding_carry_v1.md
.venv/bin/qr gates --family funding_carry --hypothesis p2_funding_carry_v1 \
  --market carry-um --costs carry --n 40 --min-history 180 \
  --benchmark cash --risk-free fred --end 2025-09-14 \
  --grid 'lookback=[3,7,14,30]' --grid 'entry=[0.05,0.10,0.15,0.20]' \
  --grid 'ceiling=[0.95,1.0]' --grid 'n_max=[5,10]' --upto 8
```
Also run the two controls named in the pre-registration (always-in carry:
`FundingCarry(entry=-1.0, exit=-2.0, ceiling=1.0, n_max=40)` behaves as
"hold every eligible unit"; and hold-T-bill is the benchmark itself) and
report them beside the family. Commit the report. **Then, once only**, the
holdout: same command with `--holdout-start 2025-09-15 --upto 11`.

**Step 3 — engine additions for the stock families.**
- `benchmark=exposure` in `qr/validate/gates.py` / `spa.py`: buy-and-hold
  of the eligible universe scaled bar by bar to the strategy's average gross
  exposure, remainder in cash. Tests first.
- `CostModel.alpaca_zero()`: $0 commission, half-spread from quotes, 1 bp
  slippage, whole shares for on-close orders. Tests.
- The four audit tests still owed (`docs/20` §10 item 11): one leg filled
  and the other not; a split on a carry unit; a Form 4 amendment published
  after the signal; a funding-interval change.

**Step 4 — E5, insider clusters.**
Build the Form 4 loader from the SEC insider-transactions data sets with
EDGAR acceptance times (`published_at` column, plus `event_time`,
`first_observed_at`, `ingested_at`, `source_hash`). Label 100 sampled
filings without looking at returns; the parser must reach 95% precision.
Prices: QuantConnect free tier is the plan's venue for this family; if you
cannot reach it from this session, say so and stop at the parser and the
audit rather than substituting a survivorship-biased source. Register the
pre-registration only after the audit passes; then run.

**Step 5 — E1 and E2** need the owner's Databento account (E1) and QC (E2).
If neither exists yet, skip to the remaining crypto families (C2, C4, C5)
in the order given in `docs/20` §11, one pre-registration each, and leave
E1/E2 queued.

**At the end of every stage:** `pytest -q`, commit, push, and append a
dated entry to the week log in `docs/20_PROGRAMME_2.md` saying what ran,
what it found, and the trial count.

## What needs the owner (ask once, in one message, then continue)

QuantConnect, Alpaca and Databento accounts; exchange readiness (Binance
futures enabled from the UAE, or Bybit); API keys only when a family
reaches incubation. Everything else in this brief is yours.

## Definition of done for this session

C1 has a verdict at every gate it reached, with both controls beside it;
the stock-family engine additions are merged with tests; E5's parser and
labelling audit exist with their precision number; the week log says what
happened; the branch is pushed. If C1 passed gates 0–9, the incubation
record (`qr forward`) is started and its first decision is logged.
