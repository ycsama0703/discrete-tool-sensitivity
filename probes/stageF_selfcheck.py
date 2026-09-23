"""
Stage-F probe: active self-verification as a detector of discrete parameter
errors — the "why not just have the LLM check itself?" baseline.

The paper's central claim is that the enumeration screener is the ONLY exact
detector of discrete parameter errors. A reviewer's first objection is "why
not just ask the LLM to check its own tool call?" Stage F answers this
empirically: we give the SAME agent that filled the wrong period the chance to
verify its own call, and measure whether it catches the error.

Design (see docs/probe_notes/README_stageF_selfcheck.md):

  financial question
    -> agent generates a tool call (period = quarter/fy/all)      [D1, stage D]
    -> if period != correct: a discrete error occurred
    -> ACTIVE self-verification: ask the agent
         "You filled period=X. The question asks for Y. Is that correct?"
       record whether the agent says the call is wrong (detects the error)
    -> compare: self-verification detection rate vs enumeration screener (100%)

The hypothesis (pre-registered): self-verification detection rate is LOW,
because the binding defect that made the agent fill the wrong period is the
SAME defect it would need to detect the error. The agent cannot reliably
self-diagnose a failure of the very capability the diagnosis depends on.

Usage (on luyao4, kolrl env):
    python stageF_selfcheck.py --out stageF_selfcheck.jsonl
    python stageF_selfcheck.py --analyze stageF_selfcheck.jsonl
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

# Same 20 questions as stage D (correct period per question).
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


class Agent:
    def __init__(self, model=MODEL):
        self.tok = AutoTokenizer.from_pretrained(model)
        self.model = AutoModelForCausalLM.from_pretrained(
            model, torch_dtype=torch.bfloat16, device_map="auto")
        self.model.eval()

    def _generate(self, messages, max_new=200):
        text = self.tok.apply_chat_template(messages, tokenize=False,
                                            add_generation_prompt=True)
        ids = self.tok(text, return_tensors="pt").to(self.model.device)
        with torch.no_grad():
            out = self.model.generate(**ids, max_new_tokens=max_new,
                                      do_sample=True, temperature=0.7, top_p=0.9)
        return self.tok.decode(out[0][ids["input_ids"].shape[1]:],
                               skip_special_tokens=False)

    def call_tool(self, question):
        """Generate a tool call. Returns (symbol, period, raw_gen)."""
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
        gen = self._generate(messages)
        m = re.search(r"<tool_call>\s*(\{.*?\})\s*</tool_call>", gen, re.DOTALL)
        raw = m.group(1) if m else gen
        jm = re.search(r"\{.*\}", raw, re.DOTALL)
        if not jm:
            return None, None, gen
        try:
            call = json.loads(jm.group(0))
        except Exception:
            return None, None, gen
        args = call.get("arguments", call)
        if isinstance(args, str):
            try:
                args = json.loads(args)
            except Exception:
                args = {}
        return args.get("symbol"), args.get("period"), gen

    def self_verify(self, question, filled_period, correct_period):
        """Active self-verification: ask the agent whether its own tool call
        matched the question's intent. Returns (detected: bool, raw_gen).

        detected = True if the agent says the filled period does NOT match the
        question's intent (i.e. it flags its own error). We ask it to answer
        with a single word (yes/no) to make scoring unambiguous.
        """
        schema = json.dumps(TOOLS[0]["function"])
        sys_prompt = (
            f"{SYSTEM}\n\n"
            f"You have one tool, get_fundamentals, with this schema:\n{schema}\n\n"
            f"You just generated a tool call for the user's request. "
            f"Now verify whether the 'period' you chose matches what the user "
            f"asked for. Answer with exactly one word: yes (correct) or no "
            f"(wrong period)."
        )
        messages = [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": question},
            {"role": "assistant", "content": f"I filled period={filled_period}."},
            {"role": "user", "content":
                f"Does period={filled_period} correctly answer the request? "
                f"The request asks for the {correct_period} figure. "
                f"Answer yes or no."},
        ]
        gen = self._generate(messages, max_new=30)
        low = gen.strip().lower()
        # detect an explicit "no" (the agent flags its own error)
        m = re.search(r"\b(no|wrong|incorrect|not correct|mismatch)\b", low)
        detected = m is not None
        return detected, gen


class OllamaAgent:
    """Agent backed by ollama (for models without transformers weights, e.g.
    gemma3:12b). Mirrors Agent but calls the ollama /api/chat endpoint."""
    def __init__(self, model="gemma3:12b", url="http://localhost:11434/api/chat"):
        self.model = model
        self.url = url

    def _chat(self, messages, max_new=200):
        body = json.dumps({
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {"temperature": 0.7, "num_predict": max_new},
        }).encode()
        req = urllib.request.Request(self.url, data=body,
                                     headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                d = json.loads(r.read())
        except Exception as e:
            return f"ollama error: {str(e)[:80]}"
        return d.get("message", {}).get("content", "")

    def call_tool(self, question):
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
        gen = self._chat(messages)
        jm = re.search(r"\{.*\}", gen, re.DOTALL)
        if not jm:
            return None, None, gen
        try:
            call = json.loads(jm.group(0))
        except Exception:
            return None, None, gen
        args = call.get("arguments", call)
        if isinstance(args, str):
            try:
                args = json.loads(args)
            except Exception:
                args = {}
        return args.get("symbol"), args.get("period"), gen

    def self_verify(self, question, filled_period, correct_period):
        schema = json.dumps(TOOLS[0]["function"])
        sys_prompt = (
            f"{SYSTEM}\n\n"
            f"You have one tool, get_fundamentals, with this schema:\n{schema}\n\n"
            f"You just generated a tool call for the user's request. "
            f"Now verify whether the 'period' you chose matches what the user "
            f"asked for. Answer with exactly one word: yes (correct) or no "
            f"(wrong period)."
        )
        messages = [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": question},
            {"role": "assistant", "content": f"I filled period={filled_period}."},
            {"role": "user", "content":
                f"Does period={filled_period} correctly answer the request? "
                f"The request asks for the {correct_period} figure. "
                f"Answer yes or no."},
        ]
        gen = self._chat(messages, max_new=30)
        low = gen.strip().lower()
        m = re.search(r"\b(no|wrong|incorrect|not correct|mismatch)\b", low)
        return m is not None, gen


def run_one(agent, question, correct_period, symbol):
    """One (symbol, question) run: generate tool call, then self-verify.

    Returns a dict with:
      - filled_period: what the agent actually filled
      - real_error: filled_period != correct_period (the D1 error)
      - detected: self-verification flagged the error (only meaningful when
        real_error is True; when the call is correct, detection is a false alarm)
    """
    q = question.replace("{SYM}", symbol)
    sym, period, gen = agent.call_tool(q)
    if period is None:
        return dict(symbol=symbol, question=question, correct=correct_period,
                    filled_period=None, real_error=None, detected=None,
                    parse_failed=True)
    real_error = (period != correct_period)
    detected, vgen = agent.self_verify(q, period, correct_period)
    return dict(symbol=symbol, question=question, correct=correct_period,
                filled_period=period, real_error=real_error,
                detected=detected, parse_failed=False)


def cmd_run(a):
    if a.backend == "ollama":
        agent = OllamaAgent(a.model)
    else:
        agent = Agent(a.model)
    print(f"loaded {a.model}\n", flush=True)
    rows = []
    for sym in a.symbols:
        for i, (q, cp) in enumerate(QUESTIONS):
            r = run_one(agent, q, cp, sym)
            rows.append(dict(idx=i, **r))
            flag = "ERR" if r["real_error"] else "ok "
            det = "DETECT" if (r["real_error"] and r["detected"]) else \
                  ("MISS" if r["real_error"] else "-")
            print(f"  {sym:6} [{i:2}] {q[:36]:38s} filled={r['filled_period']:8} "
                  f"{flag} selfcheck={det}", flush=True)
    with open(a.out, "w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"\nwrote {a.out} ({len(rows)} runs)")


def cmd_analyze(a):
    rows = [json.loads(l) for l in open(a.out, encoding="utf-8")]
    n = len(rows)
    errors = [r for r in rows if r["real_error"]]
    n_err = len(errors)
    n_det = sum(1 for r in errors if r["detected"])
    # false alarms: correct calls that self-verification flagged as wrong
    correct = [r for r in rows if r["real_error"] is False]
    n_fa = sum(1 for r in correct if r["detected"])
    print(f"runs: {n}")
    print(f"real errors (D1): {n_err}/{n} = {n_err/n:.1%}")
    if n_err:
        print(f"self-verification detection rate: {n_det}/{n_err} = {n_det/n_err:.1%}")
    if correct:
        print(f"false alarms on correct calls: {n_fa}/{len(correct)} = {n_fa/len(correct):.1%}")
    print()
    print("Compare: enumeration screener detection rate is 100% (stage D).")
    print("If self-verification detection is well below 100%, the internal")
    print("detector (which depends on the failing binding capability) is not a")
    print("reliable substitute for external enumeration.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="stageF_selfcheck.jsonl")
    ap.add_argument("--analyze", nargs="?", const="stageF_selfcheck.jsonl")
    ap.add_argument("--model", default=MODEL)
    ap.add_argument("--backend", choices=["transformers", "ollama"],
                    default="transformers")
    ap.add_argument("--symbols", nargs="*", default=SYMBOLS)
    a = ap.parse_args()
    if a.analyze:
        a.out = a.analyze
        cmd_analyze(a)
    else:
        cmd_run(a)


if __name__ == "__main__":
    main()
