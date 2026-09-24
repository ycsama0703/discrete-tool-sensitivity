"""
Stage-G: the stage-F three-level self-verification ladder, run against
commercial models through OpenRouter.

This is the SAME experiment as stageF_selfcheck.py — same 20 symbols x 20
questions, same tool schema, same L1/L2/L3 prompts, same temperature — with
only the inference backend swapped. That is the point: it makes the local weak
models (qwen2.5:7b, llama3.1:8b, gemma3:12b) and the commercial models
directly comparable on one capability ladder.

Two of the OpenRouter models (qwen-2.5-7b, llama-3.1-8b) are the same weights
we ran locally. They serve as a SANITY CHECK: if the API error rate differs
sharply from the local run, the harness is not comparable and the commercial
numbers cannot be read against the local ones.

Key handling: reads OPENROUTER_API_KEY from the environment, or from a .env
file in the repo root (which is gitignored). The key is never logged.

Cost: ~0.51M tokens per model (484K in / 30K out) for the full 400-case ladder.

Usage:
    python stageG_openrouter_ladder.py --model qwen/qwen-2.5-7b-instruct \
        --out stageG_qwen7b.jsonl
    python stageG_openrouter_ladder.py --analyze stageG_qwen7b.jsonl
"""

import argparse
import json
import os
import re
import sys
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

API_URL = "https://openrouter.ai/api/v1/chat/completions"

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

# Identical to stageF_selfcheck.py
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


def load_key():
    k = os.environ.get("OPENROUTER_API_KEY")
    if k:
        return k.strip()
    here = os.path.dirname(os.path.abspath(__file__))
    for path in (os.path.join(here, "..", ".env"), os.path.join(here, ".env")):
        if os.path.exists(path):
            for line in open(path, encoding="utf-8"):
                if line.startswith("OPENROUTER_API_KEY="):
                    return line.split("=", 1)[1].strip()
    sys.exit("OPENROUTER_API_KEY not found (env or .env)")


