"""Candidate B: fiscal vs calendar (SEC frame) year basis. Re-extract per field choosing, for each
year, the first concept that HAS that year (companies switch concepts over time), then the flip
geometry over random 20-firm subsets for revenue and net income, years 2022-2024."""
import json, math, random, statistics, time, urllib.request
UA = {"User-Agent": "card3-academic-research contact@example.com"}
REV = ["RevenueFromContractWithCustomerExcludingAssessedTax", "Revenues", "SalesRevenueNet",
       "RevenueFromContractWithCustomerIncludingAssessedTax"]
FIELDS = {"revenue": REV, "net_income": ["NetIncomeLoss"]}
def days(x):
    return (time.mktime(time.strptime(x["end"], "%Y-%m-%d")) - time.mktime(time.strptime(x["start"], "%Y-%m-%d"))) / 86400
def annual(gaap, c):
    if c not in gaap or "USD" not in gaap[c]["units"]: return []
    return [x for x in gaap[c]["units"]["USD"] if x.get("form") in ("10-K", "10-K/A") and "start" in x and 330 <= days(x) <= 400]
def fiscal_of(xs):
    by = {}
    for x in xs: by.setdefault(x["accn"], []).append(x)
    out = {}
    for acc, ys in by.items():
        last = max(ys, key=lambda x: x["end"]); out[str(last["fy"])] = (last["end"], last["val"])
    return out
tick = json.loads(urllib.request.urlopen(urllib.request.Request("https://www.sec.gov/files/company_tickers.json", headers=UA)).read())
cik = {v["ticker"]: v["cik_str"] for v in tick.values()}
SYMS = json.load(open("B1_edgar_extract.json")).keys()
data = {}
for s in SYMS:
    f = json.loads(urllib.request.urlopen(urllib.request.Request(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik[s]:010d}.json", headers=UA), timeout=60).read())
    gaap = f["facts"].get("us-gaap", {}); data[s] = {}
    for field, concepts in FIELDS.items():
        for Y in ("2022", "2023", "2024"):
            fv = cv = None
            for c in concepts:
                xs = annual(gaap, c)
                fi = fiscal_of(xs).get(Y); ca = next(((x["end"], x["val"]) for x in xs if x.get("frame") == f"CY{Y}"), None)
                if fi and ca: fv, cv = fi, ca; break
            data[s][(field, Y)] = (fv, cv)
    time.sleep(0.12)
json.dump({s: {f"{k[0]}|{k[1]}": v for k, v in d.items()} for s, d in data.items()}, open("B2_edgar_fiscal_calendar.json", "w"), indent=1)
for Y in ("2022", "2023", "2024"):
    diff = [s for s in data if data[s][("revenue", Y)][0] and data[s][("revenue", Y)][0] != data[s][("revenue", Y)][1]]
    have = [s for s in data if data[s][("revenue", Y)][0]]
    print(f"revenue {Y}: {len(have)} firms with both; differ: {len(diff)} -> {diff}")
rng = random.Random(0)
print("\nfield       year  decision   flip%   kappa   rho   (200 random 20-firm subsets)")
for field in FIELDS:
    for Y in ("2022", "2023", "2024"):
        pool = [s for s in data if data[s][(field, Y)][0] and data[s][(field, Y)][1]]
        fl3, flt, ks, rs = [], [], [], []
        for _ in range(200):
            sub = rng.sample(pool, 20)
            a = {s: data[s][(field, Y)][0][1] for s in sub}; b = {s: data[s][(field, Y)][1][1] for s in sub}
            top = lambda v: set(sorted(v, key=v.get, reverse=True)[:3])
            T = statistics.median(a.values())
            fl3.append(top(a) != top(b)); flt.append({s for s in sub if a[s] > T} != {s for s in sub if b[s] > T})
            xs = [s for s in sub if a[s] > 0 and b[s] > 0]
            sq = statistics.pstdev(math.log(a[s]) for s in xs); lr = [math.log(b[s] / a[s]) for s in xs]
            ks.append(statistics.mean(lr) / sq); rs.append(statistics.pstdev(lr) / sq)
        print(f"{field:11s} {Y}  top3/thr  {statistics.mean(fl3):5.1%} / {statistics.mean(flt):5.1%}  {statistics.mean(ks):+.3f}  {statistics.mean(rs):.3f}  (pool {len(pool)})")
