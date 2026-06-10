"""Subspace-regularized PCA lead-lag (US sectors -> JP sectors): faithful rebuild
+ the verifications that decide whether the gross alpha is real and tradable.

Timing (leak-free): US close on date d-1 lands ~06:00 JST on date d, before TSE
opens 09:00 JST. So JP[d] is predicted from the most recent US session strictly
before calendar date d:  U[d] = us_cc.reindex(union).ffill().shift(1).loc[d].

JP return is decomposed so we can ask WHERE the alpha lives:
  jp_co[d] = Open[d]/Close[d-1]-1   overnight GAP   (un-capturable: happens before you can fill)
  jp_oc[d] = Close[d]/Open[d]-1      intraday DRIFT  (capturable: enter at open, exit at close)
  jp_cc[d] = Close[d]/Close[d-1]-1   = gap + drift   (what a naive close-to-close backtest books)
"""
import os, json
import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "data", "raw")
OUT = os.path.join(ROOT, "out")
os.makedirs(OUT, exist_ok=True)
ANN = 252.0

US = ["XLB","XLC","XLE","XLF","XLI","XLK","XLP","XLRE","XLU","XLV","XLY"]
JP = ["1617.T","1618.T","1619.T","1620.T","1621.T","1622.T","1623.T","1624.T",
      "1625.T","1626.T","1627.T","1628.T","1629.T","1630.T","1631.T","1632.T","1633.T"]
# cyclical (+1) vs defensive (-1)
CYC = {"XLB":1,"XLC":1,"XLE":1,"XLF":1,"XLI":1,"XLK":1,"XLP":-1,"XLRE":1,"XLU":-1,"XLV":-1,"XLY":1,
       "1617.T":-1,"1618.T":1,"1619.T":1,"1620.T":1,"1621.T":-1,"1622.T":1,"1623.T":1,"1624.T":1,
       "1625.T":1,"1626.T":1,"1627.T":-1,"1628.T":1,"1629.T":1,"1630.T":-1,"1631.T":1,"1632.T":1,"1633.T":1}

def load(t):
    df = pd.read_csv(os.path.join(RAW, t.replace(".","_")+".csv"), index_col=0, parse_dates=True)
    return df[~df.index.duplicated()].sort_index()

def build():
    """Return aligned frames indexed by JP trading days."""
    us_close = pd.DataFrame({t: load(t)["Close"] for t in US})
    jp = {t: load(t) for t in JP}
    jp_close = pd.DataFrame({t: jp[t]["Close"] for t in JP})
    jp_open  = pd.DataFrame({t: jp[t]["Open"]  for t in JP})

    us_cc = us_close.pct_change()
    jp_cc = jp_close.pct_change()
    jp_oc = (jp_close / jp_open) - 1.0
    jp_co = (jp_open / jp_close.shift(1)) - 1.0

    jp_dates = jp_close.dropna(how="all").index
    union = us_cc.index.union(jp_cc.index)
    # US return that has CLOSED before the JP open on each JP date (shift on union calendar)
    us_lead = us_cc.reindex(union).ffill().shift(1).reindex(jp_dates)

    # clean: keep dates where both sides present
    good = jp_cc.reindex(jp_dates).notna().all(axis=1) & us_lead.notna().all(axis=1) \
           & jp_oc.reindex(jp_dates).notna().all(axis=1) & jp_co.reindex(jp_dates).notna().all(axis=1)
    idx = jp_dates[good]
    return dict(idx=idx,
                us_lead=us_lead.loc[idx],
                jp_cc=jp_cc.loc[idx], jp_oc=jp_oc.loc[idx], jp_co=jp_co.loc[idx])

# ---------- prior subspace for regularization ----------
def prior_corr():
    n = len(US) + len(JP)
    g_global = np.ones(n)
    g_spread = np.array([1.0]*len(US) + [-1.0]*len(JP))
    g_cyc = np.array([CYC[t] for t in US+JP], dtype=float)
    G = np.column_stack([g_global, g_spread, g_cyc])
    Q, _ = np.linalg.qr(G)                 # orthonormal basis of the 3-D prior subspace
    lam = np.array([3.0, 1.5, 1.0])
    Sig = Q @ np.diag(lam) @ Q.T + 0.5*np.eye(n)
    d = np.sqrt(np.diag(Sig))
    return Sig / np.outer(d, d)            # -> correlation matrix

PRIOR = prior_corr()

