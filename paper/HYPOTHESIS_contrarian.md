# Hypothesis test record: "contrarian intraday" (fade the overnight gap)

## Hypothesis (generated from 2026 forward data)
The forward 2026 paper trade showed the tradable intraday leg (enter at JP open on
the US lead signal, exit at close) was **negative** (Sharpe −1.25), while the
overnight gap was strongly positive (+6.55). This suggested: *the open overreacts to
the lead-lag and mean-reverts intraday, so a **contrarian** intraday position (fade
the gap: short the US-predicted-strong sectors at the open, long the predicted-weak)
should be positive.*

## Why this needs a disciplined test (not a deploy)
The contrarian **sign was chosen by looking at 2026**. Testing it on 2026 is circular
(p-hacking). A real test needs data NOT used to form the hypothesis.

## Pre-registered test design & criterion (fixed before judging)
- **Holdout**: the 2019–2025 backtest period (not used to form the contrarian sign).
- **Stability**: per-year intraday (oc) Sharpe across 2019–2026 — is the sign stable?
- **Criterion**: accept the contrarian only if its **honest-cost net (slip×2) Sharpe
  > 0.5 on the 2019–2025 holdout**. Otherwise reject (do not run a months-long
  forward test on a sign that fails its holdout).

## Result → **REJECTED**  (`paper/stability.py`, `out/stability.png`)

Per-year Sharpe:

| year | intraday oc (tradable) | gap co (un-capturable) |
|---|---|---|
| 2019 | +5.70 | +3.05 |
| 2020 | +1.51 | +1.87 |
| 2021 | +0.61 | +3.90 |
| 2022 | +2.67 | +6.28 |
| 2023 | +2.82 | +4.00 |
| 2024 | +2.05 | +4.35 |
| 2025 | +1.11 | +3.02 |
| **2026** | **−1.25** | +6.55 |

- The **gap is positive in all 8 years** — the US→JP lead-lag is robustly real across
  every regime.
- The **intraday leg was positive in 7 of 8 years** (2019–2025 all positive: the open
  *under*-reacts and the move *continues* intraday — i.e. the tradable sign is
  **momentum, not contrarian**). It was negative only in **2026** (1 flip in 8 years).
- **Holdout verdict**: contrarian intraday on 2019–2025 = gross Sharpe **−2.01**,
  net@2bp **−3.96** → **FAIL** the pre-registered criterion.

## Conclusion
The contrarian hypothesis is **rejected**. 2026's negative intraday is a single-year
**regime flip**, not a persistent "fade the gap" anomaly. The tradable intraday sign
is *mostly* momentum (positive 7/8 years) but — as already shown in `FINDINGS.md` —
nets to ≈0 after honest cost and dies on the liquidity wall (0/17 ETFs liquid). No
months-long forward test is warranted; nothing here is tradable in either direction.

This also corrects an over-generalization in FINDINGS §8: "the open overreacts and
fades intraday" is true **only for 2026**, not as a general law.
