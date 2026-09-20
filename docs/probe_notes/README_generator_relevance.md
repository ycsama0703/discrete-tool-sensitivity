# Stage-2g probe — generator relevance for discrete tool errors (card 3)

The Phase-0 probe (README_discrete_sensitivity.md) showed findata's discrete
parameters (period: quarter/fy/all, statement: balance/cashflow/income) produce
output jumps a continuous sensitivity bound cannot cover (D1/D2/D3 PASS). But
that only proves the *structure* exists. This probe tests whether a real LLM
actually MAKES these discrete errors — the generator relevance that connects
the certification story to real agent behavior.

Card 3's go condition: **at least 10% of a fixed LLM's actual semantic errors
must fall in the pre-registered adjacency graph G** (period/statement
substitutions). Otherwise the graph is mathematically valid but has no
diagnostic value for real generators.

Budget: **~$1-3** (LLM tool-call generation via OpenRouter).

## What is being tested

**G1 — the LLM makes discrete parameter errors.** When asked to call findata
tools, the LLM sometimes fills the wrong discrete parameter (period=quarter
when it should be fy, statement=income when it should be cashflow). **Kill if
error rate < 5%** — the LLM is too reliable on these parameters to matter.

**G2 — the errors fall in the adjacency graph.** The discrete errors the LLM
makes are the SAME substitutions we pre-registered (period quarter↔fy↔all,
statement balance↔cashflow↔income). **Kill if < 10% of errors are in G** —
then the graph doesn't match real generator behavior.

**G3 — the errors are schema-valid.** The wrong parameters are still accepted
by the API (no type error), so they're "legal but semantically wrong" — the
object of study. **Kill if < 80% are schema-valid** — then the errors are just
malformed calls, not discrete substitutions.

## Design

Construct financial questions that require a findata call, with ambiguity that
can induce a discrete parameter error:

| question intent | correct call | possible discrete error |
|---|---|---|
| "AAPL's quarterly revenue" | period=quarter | period=fy (annual) |
| "AAPL's annual revenue" | period=fy | period=quarter |
| "AAPL's cash flow" | statement=cashflow | statement=income |
| "AAPL's balance sheet" | statement=balance | statement=income |
| "AAPL's income statement" | statement=income | statement=balance |

The LLM is given the findata tool schema (with the discrete enums) and asked to
produce the call. We record the generated parameters and check for discrete
errors.

## Pre-registered decision rules

**G1 — LLM makes discrete errors.** Fraction of runs where the LLM fills a
wrong discrete parameter. **Kill if < 5%.**

**G2 — errors in adjacency graph.** Fraction of discrete errors that are the
pre-registered substitutions (period quarter↔fy↔all, statement
balance↔cashflow↔income). **Kill if < 10%.**

**G3 — schema-valid.** Fraction of discrete errors accepted by the API.
**Kill if < 80%.**

All three pass → card 3's generator relevance holds: a real LLM makes the
discrete errors the certification story is about.

## Running it

```bash
export OPENROUTER_API_KEY=...
python run_generator_relevance.py --n 40 --out gen_relevance_results.jsonl
python run_generator_relevance.py --analyze gen_relevance_results.jsonl
```

Model is `deepseek/deepseek-v4-flash-0731` via OpenRouter.

## Known limits

- One model family to start; cross-model replication later.
- Questions are constructed to induce discrete errors (not natural queries).
  This measures whether the LLM CAN make the error, not its natural rate.
- Tests period/statement substitutions on fundamentals. Other parameters
  (ticker, unit) later.
