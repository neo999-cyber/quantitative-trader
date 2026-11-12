# `p6_breakout_crypto_v1` — the rule against its controls, 2026-11-12 (reads the sweeps' returns; runs nothing)

- `p6_breakout_crypto_v1`: 8 variant(s); median variant `momentum_breakout_base10_controlnone_tight2_trail10`, net Sharpe 0.53
- `p6_breakout_crypto_v1_leaders`: 2 variant(s); median variant `momentum_breakout_base5_controlleaders_tight2_trail10`, net Sharpe 0.57
- `p6_breakout_crypto_v1_placebo`: 8 variant(s); median variant `momentum_breakout_base10_controlplacebo_tight2p5_trail10`, net Sharpe 0.42
- `p6_breakout_crypto_v1_late`: 8 variant(s); median variant `momentum_breakout_base10_controllate_tight2p5_trail10`, net Sharpe 0.41
- `p6_breakout_crypto_v1_nofilter`: 8 variant(s); median variant `momentum_breakout_base5_controlnofilter_tight2p5_trail20`, net Sharpe 0.88

| condition | control | bars | control scaled by | rule − control, % a year | Newey–West t | Sharpe rule | Sharpe control | met |
|---|---|---|---|---|---|---|---|---|
| (2) the setup adds to owning leaders | `p6_breakout_crypto_v1_leaders` | 2677 | 0.45 | -1.4 | -0.11 | 0.53 | 0.57 | **no** |
| (3) the day matters, not the name alone | `p6_breakout_crypto_v1_placebo` | 2677 | 1.01 | +3.4 | 0.24 | 0.53 | 0.42 | **no** |
| (4) the breakout day is not worse than the next | `p6_breakout_crypto_v1_late` | 2677 | 0.86 | +3.8 | 0.48 | 0.53 | 0.41 | yes |
| (reported) the market filter | `p6_breakout_crypto_v1_nofilter` | 2677 | 0.60 | -10.8 | -0.84 | 0.53 | 0.88 | — |
