"""
Stage-2i probe: scale up + ablation of mixed sensitivity (card 3).

Scales the Stage-2h result to more endpoints, more discrete params, more
symbols, and runs ablations to localize the increment source.

Endpoints with `period` enum (all/fy/quarter):
  /fundamentals/{symbol}/history  (also has `statement`: balance/cashflow/income)
  /enterprise-value/{symbol}
  /key-metrics/{symbol}
  /owner-earnings/{symbol}

Fields per endpoint:
  fundamentals: eps, revenue, net_income, operating_income
  enterprise-value: enterprise_value, market_cap, total_debt, cash_and_short_term
  key-metrics: pe, pb, ps, ev_ebitda, ev_revenue, debt_to_equity, current_ratio, quick_ratio
  owner-earnings: owner_earnings

Usage:
    python build_mixed_sensitivity_scale.py --symbols <20 symbols> --out mixed_scale.jsonl
    python build_mixed_sensitivity_scale.py --analyze mixed_scale.jsonl
"""

import argparse
import json
import urllib.request

BASE = "https://lum.id/findata"
PERIODS = ["quarter", "fy", "all"]
STATEMENTS = ["balance", "cashflow", "income"]

# endpoint -> fields to measure
ENDPOINTS = {
    "fundamentals": ["eps", "revenue", "net_income", "operating_income"],
    "enterprise-value": ["enterprise_value", "market_cap", "total_debt", "cash_and_short_term"],
    "key-metrics": ["pe", "pb", "ps", "ev_ebitda", "ev_revenue", "debt_to_equity", "current_ratio", "quick_ratio"],
    "owner-earnings": ["owner_earnings"],
}


def fd(path):
    try:
        with urllib.request.urlopen(BASE + path, timeout=45) as r:
            return json.loads(r.read())
    except Exception as e:
        return {"error": str(e)[:100]}


def get_value(d, field):
    if isinstance(d, list) and d:
        return d[0].get(field)
    if isinstance(d, dict):
        return d.get(field)
    return None


def rel_diff(a, b):
    if a is None or b is None:
        return None
    scale = max(abs(a), abs(b), 1e-9)
    return abs(a - b) / scale


def endpoint_path(endpoint, sym, **params):
    if endpoint == "fundamentals":
        q = "&".join(f"{k}={v}" for k, v in params.items())
        return f"/fundamentals/{sym}/history?{q}"
    return f"/{endpoint}/{sym}?" + "&".join(f"{k}={v}" for k, v in params.items())


