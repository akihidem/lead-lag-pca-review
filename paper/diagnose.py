"""Why is the forward (2026) gross negative? Decompose the SAME reg-PCA positions
into where the move happened: overnight GAP (co) vs intraday DRIFT (oc).

Hypothesis: the lead-lag is real at the OPEN (US strength -> JP sectors gap up, so
the long basket's co is positive), but the open OVERREACTS and fades intraday (oc
negative). Since only the intraday leg is tradable, the feasible strategy is
adversely selected: you buy the inflated open and ride the fade down.

This is a decomposition of realized PnL on the held positions, not a new strategy.
"""
import os, sys
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from trader import build_live, signal_for, LOOKBACK, PAPER_START
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))
from leadlag import weights_from_pred

def main():
    D = build_live()
    idx = D["jp_dates"]; us_lead, jp_cc, jp_oc = D["us_lead"], D["jp_cc"], D["jp_oc"]
    TODAY = pd.Timestamp.today().normalize()
    cc_l=cc_s=oc_l=oc_s=co_l=co_s=0.0
    rows_cc=[]; rows_co=[]; rows_oc=[]; dates=[]; n=0
    for i in range(LOOKBACK, len(idx)):
        d = idx[i]
        if d < pd.Timestamp(PAPER_START) or d >= TODAY:
            continue
        oc = jp_oc.iloc[i].values; cc = jp_cc.iloc[i].values
        if np.isnan(oc).any() or np.isnan(cc).any():
            continue
        pred = signal_for(i, idx, us_lead, jp_cc)
        if pred is None:
            continue
        w = weights_from_pred(pred)
        co = (1+cc)/(1+oc) - 1.0                      # overnight gap per asset (exact)
        wl = np.where(w>0, w, 0.0); ws = np.where(w<0, w, 0.0)
        cc_l += float(wl@cc); cc_s += float(ws@cc)
        oc_l += float(wl@oc); oc_s += float(ws@oc)
        co_l += float(wl@co); co_s += float(ws@co)
        rows_cc.append(float(w@cc)); rows_co.append(float(w@co)); rows_oc.append(float(w@oc))
        dates.append(d); n+=1

    def line(name, pnl):
        a = np.array(pnl)
        print(f"  {name:28s} cum={a.sum()*100:+6.2f}%  mean/day={a.mean()*1e4:+5.1f}bp  hit={ (a>0).mean()*100:4.0f}%")
    print(f"=== forward 2026 decomposition (reg-PCA L/S, {n} days) ===")
    line("close->close (gap+drift)", rows_cc)
    line("overnight GAP (co)", rows_co)
    line("intraday DRIFT (oc, tradable)", rows_oc)
    print("\n  by leg — does US strength predict the JP gap, then fade intraday?")
    print(f"    LONG basket : gap(co)={co_l*100:+6.2f}%  intraday(oc)={oc_l*100:+6.2f}%  full(cc)={cc_l*100:+6.2f}%")
    print(f"    SHORT basket: gap(co)={co_s*100:+6.2f}%  intraday(oc)={oc_s*100:+6.2f}%  full(cc)={cc_s*100:+6.2f}%")
    print("    (SHORT pnl already sign-applied: positive = shorts fell)")
    gap = np.array(rows_co); intr = np.array(rows_oc)
    print(f"\n  GAP Sharpe={gap.mean()/ (gap.std()+1e-12)*np.sqrt(252):+5.2f}  "
          f"INTRADAY Sharpe={intr.mean()/(intr.std()+1e-12)*np.sqrt(252):+5.2f}")

    # plot: the lead-lag is real at the open (gap soars) but the tradable intraday fades
    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "out")
    dts = pd.to_datetime(dates)
    def eq(r): return (1+np.array(r)).cumprod()
    fig, ax = plt.subplots(figsize=(9,5))
    ax.plot(dts, eq(rows_co), label="overnight GAP (co) — un-capturable, look-ahead", lw=1.8, color="tab:green")
    ax.plot(dts, eq(rows_cc), label="close→close (gap+drift)", lw=1.2, color="tab:gray")
    ax.plot(dts, eq(rows_oc), label="intraday open→close (oc) — the ONLY tradable leg", lw=1.8, color="tab:red")
    ax.plot(dts, eq(np.array(rows_oc)-2/1e4*2.0), label="intraday net @2bp", lw=1.0, color="tab:red", ls="--")
    ax.axhline(1, color="k", lw=0.5)
    ax.set_title("Forward 2026 OOS: lead-lag is real at the open, but fades intraday\n(reg-PCA L/S on TOPIX-17; PAPER)")
    ax.legend(fontsize=8); ax.set_ylabel("growth of 1")
    fig.tight_layout(); fig.savefig(os.path.join(OUT,"forward.png"), dpi=110)
    print(f"  wrote {os.path.join(OUT,'forward.png')}")

if __name__ == "__main__":
    main()
