"""Candidate A (price adjustment): what do the adjustment switches actually do?
1. yfinance auto_adjust True vs False (and the Adj Close column)
2. findata /ohlc: split-adjusted or raw?
3. corporate actions available (dividends, splits)
Universe mixes high-dividend, no-dividend and split stocks. Snapshot saved."""
import json, time, urllib.request
import yfinance as yf

SYMS = ["KO", "PEP", "PG", "JNJ", "XOM", "CVX", "VZ", "T", "MO", "PM", "IBM", "MMM", "ABBV", "MRK", "PFE",
        "AMZN", "GOOGL", "META", "TSLA", "NFLX", "AMD", "CRM", "ADBE", "BRK-B",
        "NVDA", "AAPL", "AVGO", "CMG", "WMT", "LRCX", "SMCI", "MSFT", "JPM", "HD"]
START, END = "2019-12-01", "2026-01-10"
out = {}
for s in SYMS:
    t = yf.Ticker(s)
    a = t.history(start=START, end=END, auto_adjust=True, actions=True)
    r = t.history(start=START, end=END, auto_adjust=False, actions=True)
    if a.empty or r.empty:
        print(s, "EMPTY"); continue
    d0 = a.index[a.index >= "2020-01-02"][0]
    out[s] = dict(
        date0=str(d0.date()),
        adj_close0=float(a.loc[d0, "Close"]), raw_close0=float(r.loc[d0, "Close"]), adjcol0=float(r.loc[d0, "Adj Close"]),
        adj_last=float(a["Close"].iloc[-1]), raw_last=float(r["Close"].iloc[-1]), last_date=str(a.index[-1].date()),
        n_div=int((r["Dividends"] > 0).sum()), div_sum=float(r["Dividends"].sum()),
        splits=[(str(i.date()), float(v)) for i, v in r["Stock Splits"].items() if v > 0])
    time.sleep(0.3)
for s, o in out.items():
    print(f"{s:6s} 2020-01-02 raw {o['raw_close0']:9.2f} adj {o['adj_close0']:9.2f} ({o['adj_close0']/o['raw_close0']-1:+.1%}) "
          f"| last raw {o['raw_last']:8.2f} adj {o['adj_last']:8.2f} | divs {o['n_div']:2d} sum {o['div_sum']:6.2f} | splits {o['splits']}")
json.dump(out, open("A1_yf_snapshot.json", "w"), indent=1)

# findata ohlc for split stocks: raw or adjusted?
for s in ["NVDA", "AAPL", "TSLA", "AVGO", "CMG", "WMT", "KO"]:
    u = f"https://lum.id/findata/ohlc/{s}?interval=1d&from=2020-01-02&to=2020-01-06"
    try:
        d = json.loads(urllib.request.urlopen(u, timeout=60).read())
        bars = d if isinstance(d, list) else (d.get("bars") or d.get("data") or d)
        b0 = bars[0] if isinstance(bars, list) and bars else bars
        print("findata", s, json.dumps(b0)[:200])
    except Exception as e:
        print("findata", s, "ERR", e)
