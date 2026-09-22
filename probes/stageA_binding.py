"""
Stage-A probe: does the correct semantic binding dominate parameter choice?

Tests Proposition 1 of docs/llm_semantic_binding_theory.md on a real
open-weight LLM (Qwen2.5-7B-Instruct on luyao4).

For each task we build the full u x v grid (request semantics x schema
mapping). For each cell we read the model's logits at the parameter position
and take the log-odds of the two candidate parameter symbols, then recover the
saturated two-factor expansion

    ell(u,v) = a + b*u + c*v + d*u*v

and test whether d > B (the correct binding dominates) or whether a main
effect (symbol preference) dominates despite d > 0.

Uses transformers for EXACT logits (not ollama top-N), so candidates that
fall out of a top-k list are still measured exactly.

Usage (on luyao4, in the kolrl env):
    python stageA_binding.py --out stageA_binding.jsonl
    python stageA_binding.py --analyze stageA_binding.jsonl
"""

import argparse
import json
import os
import sys
import time

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

MODEL_NAME = "Qwen/Qwen2.5-7B-Instruct"
TOP_LOGPROBS = 20  # unused in transformers mode; kept for interface parity

# ---------------------------------------------------------------------------
# Task templates.
#
# u = +1 -> "quarter", u = -1 -> "annual"
# v = +1 -> symbol A means quarter, v = -1 -> symbol A means annual
# correct output z* = u*v : +1 -> A, -1 -> B
# ---------------------------------------------------------------------------

FINANCIAL = [
    ("fin_aapl_rev", "AAPL", "revenue",
     "the most recent single quarter", "the last fiscal year"),
    ("fin_msft_rev", "MSFT", "revenue",
     "the most recent single quarter", "the last fiscal year"),
    ("fin_nvda_cfo", "NVDA", "cash flow from operations",
     "the most recent single quarter", "the last fiscal year"),
    ("fin_googl_bs", "GOOGL", "total assets",
     "the most recent single quarter", "the last fiscal year"),
    ("fin_amzn_ni", "AMZN", "net income",
     "the most recent single quarter", "the last fiscal year"),
    ("fin_meta_ni", "META", "net income",
     "the most recent single quarter", "the last fiscal year"),
]

NEUTRAL = [
    ("neu_temp", "the temperature", "set to",
     "the low setting", "the high setting"),
    ("neu_unit", "the measurement", "expressed in",
     "metric units", "imperial units"),
    ("neu_mode", "the device", "configured in",
     "the fast mode", "the safe mode"),
    ("neu_fmt", "the report", "formatted as",
     "the short form", "the long form"),
]

SYMBOL_PAIRS = [("A", "B"), ("X", "Y"), ("Q", "A"), ("L", "H")]

SYSTEM = (
    "You are a precise data assistant. You call one tool. The tool has a "
    "parameter whose value must match what the user asked for. Choose the "
    "parameter value carefully."
)


def build_prompt(task, u, v, symbols, native):
    """Build a prompt whose final token position is the target parameter value.

    native=True  -> the parameter value is the literal quarter/fy string.
    native=False -> the parameter value is a symbol (A/B etc.) whose meaning
                    is given by the mapping v.
    """
    tid, obj, attr, q_phrase, a_phrase = task
    request = q_phrase if u == +1 else a_phrase

    if native:
        correct = "quarter" if u == +1 else "fy"
        prompt = (
            f"{SYSTEM}\n\n"
            f"User request: give me {obj} for {request}.\n"
            f"Tool schema: the parameter 'period' takes one of "
            f"['quarter', 'fy']. 'quarter' = single quarter, 'fy' = fiscal year.\n"
            f"Call the tool. The value of 'period' should be: "
        )
        return prompt, correct

    sym_q, sym_a = symbols
    if v == +1:
        sym_quarter, sym_annual = sym_q, sym_a
    else:
        sym_quarter, sym_annual = sym_a, sym_q
    correct = sym_quarter if u == +1 else sym_annual
    prompt = (
        f"{SYSTEM}\n\n"
        f"User request: give me {obj} for {request}.\n"
        f"Tool schema: the parameter 'period' takes one of "
        f"['{sym_quarter}', '{sym_annual}']. Here '{sym_quarter}' means single "
        f"quarter, '{sym_annual}' means fiscal year.\n"
        f"Call the tool. The value of 'period' should be: "
    )
    return prompt, correct


class BindingModel:
    def __init__(self, model_name=MODEL_NAME):
        self.tok = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModelForCausalLM.from_pretrained(
            model_name, torch_dtype=torch.bfloat16, device_map="auto")
        self.model.eval()

    def logprob(self, prompt, token_str):
        """log P(token_str | prompt) at the final position, exact."""
        ids = self.tok(prompt, return_tensors="pt")
        ids = {k: v.to(self.model.device) for k, v in ids.items()}
        with torch.no_grad():
            out = self.model(**ids)
        logits = out.logits[0, -1, :]  # final position, full vocab
        logp = torch.log_softmax(logits, dim=-1)
        # token_str may be multi-token; handle single-token candidates here
        tids = self.tok(token_str, add_special_tokens=False)["input_ids"]
        if len(tids) == 1:
            return logp[tids[0]].item()
        # multi-token: sum log-probs (approximate, first token at this position)
        return logp[tids[0]].item()


def measure_cell(bm, task, u, v, symbols, native):
    prompt, correct = build_prompt(task, u, v, symbols, native)
    if native:
        cand = {"quarter": bm.logprob(prompt, "quarter"),
                "fy": bm.logprob(prompt, "fy")}
    else:
        sym_q, sym_a = symbols
        cand = {sym_q: bm.logprob(prompt, sym_q),
                sym_a: bm.logprob(prompt, sym_a)}
    other = "fy" if correct == "quarter" else "quarter" if native else (
        sym_a if correct == sym_q else sym_q)
    ell = cand[correct] - cand[other]
    return dict(correct=correct, p_correct=cand[correct], p_other=cand[other],
                ell=ell, prompt=prompt)


