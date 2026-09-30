# Silent defaults: LLM agents filling unstated discrete tool parameters

An LLM agent asked *"which 3 of these companies had the highest revenue?"* or *"which stocks performed best
since 2023?"* has to fill parameters the user never mentioned — `period ∈ {quarter, fy, all}` on a
fundamentals API, `adjustment ∈ {splits_only, splits_and_dividends, unadjusted}` on a price API. The call is
schema-valid, returns a plausible number, raises no error — and the downstream decision can silently change.

**Start with [`docs/HANDOFF.md`](docs/HANDOFF.md)** (status, results, working rules, how to reproduce).

## Status (2026-09-30)

Experiments complete; theory narrative settled; next step is writing. The argument, each step backed by data:

1. **Generation.** When the user does not state the parameter, models silently fill a model-specific default
   (errors ≈ 0% when stated, 56–98% when unstated; 77–99% of wrong fills on one value).
2. **Detection.** No checker that does not query the tool under the alternative values can be sound
   (a two-worlds argument). Self-verification, LLM judges, self-consistency and multi-model voting all leak.
3. **Consequence.** Whether a decision flips is set by its geometry: rankings by ρ = σ_r/σ_q, thresholds by
   κ = |μ|/σ_q (measurement-theoretic meaningfulness, plus our arctan generalization); LLM deciders follow it too.
4. **Method.** Release a decision only if it is identical under every legal value — an instance of El-Yaniv &
   Wiener's consistent selective strategy; zero leaked decision errors across 6 LLMs.
5. **Cost.** Which decisions are released depends on the data, not on the model, and is predictable from (ρ, κ).
6. **Generalization.** A second financial parameter (price adjustment, entity-specific ρ-type) reproduces it.

## Headline numbers

| | |
|---|---|
| decision error, unstated parameter (6 LLMs) | `period`: 19–81% of decisions; price `adjustment`: 45–51% |
| ENUM screener | 0 leaked decision errors on every model, both parameters; releases 4–37% |
| strong LLM judge (gpt-6-luna) | `period`: misses up to 18 per model; `adjustment`: releases 98, 46 wrong (pooled) |
| multi-model voting, `adjustment` | releases 18 decisions, 17 wrong (models agree when they are wrong together) |
| release decision across 6 models | identical on 187/192 instances; all 5 exceptions are mixed-parameter calls |
| (ρ, κ) predicts release | AUC 0.83–0.87 (`period`), 0.945 (`adjustment`); output-jump magnitude ≈ chance |
| LLM makes the decision itself | flips agree with the code decision on 98–99% of instances (gpt-6-luna, deepseek) |

## Layout

```
docs/
  HANDOFF.md                 start here
  EXPERIMENT_REGISTRY.md     every experiment: ID, result, status, paper section (authoritative)
  paper_storyline.md         the paper's argument (v2): notation, LLM mechanisms, anchors, evidence
  theory_*.md                problem roots, screener guarantees, narrative table
  METHOD_EVAL_PROTOCOL.md    S7 / S7-B protocols;  S10_ADJUSTMENT_PROTOCOL.md  S10
  probe_notes/               one note per early probe (history; the registry supersedes)
probes/                      scripts and data together (same-directory imports)
```

## Reproducing

Evaluation needs no GPU and no API key (all calls are stored):

```bash
cd probes
python S10_adjustment.py summary --tags qwen gemma llama dsv41 qwen38 luna
python S7_H3_coverage.py
python S7B_llm_decision.py eval --tag luna
```

New model calls need an OpenRouter key in `.env` (API models) or a GPU host (local models); see `docs/HANDOFF.md` §6.

## Writing discipline

- Known results are written as "an instance of X" and cited (CSS, global robustness, meaningfulness, two-point arguments).
- Never write "`all` is harmless" — under findata's first-record rule it happens to return quarterly data.
- "The user stated the parameter" is a control condition, not the scenario.
- Cite only what we read in the method section (marked ✅); ◐/○ entries are background or must be verified first.