class ORAgent:
    """OpenRouter-backed agent. Same prompts as stageF's Agent/OllamaAgent."""

    def __init__(self, model, key, temperature=0.7):
        self.model = model
        self.key = key
        self.temperature = temperature
        self.in_tok = 0
        self.out_tok = 0
        self.n_calls = 0
        self.n_fail = 0
        self.cost = 0.0
        self._lock = threading.Lock()

    def _chat(self, messages, max_new=200, retries=4):
        body = json.dumps({
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": max_new,
        }).encode()
        headers = {
            "Authorization": f"Bearer {self.key}",
            "Content-Type": "application/json",
        }
        delay = 2.0
        for attempt in range(retries):
            try:
                req = urllib.request.Request(API_URL, data=body, headers=headers)
                with urllib.request.urlopen(req, timeout=120) as r:
                    d = json.loads(r.read())
                if "error" in d and not d.get("choices"):
                    raise RuntimeError(str(d["error"])[:200])
                u = d.get("usage") or {}
                with self._lock:
                    self.in_tok += u.get("prompt_tokens", 0)
                    self.out_tok += u.get("completion_tokens", 0)
                    self.cost += float(u.get("cost", 0) or 0)
                    self.n_calls += 1
                return d["choices"][0]["message"].get("content") or ""
            except Exception as e:
                msg = str(e)[:150]
                if attempt == retries - 1:
                    with self._lock:
                        self.n_fail += 1
                    return f"__API_ERROR__ {msg}"
                time.sleep(delay)
                delay *= 2
        return "__API_ERROR__"

    def call_tool(self, question):
        schema = json.dumps(TOOLS[0]["function"])
        sys_prompt = (
            f"{SYSTEM}\n\n"
            f"You have one tool, get_fundamentals, with this schema:\n{schema}\n\n"
            f"Given a user request, call the tool by returning a JSON object of "
            f"the form {{\"name\": \"get_fundamentals\", \"arguments\": {{...}}}}. "
            f"Choose 'period' carefully based on what the user asks for."
        )
        # 400 rather than 200: some models write a sentence of preamble before
        # the JSON, and a tight cap truncates the call itself (finish_reason
        # "length"), which would look like a parse failure rather than what it
        # is. The extra headroom costs a negligible number of output tokens.
        gen = self._chat([
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": question},
        ], max_new=400)
        if gen.startswith("__API_ERROR__"):
            return None, None, gen
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
        if not isinstance(args, dict):
            return None, None, gen
        return args.get("symbol"), args.get("period"), gen

    def _verify_prompt(self, question, filled_period, correct_period, level):
        """Identical wording to stageF_selfcheck.py's _verify_prompt."""
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
            msgs = [
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
            msgs = [
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": question},
                {"role": "assistant", "content": f"I called get_fundamentals with period={filled_period}."},
                {"role": "user", "content":
                    f"Review your call. Is period={filled_period} the correct "
                    f"period for this request? Answer yes or no."},
            ]
        else:
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
            msgs = [
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": question},
                {"role": "assistant", "content": f"I called get_fundamentals with period={filled_period}."},
                {"role": "user", "content":
                    f"Which parameter is wrong? Answer with one of: symbol, "
                    f"statement, period, none."},
            ]
        return msgs

    def verify(self, question, filled_period, correct_period, level):
        gen = self._chat(self._verify_prompt(question, filled_period,
                                             correct_period, level), max_new=30)
        low = gen.strip().lower()
        if level == 3:
            return bool(re.search(r"\bperiod\b", low)), gen
        return bool(re.search(r"\b(no|wrong|incorrect|not correct|mismatch)\b", low)), gen


def run_one(agent, question, correct_period, symbol):
    q = question.replace("{SYM}", symbol)
    sym, period, gen = agent.call_tool(q)
    if period is None:
        # Two distinct causes, kept apart because they mean different things:
        #   api_error  - the request itself failed (infrastructure)
        #   no_toolcall- the model answered in prose instead of emitting a tool
        #                call. This is real model behaviour, not a harness bug,
        #                and must not be silently counted as "no error".
        why = "api_error" if gen.startswith("__API_ERROR__") else "no_toolcall"
        return dict(symbol=symbol, question=question, correct=correct_period,
                    filled_period=None, real_error=None,
                    det_L1=None, det_L2=None, det_L3=None, parse_failed=True,
                    fail_reason=why, raw_head=gen[:200])
    real_error = (period != correct_period)
    d1, _ = agent.verify(q, period, correct_period, 1)
    d2, _ = agent.verify(q, period, correct_period, 2)
    d3, _ = agent.verify(q, period, correct_period, 3)
    return dict(symbol=symbol, question=question, correct=correct_period,
                filled_period=period, real_error=real_error,
                det_L1=d1, det_L2=d2, det_L3=d3, parse_failed=False)


def cmd_run(a):
    key = load_key()
    agent = ORAgent(a.model, key, temperature=a.temperature)
    symbols = SYMBOLS[:a.n_symbols]
    print(f"model={a.model}  symbols={len(symbols)}  questions={len(QUESTIONS)}  "
          f"temp={a.temperature}\n", flush=True)

    # resume: skip (symbol, idx) already present in the output file
    done = set()
    if a.resume and os.path.exists(a.out):
        for line in open(a.out, encoding="utf-8"):
            try:
                r = json.loads(line)
                done.add((r["symbol"], r["idx"]))
            except Exception:
                pass
        print(f"resuming: {len(done)} cases already done\n", flush=True)

    # build the work list, then run cases concurrently (each case is 4 serial
    # API calls: the tool call, then L1/L2/L3 which depend on its result)
    work = [(sym, i, q, cp)
            for sym in symbols
            for i, (q, cp) in enumerate(QUESTIONS)
            if (sym, i) not in done]
    print(f"{len(work)} cases to run, concurrency={a.concurrency}\n", flush=True)

    fh = open(a.out, "a" if a.resume else "w", encoding="utf-8")
    write_lock = threading.Lock()
    t0 = time.time()
    n_done = 0
    try:
        with ThreadPoolExecutor(max_workers=a.concurrency) as ex:
            futs = {ex.submit(run_one, agent, q, cp, sym): (sym, i)
                    for sym, i, q, cp in work}
            for fut in as_completed(futs):
                sym, i = futs[fut]
                try:
                    r = fut.result()
                except Exception as e:
                    print(f"  {sym:6} [{i:2}] CASE FAILED: {str(e)[:80]}", flush=True)
                    continue
                with write_lock:
                    fh.write(json.dumps(dict(idx=i, **r), ensure_ascii=False) + "\n")
                    fh.flush()
                    n_done += 1
                    done_n = n_done
                fp = r["filled_period"] if r["filled_period"] is not None else "?"
                flag = "ERR" if r["real_error"] else ("ok " if r["real_error"] is False else "PARSE")
                l1 = "D" if (r["real_error"] and r["det_L1"]) else ("M" if r["real_error"] else "-")
                l2 = "D" if (r["real_error"] and r["det_L2"]) else ("M" if r["real_error"] else "-")
                l3 = "D" if (r["real_error"] and r["det_L3"]) else ("M" if r["real_error"] else "-")
                rate = done_n / max(time.time() - t0, 1e-9)
                eta = (len(work) - done_n) / rate if rate > 0 else 0
                print(f"  [{done_n:3}/{len(work)}] {sym:6} q{i:02} filled={fp:8} {flag} "
                      f"L1={l1} L2={l2} L3={l3}  ${agent.cost:.3f} eta={eta/60:.0f}m",
                      flush=True)
    finally:
        fh.close()
        print(f"\ntokens: {agent.in_tok} in, {agent.out_tok} out  "
              f"calls={agent.n_calls} failed={agent.n_fail}  cost=${agent.cost:.4f}")
        print(f"elapsed: {(time.time()-t0)/60:.1f} min")
        print(f"wrote {a.out}")


def cmd_analyze(a):
    rows = [json.loads(l) for l in open(a.out, encoding="utf-8")]
    n = len(rows)
    errors = [r for r in rows if r["real_error"]]
    n_err = len(errors)
    failed = [r for r in rows if r.get("parse_failed")]
    n_api = sum(1 for r in failed if r.get("fail_reason") == "api_error")
    n_noc = sum(1 for r in failed if r.get("fail_reason") == "no_toolcall")
    n_unk = len(failed) - n_api - n_noc
    print(f"runs: {n}")
    print(f"  emitted a tool call : {n - len(failed)}/{n} = {(n-len(failed))/n:.1%}")
    print(f"  no tool call (prose): {n_noc}"
          + (f"  [+{n_unk} unclassified]" if n_unk else ""))
    print(f"  API failures        : {n_api}")
    if not n_err:
        print("\nno real errors - nothing to detect")
        return
    denom = n - len(failed)
    print(f"\nreal errors (D1): {n_err}/{denom} of parsed = {n_err/denom:.1%}"
          f"   ({n_err/n:.1%} of all runs)")
    print()
    print("ladder level        recall (detect)   precision")
    for lvl, key in [("L1 value-compare", "det_L1"),
                     ("L2 semantic-judge", "det_L2"),
                     ("L3 error-locate", "det_L3")]:
        n_det = sum(1 for r in errors if r[key])
        recall = n_det / n_err
        flagged = [r for r in rows if r[key]]
        prec = (sum(1 for r in flagged if r["real_error"]) / len(flagged)) if flagged else float("nan")
        print(f"  {lvl:18} {n_det:3}/{n_err:3} = {recall:6.1%}   {prec:6.1%}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="qwen/qwen-2.5-7b-instruct")
    ap.add_argument("--out", default="stageG_out.jsonl")
    ap.add_argument("--analyze", nargs="?", const=None)
    ap.add_argument("--temperature", type=float, default=0.7)
    ap.add_argument("--n-symbols", type=int, default=20,
                    help="use fewer symbols for a cheap smoke test")
    ap.add_argument("--resume", action="store_true",
                    help="append to --out, skipping cases already present")
    ap.add_argument("--concurrency", type=int, default=8,
                    help="cases run in parallel (each case = 4 serial API calls)")
    a = ap.parse_args()
    if a.analyze is not None or "--analyze" in sys.argv:
        if a.analyze:
            a.out = a.analyze
        cmd_analyze(a)
    else:
        cmd_run(a)


if __name__ == "__main__":
    main()
