# Stage-C probe — activation intervention: does the binding signal control parameter choice?

**Status: DESIGN (not yet run).** This is the causal-evidence layer of the
mechanism story (`docs/llm_semantic_binding_theory.md` §5). Stage A showed
behaviorally that binding rarely dominates (d > B in 10%). Stage C asks the
causal question: is there a layer whose activation carries the binding signal
and controls parameter choice by the relation uv?

## What this tests

Theory §5: with a single-token two-candidate readout, the output log-odds is

```
ell(u,v) = w^T h(u,v) + beta
```

and the state h has the same saturated expansion `h = h0 + u·hu + v·hv + uv·huv`.
The binding interaction is `d = w^T huv`. The causal claim is that some
intermediate layer's activation, when patched, changes parameter preference
**by the relation uv** — not just by degrading output generally.

## Design

### Setup

- Model: Qwen2.5-7B-Instruct (transformers, bf16, device_map="auto"), same as
  Stage A. Reuse `stageA_binding.py`'s task/prompt construction and logits read.
- Task: start with ONE task (e.g. fin_aapl_rev, adapter A/B) to keep it cheap,
  then expand if the signal is found.

### Step 1 — locate the binding layer (causal tracing)

For the 4 (u,v) inputs of one task:
1. Run each input, record the residual-stream activation at every layer
   (hook `model.model.layers[i]` output).
2. **Patching**: for a target input T, replace layer L's activation with the
   activation from a source input S (same position), and measure how the
   parameter log-odds ell changes.
3. **Which patch moves ell toward S's value?** If patching layer L from S into
   T makes T's ell approach S's ell, then L carries the information that
   distinguishes them. The binding signal lives where patching changes ell by
   the uv relation.

### Step 2 — directionality (the load-bearing check)

The binding claim requires that the patch changes ell **by the relation uv**,
not just by degrading output. Concretely:
- Patch the binding layer with the **correct-direction** activation → ell
  should move toward the correct parameter.
- Patch with the **wrong-direction** activation → ell should move toward the
  wrong parameter.
- If patching only degrades ell (both directions hurt), the layer carries
  general task information, not a binding signal.

### Step 3 — controls (from theory §5)

- **Random position**: patch a random position, not the parameter position.
- **Unrelated semantics**: patch with an activation from an unrelated task.
- **Equal-strength random vector**: patch with a random vector of the same
  norm, to rule out "any perturbation changes ell".
- **Bidirectional + destroy/restore**: patching to the wrong direction should
  destroy the correct preference; patching back should restore it. This
  mutual confirmation prevents mistaking general generation damage for a
  specific mechanism.

## Pre-registered verdicts

- **C1 (binding layer exists):** there is a layer L where patching from S into
  T moves ell toward S's value, and this is specific to L (neighboring layers
  don't do it).
- **C2 (directionality):** correct-direction patch moves ell toward correct,
  wrong-direction patch moves it toward wrong — not just degradation.
- **C3 (specificity):** random-position / unrelated-semantics / random-vector
  controls do NOT reproduce the effect.
- **C4 (destroy/restore):** wrong-direction patch destroys the correct
  preference; restoring the original activation restores it.

**Stopping / narrowing** (theory §8): if patching only degrades output
generally (no directionality), or the effect is not layer-specific, or the
controls reproduce it — the binding-layer hypothesis is not supported and we
say so. The paper then rests on the behavioral layer (Stage A) + consequence
layer, which still stand.

## Result (2026-09-22, qwen2.5:7b-instruct, fin_aapl_rev, adapter A/B)

**Patch effect by layer** (mean |delta ell| over 12 patches per layer):

| layers | mean |delta| | reading |
|---|---|---|---|
| 0–16 | < 0.33 | early layers carry no u/v-discriminating signal |
| 17–18 | 0.65–1.03 | onset |
| 19–25 | 5.27–10.04 | late layers strongly change parameter preference |

The binding signal, if present, lives in the late layers (19–25), near the
output. This matches intuition: early layers process general semantics, late
layers bind u/v to the parameter choice.

**Random-vector control** (equal-norm random vector vs real patch, late layers):

| target | layer | real delta | random delta |
|---|---|---|---|
| u=-1,v=-1 (base +5.31) | L19 | −5.56 | −3.94 |
| | L20 | −6.69 | −3.31 |
| | L21 | −7.88 | −2.31 |
| u=+1,v+1 (base +9.94) | L19 | −14.56 | −7.62 |
| | L20 | −17.75 | −7.06 |
| | L21 | −18.44 | −6.44 |

**Reading:** random patches DO change ell (general disruption component), but
real patches exceed random by ~2–3× at late layers (e.g. L20: −17.75 vs −7.06).
So there IS a binding signal in the late layers beyond general disruption —
but it is mixed with a large disruption component, and the direction is not
clean (some patches move ell toward the source, some away).

## Verdict: PARTIAL

- **C1 (binding layer exists):** PARTIAL. Late layers (19–25) strongly change
  ell, and real patches exceed random controls by 2–3×. But the effect is not
  layer-sharp (18–25 all show it) and is contaminated by disruption.
- **C2 (directionality):** NOT CLEAN. Some patches move ell toward the source,
  some away. Not a clean "by the relation uv" transfer.
- **C3 (specificity):** PARTIAL. Random-vector control shows real > random, but
  random itself has a large effect (disruption), so specificity is incomplete.
- **C4 (destroy/restore):** not yet run.

**Honest conclusion:** the late layers carry a binding signal (real > random),
but it is entangled with general disruption and the direction is not clean.
This is consistent with the theory's caution (theory §5: `d = w^T huv != ||huv||`;
single patch success is not full causal identification). The mechanism layer
rests primarily on the behavioral result (Stage A); Stage C gives suggestive
but not clean causal evidence.

## What this does NOT claim

- Finding a layer whose patch changes ell does NOT prove a dedicated
  "binding-ID" neural circuit (theory §5: `d = w^T huv != ||huv||`).
- Single patch success is not full causal identification (theory §5).
- This is one model (qwen2.5:7b-instruct); external validity is limited.

## Cost

- Same model/env as Stage A (already set up on luyao4).
- Causal tracing over 28 layers × 4 inputs × several patch targets — a few
  hundred forward passes. Minutes, not hours.
- No API key, no new downloads.

## Files

- `probes/stageC_patch.py` — the probe (to be written)
- `probes/stageC_patch.jsonl` — results
- this note
