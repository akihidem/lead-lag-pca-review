"""Automated PAPER trader for the US->JP sector lead-lag (subspace-reg PCA) strategy.

IMPORTANT — this is PAPER ONLY. Our own verification (see ../FINDINGS.md) showed
this strategy nets ~0 after honest costs and has no liquid instrument. We run it
not because we expect profit, but as (1) reusable measurement infrastructure and
(2) a forward out-of-sample test: the backtest stopped at 2025-12-31, so every
trade booked here (2026-01-01 onward) is on data the model never saw.

Faithful to "the theory": trades the ONLY feasible realization — enter the L/S
sector basket at the JP OPEN (signal = last US close, known ~06:00 JST), exit at
the JP CLOSE, flat overnight. Honest intraday cost = slip x 2 (full daily round
trip on gross notional). No broker, no real orders: it appends simulated fills to
paper/ledger.csv and emits the next session's target basket.

Run idempotently each morning (~07:30 JST, after US close, before TSE open):
it books every newly-completed JP day and prints today's target.
"""
import os, sys, json
import numpy as np, pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "src"))
from leadlag import US, JP, jp_signal, weights_from_pred  # reuse the model + PRIOR

import yfinance as yf

LIVE = os.path.join(HERE, "live_raw"); os.makedirs(LIVE, exist_ok=True)
LEDGER = os.path.join(HERE, "ledger.csv")
STATE = os.path.join(HERE, "state.json")
FETCH_START = "2025-09-01"     # gives >60 JP days of lookback before the paper period
PAPER_START = "2026-01-01"     # forward OOS: backtest ended 2025-12-31
LOOKBACK = 60
W_REG = 0.90                   # the paper's spec ("90% prior"); FINDINGS shows w~0.5 was better
NAME = {"1617.T":"Foods","1618.T":"EnergyRes","1619.T":"Construction","1620.T":"RawMatChem",
        "1621.T":"Pharma","1622.T":"AutoTransp","1623.T":"SteelNonferr","1624.T":"Machinery",
        "1625.T":"ElecPrecision","1626.T":"ITServices","1627.T":"PowerGas","1628.T":"TranspLog",
        "1629.T":"Trading","1630.T":"Retail","1631.T":"Banks","1632.T":"FinExBanks","1633.T":"RealEstate"}

def fetch_live():
    for t in US + JP:
        try:
            df = yf.download(t, start=FETCH_START, auto_adjust=True, progress=False, threads=False)
            if df is not None and len(df) > LOOKBACK:
                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = df.columns.get_level_values(0)
                df[["Open","High","Low","Close","Volume"]].to_csv(os.path.join(LIVE, t.replace(".","_")+".csv"))
        except Exception as e:
            print(f"  warn: {t} fetch failed: {str(e)[:60]}")

def load(t):
    df = pd.read_csv(os.path.join(LIVE, t.replace(".","_")+".csv"), index_col=0, parse_dates=True)
    return df[~df.index.duplicated()].sort_index()

def build_live():
    us_close = pd.DataFrame({t: load(t)["Close"] for t in US})
    jp_close = pd.DataFrame({t: load(t)["Close"] for t in JP})
    jp_open  = pd.DataFrame({t: load(t)["Open"]  for t in JP})
    us_cc = us_close.pct_change()
    jp_cc = jp_close.pct_change()
    jp_oc = (jp_close / jp_open) - 1.0
    jp_dates = jp_close.dropna(how="all").index
    union = us_cc.index.union(jp_cc.index)
    us_lead = us_cc.reindex(union).ffill().shift(1).reindex(jp_dates)
    return dict(jp_dates=jp_dates, us_lead=us_lead, jp_cc=jp_cc.reindex(jp_dates),
                jp_oc=jp_oc.reindex(jp_dates), jp_open=jp_open, jp_close=jp_close)

def signal_for(d_idx, idx, us_lead, jp_cc):
    """reg-PCA predicted JP cross-section for JP day at position d_idx (uses history < d)."""
    wu = us_lead.iloc[d_idx-LOOKBACK:d_idx].values
    wj = jp_cc.iloc[d_idx-LOOKBACK:d_idx].values
    if np.isnan(wu).any() or np.isnan(wj).any():
        return None
    su = (wu - wu.mean(0))/(wu.std(0)+1e-9)
    sj = (wj - wj.mean(0))/(wj.std(0)+1e-9)
    u_today = us_lead.iloc[d_idx].values
    if np.isnan(u_today).any():
        return None
    u_today = (u_today - wu.mean(0))/(wu.std(0)+1e-9)
    return jp_signal(su, sj, u_today, W_REG)

