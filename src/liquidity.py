"""Does restricting to LIQUID TOPIX-17 ETFs preserve the edge, or collapse it?

The reproduction claimed only ~4/17 ETFs are liquid (>JPY 100M/day) and that
restricting to them "collapses the strategy" via lost diversification. Test it:
rank JP ETFs by yen turnover, then run the FEASIBLE intraday reg-PCA strategy
trading only the top-k liquid names (signal still uses the full 28-asset model).
Net uses the honest intraday cost = slip x 2 (flat-overnight full daily round-trip).
"""
import os, json
import numpy as np, pandas as pd
from leadlag import build, run, load, JP, OUT, ANN

def net_intraday(pnl, slip_bps): return pnl - (slip_bps/1e4)*2.0
def summ(r):
    mu, sd = r.mean()*ANN, r.std()*np.sqrt(ANN)
    sh = mu/sd if sd>0 else 0.0
    eq=(1+r).cumprod(); dd=(eq/eq.cummax()-1).min()
    return dict(ann=float(mu), sharpe=float(sh), maxdd=float(dd))

NAME = {"1617.T":"Foods","1618.T":"EnergyRes","1619.T":"Construction","1620.T":"RawMatChem",
        "1621.T":"Pharma","1622.T":"AutoTransp","1623.T":"SteelNonferr","1624.T":"Machinery",
        "1625.T":"ElecPrecision","1626.T":"ITServices","1627.T":"PowerGas","1628.T":"TranspLog",
        "1629.T":"Trading","1630.T":"Retail","1631.T":"Banks","1632.T":"FinExBanks","1633.T":"RealEstate"}

def main():
    data = build()

    # --- yen turnover per JP ETF (Close*Volume), mean over last ~2y ---
    turn = {}
    for t in JP:
        df = load(t)
        recent = df[df.index >= "2024-01-01"]
        turn[t] = float((recent["Close"]*recent["Volume"]).mean())
    rank = sorted(JP, key=lambda t: turn[t], reverse=True)
    print("=== JP TOPIX-17 ETF liquidity (mean daily yen turnover, 2024-2025) ===")
    for i,t in enumerate(rank):
        flag = ">¥100M" if turn[t]>1e8 else (">¥50M" if turn[t]>5e7 else "thin")
        print(f"  {i+1:2d}. {t} {NAME[t]:13s} ¥{turn[t]/1e6:8.1f}M  {flag}")
    n_liquid = sum(1 for t in JP if turn[t]>1e8)
    print(f"  -> {n_liquid}/17 ETFs above ¥100M/day")

    jp_pos = {t:i for i,t in enumerate(JP)}
    print("\n=== feasible intraday reg-PCA restricted to top-k liquid names ===")
    res = {"turnover_yen_M": {NAME[t]: turn[t]/1e6 for t in rank}, "n_liquid_100M": n_liquid, "by_k": {}}
    for k in [4,6,8,12,17]:
        mask = np.zeros(len(JP), bool)
        for t in rank[:k]: mask[jp_pos[t]] = True
        bt = run(data, model="reg", ret="oc", trade_mask=mask)
        g = summ(bt["pnl"]); n1 = summ(net_intraday(bt["pnl"],1)); n2 = summ(net_intraday(bt["pnl"],2))
        res["by_k"][k] = {"gross":g,"net1bp":n1,"net2bp":n2}
        print(f"  k={k:2d} liquid names: gross Sh={g['sharpe']:5.2f} ann={g['ann']*100:5.1f}% | "
              f"net@1bp Sh={n1['sharpe']:5.2f} | net@2bp Sh={n2['sharpe']:5.2f}")

    with open(os.path.join(OUT,"results_liquidity.json"),"w") as f:
        json.dump(res, f, indent=2)
    print(f"\nwrote {os.path.join(OUT,'results_liquidity.json')}")

if __name__ == "__main__":
    main()
