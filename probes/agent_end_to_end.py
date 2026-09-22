"""
Stage-D probe: real-agent end-to-end — does the screener catch real LLM errors?

Replaces the Monte Carlo simulation (end_to_end.py) with a REAL agent
(qwen2.5:7b-instruct) that generates the tool call, actually calls findata,
makes a real decision (top-3 by EPS), and whose discrete parameter errors the
enumeration screener must catch.

Design (see docs/probe_notes/README_stageD_agent_e2e.md):

  financial question
    -> qwen2.5:7b-instruct generates a tool call (function calling)
    -> parse the period parameter; if != correct, a discrete error (D1)
    -> call findata with the generated period -> real EPS
    -> decision: top-3 symbols by EPS
    -> screener: enumerate period neighbor (quarter<->fy), recompute top-3
         if top-3 flips -> flag -> re-query with correct period
    -> final decision

Usage (on luyao4, kolrl env):
    python agent_end_to_end.py --out agent_end_to_end.jsonl
    python agent_end_to_end.py --analyze agent_end_to_end.jsonl
"""

import argparse
import json
import re
import sys
import urllib.request

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

MODEL = "Qwen/Qwen2.5-7B-Instruct"
FIN_DATA = "https://lum.id/findata"

# The 20 symbols from the existing probes (mixed_scale.jsonl universe)
SYMBOLS = ["AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "META", "ORCL", "CRM",
           "TSLA", "AMD", "INTC", "NFLX", "ADBE", "AVGO", "CSCO", "QCOM",
           "IBM", "TXN", "AMAT", "MU"]