def build(symbols, out_path):
    rows = []
    for sym in symbols:
        # period substitution: quarter -> fy, quarter -> all
        for endpoint, fields in ENDPOINTS.items():
            d_base = fd(endpoint_path(endpoint, sym, period="quarter", limit=1))
            if "error" in d_base:
                continue
            for p2 in PERIODS:
                if p2 == "quarter":
                    continue
                d2 = fd(endpoint_path(endpoint, sym, period=p2, limit=1))
                if "error" in d2:
                    continue
                for field in fields:
                    v1 = get_value(d_base, field)
                    v2 = get_value(d2, field)
                    diff = rel_diff(v1, v2)
                    if diff is not None:
                        rows.append(dict(
                            symbol=sym, endpoint=endpoint, param="period",
                            from_val="quarter", to_val=p2, field=field,
                            v1=v1, v2=v2, observed_jump=diff))
        # statement substitution on fundamentals: income -> balance/cashflow
        # This is a STRUCTURAL jump: income has eps/revenue, balance has
        # total_assets, cashflow has operating_cash_flow. Fields don't overlap,
        # so the jump is "field present in one statement, absent in another".
        # We measure it as: a field present in the base (income) is ABSENT in
        # the neighbor (balance/cashflow) -> structural jump = 1.0 (complete).
        d_base = fd(endpoint_path("fundamentals", sym, period="quarter", statement="income", limit=1))
        if "error" not in d_base:
            base_fields = set(get_value(d_base, f) is not None for f in ENDPOINTS["fundamentals"])
            for s2 in STATEMENTS:
                if s2 == "income":
                    continue
                d2 = fd(endpoint_path("fundamentals", sym, period="quarter", statement=s2, limit=1))
                if "error" in d2:
                    continue
                # structural jump: fraction of income fields that are ABSENT in s2
                present_in_s2 = sum(1 for f in ENDPOINTS["fundamentals"]
                                    if get_value(d2, f) is not None)
                n_fields = len(ENDPOINTS["fundamentals"])
                # if income fields are absent in s2, structural jump is high
                struct_jump = 1.0 - present_in_s2 / n_fields
                rows.append(dict(
                    symbol=sym, endpoint="fundamentals", param="statement",
                    from_val="income", to_val=s2, field="STRUCTURAL",
                    v1=None, v2=None, observed_jump=struct_jump))
        print(f"  {sym}: {sum(1 for r in rows if r['symbol']==sym)} jumps")
    with open(out_path, "w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    return rows


def analyze(path):
    rows = [json.loads(l) for l in open(path, encoding="utf-8")]
    print(f"total substitutions: {len(rows)}\n")

    from collections import defaultdict

    # D_G per (endpoint, param, from, to) = max jump
    def dg_by(key_fn):
        groups = defaultdict(list)
        for r in rows:
            groups[key_fn(r)].append(r["observed_jump"])
        return {k: max(v) for k, v in groups.items()}

    # A1: by endpoint (period quarter->fy)
    print("=== A1: D_G by endpoint (period quarter->fy) ===")
    by_ep = dg_by(lambda r: (r["endpoint"], r["param"], r["from_val"], r["to_val"]))
    ep_dg = defaultdict(list)
    for (ep, param, frm, to), dg in by_ep.items():
        if param == "period" and frm == "quarter" and to == "fy":
            ep_dg[ep].append(dg)
    for ep, dgs in sorted(ep_dg.items()):
        print(f"  {ep:20s} D_G = {max(dgs):.1%} (n={len(dgs)})")
    n_ep_nonzero = sum(1 for ep, dgs in ep_dg.items() if max(dgs) > 0.10)
    print(f"  endpoints with D_G > 10%: {n_ep_nonzero}/{len(ep_dg)}")

    # A2: by discrete param
    print("\n=== A2: D_G by discrete param ===")
    by_param = dg_by(lambda r: (r["param"], r["from_val"], r["to_val"]))
    for (param, frm, to), dg in sorted(by_param.items()):
        print(f"  {param:10s} {frm}->{to}: D_G = {dg:.1%}")

    # A3: by field (fundamentals, period quarter->fy)
    print("\n=== A3: D_G by field (fundamentals, period quarter->fy) ===")
    by_field = defaultdict(list)
    for r in rows:
        if r["endpoint"] == "fundamentals" and r["param"] == "period" \
           and r["from_val"] == "quarter" and r["to_val"] == "fy":
            by_field[r["field"]].append(r["observed_jump"])
    for f, jumps in sorted(by_field.items()):
        print(f"  {f:20s} D_G = {max(jumps):.1%} (n={len(jumps)})")

    # A4: by symbol (fundamentals, period quarter->fy)
    print("\n=== A4: D_G by symbol (fundamentals, period quarter->fy) ===")
    by_sym = defaultdict(list)
    for r in rows:
        if r["endpoint"] == "fundamentals" and r["param"] == "period" \
           and r["from_val"] == "quarter" and r["to_val"] == "fy":
            by_sym[r["symbol"]].append(r["observed_jump"])
    n_sym_nonzero = 0
    for s, jumps in sorted(by_sym.items()):
        dg = max(jumps)
        if dg > 0.10:
            n_sym_nonzero += 1
        print(f"  {s:8s} D_G = {dg:.1%}")
    print(f"  symbols with D_G > 10%: {n_sym_nonzero}/{len(by_sym)}")

    # verdict
    s1 = n_ep_nonzero >= 3
    period_dg = max((v for (p, f, t), v in by_param.items() if p == "period"), default=0)
    stmt_dg = max((v for (p, f, t), v in by_param.items() if p == "statement"), default=0)
    s2 = period_dg > 0.10 and stmt_dg > 0.10
    s3 = n_sym_nonzero / len(by_sym) >= 0.8 if by_sym else False
    print(f"\n=== VERDICT ===")
    print(f"  S1 generalizes across endpoints ({n_ep_nonzero}/4 >= 3): "
          f"{'PASS' if s1 else 'FAIL'}")
    print(f"  S2 generalizes across params (period & statement): "
          f"{'PASS' if s2 else 'FAIL'}")
    print(f"  S3 generalizes across symbols ({n_sym_nonzero}/{len(by_sym)} >= 80%): "
          f"{'PASS' if s3 else 'FAIL'}")
    print(f"\n  All PASS -> increment is structural and generalizes; ablation")
    print(f"  localizes its source (endpoint/param/field/symbol).")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", default="AAPL,MSFT,NVDA,GOOGL,AMZN,META,ORCL,CRM,TSLA,AVGO,AMD,INTC,QCOM,TXN,IBM,CSCO,ADBE,ORCL,NFLX,PYPL")
    ap.add_argument("--out", default="mixed_scale.jsonl")
    ap.add_argument("--analyze", metavar="PATH")
    a = ap.parse_args()
    if a.analyze:
        analyze(a.analyze)
    else:
        syms = [s.strip().upper() for s in a.symbols.split(",") if s.strip()]
        print(f"building scaled mixed sensitivity for {len(syms)} symbols ...")
        rows = build(syms, a.out)
        print(f"\nwrote {a.out} ({len(rows)} substitutions)")
        print("\nrun: python build_mixed_sensitivity_scale.py --analyze " + a.out)


if __name__ == "__main__":
    main()
