# Stage-G probe — the stage-F ladder across a capability scale

**Status: group 1 (same-family scale) DONE.**

Stage F showed self-verification is unreliable on three local weak models. The
obvious objection: that is a weak-model artifact. Stage G answers it by running
**the identical experiment** — same 20 symbols x 20 questions, same tool schema,
same L1/L2/L3 prompts, same temperature 0.7 — against larger models through
OpenRouter, with only the inference backend swapped.

Scripts: `probes/stageG_openrouter_ladder.py` (the run),
`probes/stageG_scale_table.py` (the table, reads both local and API outputs).

## Design: a scale ladder, not a grab-bag of strong models

The question is whether the phenomenon **decays with scale**, so the selection
holds the family fixed and varies only the parameter count — and the small end
is already measured locally:

| pair | ratio |
|---|---|
| qwen2.5 **7B** (local) -> qwen2.5 **72B** (API) | ~10x |
| llama3.1 **8B** (local) -> llama3.3 **70B** (API) | ~9x |

Cost for all four at the full 400-case ladder: **~$0.33**.

## Sanity check: same weights, local vs API

`qwen-2.5-7b` and `llama-3.1-8b` are the *same weights* we run locally. If the
API numbers diverged, the harness would not be comparable and the scale
comparison would be void.

| model | error rate (local -> API) | L3 recall (local -> API) |
|---|---|---|
| qwen2.5-7b | 27.3% -> 30.8% | 4.6% -> 0.0% |
| llama3.1-8b | 27.5% -> 29.4% | 60.6% -> 63.8% |

llama is the striking one: not just the error rate but its idiosyncratic
*signature* reproduces — the "cry wolf" pattern of ~30% precision at every
ladder level, and an L3 recall near 60%. That is not something that matches by
chance. **The harness is comparable.**

## Result

| model | size | src | emit | err | L1 rec/pre | L2 rec/pre | L3 rec/pre |
|---|---|---|---|---|---|---|---|
| qwen2.5-7b | 7B | local | 100% | 27.3% | 100/99 | 100/65 | **4.6/8.9** |
| qwen2.5-7b | 7B | API | 98% | 30.8% | 99/99 | 99/72 | **0.0/0.0** |
| qwen2.5-72b | 72B | API | 100% | **38.2%** | 100/100 | 99/99 | **68.6/99.1** |
| llama3.1-8b | 8B | local | 99% | 27.5% | 100/30 | 100/28 | **60.6/24.0** |
| llama3.1-8b | 8B | API | 99% | 29.4% | 100/32 | 100/29 | **63.8/27.1** |
| llama3.3-70b | 70B | API | 99% | **25.9%** | 100/100 | **8.7/17.6** | **6.8/58.3** |
| gemma3-12b | 12B | local | 100% | 29.8% | 100/100 | 99/76 | 22.7/73.0 |

(`emit` = fraction of runs producing a parseable tool call; `err` is over
parsed calls. Enumeration screener: 100% recall AND 100% precision on every
row, because it does not depend on the model.)

### Finding 1: scale does not fix the binding defect

| family | small | large |
|---|---|---|
| qwen | 27.3% | **38.2%** (worse) |
| llama | 29.4% | **25.9%** (slightly better) |

A ~10x increase in parameters leaves the period error rate in a 26-38% band,
with no consistent direction and certainly no order-of-magnitude improvement.
**Filling the wrong discrete parameter is not a small-model failing.** This is
the load-bearing result for the paper: the error the screener exists to catch
does not go away as models get bigger.

### Finding 2: self-verification is unreliable in an *unpredictable* way

This revises stage F's conclusion, and the revision makes it stronger.

| family | L3 recall, small -> large |
|---|---|
| qwen | 4.6% -> **68.6%** (large improvement) |
| llama | 63.8% -> **6.8%** (large degradation) |

Same ~10x scale step, **opposite directions**. And within a single size class
the spread is enormous: at 70-72B, L3 recall is 68.6% (qwen) versus 6.8%
(llama).

llama-3.3-70b is the sharpest case: L1 is perfect (100% recall, 100%
precision) — told the correct period, it judges flawlessly — but L2 collapses
to 8.7%. Without being handed the answer it almost always says its own call was
fine.

**The revised claim:** stage F said self-verification localizes poorly. The
scale data says something more useful — self-verification's reliability is
*not predictable from scale or family*. L3 recall ranges from 6.8% to 68.6%
across four models, and scaling a family up 10x can move it either way.

That is a stronger argument for the screener than "self-check is always bad":
you cannot fix this by picking a bigger or better model, because you cannot
know in advance which regime your model is in. The screener is 100%/100%
everywhere precisely because it never consults the model.

## A harness lesson worth recording

The first llama-3.3-70b run reported **12.5% tool-call emission and a 2.5%
error rate**. Read naively that says "the 70B model barely makes these
mistakes" — a clean, plausible, and completely wrong finding.

The cause was the parser, not the model. llama emits

```json
{"type":"function","name":"get_fundamentals",
 "parameters":{"symbol":{"type":"string","value":"AAPL"}, ...
```

— `parameters` rather than `arguments`, with each value wrapped in its schema
type annotation. The parser accepted only the OpenAI-style `arguments` with
bare values, so 87.5% of valid calls were discarded. The verbose format also
overran the 400-token cap, truncating calls mid-JSON.

Two things made this catchable rather than publishable:

1. **Failures were split by cause** (`no_toolcall` vs `api_error`) and the
   emission rate was reported *beside* the error rate, instead of a single
   `parse_failed` flag. A 12.5% emission rate is obviously wrong in a way that
   "error rate 2.5%" is not.
2. The error rate denominator is parsed calls, so a parsing gap shows up as a
   collapsing denominator rather than a flattering numerator.

**The general point for cross-model comparison: "the model produced nothing"
and "I failed to parse it" must be recorded separately.** Otherwise harness
gaps masquerade as model capability differences — and they masquerade in the
direction of *stronger models looking better*, which is exactly the direction
one is least likely to question.

Fixes: accept `arguments` or `parameters`, unwrap `{"type":..,"value":..}`
envelopes, raise the tool-call cap to 800 tokens. After the fix llama-3.3-70b
emits 99.2%.

## Engineering notes

- **Concurrency is required.** Serially one case (4 dependent calls) took ~60s,
  i.e. ~6.7h per model; at concurrency 12 it is 2-90 min depending on provider.
  qwen-2.5-7b (Phala) is an order of magnitude slower than the rest.
- **Resumable** (`--resume` skips cases already in the output), so a mid-run
  failure does not waste spend.
- Cost tracked live from OpenRouter's `usage.cost`. Group 1 total: ~$0.33.
- ~100 cases already gives error rate and L3 recall within a couple of points
  of the 400-case value, useful if a later group needs to be cheaper.
- Key read from `OPENROUTER_API_KEY` or a gitignored `.env`; never logged.

## Still open

- Groups 2 and 3 (cheap deployment tier: gpt-4o-mini, gemini-2.5-flash,
  deepseek-chat; frontier: gpt-5.1, claude-sonnet-5), ~$2.7.
- Whether the L2/L3 spread tracks anything predictable (instruction-tuning
  recipe? tool-call training?) or is simply idiosyncratic. Four models cannot
  answer this.

## Files

- `probes/stageG_openrouter_ladder.py` — the run
- `probes/stageG_scale_table.py` — the table
- `probes/stageG_{qwen7b,qwen72b,llama8b,llama70b}.jsonl` — results
- this note
