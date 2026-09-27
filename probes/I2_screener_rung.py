"""
I2 (registry: docs/EXPERIMENT_REGISTRY.md) — ladder rung L2.5:
can the screener's output, handed back to the model, make it repair the call?

Context. The B2/B3 ladder (stage F/G) measured DETECTION with graded help:
  L1  told the correct answer              -> ~100% (oracle)
  L2  told nothing ("review your call")    -> recall high, precision collapses
  L3  told "something is wrong", not where -> 0.0%-89.8% across 12 configs
The main line (claim C6) says: the model is not missing capability, it is
missing WHERE to look, and only enumeration can supply that. The rung between
L3 and L1 — "told where, not the answer" — is exactly the screener's output and
has never been measured. I1 (stage J) showed that telling the model where (S2/S3)
fixes errors, but those descriptions were written with hindsight. Here the hint
is restricted to what the enumeration screener actually knows at deployment.

What the screener knows, and all it is allowed to say:
  - which parameter the result is sensitive to (it enumerated every enum value)
  - what the tool returns under each value (it made those calls)
  - NOT which value is correct.

Arms (applied to EVERY case, correct or wrong — on this universe the screener
flags every question, S4: 20/20, so a deployment would show the hint on all):
  R0 reask   control: "reconsider period; answer quarter/fy/all". Same answer
             format, no screener information. Separates "a second chance" from
             "the screener's information".
  R1 where   L2.5a: screener says the result depends on `period`, values return
             different data, it did not decide which is correct.
  R2 where+outputs  L2.5b: R1 plus what the tool actually returned under each
             value (first record: period_type, period_end_date, revenue),
             fetched live from findata. Only enumeration can produce this.

The model's call is REPLAYED from the recorded ladder file (same cases, same
errors as B2/B3), so results line up row-for-row with L1/L2/L3.

Metrics (per arm; the arm's one-word answer becomes the final period):
  repair      P(final == correct | originally wrong)
  corruption  P(final != correct | originally right)
  err_after   P(final != correct)          vs err_before (the recorded rate)
  Reported STRICT (as in B2/B3: `all` is an error) and CHARITABLE (`all`
  counts as right for quarter questions, because findata's `all` series leads
  with the same quarterly record — see S4).

PRE-REGISTERED PREDICTIONS (fixed before any run; thresholds are proposals):
  H1 main line   R2 err_after <= 0.5 x err_before, and
                 R2 repair >= R0 repair + 30pp               (qwen2.5-7b local)
  H2 not just a second chance   R0 repair <= 20%
  H3 decomposition   R2 repair >= R1 repair + 15pp -> the enumeration OUTPUTS
                 carry the effect beyond naming the parameter. If R1 ~ R2,
                 naming the parameter is enough (still screener-derived).
  H4 cost        R2 corruption <= 5%
  H5 (full run)  across configs, the spread of R2 repair is much narrower than
                 L3's 0-90% -> screener information removes the unpredictable
                 dependence on which model you happen to run.
  FALSIFIED if   R2 repair <= R0 repair + 10pp: telling the model where does not
                 help; the screener cannot work THROUGH the model and must act
                 directly (select / abstain / ask the user). Report as such.

Known caveats (write into the note whatever the result):
  - Ground-truth periods for the ambiguous questions ("current assets",
    "cash flow from operations"...) were assigned by us.
  - R2 shows the API's own record labels (Q3 / FY). That is interface
    information, legitimately available to a screener, but the effect may
    depend on APIs labelling their records.
  - findata's fundamentals endpoint returns income-statement fields whatever
    `statement` is, so R2 shows revenue even for balance-sheet questions.

Usage:
  # smoke test (5 symbols x 20 questions), local qwen on luyao4
  python I2_screener_rung.py --replay stageF_ladder_qwen.jsonl \
      --backend transformers --n-symbols 5 --out I2_qwen_smoke.jsonl
  # API model (reads OPENROUTER_API_KEY like stage G)
  python I2_screener_rung.py --replay stageG_sonnet5.jsonl \
      --backend openrouter --model anthropic/claude-sonnet-5 --out I2_sonnet5.jsonl
  python I2_screener_rung.py --analyze I2_qwen_smoke.jsonl
"""

import argparse
import json
import os
import re
import urllib.request
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
FIN = "https://lum.id/findata"
CACHE = os.path.join(HERE, "I2_findata_first_records.json")

