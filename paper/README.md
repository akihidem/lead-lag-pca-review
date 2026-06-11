# paper/ — automated PAPER trader (forward OOS test)

**PAPER ONLY. No broker, no orders, no capital.** This subsystem exists for two
reasons, neither of which is "we expect profit":

1. **Measurement infrastructure** — a reusable signal→execution→ledger→PnL pipeline.
2. **Forward out-of-sample test** — the backtest in [`../FINDINGS.md`](../FINDINGS.md)
   stopped at 2025-12-31, so every trade booked here (2026 onward) is on unseen data.

## What it trades

The only *feasible* realization of the strategy (see FINDINGS §3): enter the
long-top-30% / short-bottom-30% TOPIX-17 sector basket at the **JP open** (signal =
last US close, known ~06:00 JST), exit at the **JP close**, flat overnight. Honest
intraday cost = `slip × 2` (full daily round trip). Prior weight `w_reg = 0.90`
(the paper's spec).

## Forward result so far (2026 OOS)

Over ~4.5 months of data the model never saw, the edge is **negative even before
costs** — it has not merely decayed but inverted:

| metric | value |
|---|---|
| hit rate (gross>0) | 44% |
| mean daily gross | −5.2 bp |
| **gross** | annualized **−13.2%**, Sharpe **−1.32** |
| net @2bp | annualized −23.3%, Sharpe −2.33 |

(Small sample; the point is there is **no positive edge live** — consistent with,
and stronger than, the backtest's "not tradable" conclusion.)

## Run it

```bash
../.venv/bin/python trader.py     # idempotent: books newly-completed days, prints today's target
```

Automated daily via cron (07:30 JST, Mon–Fri):
```
30 7 * * 1-5 /home/muko1/Projects/lead-lag-pca-review/paper/run_daily.sh
```

## Files (runtime artifacts are git-ignored)

- `trader.py` — the engine (committed)
- `run_daily.sh` — cron wrapper (committed)
- `ledger.csv`, `state.json`, `live_raw/`, `logs/` — the running paper track record (local only)
