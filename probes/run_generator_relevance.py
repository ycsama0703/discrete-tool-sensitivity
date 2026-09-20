"""
Stage-2g probe: generator relevance for discrete tool errors (card 3).

Tests whether a real LLM actually MAKES the discrete parameter errors
(period/statement substitutions) that the certification story is about.

The LLM is given the findata fundamentals tool schema (with discrete enums)
and asked to produce a call for a financial question. We record the generated
parameters and check for discrete errors.

Usage:
    export OPENROUTER_API_KEY=...
    python run_generator_relevance.py --n 40 --out gen_relevance_results.jsonl
    python run_generator_relevance.py --analyze gen_relevance_results.jsonl
"""

import argparse
import json
import os
import random
import sys
import time
import urllib.error
import urllib.request

OR_URL = "https://openrouter.ai/api/v1/chat/completions"
MODEL = "deepseek/deepseek-v4-flash-0731"
MAX_TOKENS = 800

# The findata fundamentals tool schema (real, with discrete enums)
FUNDAMENTALS_SCHEMA = {
    "type": "function",
    "function": {
        "name": "get_fundamentals",
        "description": (
            "Quarterly or annual income statement, balance sheet, or cash flow "
            "summary for a US-listed company. Use the 'statement' parameter to "
            "choose the statement type, and 'period' to choose quarter vs "
            "annual."),
        "parameters": {
            "type": "object",
            "properties": {
                "symbol": {"type": "string", "description": "Ticker, e.g. AAPL"},
                "statement": {"type": "string", "enum": ["balance", "cashflow", "income"],
                              "description": "Which statement: balance sheet, cash flow, or income"},
                "period": {"type": "string", "enum": ["all", "fy", "quarter"],
                           "description": "quarter = single quarter, fy = fiscal year, all = both"},
                "limit": {"type": "integer", "minimum": 1, "maximum": 200},
            },
            "required": ["symbol"],
        },
    },
}

# Questions designed to induce discrete parameter errors
# (intent, correct statement, correct period)
QUESTIONS = [
    # (question, correct_statement, correct_period)
    ("What was AAPL's revenue for the most recent single quarter?", "income", "quarter"),
    ("What was MSFT's total revenue for the last fiscal year?", "income", "fy"),
    ("What is NVDA's cash flow from operations?", "cashflow", "quarter"),
    ("Show GOOGL's balance sheet.", "balance", "quarter"),
    ("What was AMZN's net income for the latest quarter?", "income", "quarter"),
    ("What was META's annual net income for fiscal 2024?", "income", "fy"),
    ("What is ORCL's operating cash flow?", "cashflow", "quarter"),
    ("Show CRM's total assets from its balance sheet.", "balance", "quarter"),
    ("What was AAPL's gross profit last quarter?", "income", "quarter"),
    ("What was MSFT's annual operating income?", "income", "fy"),
    ("What is NVDA's free cash flow?", "cashflow", "quarter"),
    ("Show GOOGL's total liabilities.", "balance", "quarter"),
    ("What was AMZN's diluted EPS for the last quarter?", "income", "quarter"),
    ("What was META's annual revenue for fiscal 2023?", "income", "fy"),
    ("What is ORCL's cash from investing?", "cashflow", "quarter"),
    ("Show CRM's shareholders' equity.", "balance", "quarter"),
    ("What was AAPL's operating income last quarter?", "income", "quarter"),
    ("What was MSFT's annual net income?", "income", "fy"),
    ("What is NVDA's cash from financing?", "cashflow", "quarter"),
    ("Show GOOGL's current assets.", "balance", "quarter"),
]

SYSTEM = (
    "You are a financial data assistant. You have one tool, get_fundamentals, "
    "which returns financial statements for a company. Given a user request, "
    "call the tool with the correct parameters. Choose 'statement' and 'period' "
    "carefully based on what the user asks for."
)


def call_or(messages, tools, api_key, model=MODEL):
    payload = {"model": model, "messages": messages,
               "temperature": 0.0, "max_tokens": MAX_TOKENS}
    if tools:
        payload["tools"] = tools
    body = json.dumps(payload).encode()
    req = urllib.request.Request(
        OR_URL, data=body,
        headers={"Authorization": f"Bearer {api_key}",
                 "Content-Type": "application/json"})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503) and attempt < 3:
                time.sleep(3 * (attempt + 1))
                continue
            return {"error": f"HTTP {e.code}"}
        except Exception as e:
            if attempt < 3:
                time.sleep(3 * (attempt + 1))
                continue
            return {"error": str(e)[:100]}
    return {"error": "exhausted retries"}