def run_task(bm, task, native, symbols, out_rows):
    ells = {}
    for u in (+1, -1):
        for v in (+1, -1):
            r = measure_cell(bm, task, u, v, symbols, native)
            ells[(u, v)] = r["ell"]
            out_rows.append(dict(task=task[0], native=native,
                                 symbols="-".join(symbols), u=u, v=v, **r))
    return ells


def recover_coeffs(ells, native):
    if any(ells[(u, v)] is None for u in (+1, -1) for v in (+1, -1)):
        return None
    a = 0.25 * sum(ells[(u, v)] for u in (+1, -1) for v in (+1, -1))
    b = 0.25 * sum(u * ells[(u, v)] for u in (+1, -1) for v in (+1, -1))
    if native:
        return dict(a=a, b=b, c=None, d=None, native=True)
    c = 0.25 * sum(v * ells[(u, v)] for u in (+1, -1) for v in (+1, -1))
    d = 0.25 * sum(u * v * ells[(u, v)] for u in (+1, -1) for v in (+1, -1))
    return dict(a=a, b=b, c=c, d=d, native=False)


def cmd_run(a):
    print(f"loading {a.model} ...", flush=True)
    bm = BindingModel(a.model)
    print("loaded\n", flush=True)
    rows, results = [], []
    for task in FINANCIAL + NEUTRAL:
        ells = run_task(bm, task, native=True, symbols=("A", "B"), out_rows=rows)
        results.append(dict(task=task[0], interface="native",
                            coeffs=recover_coeffs(ells, native=True),
                            ells={f"{u},{v}": ells[(u, v)] for u in (+1, -1) for v in (+1, -1)}))
        print(f"  native {task[0]} done", flush=True)
    for task in FINANCIAL + NEUTRAL:
        for symbols in SYMBOL_PAIRS:
            ells = run_task(bm, task, native=False, symbols=symbols, out_rows=rows)
            results.append(dict(task=task[0], interface="adapter",
                                symbols="-".join(symbols),
                                coeffs=recover_coeffs(ells, native=False),
                                ells={f"{u},{v}": ells[(u, v)] for u in (+1, -1) for v in (+1, -1)}))
        print(f"  adapter {task[0]} done", flush=True)
    with open(a.out, "w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    with open(a.out.replace(".jsonl", "_coeffs.jsonl"), "w", encoding="utf-8") as fh:
        for r in results:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"\nwrote {a.out} ({len(rows)} cells) and "
          f"{a.out.replace('.jsonl','_coeffs.jsonl')} ({len(results)} tasks)")


def cmd_analyze(a):
    coeffs = [json.loads(l) for l in open(a.coeffs, encoding="utf-8")]
    print(f"tasks: {len(coeffs)}\n")
    print(f"{'task':<22}{'iface':<9}{'sym':<6}{'a':>7}{'b':>7}{'c':>7}{'d':>7}  d>B?  verdict")
    print("-" * 78)
    n_dom = n_pos_wrong = n_sympref = 0
    n_adapter = 0
    for r in coeffs:
        c = r["coeffs"]
        if c is None:
            print(f"{r['task']:<22}{r['interface']:<9}{r.get('symbols','-'):<6}  (incomplete)")
            continue
        a, b = c["a"], c["b"]
        if c.get("native"):
            verdict = "req-b" if b > 0 else "req-?"
            print(f"{r['task']:<22}{r['interface']:<9}{'-':<6}"
                  f"{a:>7.2f}{b:>7.2f}{'-':>7}{'-':>7}  {'-':<5}  {verdict}")
            continue
        n_adapter += 1
        c_, d = c["c"], c["d"]
        B = max(abs(a) + abs(b) + abs(c_),
                max(-a * u * v - b * v - c_ * u for u in (+1, -1) for v in (+1, -1)))
        d_gt_B = d > B
        pos_wrong = d > 0 and not d_gt_B
        if d_gt_B:
            n_dom += 1
        if pos_wrong:
            n_pos_wrong += 1
        if abs(a) > 0.5:
            n_sympref += 1
        verdict = "DOM" if d_gt_B else ("pos-wrong" if pos_wrong else "other")
        print(f"{r['task']:<22}{r['interface']:<9}{r.get('symbols','-'):<6}"
              f"{a:>7.2f}{b:>7.2f}{c_:>7.2f}{d:>7.2f}  {str(d_gt_B):<5}  {verdict}")
    print("\n=== VERDICT ===")
    tot = n_adapter
    print(f"  (adapter cells only; native is the request-understanding check)")
    print(f"  V1 d>B dominates: {n_dom}/{tot} = {n_dom/tot:.0%}")
    print(f"  V2 d>0 but wrong (pos-wrong): {n_pos_wrong}/{tot} = {n_pos_wrong/tot:.0%}")
    print(f"  V3 symbol preference |a|>0.5: {n_sympref}/{tot} = {n_sympref/tot:.0%}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="stageA_binding.jsonl")
    ap.add_argument("--analyze", metavar="COEFFS_JSONL")
    ap.add_argument("--model", default=MODEL_NAME,
                    help="HF model id (default Qwen/Qwen2.5-7B-Instruct)")
    a = ap.parse_args()
    if a.analyze:
        a.coeffs = a.analyze
        cmd_analyze(a)
    else:
        cmd_run(a)


if __name__ == "__main__":
    main()