SYSTEM = "You are a financial data assistant. Call the tool with the correct parameters."
SCHEMA = {
    "name": "get_fundamentals",
    "description": ("Quarterly or annual income statement, balance sheet, or cash flow "
                    "summary for a US-listed company. Use 'statement' to choose the "
                    "statement type, and 'period' to choose quarter vs annual."),
    "parameters": {
        "type": "object",
        "properties": {
            "symbol": {"type": "string", "description": "Ticker, e.g. AAPL"},
            "statement": {"type": "string", "enum": ["balance", "cashflow", "income"],
                          "description": "Which statement: balance sheet, cash flow, or income"},
            "period": {"type": "string", "enum": ["all", "fy", "quarter"],
                       "description": "quarter = single quarter, fy = fiscal year, all = both"},
        },
        "required": ["symbol"],
    },
}  # identical to stage F/G, so the model sees the same interface

ANSWER = "Answer with exactly one word: quarter, fy, or all."


# --- what the screener knows: the tool's output under every enum value ------

def first_records(symbols):
    cache = json.load(open(CACHE, encoding="utf-8")) if os.path.exists(CACHE) else {}
    for s in symbols:
        if s in cache:
            continue
        cache[s] = {}
        for p in ("quarter", "fy", "all"):
            req = urllib.request.Request(f"{FIN}/fundamentals/{s}/history?period={p}",
                                         headers={"User-Agent": "research"})
            with urllib.request.urlopen(req, timeout=30) as r:
                d = json.loads(r.read())
            rec = d[0] if isinstance(d, list) and d else {}
            kinds = sorted({x.get("period_type") for x in d}) if isinstance(d, list) else []
            cache[s][p] = dict(period_type=rec.get("period_type"),
                               period_end_date=rec.get("period_end_date"),
                               revenue=rec.get("revenue"), kinds=kinds)
    json.dump(cache, open(CACHE, "w", encoding="utf-8"), indent=1)
    return cache


def fmt_outputs(sym, rec):
    def one(p):
        r = rec[p]
        rev = f"{r['revenue']:,}" if isinstance(r["revenue"], (int, float)) else "n/a"
        return (f"  period={p}: first record period_type={r['period_type']}, "
                f"period_end_date={r['period_end_date']}, revenue={rev}")
    lines = [one("quarter"), one("fy"), one("all")]
    lines[2] += (f" (the series mixes record types: {', '.join(k for k in rec['all']['kinds'] if k)})")
    return f"What the tool returns for {sym} under each value of period:\n" + "\n".join(lines)


# --- prompts ----------------------------------------------------------------

def messages(arm, question, filled, sym, rec):
    base = (f"{SYSTEM}\n\nYou have one tool, get_fundamentals, with this schema:\n"
            f"{json.dumps(SCHEMA)}\n\nYou just generated a tool call for the user's request.")
    if arm == "R0":
        follow = (f"Reconsider the 'period' you chose for this request. Which value of "
                  f"period does the request need? {ANSWER}")
    else:
        follow = ("An external screener re-ran your call with every allowed value of each "
                  "parameter. It found that the result depends on the 'period' parameter: "
                  "different values of period return different data. The screener did NOT "
                  "determine which value is correct for this request.")
        if arm == "R2":
            follow += "\n\n" + fmt_outputs(sym, rec)
        follow += f"\n\nWhich value of period does the request need? {ANSWER}"
    return [
        {"role": "system", "content": base},
        {"role": "user", "content": question},
        {"role": "assistant", "content": f"I called get_fundamentals with period={filled}."},
        {"role": "user", "content": follow},
    ]


def parse_answer(gen):
    low = (gen or "").strip().lower()
    if low.strip(" .\"'`*") in ("quarter", "fy", "all"):
        return low.strip(" .\"'`*")
    hits = re.findall(r"\b(quarter|fy|all)\b", low)
    return hits[-1] if hits else None  # reasoning text tends to end with the answer


# --- backends (reuse stage F/G agents so decoding settings match) ------------

def make_backend(a):
    if a.backend == "transformers":
        from stageF_selfcheck import Agent
        ag = Agent(a.model)
        return lambda m: ag._generate(m, max_new=30)
    if a.backend == "ollama":
        from stageF_selfcheck import OllamaAgent
        ag = OllamaAgent(a.model)
        return lambda m: ag._chat(m, max_new=30)
    from stageG_openrouter_ladder import ORAgent, load_key
    ag = ORAgent(a.model, load_key())
    return lambda m: ag._chat(m, max_new=600)  # reasoning models, see stage G


# --- run / analyze ----------------------------------------------------------

