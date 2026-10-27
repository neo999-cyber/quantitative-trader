# `p4_exchange_inflow_v1` — amendment 1 (27 October 2026, before any run)

*Registered beside the memo (seq 990) after the family and the instrument were built on fixtures and before the
real instrument was built or any flow was read against a price. It fixes what the memo left open or got wrong
about the data; the mechanism, the signal, the grid, the prediction, the cost and the falsifiers stand.*

1. **The sample.** The memo's in-sample begins 17 August 2017, Binance's first spot bar. The instrument is the
   USDⓈ-M perpetual (the memo's own tightening, both sides on one venue), whose bars begin 1 January 2020 in the
   lake: **in-sample 1 January 2020 → 31 December 2023** (four years). **Holdout 1 January 2024 → the refresh
   date of the Coin Metrics mirror**, opened once. The minimum of 80 signal days at k = 1.5 applies inside the
   in-sample window and is counted by the build (`qr data inflow-build --count-start 2020-01-01 --count-end
   2023-12-31`) before the run.
2. **Timing on daily bars.** Day d's metrics are usable from 12:00 UTC on d + 1, as registered: the signal sits
   on the bar of d + 1 and a target set there fills at that bar's close (24:00 UTC); the position is held over
   the next h bars and exits at the close of d + 1 + h. The move during d + 1 itself is not captured — the
   price of acting on daily bars, stated.
3. **One position at a time** means a signal inside an open hold is not acted on; holds are never extended.
4. **The instrument.** `inflow-um` (`qr/data/inflow.py`): the perp's daily bars, the venue's daily funding sum
   (gross; the long pays a positive rate, so the short receives it), and `cm_netflow_z` — net inflow
   standardised against the ninety days before the day (sixty needed), placed on the next bar. The Coin Metrics
   mirror is refreshed on 27 October 2026 before the build, the previous copy kept beside it.
5. **Cost.** `--costs maker_dow`: the stage-1 maker cost blended by weekday (96% of resting orders filled on
   weekdays, 92% at weekends; 3.2 bps a side), funding settled gross. Frozen.
6. **Controls as their own sweeps.** `p4_exchange_inflow_v1_mirror` (long after extreme outflows, z ≤ −k, the
   same nine variants), `_placebo` (the flow series shifted 180 days later), `_random` (short on as many days as
   the family's k would fire, drawn at random among the days a z exists with a fixed seed, the same holds — the
   sample's own drift, which a short has to overcome).
7. **The runs**, once each, counted:

        qr gates --family exchange_inflow_fade --hypothesis p4_exchange_inflow_v1 --market inflow-um --interval 1d \
          --basket btc --costs maker_dow --engine ledger --benchmark cash --risk-free fred \
          --start 2020-01-01 --end 2023-12-31 --grid "k=[1.0,1.5,2.0]" --grid "h=[1,3,7]" --upto 8

   then `_mirror` (`--param control=mirror`), `_placebo` (`--param control=placebo`) and `_random`
   (`--param control=random`) on the same grid.