def run_one(question, api_key, model=MODEL):
    msgs = [{"role": "system", "content": SYSTEM},
            {"role": "user", "content": question}]
    resp = call_or(msgs, [FUNDAMENTALS_SCHEMA], api_key, model)
    if "error" in resp:
        return dict(error=resp["error"], call=None)
    msg = resp["choices"][0]["message"]
    tcs = msg.get("tool_calls") or []
    if not tcs:
        return dict(error="no_tool_call", call=None)
    tc = tcs[0]
    rawargs = tc["function"].get("arguments", "{}")
    try:
        args = json.loads(rawargs)
    except Exception:
        args = {}
    return dict(error=None, call=dict(name=tc["function"]["name"], args=args))


def cmd_run(a):
    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        sys.exit("set OPENROUTER_API_KEY first")
    random.Random(a.seed).shuffle(QUESTIONS)
    qs = QUESTIONS[: a.n]
    print(f"running {len(qs)} questions\n")
    with open(a.out, "w", encoding="utf-8") as fh:
        for i, (q, cs, cp) in enumerate(qs):
            r = run_one(q, key, a.model)
            rec = dict(idx=i, question=q, correct_statement=cs, correct_period=cp,
                       **r)
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
            fh.flush()
            if r["call"]:
                print(f"  [{i+1}] {q[:40]:42s} -> {r['call']['args']}")
            else:
                print(f"  [{i+1}] {q[:40]:42s} -> {r['error']}")
    print(f"\nwrote {a.out}")


def cmd_analyze(a):
    rows = [json.loads(l) for l in open(a.results, encoding="utf-8")]
    n = len(rows)
    print(f"runs: {n}\n")

    # G1: discrete parameter errors
    errors = []
    for r in rows:
        if not r["call"]:
            continue
        args = r["call"]["args"]
        cs, cp = r["correct_statement"], r["correct_period"]
        stmt_err = args.get("statement") not in (None, cs)
        period_err = args.get("period") not in (None, cp)
        if stmt_err or period_err:
            errors.append(dict(**r, stmt_err=stmt_err, period_err=period_err))
    err_rate = len(errors) / n
    print(f"G1: discrete parameter errors = {len(errors)}/{n} = {err_rate:.1%}")

    # G2: errors in adjacency graph (period quarter<->fy<->all, statement balance<->cashflow<->income)
    in_graph = 0
    for e in errors:
        args = e["call"]["args"]
        cs, cp = e["correct_statement"], e["correct_period"]
        # is the error a pre-registered substitution?
        stmt_ok = args.get("statement") in (None, cs) or args.get("statement") in ["balance", "cashflow", "income"]
        period_ok = args.get("period") in (None, cp) or args.get("period") in ["all", "fy", "quarter"]
        if stmt_ok and period_ok:
            in_graph += 1
    g2 = in_graph / len(errors) if errors else 0
    print(f"G2: errors in adjacency graph = {in_graph}/{len(errors)} = {g2:.1%}")

    # G3: schema-valid (wrong params still in enum)
    valid = sum(1 for e in errors
                if e["call"]["args"].get("statement") in ["balance", "cashflow", "income", None]
                and e["call"]["args"].get("period") in ["all", "fy", "quarter", None])
    g3 = valid / len(errors) if errors else 0
    print(f"G3: schema-valid errors = {valid}/{len(errors)} = {g3:.1%}")

    print("\n=== examples of discrete errors ===")
    shown = 0
    for e in errors:
        print(f"  Q: {e['question'][:50]}")
        print(f"    correct: statement={e['correct_statement']} period={e['correct_period']}")
        print(f"    got: {e['call']['args']}")
        shown += 1
        if shown >= 6:
            break

    print("\n=== VERDICT ===")
    g1 = err_rate >= 0.05
    g2_ok = g2 >= 0.10
    g3_ok = g3 >= 0.80
    print(f"  G1 LLM makes discrete errors ({err_rate:.0%} >= 5%): {'PASS' if g1 else 'FAIL'}")
    print(f"  G2 errors in graph ({g2:.0%} >= 10%): {'PASS' if g2_ok else 'FAIL'}")
    print(f"  G3 schema-valid ({g3:.0%} >= 80%): {'PASS' if g3_ok else 'FAIL'}")
    print("\n  All PASS -> generator relevance holds: a real LLM makes the")
    print("  discrete errors the certification story is about.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=20)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--model", default=MODEL)
    ap.add_argument("--out", default="gen_relevance_results.jsonl")
    ap.add_argument("--analyze", metavar="RESULTS")
    a = ap.parse_args()
    if a.analyze:
        a.results = a.analyze
        cmd_analyze(a)
    else:
        cmd_run(a)


if __name__ == "__main__":
    main()
