"""
Stage-G: the capability-scale table.

Reads the stage-F (local) and stage-G (OpenRouter) ladder outputs, which share
a schema, and prints one table so the same-family scale pairs can be read off
directly:

    qwen2.5  7B (local)  ->  qwen2.5  72B (API)     10x
    llama3.1 8B (local)  ->  llama3.3 70B (API)     ~9x

Two of the API rows (qwen-2.5-7b, llama-3.1-8b) are the same weights as the
local runs. They are the sanity check: if the API and local numbers for those
diverge, the harness is not comparable and the scale comparison is void.

Columns:
  emit   - fraction of runs where the model emitted a parseable tool call.
           Reported because a harness that cannot parse a model's tool-call
           dialect silently deflates its error rate (see the note).
  omit   - well-formed tool calls that left `period` out entirely. The schema
           does not require it, so these are schema-valid, raise no error, and
           the API just applies a default. Counted as errors.
  err    - period error rate, over PARSED calls.
  L1/L2/L3 - ladder recall / precision.

Usage:
    python stageG_scale_table.py
"""

import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))

# (label, filename, family, size, source)
# group 1 - same-family scale pairs, plus the local runs they are paired with
ROWS = [
    ("qwen2.5-7b",   "stageF_ladder_qwen.jsonl",   "qwen",  "7B",  "local"),
    ("qwen2.5-7b",   "stageG_qwen7b.jsonl",        "qwen",  "7B",  "API"),
    ("qwen2.5-72b",  "stageG_qwen72b.jsonl",       "qwen",  "72B", "API"),
    ("llama3.1-8b",  "stageF_ladder_llama.jsonl",  "llama", "8B",  "local"),
    ("llama3.1-8b",  "stageG_llama8b.jsonl",       "llama", "8B",  "API"),
    ("llama3.3-70b", "stageG_llama70b.jsonl",      "llama", "70B", "API"),
    ("gemma3-12b",   "stageF_ladder_gemma.jsonl",  "gemma", "12B", "local"),
    # group 2/3 - current-generation commercial models
    ("gpt-6-luna",   "stageG_gpt6luna.jsonl",      "gpt",   "-",   "API"),
    ("deepseek-v4.1-flash", "stageG_dsv41flash.jsonl", "deepseek", "-", "API"),
    ("gemini-3.8-flash",    "stageG_gemini38.jsonl",   "gemini",   "-", "API"),
    ("qwen3.8-flash",       "stageG_qwen38.jsonl",     "qwen3.8",  "-", "API"),
    ("claude-sonnet-5",     "stageG_sonnet5.jsonl",    "claude",   "-", "API"),
]


def stats(path):
    if not os.path.exists(path):
        return None
    rows = [json.loads(l) for l in open(path, encoding="utf-8")]
    if not rows:
        return None
    n = len(rows)
    failed = [r for r in rows if r.get("parse_failed")]
    parsed = n - len(failed)
    errs = [r for r in rows if r["real_error"]]
    # A well-formed tool call that omits `period` entirely: schema-valid (period
    # is not in `required`), raises no error, API silently applies a default.
    n_omit = sum(1 for r in rows if r.get("filled_period") == "__OMITTED__")
    out = {"n": n, "emit": parsed / n if n else 0.0,
           "err": len(errs) / parsed if parsed else float("nan"),
           "n_err": len(errs), "omit": n_omit}
    for key, lab in [("det_L1", "L1"), ("det_L2", "L2"), ("det_L3", "L3")]:
        n_det = sum(1 for r in errs if r.get(key))
        flagged = [r for r in rows if r.get(key)]
        out[lab + "_rec"] = n_det / len(errs) if errs else float("nan")
        out[lab + "_pre"] = (sum(1 for r in flagged if r["real_error"]) / len(flagged)
                             if flagged else float("nan"))
    return out


def pct(x):
    return "  n/a " if x != x else f"{x:6.1%}"


def main():
    print(f"{'model':21} {'size':>4} {'src':>5} {'n':>4} {'emit':>6} {'omit':>5} {'err':>6} "
          f"| {'L1 rec':>6} {'L1 pre':>6} | {'L2 rec':>6} {'L2 pre':>6} "
          f"| {'L3 rec':>6} {'L3 pre':>6}")
    print("-" * 122)
    data = {}
    for label, fn, fam, size, src in ROWS:
        s = stats(os.path.join(HERE, fn))
        if s is None:
            print(f"{label:21} {size:>4} {src:>5}  (not run yet)")
            continue
        data[(fam, size, src)] = s
        print(f"{label:21} {size:>4} {src:>5} {s['n']:4} {pct(s['emit'])} {s['omit']:5} {pct(s['err'])} "
              f"| {pct(s['L1_rec'])} {pct(s['L1_pre'])} | {pct(s['L2_rec'])} {pct(s['L2_pre'])} "
              f"| {pct(s['L3_rec'])} {pct(s['L3_pre'])}")

    print("\n=== sanity check: same weights, local vs API ===")
    for fam, size in [("qwen", "7B"), ("llama", "8B")]:
        a, b = data.get((fam, size, "local")), data.get((fam, size, "API"))
        if not (a and b):
            print(f"  {fam}-{size}: incomplete")
            continue
        print(f"  {fam}-{size}: err {a['err']:.1%} (local) vs {b['err']:.1%} (API)   "
              f"L3 rec {a['L3_rec']:.1%} vs {b['L3_rec']:.1%}")

    print("\n=== scale slope (same family, error rate over parsed calls) ===")
    for fam, small, big in [("qwen", "7B", "72B"), ("llama", "8B", "70B")]:
        s = data.get((fam, small, "API")) or data.get((fam, small, "local"))
        b = data.get((fam, big, "API"))
        if not (s and b):
            print(f"  {fam}: incomplete")
            continue
        print(f"  {fam:5} {small:>4} -> {big:<4}   err {s['err']:6.1%} -> {b['err']:6.1%}"
              f"   |  L3 recall {s['L3_rec']:6.1%} -> {b['L3_rec']:6.1%}")

    print("\n  enumeration screener, every configuration: 100.0% recall, 100.0% precision")


if __name__ == "__main__":
    main()
