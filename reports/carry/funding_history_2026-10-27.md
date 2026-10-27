# Carry holding — what the funding paid, by year, against the T-bill (2026-10-27)

Annualised funding collected by a short USDⓈ-M perp held every day of the year (sum of the day's settlements,
fraction of notional), from the lake's carry units; the T-bill is the year's mean DTB3. Gross of costs and
of basis; a descriptive read, no rule. Percent a year.

| year | BTCUSDT | ETHUSDT | SOLUSDT | T-bill | BTCUSDT − T-bill | ETHUSDT − T-bill | SOLUSDT − T-bill |
|---|---|---|---|---|---|---|---|
| 2020 | 17.2 | 27.4 | -12.6 | 0.4 | 16.8 | 27.1 | -12.9 |
| 2021 | 30.6 | 37.5 | 28.6 | 0.0 | 30.6 | 37.5 | 28.5 |
| 2022 | 4.2 | 0.8 | -38.6 | 2.0 | 2.1 | -1.2 | -40.6 |
| 2023 | 7.9 | 8.3 | 1.3 | 5.1 | 2.8 | 3.2 | -3.8 |
| 2024 | 11.9 | 13.0 | 13.6 | 5.0 | 7.0 | 8.0 | 8.6 |
| 2025 | 5.1 | 4.9 | 0.4 | 4.1 | 1.1 | 0.9 | -3.7 |
| 2026 | 2.6 | 1.6 | -1.7 | 3.6 | -1.0 | -2.1 | -5.3 |

## Per symbol

| symbol | from | months | negative months | days with funding ≤ 0 | median annualised | worst 90 days (ends) | best 90 days | last 365 days |
|---|---|---|---|---|---|---|---|---|
| BTCUSDT | 2020-01-01 | 80 | 6 | 12% | 8.3% | -0.39% (2026-05-06) | 16.65% | 3.4% |
| ETHUSDT | 2020-01-01 | 80 | 6 | 12% | 8.8% | -1.67% (2022-11-24) | 21.47% | 2.4% |
| SOLUSDT | 2020-09-14 | 72 | 21 | 29% | 7.1% | -42.38% (2023-01-13) | 19.62% | -1.7% |

## The last 365 days on the capital it ties up (round trip 21.5 bps, both legs in and out)

| symbol | gross | net of one round trip | on capital at 1× | on capital at 2.5× |
|---|---|---|---|---|
| BTCUSDT | 3.4% | 3.19% | 1.59% | 2.28% |
| ETHUSDT | 2.4% | 2.19% | 1.09% | 1.56% |
| SOLUSDT | -1.7% | -1.92% | -0.96% | -1.37% |

At 1× the perp margin is the full notional in USDT earning nothing, so the yield on the money parked is half the
funding; at 2.5× (the rehearsal's setting) the perp leg needs 40% of its notional and a basis spike can liquidate it.
The exchange is the counterparty for the whole holding either way (`docs/31` §13 B for the stress tiers).
