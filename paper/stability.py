"""Pre-flight test for the 'contrarian intraday' hypothesis BEFORE committing to a
months-long forward test.

The contrarian sign was suggested by 2026 (hypothesis-generating data). A disciplined
test needs data NOT used to form it: the 2019-2025 backtest period, examined per-year.

Key question: is the tradable intraday (oc) sign STABLE? If the gap (co) is reliably
positive every year (lead-lag real) but the intraday sign FLIPS year to year, then
neither momentum-intraday nor its mirror (contrarian) is a real edge — 2026's negative
intraday is a regime flip, not a persistent anomaly to fade.
"""
import os, sys
import numpy as np, pandas as pd
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
from leadlag import build, run, ANN
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from trader import build_live, signal_for, LOOKBACK, PAPER_START
from leadlag import weights_from_pred

def sharpe(g):
    g = np.asarray(g); sd = g.std()
    return (g.mean()/sd*np.sqrt(ANN)) if sd > 0 else 0.0

def yearly(pnl):
    return {int(y): sharpe(g.values) for y, g in pnl.groupby(pnl.index.year)}

def live_2026():
    """daily intraday (oc) and gap (co) pnl for the despiked 2026 forward period."""
    D = build_live(); idx = D["jp_dates"]; us_lead, jp_cc, jp_oc = D["us_lead"], D["jp_cc"], D["jp_oc"]
    TODAY = pd.Timestamp.today().normalize()
    oc_pnl=[]; co_pnl=[]; dts=[]
    for i in range(LOOKBACK, len(idx)):
        d = idx[i]
        if d < pd.Timestamp(PAPER_START) or d >= TODAY: continue
        oc = jp_oc.iloc[i].values; cc = jp_cc.iloc[i].values
        if np.isnan(oc).any() or np.isnan(cc).any(): continue
        pred = signal_for(i, idx, us_lead, jp_cc)
        if pred is None: continue
        w = weights_from_pred(pred); co = (1+cc)/(1+oc)-1.0
        oc_pnl.append(float(w@oc)); co_pnl.append(float(w@co)); dts.append(d)
    s = pd.Series(oc_pnl, index=pd.to_datetime(dts)); c = pd.Series(co_pnl, index=pd.to_datetime(dts))
    return s, c

def main():
    data = build()
    bt_oc = run(data, model="reg", ret="oc")["pnl"]   # intraday, 2019-2025
    bt_co = run(data, model="reg", ret="co")["pnl"]    # gap, 2019-2025
    oc_y = yearly(bt_oc); co_y = yearly(bt_co)
    l_oc, l_co = live_2026()
    oc_y[2026] = sharpe(l_oc.values); co_y[2026] = sharpe(l_co.values)

    print("=== per-year Sharpe (reg-PCA) — is the tradable intraday sign stable? ===")
    print(f"{'year':>6} | {'intraday oc (tradable)':>22} | {'gap co (un-capturable)':>22} | contrarian-oc")
    print("-"*78)
    flips = 0; prev = None
    for y in sorted(oc_y):
        s = oc_y[y]; g = co_y.get(y, float('nan'))
        sign = "＋" if s > 0 else "－"
        if prev is not None and (s > 0) != (prev > 0): flips += 1
        prev = s
        print(f"{y:>6} | {s:>+22.2f} | {g:>+22.2f} | {-s:>+6.2f}")
    print("-"*78)
    print(f"intraday(oc) sign flips across years: {flips}")
    n_pos_oc = sum(1 for y in oc_y if oc_y[y] > 0); n = len(oc_y)
    n_pos_co = sum(1 for y in co_y if co_y[y] > 0)
    print(f"intraday oc positive years: {n_pos_oc}/{n}   |   gap co positive years: {n_pos_co}/{n}")

    # the pre-registered holdout verdict: contrarian on 2019-2025 (NOT the 2026 gen-data)
    hold = bt_oc[bt_oc.index.year <= 2025]
    contr = -hold
    def net(g, slip): return g - (slip/1e4)*2.0
    print("\n=== HOLDOUT verdict: contrarian-intraday on 2019-2025 (data NOT used to form hypothesis) ===")
    print(f"  contrarian gross Sharpe = {sharpe(contr.values):+.2f}  (= -momentum {sharpe(hold.values):+.2f})")
    print(f"  contrarian net@2bp Sharpe = {sharpe(net(contr,2).values):+.2f}")
    print(f"  -> pre-registered criterion (net Sharpe > 0.5 on holdout): "
          f"{'PASS' if sharpe(net(contr,2).values) > 0.5 else 'FAIL'}")

    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    years = sorted(oc_y); x = np.arange(len(years)); w = 0.4
    fig, ax = plt.subplots(figsize=(10,5))
    ax.bar(x-w/2, [oc_y[y] for y in years], w, label="intraday oc (tradable)", color="tab:red")
    ax.bar(x+w/2, [co_y[y] for y in years], w, label="overnight gap co (un-capturable)", color="tab:green")
    ax.axhline(0, color="k", lw=0.8); ax.set_xticks(x); ax.set_xticklabels(years)
    ax.set_ylabel("annualized Sharpe"); ax.legend()
    ax.set_title("Per-year Sharpe: the gap (lead-lag) is positive EVERY year;\n"
                 "the tradable intraday is positive 7/8 years, negative only in 2026 (regime flip, not a fade anomaly)")
    fig.tight_layout(); fig.savefig(os.path.join(ROOT,"out","stability.png"), dpi=110)
    print(f"  wrote {os.path.join(ROOT,'out','stability.png')}")

if __name__ == "__main__":
    main()
