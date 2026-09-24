# Daloopa period-binding probe — local models on the same questions as commercial models

**Status: DONE.** We run our three local models (qwen2.5:7b, llama3.1:8b,
gemma3:12b) on the Daloopa financial-retrieval questions, asking each model to
classify the period intent (fiscal year vs quarter) of each question, and
compare against the true period extracted by rule. This measures the discrete
period binding capability — the same capability that, when it fails, makes an
agent fill the wrong `period` tool parameter.

Script: `probes/daloopa_period_binding.py`. Data: Daloopa `train.csv`
(500 questions × 6 commercial models).

## Result

On the 467 questions with a clear period intent (fy or quarter):

| model | period binding error |
|---|---|
| llama3.1:8b (local) | **0.0%** |
| qwen2.5:7b (local) | 0.2% |
| gemma3:12b (local) | 0.2% |
| claude_dlp (commercial, grounded) | 0.4% |
| gemini (commercial) | 4.7% |
| claude (commercial) | 4.9% |
| perplexity (commercial) | 5.8% |
| chatgpt (commercial) | 6.9% |
| grok (commercial) | 9.2% |

## Interpretation (careful)

**Local weak models bind period intent almost perfectly (0-0.2%) when the
question explicitly names the period.** This is NOT "local models are better
than commercial models" — the tasks differ:

- **Local models** only classify period intent (a guided two-way choice).
- **Commercial models** retrieve the number from financial filings, where they
  can pick the wrong adjacent period (FY2022 vs FY2023, Q3 vs Q4).

So the commercial 5-9% errors come from the *retrieval* process, not from
period-intent classification per se.

## What this actually shows (the valuable part)

**It draws the explicit-vs-ambiguous boundary:**

- **Explicit period** ("fiscal year 2023", "Q3 2023"): local models bind at
  ~0% error.
- **Ambiguous period** (our stage D: "current assets", "cash from investing"):
  local models make 24-28% errors.

This strengthens the paper's core claim: binding failure is NOT "the model
doesn't understand period semantics" — it is that **binding is insufficient on
ambiguous input**. When the period is explicit, binding is near-perfect; when
it is ambiguous, binding collapses.

## Honest limitations

- The prompt is guided (explicitly asks fy/quarter), which may be optimistic.
- This measures period-intent classification, not agent tool-parameter filling
  (our stage D/F scenario). It is a *contrast* (explicit vs ambiguous), not a
  direct replication of the commercial retrieval errors.

## Files

- `probes/daloopa_period_binding.py` — the probe
- `probes/daloopa_period_{qwen,llama,gemma}.jsonl` — results
- this note