def basket(w):
    longs = {NAME[JP[i]]: round(float(w[i]),4) for i in range(len(JP)) if w[i] > 0}
    shorts = {NAME[JP[i]]: round(float(w[i]),4) for i in range(len(JP)) if w[i] < 0}
    return longs, shorts

def main():
    print("=== US->JP lead-lag PAPER trader (intraday, honest cost) — PAPER ONLY ===")
    fetch_live()
    D = build_live()
    idx = D["jp_dates"]
    us_lead, jp_cc, jp_oc = D["us_lead"], D["jp_cc"], D["jp_oc"]

    done = set()
    rows = []
    if os.path.exists(LEDGER):
        prev = pd.read_csv(LEDGER)
        done = set(pd.to_datetime(prev["date"]).dt.strftime("%Y-%m-%d"))
        rows = prev.to_dict("records")

    # book every completed JP day in the paper period not yet in the ledger
    booked = 0
    for i in range(LOOKBACK, len(idx)):
        d = idx[i]
        ds = d.strftime("%Y-%m-%d")
        if d < pd.Timestamp(PAPER_START) or ds in done:
            continue
        oc = jp_oc.iloc[i].values            # realized intraday (open->close) for the basket
        if np.isnan(oc).any():               # today not closed yet -> skip booking
            continue
        pred = signal_for(i, idx, us_lead, jp_cc)
        if pred is None:
            continue
        w = weights_from_pred(pred)
        gross = float(w @ oc)
        longs, shorts = basket(w)
        rows.append(dict(date=ds, mode="live", gross_ret=gross,
                         n_long=len(longs), n_short=len(shorts),
                         longs=json.dumps(longs, ensure_ascii=False),
                         shorts=json.dumps(shorts, ensure_ascii=False)))
        done.add(ds); booked += 1

    led = pd.DataFrame(rows).sort_values("date").reset_index(drop=True)
    led.to_csv(LEDGER, index=False)

    # next target: latest JP day whose US lead is known (today, even if not yet closed)
    target = None
    for i in range(len(idx)-1, LOOKBACK, -1):
        pred = signal_for(i, idx, us_lead, jp_cc)
        if pred is not None:
            w = weights_from_pred(pred); lo, sh = basket(w)
            target = dict(for_open_on=idx[i].strftime("%Y-%m-%d"), longs=lo, shorts=sh)
            break
    json.dump({"updated": idx[-1].strftime("%Y-%m-%d"), "next_target": target,
               "n_booked_this_run": booked}, open(STATE,"w"), ensure_ascii=False, indent=2)

    # summary
    if len(led):
        g = led["gross_ret"].values
        def stats(slip):
            r = g - (slip/1e4)*2.0
            ann = r.mean()*252; sd = r.std()*np.sqrt(252)
            return ann, (ann/sd if sd>0 else 0.0), (1+r).prod()-1
        print(f"booked {booked} new day(s). paper period {led['date'].iloc[0]}..{led['date'].iloc[-1]} ({len(led)} days)")
        print(f"  hit rate (gross>0): {(g>0).mean()*100:.0f}%   mean daily gross: {g.mean()*1e4:+.1f} bp")
        for slip in [0,2,5]:
            ann,sh,cum = stats(slip)
            tag = "gross" if slip==0 else f"net@{slip}bp"
            print(f"  {tag:9s} cumulative={cum*100:+6.2f}%  annualized={ann*100:+6.1f}%  Sharpe={sh:+5.2f}")
    if target:
        print(f"\n  TARGET for next JP open ({target['for_open_on']}) — PAPER:")
        print(f"    LONG : {', '.join(target['longs'].keys())}")
        print(f"    SHORT: {', '.join(target['shorts'].keys())}")
    print(f"\n  ledger: {LEDGER}\n  (PAPER ONLY — verification says do NOT deploy capital; see FINDINGS.md)")

if __name__ == "__main__":
    main()
