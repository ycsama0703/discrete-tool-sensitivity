# Stage-2k probe — end-to-end: does the screener solve the problem? (card 3)

The core claim (continuous certification gives false safety on discrete errors)
and the three application variants (A/B/C) are settled. This probe is the
**"solve the problem"** step: does the screener actually REDUCE decision errors
when an agent flips a discrete parameter?

## The honest framing

The screener does NOT stop the agent from making discrete errors (it can't —
weak models make them 12–18.75% of the time). It CATCHES the error before the
wrong output reaches a decision. So the metric is not "fewer agent errors" but
"fewer wrong DECISIONS".

## Design

Decision task: "rank 20 symbols by EPS, pick the 3 most expensive."
- correct period = quarter (the intended query)
- agent flips period=quarter → fy with probability p_err (measured weak-model
  rate 12–18.75%)

**Baseline** (no screener): agent queries, may flip, uses whatever EPS it got,
picks top-3. If it flipped, its top-3 is wrong → decision error.

**Screener**: agent queries, may flip. Before deciding, the screener flags the
query as decision-unsafe. If flagged, the agent re-queries correctly.

Two screener designs (using measured precision/recall from variant A):
- **output-jump screening** (v1's failed approach): recall 69%, precision 73%
- **enumeration screening** (v2): recall 100%, precision 100% (recomputes the
  decision for each neighbor)

## Results (Monte Carlo, 50k runs, real EPS data)

| p_err | baseline | output-jump | enum | output-jump re-query | enum re-query |
|---|---|---|---|---|---|
| 5.0% | 4.9% | 1.6% | 0.0% | 4.7% | 4.9% |
| 12.0% | 12.1% | 3.8% | 0.0% | 11.5% | 12.1% |
| 18.8% | 19.0% | 5.9% | 0.0% | 18.0% | 19.0% |
| 30.0% | 30.2% | 9.4% | 0.0% | 28.5% | 30.2% |
| 50.0% | 50.0% | 15.4% | 0.0% | 47.4% | 50.0% |

## What this shows

- **Output-jump screening reduces decision error ~69%** (12% → 3.8% at the
  measured error rate), but cannot reach 0 — it misses 31% of decision flips
  (the D4 failure from variant A, now shown to have real end-to-end cost).
- **Enumeration screening reduces decision error to 0%** (12% → 0%), at the
  cost of re-querying every run (12.1% re-query rate = the price of safety).
- At the measured weak-model error rate (12–18.75%), the enumeration screener
  drives decision error from ~12% to 0%.

**This is the "solve the problem" evidence**: not making the agent smarter, but
catching the error before it reaches a decision. The enumeration screener is
the actionable tool; output-jump screening is the incomplete baseline that
motivates it.

## Running it

```bash
python end_to_end.py --in mixed_scale.jsonl
```

## Known limits

- Monte Carlo simulation over real EPS data, not a live agent loop. The agent
  flip probability is taken from the measured generator-relevance error rates.
- The screener's re-query cost is modeled as a fraction of runs, not real API
  latency/cost.
- Decision task is EPS ranking (no external prices); a real valuation decision
  would be a stronger test.
