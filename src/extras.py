"""Honest-execution layer + plots.

Key correction over a naive close-to-close backtest:
  The US signal arrives ~06:00 JST, AFTER the prior JP close. So you can only act
  at the JP OPEN. The ONLY feasible realization is intraday open->close (oc), and
  it goes FLAT overnight => you round-trip the FULL book every day. Hence the
  honest intraday cost is slip x 2.0 (enter + exit on gross notional 1.0),
  not slip x |dw|. cc / co realizations are LOOK-AHEAD (need to hold from prior
  close, before the signal exists) and are reported only to show the illusory edge.
"""
import os, json
import numpy as np, pandas as pd
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from leadlag import build, run, stats, OUT, ANN

GROSS_NOTIONAL = 1.0  # 0.5 long + 0.5 short

def net_intraday(pnl, slip_bps):
    """flat-overnight intraday strategy: full round-trip daily => slip x 2 x gross."""
    return pnl - (slip_bps/1e4) * 2.0 * GROSS_NOTIONAL

def summ(r):
    mu, sd = r.mean()*ANN, r.std()*np.sqrt(ANN)
    sh = mu/sd if sd>0 else 0.0
    eq = (1+r).cumprod(); dd = (eq/eq.cummax()-1).min()
    return dict(ann=float(mu), sharpe=float(sh), maxdd=float(dd))

def main():
    data = build()
    res = {}

    # ---- (A) fair test of regularization on the ONLY feasible basis (intraday oc) ----
    print("=== (A) mom / plain / reg  on TRADABLE intraday (open->close), honest cost ===")
    tbl = {}
    for m in ["mom","plain","reg"]:
        bt = run(data, model=m, ret="oc")
        g = summ(bt["pnl"])
        n2 = summ(net_intraday(bt["pnl"], 2))
        n5 = summ(net_intraday(bt["pnl"], 5))
        tbl[m] = {"gross": g, "net2bp": n2, "net5bp": n5}
        print(f"  {m:6s} gross Sh={g['sharpe']:5.2f} ann={g['ann']*100:5.1f}% | "
              f"net@2bp Sh={n2['sharpe']:5.2f} ann={n2['ann']*100:5.1f}% | "
              f"net@5bp Sh={n5['sharpe']:5.2f} ann={n5['ann']*100:5.1f}%")
    res["tradable_compare"] = tbl

    # ---- (B) feasible cost ladder (reg, intraday) ----
    print("\n=== (B) feasible cost ladder (reg PCA, intraday open->close, full daily round-trip) ===")
    bt = run(data, model="reg", ret="oc")
    ladder = {}
    for slip in [0,1,2,3,5,10]:
        s = summ(net_intraday(bt["pnl"], slip))
        ladder[slip] = s
        print(f"  slip={slip:2d}bp  Sharpe={s['sharpe']:5.2f}  ann={s['ann']*100:6.1f}%  maxDD={s['maxdd']*100:6.1f}%")
    res["feasible_cost_ladder"] = ladder

    # ---- (C) where does the gross live: gap (co, look-ahead) vs intraday (oc, feasible) ----
    print("\n=== (C) decomposition of gross close-to-close (reg PCA) ===")
    parts = {}
    for ret,lab in [("cc","close->close (LOOK-AHEAD)"),("co","overnight GAP (LOOK-AHEAD)"),("oc","intraday (FEASIBLE)")]:
        b = run(data, model="reg", ret=ret)
        parts[ret] = summ(b["pnl"])
        print(f"  {ret}  {lab:28s} ann={parts[ret]['ann']*100:6.1f}%  Sharpe={parts[ret]['sharpe']:5.2f}")
    share_gap = parts["co"]["ann"] / parts["cc"]["ann"]
    print(f"  -> overnight gap is {share_gap*100:.0f}% of the close-to-close annual return (un-capturable)")
    res["decomp"] = parts; res["gap_share_of_cc"] = float(share_gap)

    # ---- (D) OOS & regime on the feasible intraday strategy, honest cost ----
    print("\n=== (D) OOS & regime — feasible intraday net @2bp (honest cost) ===")
    b = run(data, model="reg", ret="oc")
    periods = {"full_2019_2025":("2019-01-01","2025-12-31"),
               "IS_2019_2023":("2019-01-01","2023-12-31"),
               "OOS_2024_2025":("2024-01-01","2025-12-31"),
               "2020_covid":("2020-01-01","2020-12-31"),
               "2022_bear":("2022-01-01","2022-12-31")}
    oo = {}
    for nm,(lo,hi) in periods.items():
        s = b[(b.index>=lo)&(b.index<=hi)]
        g = summ(s["pnl"]); n2 = summ(net_intraday(s["pnl"],2))
        oo[nm] = {"gross":g, "net2bp":n2}
        print(f"  {nm:16s} gross Sh={g['sharpe']:5.2f} ann={g['ann']*100:6.1f}% | "
              f"net@2bp Sh={n2['sharpe']:5.2f} ann={n2['ann']*100:6.1f}%")
    res["oos_honest"] = oo

    # ---- plots ----
    idx = data["idx"]
    b_cc = run(data, model="reg", ret="cc")
    b_co = run(data, model="reg", ret="co")
    b_oc = run(data, model="reg", ret="oc")
    def eq(pnl): return (1+pnl).cumprod()
    fig, ax = plt.subplots(1, 2, figsize=(13,5))
    ax[0].plot(b_cc.index, eq(b_cc["pnl"]), label="close→close (gap+drift) — LOOK-AHEAD", lw=1.6)
    ax[0].plot(b_co.index, eq(b_co["pnl"]), label="overnight GAP only — LOOK-AHEAD", lw=1.3)
    ax[0].plot(b_oc.index, eq(b_oc["pnl"]), label="intraday open→close — FEASIBLE", lw=1.8, color="k")
    ax[0].set_title("Where the gross alpha lives (reg PCA, gross)"); ax[0].legend(fontsize=8); ax[0].set_yscale("log")
    ax[0].axhline(1, color="grey", lw=0.5)

    oc_g = b_oc["pnl"]
    ax[1].plot(idx[-len(oc_g):], eq(oc_g), label="intraday gross", color="k", lw=1.8)
    ax[1].plot(idx[-len(oc_g):], eq(net_intraday(oc_g,2)), label="net @2bp (full daily round-trip)", lw=1.4)
    ax[1].plot(idx[-len(oc_g):], eq(net_intraday(oc_g,5)), label="net @5bp", lw=1.4)
    ax[1].axvline(pd.Timestamp("2024-01-01"), color="red", ls="--", lw=1, label="OOS start 2024")
    ax[1].set_title("Feasible (intraday) strategy: cost eats the edge"); ax[1].legend(fontsize=8)
    ax[1].axhline(1, color="grey", lw=0.5)
    fig.tight_layout(); fig.savefig(os.path.join(OUT,"equity.png"), dpi=110)
    print(f"\nwrote {os.path.join(OUT,'equity.png')}")

    # save equity csv
    pd.DataFrame({"cc_gross": eq(b_cc["pnl"]), "co_gross": eq(b_co["pnl"]),
                  "oc_gross": eq(b_oc["pnl"]), "oc_net2bp": eq(net_intraday(b_oc["pnl"],2))}).to_csv(os.path.join(OUT,"equity.csv"))

    with open(os.path.join(OUT,"results_honest.json"),"w") as f:
        json.dump(res, f, indent=2)
    print(f"wrote {os.path.join(OUT,'results_honest.json')}")

if __name__ == "__main__":
    main()
