# `p4_cot_crowding_v1` — amendment 1 (27 October 2026, before any run)

*Registered beside the memo (seq 989) after the family and the instrument were built on fixtures and before the
real instrument was built or any funding was read against the positioning. It fixes what the memo left open or
got wrong about the data; the mechanism, the signal, the grid, the prediction, the cost and the falsifiers
stand.*

1. **The sample.** The memo's in-sample begins 10 April 2018, the first CME bitcoin report. The lake's carry
   unit — and Binance's funding — begins 1 January 2020, so the funding test can only start there:
   **in-sample 1 January 2020 → 31 December 2024** (about 260 released reports); the 2018–2019 reports feed the
   trailing percentiles only, so the 52-week window is complete from the first in-sample week. **Holdout
   1 January 2025 → 31 August 2026** as registered (the lake's funding ends there), opened once. The minimum of
   35 crowded weeks at p = 90 applies inside the in-sample window and is counted by the instrument build
   (`qr data cot-build --count-start 2020-01-01 --count-end 2024-12-31`) before the run.
2. **Availability.** Saturday 00:00 UTC after the report Tuesday (report + 4 days) in an ordinary week, as
   registered. **In a week with a US federal holiday on the Tuesday through Friday the CFTC releases on the
   following Monday, so such a row is usable from the Tuesday after (report + 7 days).** The memo's rule read
   those weeks three days early; the instrument applies the later stamp (`qr.data.cot.release_time`).
3. **The instrument.** `carrycot-um` (`qr/data/cot.py`): the carry unit's daily bars with `cot_crowd`,
   `cot_pct_26` and `cot_pct_52`, each day carrying the latest release known by its open; the percentile counts
   the trailing reports including the current one. A target set on the Saturday bar fills at Saturday's close.
4. **The rule's engine form.** `CarryCrowdingTimer(p, window)` (`qr/strategies/cot.py`): hold the unit while the
   percentile is below p, out while it is at or above p, back in at the first release below it — no hysteresis.
   Weight 1.0 of the sleeve on the one unit, sized on spot notional with the perp margin as the reserve line
   (the ledger's default). The cost model is `--costs carry_maker`: spot at the fee alone (7.5 bps, VIP 0 with
   BNB) plus the perp leg at the maker cost measured in stage 1 (3.2 bps blended) — 10.7 a side, 21.5 the round
   trip, as the memo froze; the unit's fill-rate haircut (0.94) applies as it did to C2 v2.
5. **Controls as their own sweeps.** `p4_cot_crowding_v1_always_in` (the holding with no rule, one variant;
   on this one-unit universe gate 5's buy-and-hold is the same costed book, so the family runs with
   `--benchmark buyhold` — the comparator the memo named), `_mirror` (in only while crowded), `_placebo` (the
   crowded flags permuted in blocks of thirteen weeks, 91 daily bars, fixed seed), `_eth` (the same six variants
   on the ETHUSDT unit against the CME Ether rows, from 2021; reported, not pooled).
6. **The sort test** is `scripts/p4_cot_sort.py`: the funding over the 28 days from each release, annualised,
   crowded weeks against the rest at every (window, p); Welch's t on every fourth report from the first (phase
   0, the registered non-overlapping statistic), the other three phases reported beside it. One counted run.
7. **The runs**, once each, counted:

        qr gates --family carry_crowding_timer --hypothesis p4_cot_crowding_v1 --market carrycot-um --interval 1d \
          --basket btc --costs carry_maker --engine ledger --benchmark buyhold \
          --start 2020-01-01 --end 2024-12-31 --grid "p=[80,90,95]" --grid "window=[26,52]" --upto 8
        python scripts/p4_cot_sort.py --start 2020-01-01 --end 2024-12-31

   then `_always_in` (`--param control=always_in --param p=90 --param window=52`), `_mirror`
   (`--param control=mirror`), `_placebo` (`--param control=placebo`) on the same grid, and `_eth`
   (`--basket eth`, the family's grid).
