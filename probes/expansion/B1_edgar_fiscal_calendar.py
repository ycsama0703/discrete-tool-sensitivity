"""Candidate B (fiscal vs calendar year) on SEC EDGAR companyfacts.
year_basis=fiscal  : the annual period the company labels fiscal year Y (the 10-K whose latest period is it)
year_basis=calendar: the annual fact SEC assigns frame 'CY{Y}' (closest ~365-day period to calendar Y)
Universe mixes December and off-cycle fiscal year ends. Snapshot saved."""
import json, math, statistics, time, urllib.request, random
UA = {"User-Agent": "card3-academic-research contact@example.com"}
def get(u):
    return json.loads(urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=60).read())

SYMS = ["WMT","HD","TGT","NVDA","LOW","DELL","CRM",           # Jan
        "ORCL","NKE","FDX","GIS",                                # May
        "MSFT","CSCO","INTU","PG","CLX","ADP","EL",              # Jun/Jul
        "AAPL","COST","DE","V","SBUX","DIS","ACN","MU","ADBE","QCOM","AVGO",  # Aug-Nov
        "KO","PEP","JNJ","XOM","CVX","GOOGL","AMZN","META","TSLA","IBM","MRK","PFE","UNH","CAT","HON","MCD","T","VZ"]  # Dec
REV = ["RevenueFromContractWithCustomerExcludingAssessedTax", "Revenues", "SalesRevenueNet",
       "RevenueFromContractWithCustomerIncludingAssessedTax"]
tick = get("https://www.sec.gov/files/company_tickers.json")
cik = {v["ticker"]: v["cik_str"] for v in tick.values()}
snap, out = {}, {}
for s in SYMS:
    try:
        f = get(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik[s]:010d}.json")
    except Exception as e:
        print(s, "ERR", e); continue
    snap[s] = f
    gaap = f["facts"].get("us-gaap", {})
    res = {}
    for field, concepts in (("revenue", REV), ("net_income", ["NetIncomeLoss"])):
        best = None
        for c in concepts:
            if c not in gaap or "USD" not in gaap[c]["units"]: continue
            facts = [x for x in gaap[c]["units"]["USD"] if x.get("form") in ("10-K", "10-K/A") and "start" in x]
            annual = [x for x in facts if 330 <= (time.mktime(time.strptime(x["end"], "%Y-%m-%d")) - time.mktime(time.strptime(x["start"], "%Y-%m-%d"))) / 86400 <= 400]
            # fiscal label: for each filing, its latest annual period carries the filing's fy
            by_accn = {}
            for x in annual: by_accn.setdefault(x["accn"], []).append(x)
            fiscal = {}
            for acc, xs in by_accn.items():
                last = max(xs, key=lambda x: x["end"]); fiscal[last["fy"]] = (last["end"], last["val"])
            cal = {x["frame"]: (x["end"], x["val"]) for x in annual if x.get("frame", "").startswith("CY") and len(x["frame"]) == 6}
            if fiscal and cal and (best is None or len(fiscal) > len(best[0])):
                best = (fiscal, cal, c)
        if best: res[field] = dict(concept=best[2], fiscal={str(k): v for k, v in best[0].items()}, calendar=best[1])
    out[s] = res
    fye = res.get("revenue", {}).get("fiscal", {}).get("2023", ("?",))[0]
    r = res.get("revenue", {})
    print(f"{s:5s} FY2023 ends {fye} | rev fiscal2023 {r.get('fiscal',{}).get('2023',(0,0))[1]/1e9:8.2f}B "
          f"calendar CY2023 {r.get('calendar',{}).get('CY2023',(0,0))[1]/1e9:8.2f}B (end {r.get('calendar',{}).get('CY2023',('?',))[0]}) [{r.get('concept')}]")
    time.sleep(0.15)
json.dump(out, open("B1_edgar_extract.json", "w"), indent=1)
print("saved", len(out))
