# Stage-2j probe — three application variants of card 3 (mixed sensitivity)

Card 3's core claim (continuous sensitivity certification misses discrete tool
errors; S_mix = L_G·ε + D_G covers them) is settled. This probe tests the THREE
application stories the paper could tell, to see which one has the strongest
evidence. All three reuse the existing `mixed_scale.jsonl` (420 discrete
substitutions, 20 symbols, 4 endpoints, 2 discrete params) — **no new data
collection, no LLM, $0**.

## The three variants

| variant | story | what it needs to show | script |
|---|---|---|---|
| **B — interface audit** | tool dev runs an automated QA that lists which param combos jump | audit report surfaces dangerous combos | `audit_interface_sensitivity.py` |
| **A — decision screener** | agent checks before using an output whether the DECISION is fragile | discrete error flips real decisions; screener catches it | `decision_flip.py`, `decision_screener.py` |
| **C — tool routing** | agent picks the most robust tool via S_mix | S_mix ranks tools by robustness, stably | `route_by_sensitivity.py` |

## Variant B — interface sensitivity audit (PASS)

Reorganizes the 420 substitutions into a danger list: per (endpoint, param,
from→to), the worst-case output jump D_G.

```
enterprise-value  period quarter->fy   D_G=86.7%  <-- DANGEROUS
fundamentals      period quarter->fy   D_G=97.3%  <-- DANGEROUS
fundamentals      statement income->balance  100% <-- DANGEROUS
fundamentals      statement income->cashflow 100% <-- DANGEROUS
key-metrics       period quarter->all  D_G=43.4%  <-- DANGEROUS
key-metrics       period quarter->fy   D_G=53.1%  <-- DANGEROUS
enterprise-value  period quarter->all  D_G= 0.0%
fundamentals      period quarter->all  D_G= 0.0%
owner-earnings    period quarter->all  D_G= 0.0%
```

**Verdict: PASS (V1/V2/V3).** The audit is NOT "everything is dangerous" — it
distinguishes dangerous combos (quarter→fy, statement swaps) from safe ones
(quarter→all on most endpoints). That discrimination is the audit's value.

## Variant A — decision screener (v1 partial-fail → v2 PASS)

The decision task: "rank the 20 symbols by EPS, pick the 3 most expensive."
period=quarter vs fy gives different EPS → different ranking → different pick.

**v1 (`decision_flip.py`) — the decision DOES flip:**
- D1: 80% of symbols change rank (16/20)
- D2: top-3 selection flips 2/3 (overlap 1/3)
- D3: 28.9% of pairwise "A more expensive than B" comparisons flip
- **D4 FAIL: EPS jump magnitude does NOT predict rank change (corr −0.12)**

**Why D4 fails (the real finding):** decision flip is a RELATIVE, cross-symbol
structure change. All symbols' EPS jump ~3–4× together quarter→fy, so the
ranking reshuffles in a way no single-query output statistic predicts. A symbol
with a 93% jump (TSLA) barely moves rank; one with a 3% jump (AMZN) moves 7
places. **"Output jump is small" ≠ "decision is safe."** This directly supports
the paper's core claim — an agent cannot trust an output because it looks stable.

**v2 (`decision_screener.py`) — the correct screener is ENUMERATION, not
prediction:**
- For each discrete neighbor, recompute the DECISION; if it flips, flag it.
- This is S_mix's D_G idea applied in decision space instead of output space.
- Output-jump screening (v1's approach) misses 31% of decision flips
  (precision 73%, recall 69%); enumeration catches 100% by construction.
- **Verdict: PASS (E1/E2/E3).**

## Variant C — tool routing by sensitivity (PASS)

Different endpoints have different sensitivity to the SAME substitution
(period=quarter→fy):

```
key-metrics      D_G = 53.1%   (most robust)
enterprise-value D_G = 86.7%
fundamentals     D_G = 97.3%   (least robust)
```

- R1: endpoints differ (spread 44%)
- R2: 3 distinct sensitivity levels → usable ranking
- R3: ranking stable across symbols — key-metrics ≤ fundamentals D_G in 20/20
  symbols (100%)
- **Verdict: PASS (R1/R2/R3).** An agent can route to key-metrics for a
  period-sensitive query.

## Which variant is strongest?

- **B** is the cheapest and cleanest (pure reorganization, no new claim), but
  it's the least novel — it's a QA report, not a research result.
- **A** has the strongest research finding: **D4's failure** (output jump does
  not predict decision flip) is a genuine, non-obvious result that directly
  supports the "certification gives false safety" thesis. The enumeration
  screener is the actionable tool.
- **C** is clean and PASSes, but the finding (endpoints differ in robustness)
  is more of a useful property than a surprising result.

**Recommendation: A is the strongest story.** It has the surprising negative
(D4) that becomes the motivation, plus the actionable positive (enumeration
screener). B and C are supporting evidence.

## Running it

```bash
python audit_interface_sensitivity.py --in mixed_scale.jsonl   # variant B
python decision_flip.py --in mixed_scale.jsonl                 # variant A v1
python decision_screener.py --in mixed_scale.jsonl             # variant A v2
python route_by_sensitivity.py --in mixed_scale.jsonl          # variant C
```

## Known limits

- Decision task is EPS ranking (no external prices). A real valuation decision
  (P/E, DCF) would be a stronger test; findata's `pe` field is null.
- Enumeration screener is trivially correct (it recomputes the decision); the
  open question is cost (enumerating all neighbors) vs output-jump screening.
- Variant C tested 3 endpoints with quarter→fy data (owner-earnings has none).
