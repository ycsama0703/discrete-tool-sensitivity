# Stage-G probe — the stage-F ladder across models and scale

**Status: DONE. 12 configurations, 4,800 agent runs, ~$5.9.**

Stage F showed self-verification is unreliable on three local weak models. The
obvious objection: that is a weak-model artifact. Stage G answers it by running
**the identical experiment** — same 20 symbols x 20 questions, same tool schema,
same L1/L2/L3 prompts, same temperature 0.7 — against larger and current
commercial models through OpenRouter, with only the inference backend swapped.

Scripts: `probes/stageG_openrouter_ladder.py` (the run),
`probes/stageG_scale_table.py` (the table, reads both local and API outputs).

## Sanity check: same weights, local vs API

`qwen-2.5-7b` and `llama-3.1-8b` are the *same weights* we run locally. If the
API numbers diverged, the harness would not be comparable and nothing else here
could be read against the local results.

| model | error rate (local -> API) | L3 recall (local -> API) |
|---|---|---|
| qwen2.5-7b | 27.3% -> 30.8% | 4.6% -> 0.0% |
| llama3.1-8b | 27.5% -> 29.4% | 60.6% -> 63.8% |

llama is the striking one: not just the error rate but its idiosyncratic
*signature* reproduces — the "cry wolf" pattern of ~30% precision at every
ladder level, and L3 recall near 60%. **The harness is comparable.**

## Result

| model | size | src | emit | omit | err | L1 rec/pre | L2 rec/pre | L3 rec/pre |
|---|---|---|---|---|---|---|---|---|
| qwen2.5-7b | 7B | local | 100% | 0 | 27.3% | 100/99 | 100/65 | **4.6**/8.9 |
| qwen2.5-7b | 7B | API | 98% | 0 | 30.8% | 99/99 | 99/72 | **0.0**/0.0 |
| qwen2.5-72b | 72B | API | 100% | 0 | **38.2%** | 100/100 | 99/99 | **68.6**/99.1 |
| llama3.1-8b | 8B | local | 99% | 0 | 27.5% | 100/30 | 100/28 | **60.6**/24.0 |
| llama3.1-8b | 8B | API | 99% | 0 | 29.4% | 100/32 | 100/29 | **63.8**/27.1 |
| llama3.3-70b | 70B | API | 99% | 0 | **25.9%** | 100/100 | 8.7/17.6 | **6.8**/58.3 |
| gemma3-12b | 12B | local | 100% | 0 | 29.8% | 100/100 | 99/76 | **22.7**/73.0 |
| gpt-6-luna | — | API | 99% | 0 | 31.7% | 100/98 | 0.0/0.0 | **0.0**/0.0 |
| deepseek-v4.1-flash | — | API | 100% | 1 | 36.5% | 93/91 | 14/91 | **36.3**/79.1 |
| gemini-3.8-flash | — | API | 98% | **100** | 37.9% | 99/99 | 15/100 | **20.8**/83.8 |
| qwen3.8-flash | — | API | 100% | 1 | 29.5% | 100/100 | 83/80 | **89.8**/32.6 |
| claude-sonnet-5 | — | API | 100% | 0 | 36.5% | 100/99 | 92/92 | **76.7**/99.1 |

`emit` = fraction of runs producing a parseable tool call. `omit` = well-formed
calls that left `period` out entirely. `err` is over parsed calls.
**Enumeration screener: 100% recall AND 100% precision on every row**, because
it never consults the model.

### Finding 1: nothing fixes the error rate — not scale, not generation, not vendor

| | error rate |
|---|---|
| 7B-12B local models | 27.3 - 29.8% |
| 70-72B | 25.9 - 38.2% |
| current commercial (5 vendors) | 29.5 - 37.9% |

**Every one of the twelve configurations lands between 25.9% and 38.2%.** A
~10x parameter increase does not help; neither does roughly two model
generations; neither does moving from an open 7B to a frontier commercial
model. `claude-sonnet-5` errs at 36.5%, *higher* than the local 7B's 27.3%.

This is the load-bearing result for the paper: **the error the screener exists
to catch does not go away as models improve.** Anyone waiting for the next
model release to solve it will be waiting indefinitely.

### Finding 2: self-verification is unreliable *unpredictably*

This revises stage F's conclusion, and the revision makes it stronger.

L3 (error localization) recall across the twelve configurations spans
**0.0% to 89.8%** — essentially the entire range. And it moves in no
interpretable direction:

| comparison | L3 recall |
|---|---|
| qwen 7B -> 72B | 4.6% -> **68.6%** (improves) |
| llama 8B -> 70B | 63.8% -> **6.8%** (degrades) |
| within 70-72B | 6.8% (llama) vs 68.6% (qwen) |
| gpt-6-luna | **0.0%** |
| qwen3.8-flash | **89.8%**, but precision only 32.6% |
| claude-sonnet-5 | 76.7% at 99.1% precision — the best of the twelve |

Even where recall is high, precision often is not: `qwen3.8-flash` catches
89.8% of real errors but only 32.6% of what it flags is a real error. It is
close to flagging everything.

