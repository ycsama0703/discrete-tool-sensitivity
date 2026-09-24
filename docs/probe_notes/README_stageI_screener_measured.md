# Stage-I probe — what the screener actually achieves when you measure it

**Status: DONE. This probe corrects a claim the paper has been making.**

## Why this exists

The repo reports the enumeration screener at **100% precision and 100% recall**
in three places. On inspection, none of the three is a measurement:

| place | claim | what the code does |
|---|---|---|
| `baseline_family.py` (stage E) | prec/recall 100% | `our_flags = true_flip  # by construction` — an identity |
| `agent_end_to_end.py` (stage D) | decision error 100% -> 0% | the screener branch queries `correct_period` in **both** arms — an oracle |
| `stageG_scale_table.py` | "100/100 every configuration" | a hardcoded `print`, never executed |

The stage D case is the sharpest. The code reads:

```python
if cross_flip[sym]:
    eps = findata_eps(sym, correct_period)   # "screener flags it and re-queries"
else:
    eps = findata_eps(sym, correct_period)   # no error, also correct period
```

Both branches are identical. The "screener" is one line of *always use the right
answer*. Its 0% decision error is true by construction, and it presumes exactly
the thing that is unavailable in deployment: knowing which period is correct.

## What this probe measures instead

Real tool calls from all 12 stage-F/G configurations, real findata EPS for the
20 symbols under `quarter` and `fy`, and an **implementable** screener:

> For each symbol, enumerate the period enum, recompute the top-3, and flag the
> question if the decision is not invariant. Never consult the model.

Definitions were fixed before running (they are in the script docstring). Two
events are kept apart rather than conflated:

- **param error** — the agent filled a period != the correct one
- **decision error** — the resulting top-3 differs from the correct top-3

They come apart: a wrong period that does not reorder the top-3 harms no
decision. The screener targets decision errors.

## Result

| config | Q | param err | decision err | flagged | DEC recall | DEC precision |
|---|---|---|---|---|---|---|
| qwen2.5-7b (local) | 20 | 7 | 0 | 20 | n/a | 0% |
| qwen2.5-72b | 20 | 8 | 0 | 20 | n/a | 0% |
| llama3.1-8b (local) | 20 | 8 | 4 | 20 | **100%** | 20% |
| llama3.3-70b | 20 | 8 | 0 | 20 | n/a | 0% |
| gpt-6-luna | 20 | 7 | 0 | 20 | n/a | 0% |
| deepseek-v4.1-flash | 20 | 8 | 2 | 20 | **100%** | 10% |
| gemini-3.8-flash | 20 | 8 | 1 | 20 | **100%** | 5% |
| qwen3.8-flash | 20 | 7 | 4 | 20 | **100%** | 20% |
| claude-sonnet-5 | 20 | 8 | 3 | 20 | **100%** | 15% |

**Recall is 100% wherever it is defined** — the pre-registered expectation held.
**Precision is 5-20%**, not 100%.

The screener flagged **20/20 questions for every configuration** — identically,
because it never looks at the model. On these 20 symbols the top-3 always moves
between `quarter` and `fy` (MU is rank 1 quarterly and rank 18 annually; NFLX
goes 16 -> 1), so every question is period-sensitive and every question is
flagged.

### The flag rate is a property of the data, not of the screener

Running the same check across the four symbol universes in `tau_universe.jsonl`:

| universe | flag rate |
|---|---|
| CONSUMER | **50%** |
| ENERGY_STAPLES | 67% |
| FIN_HEALTH | 75% |
| TECH | **92%** |
| all 48 tasks | 71% |

The 100% in the table above comes from using 20 large-cap tech stocks — the most
period-sensitive corner available. On consumer names the screener passes half
the queries. **It does discriminate; we tested it on the worst case.**

## What the screener actually provides

Not "exact detection". What it provides is:

> **zero missed decision errors, at the cost of over-warning at a rate set by
> how period-sensitive the data is (50-92% here).**

Against the best self-check we measured:

| | recall | precision | missed |
|---|---|---|---|
| self-verification (claude-sonnet-5, best of 12) | 76.7% | 99.1% | **23%** |
| enumeration screener (measured) | **100%** | 5-20% | **0** |

These are different trade-offs, not one dominating the other. The honest claim
is **"the only method with a zero-miss guarantee"**, not "the only exact method".

## What must change in the write-up

- Delete "precision 100%" / "exact" wherever it describes the screener.
- Stage D's "100% -> 0%" must be labelled an oracle bound, not a result.
- Stage E's table should mark our row as an identity, not a measured baseline.
- The screener's value proposition becomes *guarantee* (zero misses) and
  *measurement* (how period-dependent is this decision), not *precision*.

## Limitations

- The decision task (top-3 by EPS over 20 symbols) is ours, not a naturally
  occurring workload. Real decision errors turned out to be rare (0-4 of 20
  questions) because most models fill `all`, which resolves to the quarter
  series and is therefore right whenever the question wanted quarter.
- Daloopa cannot substitute: it is single-number retrieval with no decision, so
  "does the decision flip across periods" is undefined there. That is a
  benchmark/method mismatch, not evidence about the screener.
- **We have never evaluated the screener on a naturally occurring decision
  workload.** That gap is real and should be stated in the paper.

## Files

- `probes/stageI_screener_measured.py` — the probe
- `probes/stageI_eps_cache.json` — findata EPS snapshot used
- this note
