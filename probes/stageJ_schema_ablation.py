"""
Stage-J: is the period error a model defect or an interface defect?

Every error rate we report (25.9-38.2% across 12 configurations) was measured
against ONE tool schema, in which `period` is optional:

    "required": ["symbol"]

A reviewer will ask how much of that number is the model failing to bind, and
how much is simply a schema that never demanded the parameter. We cannot
currently answer. Our own data already shows the question is live:
gemini-3.8-flash omitted `period` on 100/400 calls, which is schema-valid
precisely because it is not required.

This probe holds the model, questions, symbols and ladder fixed and varies only
the schema:

    S0  baseline           required: [symbol]            (what everything so far used)
    S1  period required    required: [symbol, period]
    S2  S1 + descriptions  period required AND the enum values spelled out,
                           INCLUDING examples naming fields our test set uses
    S3  S2 minus the hint  same semantics, but no wording that points at the
                           test set - the control that decides whether S2 is an
                           interface finding or just leakage

PRE-REGISTERED READING (fixed before running):
  - If S1/S2 collapse the error rate (say below ~10%), then a large part of what
    we have been calling a binding defect is an interface defect, and the
    paper's framing must change: the screener would be guarding against a
    problem that better schema design largely removes.
  - If the error rate survives S1/S2, the schema confound is ruled out and the
    binding-defect reading is much stronger. This is the control that makes the
    existing numbers defensible.
  - S2 - S1 isolates how much is carried by description quality alone.

Note S1 removes the "omitted period" failure mode by construction; that is the
point. Omissions under S0 are counted as errors, so a drop from S0 to S1 partly
just reflects omissions becoming impossible. The models we run here (qwen) had
~0 omissions under S0, so for them the comparison is clean; for gemini it would
not be, and that must be said when the sweep is widened.

Backends (added 2026-09-27; the prompt and the parser are identical across
backends, only generation differs):
    transformers  local HF weights (qwen, llama)             max_new_tokens 400
    ollama        local quantized model (gemma, as stage F)   num_predict 400
    openrouter    API models; reuses stage G's client, which falls back to the
                  `reasoning` field when a reasoning model leaves `content`
                  empty                                        max_tokens 2000

Usage:
    python stageJ_schema_ablation.py --variant S0 --out stageJ_qwen_S0.jsonl
    python stageJ_schema_ablation.py --variant S0 --backend ollama --model gemma3:12b --out stageJ_gemma_S0.jsonl
    python stageJ_schema_ablation.py --variant S0 --backend openrouter --model anthropic/claude-sonnet-5 --out stageJ_sonnet5_S0.jsonl
    python stageJ_schema_ablation.py --compare stageJ_qwen_S0.jsonl stageJ_qwen_S1.jsonl ...
"""

import argparse
import json
import os
import re
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor

MODEL = "Qwen/Qwen2.5-7B-Instruct"

SYMBOLS = ["AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "META", "ORCL", "CRM",
           "TSLA", "AMD", "INTC", "NFLX", "ADBE", "AVGO", "CSCO", "QCOM",
           "IBM", "TXN", "AMAT", "MU"]

SYSTEM = "You are a financial data assistant. Call the tool with the correct parameters."

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
    ("What was {SYM}'s diluted EPS for the last quarter?", "quarter"),
    ("What was {SYM}'s annual diluted EPS for fiscal 2024?", "fy"),
    ("What is {SYM}'s cash from investing?", "quarter"),
    ("What was {SYM}'s annual cash flow from operations?", "fy"),
    ("Show {SYM}'s current assets.", "quarter"),
    ("What was {SYM}'s annual revenue for fiscal 2023?", "fy"),
    ("What is {SYM}'s cash from financing?", "quarter"),
    ("What was {SYM}'s annual net income for fiscal 2023?", "fy"),
    ("Show {SYM}'s shareholders' equity.", "quarter"),
    ("What was {SYM}'s annual operating income for fiscal 2023?", "fy"),
]

# --- the only thing that varies across conditions ---------------------------

_BASE_DESC = ("Quarterly or annual income statement, balance sheet, or cash flow "
              "summary for a US-listed company. Use 'statement' to choose the "
              "statement type, and 'period' to choose quarter vs annual.")

_PERIOD_DESC_TERSE = "quarter = single quarter, fy = fiscal year, all = both"

_PERIOD_DESC_FULL = (
    "Which reporting period to return. REQUIRED - you must choose one. "
    "'quarter' = a single three-month reporting period (use this when the "
    "request is about one quarter, the latest quarter, or a point-in-time "
    "balance such as current assets or shareholders' equity). "
    "'fy' = one fiscal year, i.e. the four quarters summed (use this when the "
    "request says annual, full-year, or names a fiscal year). "
    "'all' = both series are returned; only use this when the request "
    "explicitly asks to compare quarterly and annual figures. "
    "quarter and fy are different questions, not approximations of each other: "
    "an fy figure is roughly four times the corresponding quarterly one.")

