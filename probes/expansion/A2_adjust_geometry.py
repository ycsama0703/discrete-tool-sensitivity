"""Candidate A: flip geometry of the OpenBB-style `adjustment` parameter
{splits_and_dividends, splits_only, none}, built from yfinance data:
  splits_and_dividends = auto_adjust=True Close
  splits_only          = auto_adjust=False Close (yfinance raw is already split-adjusted)
  none                 = splits_only x (product of split factors after that date)  [as traded]
Only 'real' splits (integer-ish ratios >= 1.5) are used; spin-off factors (1.046, 1.324...) are ignored.
Decisions over random 20-stock subsets of the universe:
  top-3 by return over a window; threshold 'close on date > T' (T = median under the reference mode)."""
import json, math, random, statistics
import yfinance as yf

SYMS = ["KO","PEP","PG","JNJ","XOM","CVX","VZ","T","MO","PM","IBM","MMM","ABBV","MRK","PFE",
        "AMZN","GOOGL","META","TSLA","NFLX","AMD","CRM","ADBE","BRK-B",
        "NVDA","AAPL","AVGO","CMG","WMT","LRCX","SMCI","MSFT","JPM","HD"]
H = {}
for s in SYMS:
    t = yf.Ticker(s)
    a = t.history(start="2019-12-01", end="2026-01-10", auto_adjust=True)["Close"]
    r = t.history(start="2019-12-01", end="2026-01-10", auto_adjust=False, actions=True)
    sp = {d: v for d, v in r["Stock Splits"].items() if v >= 1.5}
    H[s] = dict(adj=a, raw=r["Close"], splits=sp)

def price(s, mode, date):
    h = H[s]; idx = h["raw"].index[h["raw"].index <= date][-1]
    if mode == "splits_and_dividends": return float(h["adj"].loc[idx])
    p = float(h["raw"].loc[idx])
    if mode == "none":
        for d, f in h["splits"].items():
            if d > idx: p *= f
    return p

MODES = ["splits_and_dividends", "splits_only", "none"]
def geom(vals_ref, vals_alt):
    xs = [s for s in vals_ref if vals_ref[s] > 0 and vals_alt[s] > 0]
    lq = [math.log(vals_ref[s]) for s in xs]; lr = [math.log(vals_alt[s] / vals_ref[s]) for s in xs]
    sq = statistics.pstdev(lq); return statistics.mean(lr) / sq, statistics.pstdev(lr) / sq  # kappa, rho

rng = random.Random(0)
subsets = [sorted(rng.sample(SYMS, 20)) for _ in range(200)]
tz = H["KO"]["raw"].index.tz
import pandas as pd
D = lambda x: pd.Timestamp(x, tz=tz)
print("decision                      ref -> alt                      flip%   mean kappa  mean rho")
for win in [("2025-01-02", "2025-12-31"), ("2023-01-03", "2025-12-31"), ("2021-01-04", "2025-12-31")]:
    for alt in ["splits_only", "none"]:
        flips, ks, rs = [], [], []
        for sub in subsets:
            ret = lambda m: {s: price(s, m, D(win[1])) / price(s, m, D(win[0])) for s in sub}
            a, b = ret("splits_and_dividends"), ret(alt)
            top = lambda v: set(sorted(v, key=v.get, reverse=True)[:3])
            flips.append(top(a) != top(b)); k, r = geom(a, b); ks.append(k); rs.append(r)
        print(f"top3 return {win[0][:4]}-{win[1][:4]}          total -> {alt:14s}   {statistics.mean(flips):5.1%}   {statistics.mean(ks):+8.3f}  {statistics.mean(rs):7.3f}")
for day in ["2021-06-30", "2023-06-30", "2025-06-30"]:
    for alt in ["splits_only", "none"]:
        flips, ks, rs = [], [], []
        for sub in subsets:
            a = {s: price(s, "splits_and_dividends", D(day)) for s in sub}
            b = {s: price(s, alt, D(day)) for s in sub}
            T = statistics.median(a.values())
            flips.append({s for s in sub if a[s] > T} != {s for s in sub if b[s] > T}); k, r = geom(a, b); ks.append(k); rs.append(r)
        print(f"threshold close {day} > median  adj -> {alt:14s}   {statistics.mean(flips):5.1%}   {statistics.mean(ks):+8.3f}  {statistics.mean(rs):7.3f}")
