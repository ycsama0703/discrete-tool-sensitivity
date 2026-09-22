# Stage-A probe — semantic binding: does the correct binding dominate parameter choice?

**Status: DESIGN (not yet run).** This is the experiment plan for the mechanism
layer of the paper (`docs/llm_semantic_binding_theory.md`). It tests the
central proposition on a real open-weight LLM (qwen2.5:7b on luyao4).

## What this tests

The theory (§4 of `llm_semantic_binding_theory.md`) claims: an LLM's choice of
a discrete tool parameter is governed by a saturated two-factor expansion of
the output log-odds

```
ℓ(u,v) = a + b·u + c·v + d·u·v
```

- `u ∈ {−1,+1}` — request semantics (quarter / annual)
- `v ∈ {−1,+1}` — schema mapping direction (which symbol means which)
- `a` — fixed symbol preference
- `b` — request main effect
- `c` — schema main effect
- `d` — the request×mapping interaction (the "correct binding" signal)

**Proposition 1:** all four request–mapping combinations are correct iff
`d > B`, where `B = max_{u,v}{−a·u·v − b·v − c·u}` (equivalently, the
conservative sufficient condition `d > |a|+|b|+|c|`).

The load-bearing claim is that **`d` can be positive yet the model still
chooses the wrong parameter** — because a fixed symbol preference `a` (or
another main effect) dominates. The toy example `a=2, b=c=0, d=1` gives
`ℓ = 2 + u·v > 0` always, so the model always picks symbol A and is wrong on
two of the four balanced combinations.

## Design

### Task construction (the u×v grid)

For each base task (fixed stock, field, data snapshot), build the full 2×2:

| request `u` | mapping `v` | correct output `z* = u·v` |
|---|---|---|
| quarter (+1) | A=quarter (+1) | A (+1) |
| quarter (+1) | A=annual (−1) | B (−1) |
| annual (−1) | A=quarter (+1) | B (−1) |
| annual (−1) | A=annual (−1) | A (+1) |

The two candidates are `a_+` and `a_-` — identical calls except the target
parameter symbol. We measure `ℓ(u,v) = log P(a_+ | I_u, S_v) / P(a_- | I_u, S_v)`.

**Neutral symbol pairs.** Use several symbol pairs (A/B, X/Y, Q/A, …) balanced
for position, token length, and example form, so `a` (symbol preference) is not
confounded with one specific pair. The mapping `v` is randomized across pairs.

**Native + adapter interface.** Keep the native `quarter`/`fy` interface AND a
symbol-adapter interface (A/B), and confirm the backend operation is strictly
equivalent. This is the §2 equivariance check — a mechanism discriminator, not
a claim that the real API uses A/B.

### Getting the log-probs (transformers, exact)

**Decision (2026-09-22): use transformers, not ollama.** We first tried ollama's
`/api/generate` with `logprobs`/`top_logprobs`. Two problems forced the switch:

1. **Instruct models don't emit a bare token at an arbitrary position.** With a
   prompt ending at the parameter position, qwen2.5:7b-instruct keeps generating
   natural language ("The", "Call", ...) instead of the parameter value. We are
   not sampling — we only need the distribution at that position — but ollama
   only exposes the top-N, and the candidate can fall out of the top-20.
2. **top_logprobs caps at 20** (`top_logprobs must be between 0 and 20`), so a
   low-probability candidate (e.g. symbol B when the model strongly prefers A)
   is unmeasurable.

Transformers gives the **exact full-vocab logits** at the final position
(`model(**ids).logits[0, -1, :]`), so every candidate is measured exactly
regardless of rank. This is also the environment Stage C (activation
intervention) needs, so the setup is reused.

**Environment on luyao4:** `kolrl` conda env has torch 2.9.1+cu128, CUDA
available, transformers 5.3.0, accelerate 1.15.0. GPU is an RTX 5080 (16GB,
idle). Qwen2.5-7B-Instruct weights (~15GB bf16) downloaded to the HF cache.
Model loaded with `torch_dtype=torch.bfloat16, device_map="auto"` to fit 16GB.

**Candidate tokens are single-token** (A/B/X/Y/Q/L/H), so the log-prob is
exact. The native interface's `quarter`/`fy` are multi-token; there we take the
first-token log-prob as an approximation, which is acceptable because the
native interface only measures request understanding (b), not binding (d).

### Computing the coefficients

Per task, from the four `ℓ(u,v)` values, recover (exact, saturated):

```
a = ¼ Σ ℓ(u,v)      b = ¼ Σ u·ℓ(u,v)
c = ¼ Σ v·ℓ(u,v)    d = ¼ Σ u·v·ℓ(u,v)
```

Then compute the four margins `M(u,v) = u·v·ℓ(u,v)` and `B`.

**Report per-task distributions**, not pooled averages. Averaging logits across
tasks before computing errors hides task heterogeneity; averaging log-odds is
not the log-odds of the average probability. Report task-level uncertainty and
keep a held-out set of request templates / symbol pairs.

## Pre-registered verdicts

Write these BEFORE running (they are the decision rules, not post-hoc):

- **V1 (binding can dominate):** across tasks, `d > B` holds for a
  substantial fraction (pre-register threshold, e.g. ≥ 60% of tasks) → the
  correct binding signal dominates parameter choice in those tasks.
