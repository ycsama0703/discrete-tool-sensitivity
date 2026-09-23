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

    def _verify_prompt(self, question, filled_period, correct_period, level):
        """Build the self-verification prompt for a given ladder level.

        L1 (value comparison): tells the agent the correct period, so it only
            needs to compare values (all != quarter). Easiest.
        L2 (semantic judgment): only replays what the agent filled, no correct
            answer. The agent must judge from its own understanding whether the
            period matches the question. This is the "fair" version.
        L3 (error localization): an external screener flagged the call as
            possibly wrong but did NOT say which parameter. The agent must
            identify which parameter (symbol/statement/period) is wrong.
        """
        schema = json.dumps(TOOLS[0]["function"])
        if level == 1:
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
        elif level == 2:
            sys_prompt = (
                f"{SYSTEM}\n\n"
                f"You have one tool, get_fundamentals, with this schema:\n{schema}\n\n"
                f"You just generated a tool call for the user's request. "
                f"Review your own call. Is the 'period' you chose the right one "
                f"for what the user asked? Answer with exactly one word: "
                f"yes (correct) or no (wrong period)."
            )
            messages = [
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": question},
                {"role": "assistant", "content": f"I called get_fundamentals with period={filled_period}."},
                {"role": "user", "content":
                    f"Review your call. Is period={filled_period} the correct "
                    f"period for this request? Answer yes or no."},
            ]
        else:  # level 3
            sys_prompt = (
                f"{SYSTEM}\n\n"
                f"You have one tool, get_fundamentals, with this schema:\n{schema}\n\n"
                f"You just generated a tool call for the user's request. "
                f"An external screener flagged your call as possibly wrong, but "
                f"it did NOT tell you which parameter is wrong. Check your call "
                f"and identify which parameter (symbol, statement, or period) is "
                f"wrong. Answer with exactly one word: symbol, statement, period, "
                f"or none."
            )
            messages = [
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": question},
                {"role": "assistant", "content": f"I called get_fundamentals with period={filled_period}."},
                {"role": "user", "content":
                    f"Which parameter is wrong? Answer with one of: symbol, "
                    f"statement, period, none."},
            ]
        return messages

    def verify_L1(self, question, filled_period, correct_period):
        """L1 value comparison: correct period is given. detected = says 'no'."""
        messages = self._verify_prompt(question, filled_period, correct_period, 1)
        gen = self._generate(messages, max_new=30)
        low = gen.strip().lower()
        m = re.search(r"\b(no|wrong|incorrect|not correct|mismatch)\b", low)
        return m is not None, gen

    def verify_L2(self, question, filled_period, correct_period):
        """L2 semantic judgment: no correct answer given. detected = says 'no'."""
        messages = self._verify_prompt(question, filled_period, correct_period, 2)
        gen = self._generate(messages, max_new=30)
        low = gen.strip().lower()
        m = re.search(r"\b(no|wrong|incorrect|not correct|mismatch)\b", low)
        return m is not None, gen

    def verify_L3(self, question, filled_period, correct_period):
        """L3 error localization: screener flagged, agent must name the param.
        detected = says 'period' (when the real error is a wrong period)."""
        messages = self._verify_prompt(question, filled_period, correct_period, 3)
        gen = self._generate(messages, max_new=30)
        low = gen.strip().lower()
        m = re.search(r"\bperiod\b", low)
        return m is not None, gen


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

    def _verify_prompt(self, question, filled_period, correct_period, level):
        """Same ladder prompts as Agent (see Agent._verify_prompt)."""
        schema = json.dumps(TOOLS[0]["function"])
        if level == 1:
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
        elif level == 2:
            sys_prompt = (
                f"{SYSTEM}\n\n"
                f"You have one tool, get_fundamentals, with this schema:\n{schema}\n\n"
                f"You just generated a tool call for the user's request. "
                f"Review your own call. Is the 'period' you chose the right one "
                f"for what the user asked? Answer with exactly one word: "
                f"yes (correct) or no (wrong period)."
            )
            messages = [
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": question},
                {"role": "assistant", "content": f"I called get_fundamentals with period={filled_period}."},
                {"role": "user", "content":
                    f"Review your call. Is period={filled_period} the correct "
                    f"period for this request? Answer yes or no."},
            ]
        else:  # level 3
            sys_prompt = (
                f"{SYSTEM}\n\n"
                f"You have one tool, get_fundamentals, with this schema:\n{schema}\n\n"
                f"You just generated a tool call for the user's request. "
                f"An external screener flagged your call as possibly wrong, but "
                f"it did NOT tell you which parameter is wrong. Check your call "
                f"and identify which parameter (symbol, statement, or period) is "
                f"wrong. Answer with exactly one word: symbol, statement, period, "
                f"or none."
            )
            messages = [
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": question},
                {"role": "assistant", "content": f"I called get_fundamentals with period={filled_period}."},
                {"role": "user", "content":
                    f"Which parameter is wrong? Answer with one of: symbol, "
                    f"statement, period, none."},
            ]
        return messages

    def verify_L1(self, question, filled_period, correct_period):
        messages = self._verify_prompt(question, filled_period, correct_period, 1)
        gen = self._chat(messages, max_new=30)
        low = gen.strip().lower()
        m = re.search(r"\b(no|wrong|incorrect|not correct|mismatch)\b", low)
        return m is not None, gen

    def verify_L2(self, question, filled_period, correct_period):
        messages = self._verify_prompt(question, filled_period, correct_period, 2)
        gen = self._chat(messages, max_new=30)
        low = gen.strip().lower()
        m = re.search(r"\b(no|wrong|incorrect|not correct|mismatch)\b", low)
        return m is not None, gen

    def verify_L3(self, question, filled_period, correct_period):
        messages = self._verify_prompt(question, filled_period, correct_period, 3)
        gen = self._chat(messages, max_new=30)
        low = gen.strip().lower()
        m = re.search(r"\bperiod\b", low)
        return m is not None, gen


