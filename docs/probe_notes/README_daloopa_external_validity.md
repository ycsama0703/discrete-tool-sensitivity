# Daloopa external-validity probe — real commercial models make discrete period errors

**Status: DONE (pure data analysis, zero cost).** Uses the public Daloopa
financial-retrieval benchmark (500 questions × 6 models, per-question results
with error classification) to answer: **do real commercial models make the
discrete parameter errors our paper is about?** And: **are those errors
enumerable neighbors the screener can cover?**

Data: `D:\luyao4\exp\daloopa\train.csv` (MIT, from
`https://huggingface.co/datasets/daloopa/financial-retrieval`).
Analysis: `D:\luyao4\exp\daloopa\analyze_discrete_period_errors.py`.

## Why this matters

Our stage F / stage D experiments use weak open models (qwen2.5:7b,
llama3.1:8b, gemma3:12b) that we run ourselves. A reviewer's objection: "your
conclusion is only about weak models you chose; do real commercial models make
these errors?" Daloopa answers this with **real frontier models** (ChatGPT,
Claude, Grok, Gemini, Perplexity) on **real financial-retrieval questions**,
with a per-question error classification that includes exactly the discrete
period errors we study.

## Result

### Real commercial models DO make discrete period errors

| model | fiscal/period error rate |
|---|---|
| grok | 8.8% |
| chatgpt | 7.0% |
| perplexity | 6.2% |
| gemini | 5.6% |
| claude | 5.4% |
| **claude_dlp** (grounded) | **1.0%** |

- **5 non-grounded commercial models make 5–9% discrete period errors**
  (fiscal_vs_calendar, period_shift). This refutes the assumption that "strong
  models don't make these errors" — on real retrieval tasks they do.
- **claude_dlp (grounded to an authoritative source) drops to 1.0%** — a 5–8×
  reduction. This is the same story as our screener: grounding/authoritative
  data sharply reduces discrete parameter errors, but even grounded leaves 1%
  residual.
- **85/500 questions have at least one model making a fiscal/period error** —
  the errors are widespread, not a single model's quirk.

### The errors are enumerable neighbors (screener-coverable)

**169/170 (99.4%)** of the fiscal/period errors are adjacent-period neighbors —
FY2022 vs FY2023, Q3 vs Q4, fiscal-Q4 vs calendar-Q4 — exactly the discrete
neighborhood the enumeration screener (|S| ~ 3) covers. So the screener's
mechanism (enumerate the period neighbors, recompute) applies to real
commercial-model errors, not just our weak-model agent errors.

## Task boundary (honest)

Daloopa is **single-number retrieval by a chatbot with web search**, NOT a
tool-use agent (the paper explicitly says "No APIs, agents or wrappers"). The
errors are period-selection mistakes during retrieval — structurally the same
discrete parameter error as our agent filling the wrong `period`, but the
mechanism differs (retrieval selection vs parameter binding). **Cite as
external validity, not a direct replication.**

## What this adds to the paper

- **External validity**: the discrete-period-error phenomenon is not an
  artifact of our weak-model setup; real commercial models make it too.
- **Scope boundary**: the error rate is lower for commercial models (5–9%)
  than our weak models (24–28%), and grounding drops it to 1% — but it does
  not vanish. The screener is needed wherever the error is nonzero.
- **Screener mechanism transfers**: 99.4% of real commercial errors are
  enumerable neighbors, so the enumeration mechanism applies.

## Files

- `D:\luyao4\exp\daloopa\train.csv` — the benchmark (500 × 6)
- `D:\luyao4\exp\daloopa\analyze_discrete_period_errors.py` — the analysis
- this note
