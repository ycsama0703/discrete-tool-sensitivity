# Stage-G probe — the stage-F ladder on commercial models via OpenRouter

**Status: IN PROGRESS (harness validated, full runs pending).**

Stage F showed that self-verification is unreliable on three local weak models
(qwen2.5:7b, llama3.1:8b, gemma3:12b). The obvious objection is that this is a
weak-model artifact. Stage G answers it by running **the identical experiment**
— same 20 symbols x 20 questions, same tool schema, same L1/L2/L3 prompts, same
temperature 0.7 — against commercial models through OpenRouter, with only the
inference backend swapped.

Script: `probes/stageG_openrouter_ladder.py`.

## Model selection: a capability ladder, not a grab-bag

The point is not "test some strong models"; it is to see whether the phenomenon
**decays with scale or persists**. So the selection is structured:

**Group 1 — same-family scale (the clean slope).** Only the parameter count
varies, and the small end is already measured locally:

| model | ~cost / full run | role |
|---|---|---|
| `qwen/qwen-2.5-7b-instruct` | $0.05 | **sanity check** vs our local qwen2.5:7b |
| `qwen/qwen-2.5-72b-instruct` | $0.19 | qwen 7B -> 72B, 10x scale |
| `meta-llama/llama-3.1-8b-instruct` | $0.03 | **sanity check** vs our local llama3.1:8b |
| `meta-llama/llama-3.3-70b-instruct` | $0.06 | llama 8B -> 70B |

**Group 2 — the cheap deployment tier (closest to the paper's motivation).**
Real cost-sensitive deployments run these, not 7B local models and not Opus:

| model | ~cost |
|---|---|
| `openai/gpt-4o-mini` | $0.09 |
| `google/gemini-2.5-flash` | $0.22 |
| `deepseek/deepseek-chat` | $0.18 |

**Group 3 — frontier ceiling (two is enough; they are expensive and similar).**

| model | ~cost |
|---|---|
| `openai/gpt-5.1` | $0.91 |
| `anthropic/claude-sonnet-5` | $1.27 |

Total ~$3 for all nine at the full 400-case ladder.

## Why the two sanity-check models matter

`qwen-2.5-7b` and `llama-3.1-8b` are the *same weights* we ran locally. If the
API error rate diverges sharply from the local run, the harness is not
comparable and none of the commercial numbers can be read against the local
ones. This must pass before spending on the rest.

**Smoke test (1 symbol, 20 cases, qwen-2.5-7b):** error rate 25% vs 27.3%
locally, and — more telling than the rate — the *same error signature*: the
model fills `all`, the errors land on the quarter-intent questions, L1 catches
them, L3 does not. The harness is comparable.

## An observation the local runs could not produce

On OpenRouter some models **do not emit a tool call at all** — they answer in
prose ("To provide the most accurate information on Apple's shareholders'
equity, I would need to refer to...") and get truncated. This never happened
locally, where a chat template with an explicit tool-call format was applied.

This is real model behaviour, not a harness bug, so the script records it
separately (`fail_reason: "no_toolcall"` vs `"api_error"`) and the analysis
reports the tool-call emission rate alongside the period error rate. **These
cases must not be silently counted as "no error"** — a model that declines to
call the tool has not got the period right; it has produced nothing to check.

Two harness details follow from it:
- `max_tokens` for the tool call is 400, not 200: a tight cap truncates models
  that write a sentence of preamble, turning real output into a fake parse
  failure (`finish_reason: "length"`).
- The denominator for the period error rate is *parsed calls*, with the
  emission rate reported next to it, so the two effects stay separable.

## Engineering notes

- **Concurrency is required.** Serially, one case (4 dependent API calls) took
  ~60s, i.e. ~6.7h per model. With 8-10 concurrent cases it is ~35-45 min.
- **Resumable.** `--resume` appends and skips (symbol, idx) already in the
  output, so a mid-run failure does not waste spend.
- **Cost is tracked live** from OpenRouter's `usage.cost` field and printed
  with the ETA on every line.
- The key is read from `OPENROUTER_API_KEY` or a gitignored `.env`; it is never
  logged.

## Files

- `probes/stageG_openrouter_ladder.py` — the probe
- `probes/stageG_*.jsonl` — per-model results (pending)
- this note