`gpt-6-luna` is the cleanest failure: L1 is perfect (100% recall) — told the
correct period, it judges correctly — but L2 and L3 are both exactly **0.0%**.
Without being handed the answer it never once said its own call was wrong.

**The revised claim:** stage F said self-verification localizes poorly. The
full sweep says something more useful — self-verification's reliability is
*not predictable* from scale, generation, or vendor. It ranges from 0% to 90%,
and the same family scaled 10x can move either way.

That is a stronger argument for the screener than "self-check is always bad":
**you cannot fix this by choosing a better model, because you cannot know in
advance which regime yours is in.** The screener is 100%/100% everywhere
precisely because it never consults the model.

### Finding 3: a third, more silent failure mode — omitting `period`

`gemini-3.8-flash` emitted **100 out of 400** tool calls that were perfectly
well-formed but left `period` out entirely:

```json
{"name":"get_fundamentals","arguments":{"symbol":"AAPL","statement":"cashflow"}}
```

`period` is not in the schema's `required` list, so this is **schema-valid,
raises no error, and the API silently applies a default**. It is more silent
than filling the wrong value: a wrong value at least leaves a trace in the
call, an omission leaves none.

All of them landed on the ambiguous questions ("cash flow from operations",
"current assets", "cash from investing", "shareholders' equity") — the same
pattern as insufficient binding.

**The screener catches these unchanged**, because it enumerates the period
values and recomputes regardless of what the model wrote — one more case where
a model-independent mechanism covers something model-dependent checks miss.

## Two harness lessons

Both were caught only because failures are recorded by *cause*, not as one
generic `parse_failed` flag. Both would have produced clean, plausible, wrong
findings.

**1. llama-3.3-70b: `parameters` instead of `arguments`.** The first run
reported 12.5% tool-call emission and a 2.5% error rate — reading as "the 70B
model barely makes these mistakes". The parser only accepted OpenAI-style
`arguments` with bare values; llama emits `parameters` with each value wrapped
in its schema type annotation, which also overran the token cap. 87.5% of valid
calls were discarded. After the fix: 99.2% emission, 25.9% error.

**2. gemini-3.8-flash: omitted `period` scored as "no tool call".** This
deflated its error rate from 37.9% to an apparent 25%, and hid an entire
failure mode.

**The general point for cross-model comparison: "the model produced nothing",
"I failed to parse it", and "the model produced something incomplete" must be
recorded separately.** Otherwise harness gaps masquerade as model capability
differences — and they masquerade in the direction of *newer/stronger models
looking better*, which is the direction one is least likely to question.

A third case worth noting: the current-generation models are all reasoning
models. They spend output budget on chain-of-thought before emitting anything,
and return `content: null` with the text in `reasoning`. With stage F's
30-token verification cap they would have scored 0% everywhere, purely from
truncation. Caps were raised to 2000 (tool call) and 600 (verification).

## Engineering notes

- **Concurrency is required.** Serially one case (4 dependent calls) took ~60s,
  i.e. ~6.7h per model; at concurrency 12 it is 2-90 min depending on provider.
- **Resumable** (`--resume` skips cases already in the output).
- Cost tracked live from OpenRouter's `usage.cost`.
- ~100 cases already gives error rate and L3 recall within a couple of points
  of the 400-case value.
- Key read from `OPENROUTER_API_KEY` or a gitignored `.env`; never logged.

**Actual cost**, 400 cases x 4 calls each:

| model | cost | note |
|---|---|---|
| qwen2.5-7b / 72b / llama-8b / 70b | $0.33 total | group 1 |
| gpt-6-luna | $0.11 | |
| deepseek-v4.1-flash | $0.30 | |
| qwen3.8-flash | $0.24 | |
| gemini-3.8-flash | **$2.17** | 490K output tokens — reasoning-heavy |
| claude-sonnet-5 | **$2.71** | 687K input tokens |
| **total** | **~$5.9** | |

Reasoning models cost 3-10x the naive estimate because chain-of-thought counts
as output. `gemini-3.8-flash` produced more output tokens (490K) than input
(453K).

## Limitations

- One decision task, one parameter, one schema. The 25.9-38.2% band is specific
  to this setup; what transfers is that it does not shrink with model quality.
- `anthropic/claude-sonnet-5:batch` was requested but is unusable here: the
  `:batch` variants route to an async adapter and return 404 from
  `chat/completions`. The synchronous `claude-sonnet-5` was run instead, at
  roughly double the price.
- Twelve configurations cannot say *why* L2/L3 varies so much. Whether it tracks
  tool-call training, instruction-tuning recipe, or nothing in particular is
  open.

## Files

- `probes/stageG_openrouter_ladder.py` — the run
- `probes/stageG_scale_table.py` — the table
- `probes/stageG_{qwen7b,qwen72b,llama8b,llama70b}.jsonl` — group 1
- `probes/stageG_{gpt6luna,dsv41flash,gemini38,qwen38,sonnet5}.jsonl` — group 2/3
- this note
