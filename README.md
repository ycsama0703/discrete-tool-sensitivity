# Discrete tool-call sensitivity in LLM agents

An LLM agent calling a financial data API can substitute one discrete parameter
value for another — `period="quarter"` for `period="fy"` — and the call stays
**schema-valid**, returns HTTP 200, and produces an output that differs by
**66–72%**.

Agent-reliability work models that substitution as **quantization**: a bounded,
small error, absorbed by disturbance rejection. Quantization presumes the
discrete grid finely approximates a continuum. A semantic enum is not such a
grid — `quarter` and `fy` are different questions, not adjacent cells — so the
error model that is supposed to cover this case does not.

This repository holds the probes, data and paper framework for that finding.

## Status (2026-09-21)

An **empirical / measurement** paper, not a theory paper. Every proposition we
use has a prior owner; what is ours is the **perturbation geometry** and the
measurements under it. See `docs/paper_framework.md` §4 for the full
positioning and §2.4b for the decision-geometry result.

The load-bearing gap: there is **no real-agent end-to-end experiment** yet. The
current end-to-end probe simulates an agent with an assumed error rate.

## The finding, in three layers

0. **The mechanism (why the model fills it wrong).** An LLM can represent the
   task semantics yet fail to bind it to the tool parameter: a non-binding
   output preference (symbol preference `a`) overwhelms the correct binding
   signal (`d`). On qwen2.5:7b-instruct, binding dominates in only 10% of
   task-units while symbol preference is strong in 92%, and "positive binding
   interaction but still wrong" occurs in 60%. Request understanding is not
   the failure point (native `b>0` on all tasks). See `docs/llm_semantic_binding_theory.md`.
1. **The wrong error model, not broken continuity.** The field models an LLM's
   choice of a discrete tool/control parameter as **quantization** — a bounded,
   small error absorbed by disturbance rejection. Quantization presumes the grid
   finely approximates a continuum; a semantic enum is not such a grid, and
   `quarter → fy` moves the output by 66–72%, not by half a step. Note we do
   **not** claim discreteness breaks continuity: on a finite set every function
   is continuous, and with the discrete metric the bound is informative. The
   problem is the choice of metric and error model.
2. **Decision geometry.** Which quantity governs a flip depends on the decision:
   order decisions (top-k, pairwise) are governed by `ρ = σ_r/σ_q`, absolute
   threshold decisions by `κ = |μ_r|/σ_q`. The continuous bound reports zero for
   both. The relative/absolute distinction itself is generalizability theory
   (Cronbach et al. 1972) — we transfer it, we did not discover it.
3. **Screening.** Enumerating the discrete neighbour set drives decision error
   to 0% in simulation. Enumeration is standard since 2019; our angle is that a
   schema-defined enum makes it *exact* rather than a relaxation, with `|S| ~ 3`
   instead of the `10³¹` that made enumeration infeasible in the text setting.

## Headline numbers

| | |
|---|---|
| output jump, `period=quarter→fy` | 66–72%, 100% schema-valid |
| weak models making the substitution | llama3.1:8b 12%, qwen2.5:7b 18.75% (strong models 0%) |
| `corr(ρ, flip)` vs `corr(jump, flip)`, 48 cells | **+0.851** vs **+0.110** |
| `κ` on order decisions (must be ~0) | **−0.028** |
| `κ` on threshold decisions | **+0.908** |
| CertDR-style union bound | certifies **2/48**, while **14/48** are genuinely stable |
| enumeration screener, end-to-end sim | 12% decision error → **0%** |
| binding dominates (stage A, qwen2.5:7b) | **10%** of task-units; symbol pref 92%; pos-interaction-but-wrong 60% |
| real-agent e2e (stage D, qwen2.5:7b) | real error **27.5%**; screener: decision error **100% → 0%** |
| real-agent e2e, 3 models | qwen2.5/llama3.1/gemma3 all: real error 24.5–28%, screener **100% → 0%** |
| baseline family (stage E) | enumeration screener is the only exact method: **prec/recall 100%** vs SAFER 77/62, MC 88/94, continuous/Gecko 0 |
| active self-check (stage F, 3 models) | "why not just ask the LLM to check itself?" — L3 error localization: qwen **4.6%**, gemma 22.7%, llama 60.6% (prec 24%), vs screener **100%**; L1/L2 recall ~100% but precision collapses (llama 30%). Internal detection unreliable, external enumeration reliable |
| external validity (Daloopa) | real commercial models make discrete period errors: 5 non-grounded models **5–9%**, grounded **1.0%**; **99.4%** of errors are enumerable neighbors the screener covers |

## Layout

```
docs/
  paper_framework.md        the paper: theory, experiments, positioning, story
  references.md             every work touched, by role, with verification marks
  probe_notes/              one note per probe — result, verdict, known limits
probes/                     scripts and data together (imports and default
                            paths are same-directory; do not split them)
```

## Reproducing

No API key, no GPU, no models — everything except `run_generator_relevance.py`
is pure data analysis against the public findata endpoint.

```bash
cd probes

# the phenomenon
python build_discrete_sensitivity.py --analyze discrete_sensitivity.jsonl
python build_mixed_sensitivity_scale.py --analyze mixed_scale.jsonl

# tau -> rho: field expansion, universe expansion, the margin model
python tau_expand.py --analyze tau_expand.jsonl
python tau_universe.py --analyze
python margin_model.py

# the two results the paper leans on
python decision_geometry.py      # the order/threshold crossover
python certdr_baseline.py        # prior ranking certificate as a baseline

# the mechanism layer (stage A, needs a GPU + Qwen2.5-7B-Instruct weights)
python stageA_binding.py --out stageA_binding.jsonl
python stageA_binding.py --analyze stageA_binding_coeffs.jsonl
```

To re-collect from the API (a few minutes, no key):

```bash
python tau_expand.py --collect --out tau_expand.jsonl
python tau_universe.py --collect
```

`run_generator_relevance.py` is the only probe needing models (Ollama on the
lab box: qwen2.5:7b, llama3.1:8b, gemma3:12b).

## Reading order

1. `docs/paper_storyline.md` — the full narrative arc (discovery → theory →
   experiments → why enumeration is the only reliable detector), with the
   financial framing
2. `docs/paper_framework.md` §1–2 — the claim and the corrected theory
3. `docs/probe_notes/README_decision_geometry.md` — the crossover
4. `docs/probe_notes/README_certdr_baseline.md` — why prior certificates are a
   baseline here rather than a competitor
5. `docs/paper_framework.md` §4 — what we inherit, compare against, and rebut

## Writing discipline carried in the docs

- Never write "Lipschitz presupposes continuity" — LipsLev (ICLR 2025) defines
  Lipschitz constants over Levenshtein distance.
- Never write "certifying discrete substitutions is unexplored" or "ranking
  under discrete perturbation is unexplored" — CertDR, SAFER and ℓ₀-top-k each
  refute it directly.
- Never write "we fix CertDR" — quotienting the common mode out recovers one
  cell out of 48. Worst-case bounds are the wrong instrument here regardless.
- Claims sourced from a search summary rather than a method section we read
  ourselves are marked `○` in §4 and must be verified before citing.
