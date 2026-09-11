# The "HFT tech stack" infographic vs our platform

The infographic (shared 11 Sept 2026) describes high-frequency trading: co-location, FPGAs, kernel-bypass NICs, kdb+, FIX/ITCH, microsecond latency. Its own takeaway is "speed = edge = profits". That is true for HFT and irrelevant for us: at a daily/swing horizon the edge is statistical, not latency-based, and a solo trader cannot compete on speed at any budget. This note maps each of its six layers to what we actually use, so the plan does not drift toward HFT-shaped complexity.

| HFT layer (infographic) | What it is for in HFT | Our equivalent | Applies to us? |
|---|---|---|---|
| 1. Exchanges & market data (direct feeds, Bloomberg/Refinitiv/FactSet) | Raw exchange feeds at the source | Binance bucket, Tiingo/Norgate/Sharadar, Dukascopy, FRED, EDGAR; Databento only if we ever need tick data | Same *idea* (own the data), $0–300/mo instead of $100k+/yr |
| 2. Infrastructure (co-location, FPGA, RDMA/InfiniBand) | Shave microseconds | MacBook Air for research, a shared CX23 for ops, an hourly CX53 for bursts | **No.** Latency is not our edge; a daily bar does not care about 50 µs |
| 3. Connectivity (FIX, ITCH/OUCH, multicast UDP, SmartNICs) | Native exchange protocols | Binance REST/WebSocket via CCXT or Nautilus; IBKR via ib_async; OANDA REST | **No.** Broker APIs over HTTPS are fine when you trade a few times a day |
| 4. Data layer (kdb+, Kafka, Parquet, Redis) | Ingest millions of messages/second | Parquet + DuckDB + Polars | **Parquet yes**; kdb+/Kafka/Redis no (they solve throughput problems we do not have) |
| 5. Strategy & risk (C++, Python, real-time risk engines) | C++ for the hot path, Python for research, live Greeks/exposure limits | Python everywhere (vectorbt has a Rust engine, Nautilus a Rust core, so we get compiled speed without writing C++); the 11 gates are our "risk engine" before a trade, the 1%-cap/vol-target/drawdown rules during it | **Partly.** The *concept* of a hard risk layer that the strategy cannot override is ours too; the C++ is not |
| 6. Monitoring & ops (Grafana, Prometheus, InfluxDB, PagerDuty) | 24/7 uptime with on-call | cron/Prefect, MLflow, Telegram alerts, daily reconciliation | **Lightweight version.** Grafana on the CX23 is a nice-to-have in Phase 4; PagerDuty is not |

## What to keep from the infographic
1. **Own your data** (layer 1). Already the plan's first principle.
2. **A risk layer the strategy cannot bypass** (layer 5). Ours is the gates before, the sizing caps and the Centaur gauntlet during.
3. **Monitoring is not optional once live** (layer 6). Phase 4 includes alerts and reconciliation for that reason.

## What to reject, explicitly
- Any argument that we need lower latency, faster languages, or a streaming database. If a strategy only works when executed in under a second, it is an HFT strategy, and it is out of scope by design (`PLAN.md` §8). The one open-source tool for that world, hftbacktest, is noted in the research for completeness, not for use.
- Buying "professional" infrastructure before a strategy has passed the gates. The infographic's stack costs millions per year; it exists because those firms' edge is measured in microseconds and evaporates without it. Our edge, if we find one, is measured in days and does not.
