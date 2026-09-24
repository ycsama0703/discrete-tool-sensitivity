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

### The core claim reproduces on real errors: the bound reports zero, the
### output moves a lot

This is the external-validity test of the paper's central theoretical claim.
Script: `D:\luyao4\exp\daloopa\analyze_jump_magnitude.py`.

Relative output jump = `|answer_num - gt_num| / |gt_num|` over the 170 real
period errors:

| statistic | value |
|---|---|
| median | **18.8%** |
| p75 | 38.8% |
| p90 | 99.8% |
| **> 1%** | **170/170 = 100%** |
| > 10% | 124/170 = 73% |
| > 30% | 45/170 = 26% |

**Not a single one of the 170 real period errors moves the output by less than
1%**, and 73% move it by more than 10%. Meanwhile the continuous Lipschitz
bound reports `S_cont(0) = 0` on **all** of them — a discrete substitution has
no continuous perturbation to measure. **Certification does not miss the error
quietly; it actively reports zero.**

Side-by-side with our own probes:

| | findata (our construction) | Daloopa (real commercial models) |
|---|---|---|
| sample | 96 discrete substitutions | 170 real period errors |
| median jump | 47.3% | **18.8%** |
| fraction > 10% | 62% | **73%** |
| continuous bound | **0** | **0** |
| schema-valid / no error raised | 100% | 100% |

Daloopa's median is lower than ours, and the reason is informative: our
substitutions are `quarter → fy` (a single quarter vs a full year, ~4x by
construction), whereas Daloopa mixes `FY2022 → FY2023` (adjacent years, where
YoY change is naturally only 10–20%) with quarter shifts and fiscal-vs-calendar
confusions. **Even the mildest kind of period error — one adjacent fiscal year
— still moves the output by ~19% at the median while the bound reports zero.**

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