def run_one(agent, question, correct_period, symbol):
    """One (symbol, question) run: generate tool call, then run all three
    self-verification ladder levels (L1 value comparison, L2 semantic judgment,
    L3 error localization) on the SAME call, so the three levels are compared
    on the same set of errors.

    Returns a dict with:
      - filled_period: what the agent actually filled
      - real_error: filled_period != correct_period (the D1 error)
      - det_L1 / det_L2 / det_L3: whether each level flagged the error
      - parse_failed: the tool call could not be parsed
    """
    q = question.replace("{SYM}", symbol)
    sym, period, gen = agent.call_tool(q)
    if period is None:
        return dict(symbol=symbol, question=question, correct=correct_period,
                    filled_period=None, real_error=None,
                    det_L1=None, det_L2=None, det_L3=None, parse_failed=True)
    real_error = (period != correct_period)
    d1, _ = agent.verify_L1(q, period, correct_period)
    d2, _ = agent.verify_L2(q, period, correct_period)
    d3, _ = agent.verify_L3(q, period, correct_period)
    return dict(symbol=symbol, question=question, correct=correct_period,
                filled_period=period, real_error=real_error,
                det_L1=d1, det_L2=d2, det_L3=d3, parse_failed=False)


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
            fp = r["filled_period"] if r["filled_period"] is not None else "?"
            flag = "ERR" if r["real_error"] else ("ok " if r["real_error"] is False else "PARSE")
            l1 = "D" if (r["real_error"] and r["det_L1"]) else ("M" if r["real_error"] else "-")
            l2 = "D" if (r["real_error"] and r["det_L2"]) else ("M" if r["real_error"] else "-")
            l3 = "D" if (r["real_error"] and r["det_L3"]) else ("M" if r["real_error"] else "-")
            print(f"  {sym:6} [{i:2}] {q[:30]:32s} filled={fp:8} {flag} "
                  f"L1={l1} L2={l2} L3={l3}", flush=True)
    with open(a.out, "w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"\nwrote {a.out} ({len(rows)} runs)")


def cmd_analyze(a):
    rows = [json.loads(l) for l in open(a.out, encoding="utf-8")]
    n = len(rows)
    errors = [r for r in rows if r["real_error"]]
    n_err = len(errors)
    correct = [r for r in rows if r["real_error"] is False]
    n_correct = len(correct)
    print(f"runs: {n}")
    print(f"real errors (D1): {n_err}/{n} = {n_err/n:.1%}")
    print(f"correct calls:    {n_correct}/{n} = {n_correct/n:.1%}")
    print()
    print("ladder level    recall (detect)   precision (no false alarm)")
    for lvl, key in [("L1 value-compare", "det_L1"),
                     ("L2 semantic-judge", "det_L2"),
                     ("L3 error-locate", "det_L3")]:
        # recall: of real errors, how many flagged
        n_det = sum(1 for r in errors if r[key])
        recall = n_det / n_err if n_err else float("nan")
        # precision: of calls flagged, how many were real errors
        flagged = [r for r in rows if r[key]]
        n_flag = len(flagged)
        n_flag_true = sum(1 for r in flagged if r["real_error"])
        precision = n_flag_true / n_flag if n_flag else float("nan")
        print(f"  {lvl:18} {n_det:3}/{n_err:3} = {recall:6.1%}   "
              f"{n_flag_true:3}/{n_flag:3} = {precision:6.1%}")
    print()
    print("Compare: enumeration screener detection is 100% recall AND 100%")
    print("precision (it does not depend on the model's binding capability).")
    print("If the ladder levels drop below that, the internal detector is not")
    print("a reliable substitute for external enumeration.")


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