- **V2 (main effects can dominate):** there exist tasks where `d > 0` but
  `d ≤ B` (i.e. the model is wrong on ≥1 of the 4 combinations despite a
  positive interaction) → the toy example is realized: "positive interaction
  ≠ correct parameter". This is the load-bearing claim.
- **V3 (symbol preference is real):** `a ≠ 0` across tasks (fixed symbol
  preference exists), and re-encoding the symbols (v flip) changes which
  combinations fail, consistent with `a` being a symbol preference rather than
  a request-understanding failure.
- **V4 (native vs adapter):** the native `quarter`/`fy` interface and the
  symbol-adapter interface give the same qualitative result (backend
  equivalence holds). If the adapter introduces a different difficulty, that
  is a confound to report, not to hide.

**Stopping / narrowing conditions** (from the theory §8): if the re-encoding
effect is mostly adapter-novelty, or the native errors are mostly
request-understanding failures, or the margin is already large and errors are
only sampling noise — the binding hypothesis is not supported and we say so.

## Result (2026-09-22, qwen2.5:7b-instruct, 50 task-units)

**Native interface (request understanding, b main effect):** all 10 tasks have
`b > 0` — the model correctly reads "quarter vs annual" from the request.
Request understanding is NOT the failure point.

**Adapter interface (binding, full a,b,c,d), 40 units:**

| verdict | count | share |
|---|---|---|
| V1: d > B (binding dominates) | 4/40 | 10% |
| V2: d > 0 but wrong (pos-wrong) | 24/40 | 60% |
| V3: symbol preference \|a\| > 0.5 | 37/40 | 92% |

Key observations:
- **Binding almost never dominates** (V1 10%). Only 4/40, all in neutral tasks
  on the Q-A symbol pair. Zero financial tasks.
- **Symbol preference is overwhelming** (V3 92%). `|a|` is 5.5–9.9 in financial
  tasks, smaller in neutral. Directly supports the theory's core claim: a
  non-binding output preference overwhelms the correct binding signal.
- **"Positive interaction but still wrong" is common** (V2 60%). 24/40 units
  have `d > 0` but `d <= B` — the toy example (a=2,b=c=0,d=1) realized: the
  model has a correct-direction binding signal but it is overwhelmed.
- **Financial vs neutral:** financial tasks have strong symbol preference
  (a~6-9) and binding almost never dominates; neutral tasks have weaker
  preference and occasional binding dominance (Q-A pair).

## Cross-model replication (2026-09-22, llama3.1:8b, 50 task-units)

| verdict | qwen2.5:7b | llama3.1:8b |
|---|---|---|
| V1: d > B (binding dominates) | 10% | 32% |
| V2: d > 0 but wrong (pos-wrong) | 60% | 38% |
| V3: symbol preference \|a\| > 0.5 | 92% | 60% |

**Replication holds, with a model difference.** llama3.1 has stronger binding
(V1 32% vs 10%) and weaker symbol preference (V3 60% vs 92%), but the core
conclusion is consistent across both: binding does NOT always dominate (V1
32% at most), symbol preference is still significant (V3 60%), and "positive
interaction but still wrong" still occurs (V2 38%). Both models support the
mechanism layer: binding is not always sufficient; a non-binding preference
can overwhelm it.

Note: llama3.1's Q-A symbol pair is almost always DOM (d>B) — a symbol-pair
effect, not a task effect. gemma3:12b cannot run stage A (no transformers
weights; gated repo).

## KNOWN CONFOUND (must address before this is publishable)

The `a` values are suspiciously large (financial 5.5–9.9) while `d` is small
(±4). In the smoke test, `p_correct` was −15 to −25 for both candidates — the
model is very unlikely to emit ANY symbol at the parameter position; it prefers
to continue generating natural language after "should be: ". So `a` may be
contaminated by a **position effect** ("the model doesn't want to output a bare
symbol here"), not purely symbol preference.

This affects V1/V2 interpretation: "d overwhelmed by a" may partly be "the
model doesn't want to output a symbol at this position", not "symbol preference
overwhelms binding". This is a confound a reviewer would attack.

Mitigations to consider:
1. Change the prompt so the model naturally outputs the parameter value (e.g.
   JSON completion `{"period": "`).
2. Use more neutral tasks where the model is willing to output symbols.
3. Reframe: the model's reluctance to output the parameter at the right
   position is itself evidence of weak binding — but this must be argued
   carefully, not asserted.

## What this does NOT claim

- The four-term expansion is an identity, not a discovery (no significance
  test needed for the identity itself).
- `d > 0` does NOT imply a dedicated "binding-ID" neural mechanism.
- Behavior-level binding support does NOT locate an internal mechanism — that
  is Stage C (activation intervention, needs transformers + raw weights).
- This does not inherit any real error rate or zero-error screening guarantee.

## Cost

- Model: qwen2.5:7b (Q4, ~5GB) on luyao4, GPU currently idle (16GB).
- No API key, no OpenRouter. Ollama logprobs are free.
- Runtime: small (a few hundred forward passes). Minutes, not hours.

## Files

- `probes/stageA_binding.py` — the probe (to be written)
- `probes/stageA_binding.jsonl` — results
- this note
