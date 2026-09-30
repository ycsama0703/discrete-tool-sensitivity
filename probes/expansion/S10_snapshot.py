"""S10 step 1: freeze yfinance daily closes for the 80-stock universe and validate the
'unadjusted' (as-traded) reconstruction. Output: S10_snapshot.json (in probes/)."""
import json, math
import yfinance as yf

GROUPS = {
 "DIVIDEND": ["KO","PEP","PG","JNJ","XOM","CVX","VZ","T","MO","PM","IBM","MMM","ABBV","MRK","PFE","DUK","SO","KMB","BMY","GIS"],
 "TECH":     ["NVDA","AAPL","TSLA","AMZN","GOOGL","AVGO","NFLX","LRCX","SMCI","AMD","META","MSFT","CRM","ADBE","ORCL","QCOM","INTC","CSCO","TXN","MU"],
 "FIN_IND":  ["JPM","BAC","WFC","GS","MS","C","BLK","SCHW","AXP","BRK-B","CAT","DE","HON","GE","UNP","UPS","LMT","RTX","BA","FDX"],
 "CONS_HEALTH": ["WMT","COST","HD","LOW","MCD","SBUX","NKE","CMG","TGT","DIS","UNH","LLY","TMO","ABT","MDT","AMGN","GILD","CVS","ISRG","DHR"],
}
def real_split(f):              # true forward/reverse splits; spin-off factors (1.0-1.5) are not splits
    return f >= 1.5 or 0 < f <= 1 / 1.5
snap = {"groups": GROUPS, "prices": {}, "splits": {}, "ignored_split_factors": {}}
for g, syms in GROUPS.items():
    for s in syms:
        t = yf.Ticker(s)
        a = t.history(start="2020-12-01", end="2026-01-10", auto_adjust=True)
        r = t.history(start="2020-12-01", end="2026-01-10", auto_adjust=False, actions=True)
        snap["prices"][s] = {str(d.date()): [round(float(a.loc[d, "Close"]), 4), round(float(r.loc[d, "Close"]), 4)]
                             for d in r.index if d in a.index}
        sp = [(str(d.date()), float(v)) for d, v in r["Stock Splits"].items() if v > 0]
        snap["splits"][s] = [x for x in sp if real_split(x[1])]
        ign = [x for x in sp if not real_split(x[1])]
        if ign: snap["ignored_split_factors"][s] = ign
        print(f"{g:11s} {s:6s} days {len(snap['prices'][s])} splits {snap['splits'][s]} ignored {ign}")
json.dump(snap, open("../S10_snapshot.json", "w"))

def unadjusted(s, day):
    p = snap["prices"][s][day][1]
    for d, f in snap["splits"][s]:
        if d > day: p *= f
    return p
# known as-traded closes (pre-split history); tolerance 1%
for s, day, known in [("NVDA", "2021-06-30", 800.10), ("AAPL", "2020-12-31", 132.69), ("TSLA", "2021-06-30", 679.70),
                      ("AMZN", "2021-06-30", 3440.16), ("GOOGL", "2021-06-30", 2441.79), ("GE", "2021-06-30", 13.46),
                      ("CMG", "2023-06-30", 2139.00), ("WMT", "2023-06-30", 157.18)]:
    v = unadjusted(s, day); print(f"validate {s} {day}: reconstructed {v:.2f} vs known {known:.2f} ({v/known-1:+.2%})")
