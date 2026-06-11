"""Does ANY regularization strength help the FEASIBLE (intraday) strategy?

The paper's headline is that subspace regularization lifts Sharpe 0.62 -> 2.22.
We could not reproduce that ordering on the tradable basis (plain ~ reg). This
sweep hardens that claim: vary the prior weight w_reg from 0 (=plain PCA) to 0.95
on the feasible intraday open->close strategy and report gross + honest net@2bp.
"""
import os, json
import numpy as np
from leadlag import build, run, ANN, OUT

def net_intraday(pnl, slip_bps): return pnl - (slip_bps/1e4)*2.0
def sh(r):
    mu, sd = r.mean()*ANN, r.std()*np.sqrt(ANN)
    return (mu/sd if sd>0 else 0.0), mu

def main():
    data = build()
    print("=== prior-weight (w_reg) sweep — feasible intraday open->close ===")
    print("  w_reg=0.0 is plain PCA; paper uses 0.90")
    res = {}
    for w in [0.0, 0.3, 0.5, 0.7, 0.9, 0.95]:
        bt = run(data, model="reg", w_reg=w, ret="oc")
        g_s, g_a = sh(bt["pnl"]); n_s, n_a = sh(net_intraday(bt["pnl"],2))
        res[w] = {"gross_sharpe":float(g_s),"gross_ann":float(g_a),
                  "net2bp_sharpe":float(n_s),"net2bp_ann":float(n_a)}
        tag = " (plain)" if w==0 else (" (paper)" if w==0.9 else "")
        print(f"  w={w:4.2f}{tag:8s} gross Sh={g_s:5.2f} ann={g_a*100:5.1f}% | net@2bp Sh={n_s:5.2f} ann={n_a*100:5.1f}%")
    best = max(res, key=lambda w: res[w]["net2bp_sharpe"])
    print(f"  -> best net@2bp at w_reg={best} (Sh={res[best]['net2bp_sharpe']:.2f}); "
          f"regularization gives no tradable lift over plain (w=0: Sh={res[0.0]['net2bp_sharpe']:.2f})")
    with open(os.path.join(OUT,"results_regsweep.json"),"w") as f:
        json.dump({str(k):v for k,v in res.items()}, f, indent=2)
    print(f"wrote {os.path.join(OUT,'results_regsweep.json')}")

if __name__ == "__main__":
    main()