# S3: the control for S2. S2's text names the exact ambiguous fields our test
# set uses ("current assets", "shareholders' equity"), which is not a generic
# API description - it is a hint pointed at our questions. If S2 reaches ~0%
# only because of that hint, the result is leakage, not an interface finding.
# S3 keeps the semantics and drops every clue that points at the test set.
_PERIOD_DESC_GENERIC = (
    "Which reporting period to return. REQUIRED - you must choose one. "
    "'quarter' = a single three-month reporting period. "
    "'fy' = one fiscal year, i.e. the four quarters summed. "
    "'all' = both series are returned. "
    "quarter and fy are different questions, not approximations of each other.")


def build_schema(variant):
    period = {"type": "string", "enum": ["all", "fy", "quarter"]}
    if variant == "S2":
        period["description"] = _PERIOD_DESC_FULL
    elif variant == "S3":
        period["description"] = _PERIOD_DESC_GENERIC
    else:
        period["description"] = _PERIOD_DESC_TERSE
    required = ["symbol"] if variant == "S0" else ["symbol", "period"]
    return {
        "name": "get_fundamentals",
        "description": _BASE_DESC,
        "parameters": {
            "type": "object",
            "properties": {
                "symbol": {"type": "string", "description": "Ticker, e.g. AAPL"},
                "statement": {"type": "string",
                              "enum": ["balance", "cashflow", "income"],
                              "description": "Which statement: balance sheet, cash flow, or income"},
                "period": period,
            },
            "required": required,
        },
    }


def build_messages(question, schema):
    sys_prompt = (
        f"{SYSTEM}\n\n"
        f"You have one tool, get_fundamentals, with this schema:\n"
        f"{json.dumps(schema)}\n\n"
        f"Given a user request, call the tool by returning a JSON object of "
        f"the form {{\"name\": \"get_fundamentals\", \"arguments\": {{...}}}}. "
        f"Choose 'period' carefully based on what the user asks for."
    )
    return [{"role": "system", "content": sys_prompt},
            {"role": "user", "content": question}]


class Agent:
    """transformers backend (qwen, llama). Imports torch lazily so the API
    backend can run on a machine without a GPU stack."""

    def __init__(self, model=MODEL):
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer
        self.torch = torch
        self.tok = AutoTokenizer.from_pretrained(model)
        self.model = AutoModelForCausalLM.from_pretrained(
            model, dtype=torch.bfloat16, device_map="auto")
        self.model.eval()

    def generate(self, messages):
        text = self.tok.apply_chat_template(messages, tokenize=False,
                                            add_generation_prompt=True)
        ids = self.tok(text, return_tensors="pt").to(self.model.device)
        with self.torch.no_grad():
            out = self.model.generate(**ids, max_new_tokens=400,
                                      do_sample=True, temperature=0.7, top_p=0.9)
        return self.tok.decode(out[0][ids["input_ids"].shape[1]:],
                               skip_special_tokens=False)

    def call_tool(self, question, schema):
        return parse_call(self.generate(build_messages(question, schema)))


class OllamaAgent(Agent):
    """ollama backend, same request shape as stage F's OllamaAgent."""

    def __init__(self, model="gemma3:12b", url="http://localhost:11434/api/chat"):
        self.model, self.url = model, url

    def generate(self, messages):
        body = json.dumps({"model": self.model, "messages": messages, "stream": False,
                           "options": {"temperature": 0.7, "num_predict": 400}}).encode()
        req = urllib.request.Request(self.url, data=body,
                                     headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=300) as r:
                return json.loads(r.read()).get("message", {}).get("content", "")
        except Exception as e:
            return f"__API_ERROR__ ollama: {str(e)[:80]}"


class ORAgentJ(Agent):
    """OpenRouter backend, reusing stage G's client (key loading, retries,
    cost accounting, reasoning-field fallback)."""

    def __init__(self, model):
        from stageG_openrouter_ladder import ORAgent, load_key
        self.client = ORAgent(model, load_key())

    def generate(self, messages):
        return self.client._chat(messages, max_new=2000)