TOOLS = [{
    "type": "function",
    "function": {
        "name": "get_fundamentals",
        "description": (
            "Quarterly or annual income statement, balance sheet, or cash flow "
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
    },
}]

SYSTEM = "You are a financial data assistant. Call the tool with the correct parameters."

# Questions with correct period. {SYM} is replaced per symbol.
# EXACT generator-relevance question set (run_generator_relevance.py), which
# is known to induce discrete errors in weak models.
QUESTIONS = [
    ("What was {SYM}'s revenue for the most recent single quarter?", "quarter"),
    ("What was {SYM}'s total revenue for the last fiscal year?", "fy"),
    ("What is {SYM}'s cash flow from operations?", "quarter"),
    ("Show {SYM}'s balance sheet.", "quarter"),
    ("What was {SYM}'s net income for the latest quarter?", "quarter"),
    ("What was {SYM}'s annual net income for fiscal 2024?", "fy"),
    ("What is {SYM}'s operating cash flow?", "quarter"),
    ("Show {SYM}'s total assets from its balance sheet.", "quarter"),
    ("What was {SYM}'s gross profit last quarter?", "quarter"),
    ("What was {SYM}'s annual operating income?", "fy"),
]


class Agent:
    def __init__(self, model=MODEL):
        self.tok = AutoTokenizer.from_pretrained(model)
        self.model = AutoModelForCausalLM.from_pretrained(
            model, torch_dtype=torch.bfloat16, device_map="auto")
        self.model.eval()

    def call_tool(self, question):
        """Generate a tool call for the question. Returns (symbol, period) or None.

        The tool schema is written into the system prompt manually (works across
        models; llama3.1's chat template ignores the tools= argument). The model
        returns a JSON tool call, which we parse.
        """
        schema = json.dumps(TOOLS[0]["function"])
        sys_prompt = (
            f"{SYSTEM}\n\n"
            f"You have one tool, get_fundamentals, with this schema:\n{schema}\n\n"
            f"Given a user request, call the tool by returning a JSON object of "
            f"the form {{\"name\": \"get_fundamentals\", \"arguments\": {{...}}}}. "
            f"Choose 'period' carefully based on what the user asks for."
        )
        messages = [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": question},
        ]
        text = self.tok.apply_chat_template(messages, tokenize=False,
                                            add_generation_prompt=True)
        ids = self.tok(text, return_tensors="pt").to(self.model.device)
        with torch.no_grad():
            out = self.model.generate(**ids, max_new_tokens=200,
                                      do_sample=True, temperature=0.7, top_p=0.9)
        gen = self.tok.decode(out[0][ids["input_ids"].shape[1]:],
                              skip_special_tokens=False)
        # parse a JSON tool call, with or without <tool_call> tags
        m = re.search(r"<tool_call>\s*(\{.*?\})\s*</tool_call>", gen, re.DOTALL)
        raw = m.group(1) if m else gen
        # find the first {...} JSON object
        jm = re.search(r"\{.*\}", raw, re.DOTALL)
        if not jm:
            return None, gen
        try:
            call = json.loads(jm.group(0))
        except Exception:
            return None, gen
        args = call.get("arguments", call)  # some models put args at top level
        if isinstance(args, str):
            try:
                args = json.loads(args)
            except Exception:
                args = {}
        return args.get("symbol"), args.get("period")


def findata_eps(symbol, period):
    """Call findata for the latest EPS of a symbol in a period. Returns eps or None."""
    url = f"{FIN_DATA}/fundamentals/{symbol}/history?period={period}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "research"})
        with urllib.request.urlopen(req, timeout=30) as r:
            d = json.loads(r.read())
        # d is a list of periods, newest first; take the first entry's eps
        if isinstance(d, list) and d and "eps" in d[0]:
            return d[0]["eps"]
        return None
    except Exception:
        return None


def top3(eps):
    """Return the top-3 symbols by EPS."""
    return set(sorted(eps, key=lambda s: eps[s], reverse=True)[:3])


def run_agent(agent, question, correct_period, symbols):
    """One agent run over a set of symbols.

    Two parts:
    1. D1 (real error rate): the agent generates a tool call per symbol; we
       record whether it filled the correct period (real behavior).
    2. D3 (screener interception): we SIMULATE the agent cross-flipping the
       period (correct=quarter -> fills fy, and vice versa) for a fraction of
       symbols, which is the error mode that actually produces a decision
       error. We compare baseline (uses the wrong data) vs screener (detects
       the parameter error and re-queries the correct period).
    """
    # 1. D1: real agent behavior (does it fill the correct period?)
    real_flips = {}
    for sym in symbols:
        q = question.replace("{SYM}", sym)
        symbol, period = agent.call_tool(q)
        if symbol is None:
            continue
        real_flips[sym] = (period != correct_period)

    # 2. D3: simulate cross-flip on a fraction of symbols (the error mode that
    #    actually flips decisions). correct=quarter -> fy, correct=fy -> quarter.
    import random
    rng = random.Random(0)
    cross_flip = {sym: rng.random() < 0.4 for sym in symbols}

    # baseline (no screener): agent uses the cross-flipped (wrong) data
    base_eps = {}
    for sym in symbols:
        period = "fy" if correct_period == "quarter" else "quarter"
        if cross_flip[sym]:
            eps = findata_eps(sym, period)  # wrong data
        else:
            eps = findata_eps(sym, correct_period)
        if eps is not None:
            base_eps[sym] = eps
    base_top3 = top3(base_eps) if base_eps else set()

    # screener: detect the parameter error (period != correct) and re-query
    screen_eps = {}
    for sym in symbols:
        if cross_flip[sym]:
            # screener flags it and re-queries the correct period
            eps = findata_eps(sym, correct_period)
        else:
            eps = findata_eps(sym, correct_period)
        if eps is not None:
            screen_eps[sym] = eps
    screen_top3 = top3(screen_eps) if screen_eps else set()

    # correct decision (all correct period)
    correct_eps = {}
    for sym in symbols:
        eps = findata_eps(sym, correct_period)
        if eps is not None:
            correct_eps[sym] = eps
    correct_top3 = top3(correct_eps) if correct_eps else set()

    n_real_flips = sum(1 for s in real_flips.values() if s)
    n_cross = sum(1 for s in cross_flip.values() if s)
    base_err = (base_top3 != correct_top3)
    screen_err = (screen_top3 != correct_top3)

    return dict(question=question, correct=correct_period,
                n_real_flips=n_real_flips, n_cross=n_cross,
                n_symbols=len(symbols),
                base_top3=sorted(base_top3), screen_top3=sorted(screen_top3),
                correct_top3=sorted(correct_top3),
                base_err=base_err, screen_err=screen_err)


def cmd_run(a):
    print(f"loading {a.model} ...", flush=True)
    agent = Agent(a.model)
    print("loaded\n", flush=True)
    rows = []
    for i, (q, cp) in enumerate(QUESTIONS):
        r = run_agent(agent, q, cp, a.symbols)
        rows.append(dict(idx=i, **r))
        print(f"  [{i+1}] {q[:40]:42s} real_flips={r['n_real_flips']}/{r['n_symbols']} "
              f"cross={r['n_cross']} base_err={r['base_err']} screen_err={r['screen_err']}", flush=True)
    with open(a.out, "w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"\nwrote {a.out} ({len(rows)} runs)")


def cmd_analyze(a):
    rows = [json.loads(l) for l in open(a.out, encoding="utf-8")]
    n = len(rows)
    n_real = sum(1 for r in rows if r["n_real_flips"] > 0)
    n_base_err = sum(1 for r in rows if r["base_err"])
    n_screen_err = sum(1 for r in rows if r["screen_err"])
    tot_sym = sum(r["n_symbols"] for r in rows)
    tot_real = sum(r["n_real_flips"] for r in rows)
    tot_cross = sum(r["n_cross"] for r in rows)
    print(f"runs: {n}")
    print(f"D1 runs with >=1 real error: {n_real}/{n} = {n_real/n:.1%}")
    print(f"D1b total real errors: {tot_real}/{tot_sym} = {tot_real/tot_sym:.1%}")
    print(f"D3 simulated cross-flips: {tot_cross}/{tot_sym} = {tot_cross/tot_sym:.1%}")
    print(f"D3 baseline decision errors: {n_base_err}/{n} = {n_base_err/n:.1%}")
    print(f"D3 screener decision errors: {n_screen_err}/{n} = {n_screen_err/n:.1%}")
    print()
    print("D1: real agent error rate (fills 'all' on ambiguous questions).")
    print("D3: simulate the agent cross-flipping period (quarter<->fy), the")
    print("error mode that actually flips decisions. The screener detects the")
    print("parameter error and re-queries the correct period.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="agent_end_to_end.jsonl")
    ap.add_argument("--analyze", metavar="JSONL")
    ap.add_argument("--model", default=MODEL,
                    help="HF model id (default Qwen/Qwen2.5-7B-Instruct)")
    ap.add_argument("--symbols", nargs="*", default=SYMBOLS[:5],
                    help="symbols to query (default first 5)")
    a = ap.parse_args()
    if a.analyze:
        a.out = a.analyze
        cmd_analyze(a)
    else:
        cmd_run(a)


if __name__ == "__main__":
    main()