def top_factors(corr, k=3):
    w, V = np.linalg.eigh(corr)
    order = np.argsort(w)[::-1][:k]
    return V[:, order]                     # (n,k)

def jp_signal(win_us, win_jp, u_today, w_reg):
    """win_us/win_jp: trailing standardized returns (T,nUS)/(T,nJP). u_today: (nUS,) standardized.
    Returns predicted JP cross-section (nJP,)."""
    Z = np.hstack([win_us, win_jp])
    C = np.corrcoef(Z, rowvar=False)
    C = np.nan_to_num(C, nan=0.0)
    np.fill_diagonal(C, 1.0)
    C_reg = (1 - w_reg) * C + w_reg * PRIOR
    V = top_factors(C_reg, 3)
    V_us, V_jp = V[:len(US)], V[len(US):]
    f = V_us.T @ u_today                   # factor scores from the US move that just happened
    return V_jp @ f                        # low-rank map to JP expected move

# ---------- backtest ----------
def weights_from_pred(pred, q=0.30):
    n = len(pred); k = max(1, int(round(n*q)))
    order = np.argsort(pred)
    w = np.zeros(n)
    w[order[-k:]] = 0.5/k       # long top
    w[order[:k]] = -0.5/k       # short bottom (dollar-neutral, gross=1)
    return w

def run(data, model="reg", w_reg=0.9, lookback=60, ret="cc", rebalance=1):
    idx = data["idx"]; us = data["us_lead"].values
    jp_ret = data["jp_"+ret].values
    jp_cc = data["jp_cc"].values
    T = len(idx); nJP = len(JP)
    W = np.zeros((T, nJP)); pnl = np.zeros(T); turn = np.zeros(T)
    w_prev = np.zeros(nJP); held = None
    for t in range(lookback, T):
        if model == "mom":
            pred = -jp_cc[t-1]            # 1-day cross-sectional reversal benchmark
        else:
            wu = us[t-lookback:t]; wj = jp_cc[t-lookback:t]
            su = (wu - wu.mean(0)) / (wu.std(0) + 1e-9)
            sj = (wj - wj.mean(0)) / (wj.std(0) + 1e-9)
            u_today = (us[t] - wu.mean(0)) / (wu.std(0) + 1e-9)
            wr = 0.0 if model == "plain" else w_reg
            pred = jp_signal(su, sj, u_today, wr)
        if held is None or (t - lookback) % rebalance == 0:
            w_t = weights_from_pred(pred); held = w_t
        else:
            w_t = held
        turn[t] = np.abs(w_t - w_prev).sum()
        pnl[t] = float(w_t @ jp_ret[t])
        W[t] = w_t; w_prev = w_t
    return pd.DataFrame({"pnl": pnl, "turn": turn}, index=idx).iloc[lookback:]

def stats(pnl, turn=None, slip_bps=0.0):
    r = pnl.copy()
    if turn is not None and slip_bps:
        r = r - (slip_bps/1e4)*turn
    mu, sd = r.mean()*ANN, r.std()*np.sqrt(ANN)
    sharpe = mu/sd if sd > 0 else 0.0
    eq = (1+r).cumprod(); dd = (eq/eq.cummax()-1).min()
    return dict(ann_ret=float(mu), sharpe=float(sharpe), maxdd=float(dd),
                avg_turn=float(turn.mean()) if turn is not None else None, n=int(len(r)))