def parse_call(gen):
    """Unchanged from the original qwen/llama runs; __API_ERROR__ -> parse fail."""
    if gen.startswith("__API_ERROR__"):
        return None, gen
    m = re.search(r"<tool_call>\s*(\{.*?\})\s*</tool_call>", gen, re.DOTALL)
    raw = m.group(1) if m else gen
    jm = re.search(r"\{.*\}", raw, re.DOTALL)
    if not jm:
        return None, gen
    try:
        call = json.loads(jm.group(0))
    except Exception:
        return None, gen
    args = call.get("arguments") or call.get("parameters") or call
    if isinstance(args, str):
        try:
            args = json.loads(args)
        except Exception:
            args = {}
    if not isinstance(args, dict):
        return None, gen
    p = args.get("period")
    if isinstance(p, dict):
        p = p.get("value")
    if p is None and "get_fundamentals" in gen:
        p = "__OMITTED__"
    return p, gen


def cmd_run(a):
    schema = build_schema(a.variant)
    print(f"variant={a.variant}  required={schema['parameters']['required']}")
    print(f"period.description[:70]={schema['parameters']['properties']['period']['description'][:70]}...\n",
          flush=True)
    if a.backend == "ollama":
        agent = OllamaAgent(a.model)
    elif a.backend == "openrouter":
        agent = ORAgentJ(a.model)
    else:
        agent = Agent(a.model)
    print("loaded\n", flush=True)
    work = [(sym, i, q, cp) for sym in SYMBOLS[:a.n_symbols]
            for i, (q, cp) in enumerate(QUESTIONS)]

    def one(w):
        sym, i, q, cp = w
        period, gen = agent.call_tool(q.replace("{SYM}", sym), schema)
        err = None if period is None else (period != cp)
        return dict(idx=i, symbol=sym, question=q, correct=cp,
                    filled_period=period, real_error=err,
                    variant=a.variant, parse_failed=period is None)

    workers = a.concurrency if a.backend == "openrouter" else 1
    rows = []
    with open(a.out, "w", encoding="utf-8") as fh, ThreadPoolExecutor(workers) as ex:
        for r in ex.map(one, work):
            rows.append(r)
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
            fh.flush()
            fp = r["filled_period"] if r["filled_period"] is not None else "?"
            err = r["real_error"]
            print(f"  {r['symbol']:6} [{r['idx']:2}] filled={fp:12} "
                  f"{'ERR' if err else ('ok ' if err is False else 'PARSE')}",
                  flush=True)
    if a.backend == "openrouter":
        c = agent.client
        print(f"\nAPI: {c.n_calls} calls, {c.n_fail} failed, "
              f"{c.in_tok} in / {c.out_tok} out tokens, cost ${c.cost:.3f}")
    print(f"\nwrote {a.out} ({len(rows)} runs)")


def summarise(path):
    rows = [json.loads(l) for l in open(path, encoding="utf-8")]
    n = len(rows)
    parsed = [r for r in rows if not r["parse_failed"]]
    errs = [r for r in parsed if r["real_error"]]
    omit = sum(1 for r in parsed if r["filled_period"] == "__OMITTED__")
    by_val = {}
    for r in errs:
        by_val[r["filled_period"]] = by_val.get(r["filled_period"], 0) + 1
    return dict(n=n, parsed=len(parsed), err=len(errs),
                rate=len(errs) / len(parsed) if parsed else float("nan"),
                omit=omit, by_val=by_val,
                variant=rows[0].get("variant", "?"))


def cmd_compare(files):
    print(f"{'variant':8} {'n':>4} {'parsed':>7} {'err':>5} {'rate':>7} {'omit':>5}  wrong-value breakdown")
    print("-" * 88)
    base = None
    for f in files:
        if not os.path.exists(f):
            print(f"  {f} missing")
            continue
        s = summarise(f)
        if base is None:
            base = s["rate"]
        delta = "" if s["rate"] != s["rate"] else f"  ({s['rate']-base:+.1%} vs first)"
        print(f"{s['variant']:8} {s['n']:4} {s['parsed']:7} {s['err']:5} "
              f"{s['rate']:7.1%} {s['omit']:5}  {s['by_val']}{delta}")
    print("\nPre-registered: if S1/S2 collapse the rate below ~10%, a large part of")
    print("what we called a binding defect is an interface defect. If it survives,")
    print("the schema confound is ruled out and the existing numbers are defensible.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--variant", choices=["S0", "S1", "S2", "S3"], default="S0")
    ap.add_argument("--out", default="stageJ_qwen_S0.jsonl")
    ap.add_argument("--model", default=MODEL)
    ap.add_argument("--backend", choices=["transformers", "ollama", "openrouter"],
                    default="transformers")
    ap.add_argument("--concurrency", type=int, default=8)
    ap.add_argument("--n-symbols", type=int, default=20)
    ap.add_argument("--compare", nargs="*")
    a = ap.parse_args()
    if a.compare:
        cmd_compare(a.compare)
    else:
        cmd_run(a)


if __name__ == "__main__":
    main()
