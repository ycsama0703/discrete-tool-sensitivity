"""
Daloopa period-binding probe: do our local models correctly identify the
period (fiscal year vs quarter) a financial question asks for?

Daloopa questions explicitly name a period ("fiscal year 2023", "Q3 2023").
We ask each local model to classify the question's period intent, and compare
against the true period extracted by rule. This measures the discrete period
binding capability — the same capability that, when it fails, makes an agent
fill the wrong `period` tool parameter.

Contrast with Daloopa's own commercial-model results: the 5 non-grounded
commercial models make 5-9% fiscal/period errors. Here we measure our local
weak models on the same questions.

Usage (on luyao4, kolrl env):
    python daloopa_period_binding.py --out daloopa_period_qwen.jsonl \
      --model Qwen/Qwen2.5-7B-Instruct --backend transformers
    python daloopa_period_binding.py --analyze daloopa_period_qwen.jsonl
"""

import argparse
import json
import re
import sys
import urllib.request

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

# Daloopa benchmark (500 questions x 6 models). Path configurable via
# --daloopa (default: local copy, or a path on the remote box).
DALOOPA_CSV = r"D:\luyao4\exp\daloopa\train.csv"

MODEL = "Qwen/Qwen2.5-7B-Instruct"


def load_questions(csv_path):
    """Load unique Daloopa questions and their true period intent."""
    import pandas as pd
    df = pd.read_csv(csv_path)
    uq = df.drop_duplicates("question")
    out = []
    for _, r in uq.iterrows():
        q = str(r["question"])
        period = classify_period(q)
        out.append(dict(ticker=r["ticker"], question=q, true_period=period,
                        category=r["category"]))
    return out


def classify_period(q):
    """Extract the true period intent from the question text by rule."""
    ql = q.lower()
    fy = bool(re.search(r"fiscal year|fiscal 20|annual|full year|fy20", ql))
    qtr = bool(re.search(r"\bq[1-4]\b|quarter", ql))
    if fy and not qtr:
        return "fy"
    if qtr and not fy:
        return "quarter"
    if fy and qtr:
        return "ambiguous"
    return "none"


class Agent:
    def __init__(self, model=MODEL):
        self.tok = AutoTokenizer.from_pretrained(model)
        self.model = AutoModelForCausalLM.from_pretrained(
            model, torch_dtype=torch.bfloat16, device_map="auto")
        self.model.eval()

    def _generate(self, messages, max_new=30):
        text = self.tok.apply_chat_template(messages, tokenize=False,
                                            add_generation_prompt=True)
        ids = self.tok(text, return_tensors="pt").to(self.model.device)
        with torch.no_grad():
            out = self.model.generate(**ids, max_new_tokens=max_new,
                                      do_sample=True, temperature=0.7, top_p=0.9)
        return self.tok.decode(out[0][ids["input_ids"].shape[1]:],
                               skip_special_tokens=False)

    def classify(self, question):
        """Ask the model which period the question asks for."""
        sys_prompt = (
            "You are a financial data assistant. A user asks a question about "
            "a company's financials. Determine which reporting period the "
            "question asks for. Answer with exactly one word: 'fy' (fiscal "
            "year / annual), 'quarter' (a single quarter), or 'none'."
        )
        messages = [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": question},
        ]
        gen = self._generate(messages)
        low = gen.strip().lower()
        if re.search(r"\bfy\b|fiscal year|annual|full year", low):
            return "fy", gen
        if re.search(r"\bquarter\b|\bq[1-4]\b", low):
            return "quarter", gen
        return "none", gen


class OllamaAgent:
    def __init__(self, model="gemma3:12b", url="http://localhost:11434/api/chat"):
        self.model = model
        self.url = url

    def _chat(self, messages, max_new=30):
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

    def classify(self, question):
        sys_prompt = (
            "You are a financial data assistant. A user asks a question about "
            "a company's financials. Determine which reporting period the "
            "question asks for. Answer with exactly one word: 'fy' (fiscal "
            "year / annual), 'quarter' (a single quarter), or 'none'."
        )
        messages = [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": question},
        ]
        gen = self._chat(messages)
        low = gen.strip().lower()
        if re.search(r"\bfy\b|fiscal year|annual|full year", low):
            return "fy", gen
        if re.search(r"\bquarter\b|\bq[1-4]\b", low):
            return "quarter", gen
        return "none", gen


def cmd_run(a):
    if a.backend == "ollama":
        agent = OllamaAgent(a.model)
    else:
        agent = Agent(a.model)
    print(f"loaded {a.model}\n", flush=True)
    questions = load_questions(a.daloopa)
    rows = []
    for i, q in enumerate(questions):
        pred, gen = agent.classify(q["question"])
        correct = (pred == q["true_period"])
        rows.append(dict(idx=i, **q, pred_period=pred, correct=correct))
        print(f"  [{i:3}] true={q['true_period']:8} pred={pred:8} "
              f"{'OK' if correct else 'ERR'} {q['question'][:50]}", flush=True)
    with open(a.out, "w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"\nwrote {a.out} ({len(rows)} runs)")


def cmd_analyze(a):
    rows = [json.loads(l) for l in open(a.out, encoding="utf-8")]
    n = len(rows)
    # only questions with a clear period (fy or quarter)
    clear = [r for r in rows if r["true_period"] in ("fy", "quarter")]
    n_clear = len(clear)
    n_err = sum(1 for r in clear if not r["correct"])
    print(f"runs: {n}")
    print(f"clear-period questions: {n_clear}/{n}")
    print(f"period binding errors: {n_err}/{n_clear} = {n_err/n_clear:.1%}")
    # per true-period
    for tp in ("fy", "quarter"):
        sub = [r for r in clear if r["true_period"] == tp]
        if sub:
            e = sum(1 for r in sub if not r["correct"])
            print(f"  {tp:8}: {e}/{len(sub)} = {e/len(sub):.1%}")
    print()
    print("Compare: Daloopa commercial models make 5-9% fiscal/period errors.")
    print("If local models are higher, weak models bind period worse.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="daloopa_period_qwen.jsonl")
    ap.add_argument("--analyze", nargs="?", const="daloopa_period_qwen.jsonl")
    ap.add_argument("--model", default=MODEL)
    ap.add_argument("--backend", choices=["transformers", "ollama"],
                    default="transformers")
    ap.add_argument("--daloopa", default=DALOOPA_CSV,
                    help="path to Daloopa train.csv")
    a = ap.parse_args()
    if a.analyze:
        a.out = a.analyze
        cmd_analyze(a)
    else:
        cmd_run(a)


if __name__ == "__main__":
    main()