if __name__ == "__main__":
    data = build()
    idx = data["idx"]
    print(f"panel: {len(idx)} JP days  {idx.min().date()}..{idx.max().date()}  "
          f"({len(US)} US + {len(JP)} JP sectors)")
    out = {"panel": {"n": int(len(idx)), "start": str(idx.min().date()), "end": str(idx.max().date())}}

    # (1) reproduce: momentum vs plain vs reg, gross, close-to-close
    print("\n=== (1) REPRODUCE (gross, close-to-close) ===")
    rep = {}
    for m in ["mom","plain","reg"]:
        bt = run(data, model=m, ret="cc")
        s = stats(bt["pnl"], bt["turn"], 0.0)
        rep[m] = s
        print(f"  {m:6s} Sharpe={s['sharpe']:5.2f}  ann={s['ann_ret']*100:6.1f}%  "
              f"maxDD={s['maxdd']*100:6.1f}%  turn={s['avg_turn']:.2f}")
    out["reproduce"] = rep

    # (2) cost ladder on reg PCA (close-to-close)
    print("\n=== (2) COST LADDER (reg PCA, close-to-close) ===")
    bt = run(data, model="reg", ret="cc")
    cost = {}
    for slip in [0,1,2,3,5]:
        s = stats(bt["pnl"], bt["turn"], slip)
        cost[slip] = s
        print(f"  slip={slip}bp  Sharpe={s['sharpe']:5.2f}  ann={s['ann_ret']*100:6.1f}%  maxDD={s['maxdd']*100:6.1f}%")
    out["cost_ladder"] = cost

    # (3) GAP decomposition: same signal, realize on cc / oc(tradable) / co(gap)
    print("\n=== (3) GAP vs INTRADAY decomposition (reg PCA, gross) ===")
    dec = {}
    for ret in ["cc","co","oc"]:
        bt = run(data, model="reg", ret=ret)
        s = stats(bt["pnl"], bt["turn"], 0.0)
        dec[ret] = s
        lab = {"cc":"close->close (gap+drift)","co":"overnight GAP (un-capturable)","oc":"intraday DRIFT (tradable)"}[ret]
        print(f"  {ret}  {lab:32s} Sharpe={s['sharpe']:5.2f}  ann={s['ann_ret']*100:6.1f}%")
    # tradable net: intraday return minus cost
    bt_oc = run(data, model="reg", ret="oc")
    dec["oc_net2bp"] = stats(bt_oc["pnl"], bt_oc["turn"], 2)
    print(f"  oc @2bp net: Sharpe={dec['oc_net2bp']['sharpe']:.2f}  ann={dec['oc_net2bp']['ann_ret']*100:.1f}%")
    out["decomposition"] = dec

    # (4) frequency sweep (reg PCA), net @2bp, on cc and on oc
    print("\n=== (4) FREQUENCY SWEEP (reg PCA, net @2bp) ===")
    freq = {}
    for rb in [1,2,3,5,10]:
        b_cc = run(data, model="reg", ret="cc", rebalance=rb)
        b_oc = run(data, model="reg", ret="oc", rebalance=rb)
        s_cc = stats(b_cc["pnl"], b_cc["turn"], 2)
        s_oc = stats(b_oc["pnl"], b_oc["turn"], 2)
        freq[rb] = {"cc": s_cc, "oc": s_oc}
        print(f"  every {rb:2d}d  cc:Sharpe={s_cc['sharpe']:5.2f} turn={s_cc['avg_turn']:.2f} | "
              f"oc(tradable):Sharpe={s_oc['sharpe']:5.2f} ann={s_oc['ann_ret']*100:5.1f}%")
    out["freq_sweep"] = freq

    # (5) OOS split + 2022 sensitivity (reg PCA)
    print("\n=== (5) OOS split & regime (reg PCA) ===")
    bt_cc = run(data, model="reg", ret="cc"); bt_oc = run(data, model="reg", ret="oc")
    def seg(df, lo, hi):
        m = (df.index >= lo) & (df.index <= hi)
        return df[m]
    splits = {"IS_2019_2023": ("2019-01-01","2023-12-31"),
              "OOS_2024_2025": ("2024-01-01","2025-12-31"),
              "ex2022": None}
    oos = {}
    for name,rng in splits.items():
        if name == "ex2022":
            mcc = bt_cc[(bt_cc.index < "2022-01-01") | (bt_cc.index > "2022-12-31")]
            moc = bt_oc[(bt_oc.index < "2022-01-01") | (bt_oc.index > "2022-12-31")]
        else:
            mcc = seg(bt_cc, *rng); moc = seg(bt_oc, *rng)
        s_cc_g = stats(mcc["pnl"], mcc["turn"], 0)
        s_cc_n = stats(mcc["pnl"], mcc["turn"], 2)
        s_oc_n = stats(moc["pnl"], moc["turn"], 2)
        oos[name] = {"cc_gross": s_cc_g, "cc_net2bp": s_cc_n, "oc_net2bp": s_oc_n}
        print(f"  {name:14s} cc_gross={s_cc_g['sharpe']:5.2f} | cc_net2bp={s_cc_n['sharpe']:5.2f} | "
              f"oc_net2bp(tradable)={s_oc_n['sharpe']:5.2f}")
    out["oos"] = oos

    with open(os.path.join(OUT,"results.json"),"w") as f:
        json.dump(out, f, indent=2)
    print(f"\nwrote {os.path.join(OUT,'results.json')}")