def cmd_run(a):
    rows = [json.loads(l) for l in open(os.path.join(HERE, a.replay), encoding="utf-8")]
    rows = [r for r in rows if not r.get("parse_failed") and r.get("filled_period")]
    syms = []
    for r in rows:
        if r["symbol"] not in syms:
            syms.append(r["symbol"])
    syms = syms[:a.n_symbols]
    rows = [r for r in rows if r["symbol"] in syms]
    recs = first_records(syms)
    gen = make_backend(a)

    def one(r):
        q = r["question"].replace("{SYM}", r["symbol"])
        out = dict(idx=r["idx"], symbol=r["symbol"], correct=r["correct"],
                   filled=r["filled_period"], real_error=r["real_error"],
                   det_L3=r.get("det_L3"), replay=a.replay, model=a.model)
        for arm in ("R0", "R1", "R2"):
            g = gen(messages(arm, q, r["filled_period"], r["symbol"], recs[r["symbol"]]))
            out[f"ans_{arm}"] = parse_answer(g)
            out[f"raw_{arm}"] = (g or "")[-300:]
        return out

    print(f"{len(rows)} cases, symbols={syms}, backend={a.backend}", flush=True)
    with open(os.path.join(HERE, a.out), "w", encoding="utf-8") as fh:
        if a.backend == "openrouter":
            with ThreadPoolExecutor(max_workers=a.concurrency) as ex:
                for o in ex.map(one, rows):
                    fh.write(json.dumps(o, ensure_ascii=False) + "\n"); fh.flush()
        else:
            for r in rows:
                o = one(r)
                fh.write(json.dumps(o, ensure_ascii=False) + "\n"); fh.flush()
                print(f"  {o['symbol']:5} [{o['idx']:2}] filled={o['filled']:7} "
                      f"R0={o['ans_R0']} R1={o['ans_R1']} R2={o['ans_R2']}", flush=True)
    print(f"wrote {a.out}")


def right(p, correct, charitable):
    return p == correct or (charitable and correct == "quarter" and p == "all")


def cmd_analyze(path):
    rows = [json.loads(l) for l in open(os.path.join(HERE, path), encoding="utf-8")]
    n = len(rows)
    print(f"{path}: {n} cases")
    for mode, ch in (("STRICT", False), ("CHARITABLE", True)):
        before = [not right(r["filled"], r["correct"], ch) for r in rows]
        wrong = [r for r, b in zip(rows, before) if b]
        ok = [r for r, b in zip(rows, before) if not b]
        print(f"\n[{mode}] err_before = {sum(before)}/{n} = {sum(before)/n:.1%}")
        print(f"  {'arm':4} {'parsed':>7} {'repair':>14} {'corruption':>14} {'err_after':>10}")
        for arm in ("R0", "R1", "R2"):
            k = f"ans_{arm}"
            parsed = sum(1 for r in rows if r[k])
            fin = lambda r: r[k] or r["filled"]  # unparsed -> keep original call
            rep = sum(1 for r in wrong if right(fin(r), r["correct"], ch))
            cor = sum(1 for r in ok if not right(fin(r), r["correct"], ch))
            after = sum(1 for r in rows if not right(fin(r), r["correct"], ch))
            print(f"  {arm:4} {parsed:4}/{n:<3} {rep:4}/{len(wrong):<4}={rep/max(len(wrong),1):5.1%} "
                  f"{cor:4}/{len(ok):<4}={cor/max(len(ok),1):5.1%} {after/n:9.1%}")
    l3 = [r for r in rows if r["real_error"] and r.get("det_L3") is not None]
    if l3:
        print(f"\nreference, same cases: L3 recall (localisation only) = "
              f"{sum(1 for r in l3 if r['det_L3'])}/{len(l3)}")
    print("\nPre-registered: H1 R2 err_after <= 0.5*before and R2 repair >= R0+30pp; "
          "H2 R0 repair <= 20%; H3 R2 >= R1+15pp; H4 R2 corruption <= 5%; "
          "FALSIFIED if R2 repair <= R0+10pp.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--replay", help="recorded ladder file (stage F/G output)")
    ap.add_argument("--backend", choices=["transformers", "ollama", "openrouter"],
                    default="transformers")
    ap.add_argument("--model", default="Qwen/Qwen2.5-7B-Instruct")
    ap.add_argument("--n-symbols", type=int, default=20)
    ap.add_argument("--concurrency", type=int, default=8)
    ap.add_argument("--out", default="I2_out.jsonl")
    ap.add_argument("--analyze")
    a = ap.parse_args()
    if a.analyze:
        cmd_analyze(a.analyze)
    else:
        cmd_run(a)


if __name__ == "__main__":
    main()
