"""Download US 11 sector ETFs + JP TOPIX-17 sector ETFs (OHLC, auto-adjusted).

We keep OHLC (auto_adjust=True keeps O/H/L/C on a consistent split/div-adjusted
basis) because the key verification — does the US->JP lead-lag alpha live in the
overnight OPENING GAP or in intraday drift — needs both Open and Close on the JP side.

Saved as per-ticker CSVs under data/raw/ (resumable) + combined pickle data/panel.pkl.
"""
import os, time, sys
import pandas as pd
import yfinance as yf

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "data", "raw")
os.makedirs(RAW, exist_ok=True)

START = "2019-01-01"
END = "2025-12-31"

US = {  # SPDR Select Sector ETFs (11 GICS sectors). All alive since 2018-10.
    "XLB": "Materials", "XLC": "CommServices", "XLE": "Energy", "XLF": "Financials",
    "XLI": "Industrials", "XLK": "Technology", "XLP": "Staples", "XLRE": "RealEstate",
    "XLU": "Utilities", "XLV": "HealthCare", "XLY": "Discretionary",
}
# NEXT FUNDS TOPIX-17 series on TSE (1617..1633). Yahoo suffix .T
JP = {
    "1617.T": "Foods", "1618.T": "EnergyRes", "1619.T": "Construction",
    "1620.T": "RawMatChem", "1621.T": "Pharma", "1622.T": "AutoTransp",
    "1623.T": "SteelNonferr", "1624.T": "Machinery", "1625.T": "ElecPrecision",
    "1626.T": "ITServices", "1627.T": "PowerGas", "1628.T": "TranspLogistics",
    "1629.T": "Trading", "1630.T": "Retail", "1631.T": "Banks",
    "1632.T": "FinExBanks", "1633.T": "RealEstate",
}

def fetch(ticker, tries=4):
    path = os.path.join(RAW, ticker.replace(".", "_") + ".csv")
    if os.path.exists(path):
        df = pd.read_csv(path, index_col=0, parse_dates=True)
        if len(df) > 50:
            return df, "cached"
    last = None
    for k in range(tries):
        try:
            df = yf.download(ticker, start=START, end=END, auto_adjust=True,
                             progress=False, threads=False)
            if df is not None and len(df) > 50:
                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = df.columns.get_level_values(0)
                df = df[["Open", "High", "Low", "Close", "Volume"]]
                df.to_csv(path)
                return df, "ok"
            last = f"empty({0 if df is None else len(df)})"
        except Exception as e:
            last = str(e)[:80]
        time.sleep(2.0 * (k + 1))
    return None, last

def main():
    rows = []
    for grp, d in [("US", US), ("JP", JP)]:
        for t, name in d.items():
            df, status = fetch(t)
            n = 0 if df is None else len(df)
            dr = "" if df is None else f"{df.index.min().date()}..{df.index.max().date()}"
            print(f"{grp} {t:7s} {name:14s} {status:8s} n={n:5d} {dr}", flush=True)
            rows.append((grp, t, name, n))
            time.sleep(1.2)
    ok = sum(1 for r in rows if r[3] > 50)
    print(f"\nfetched {ok}/{len(rows)} tickers with >50 rows")

if __name__ == "__main__":
    main()
