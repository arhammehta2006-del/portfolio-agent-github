"""
build_assumptions.py - turn REAL historical price data into data/assumptions.csv.

How to use
1. Download historical prices (monthly or daily) for each asset class, e.g. from NSE / niftyindices.com (index data),
   AMFI / a fund factsheet (NAV history), or a gold price source. Total-return series are best for equity.
2. Save each one in data/history/ named EXACTLY after the asset, with columns  Date,Close :
       data/history/Liquid Fund.csv   data/history/Debt Fund.csv   data/history/Gold.csv
       data/history/Large-cap Equity.csv   data/history/Mid-cap Equity.csv
3. Run:  python build_assumptions.py
   Assets with no file keep their existing (placeholder) numbers. Write your sources in SOURCES below.
"""
import os
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
HIST = os.path.join(HERE, "data", "history")
OUT = os.path.join(HERE, "data", "assumptions.csv")

# Fill this in for your data-documentation deliverable (what series, from where, which dates)
SOURCES = {
    "Liquid Fund": "e.g. <fund/index name>, <source website>, <start> to <end>",
    "Debt Fund": "e.g. <fund/index name>, <source website>, <start> to <end>",
    "Gold": "e.g. <gold price series>, <source website>, <start> to <end>",
    "Large-cap Equity": "e.g. Nifty 50 TRI, niftyindices.com, <start> to <end>",
    "Mid-cap Equity": "e.g. Nifty Midcap 150 TRI, niftyindices.com, <start> to <end>",
}


def stats_from_file(path):
    df = pd.read_csv(path)
    df.columns = [c.strip().title() for c in df.columns]
    df["Date"] = pd.to_datetime(df["Date"], dayfirst=True, errors="coerce")
    df = df.dropna(subset=["Date", "Close"]).sort_values("Date").set_index("Date")
    monthly = df["Close"].groupby(df.index.to_period("M")).last()      # month-end prices
    r = monthly.pct_change().dropna()
    years = (df.index[-1] - df.index[0]).days / 365.25
    cagr = (df["Close"].iloc[-1] / df["Close"].iloc[0]) ** (1 / years) - 1
    exp_return = r.mean() * 12                 # average yearly return (arithmetic)
    vol = r.std() * np.sqrt(12)                # yearly volatility
    return exp_return, vol, cagr, years, df.index[0].date(), df.index[-1].date()


def main():
    current = pd.read_csv(OUT).set_index("asset")
    for asset in current.index:
        f = os.path.join(HIST, f"{asset}.csv")
        if not os.path.exists(f):
            print(f"- {asset}: no file at {f}, keeping existing numbers")
            continue
        er, vol, cagr, yrs, start, end = stats_from_file(f)
        current.loc[asset, ["expected_return", "volatility"]] = [round(er, 4), round(vol, 4)]
        current.loc[asset, "source"] = f"{SOURCES[asset]} | computed {start} to {end} ({yrs:.1f} yrs), CAGR {cagr * 100:.1f}%"
        print(f"- {asset}: expected return {er * 100:.1f}%, volatility {vol * 100:.1f}%, CAGR {cagr * 100:.1f}% ({yrs:.1f} yrs)")
    current.reset_index().to_csv(OUT, index=False)
    print("Saved", OUT)


if __name__ == "__main__":
    main()
