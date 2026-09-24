# Stage-H probe — multi-model majority voting, and why it fails

**Status: DONE (zero extra inference).** "Why not just run three models and
take the majority vote?" is, next to self-verification, the most natural
objection to the enumeration screener. This probe answers it from the stage-F
data directly: qwen2.5:7b, llama3.1:8b and gemma3:12b were run on the SAME 400
(symbol, question) cases, so a 3-model vote is computable with no new API calls.

Script: `probes/stageH_voting_baseline.py` (asserts the three files are
row-aligned before voting; if they were not, the vote would be meaningless).

## Result: voting does not beat the best single model

| method | error rate |
|---|---|
| qwen2.5:7b alone | 27.3% |
| llama3.1:8b alone | 27.3% |
| gemma3:12b alone | 29.8% |
| **3-model majority vote** | **30.0%** (27.3% majority-agreed-wrong + 2.8% tie) |
| **enumeration screener** | **0.0%** |

Voting is *worse* than the best single model, once unresolved ties are counted
as failures (as they must be — a tie gives the agent no answer).

## Why: the errors are strongly correlated

Voting's entire premise is that errors are independent — if A is wrong, B is
probably right, so the majority rescues you. That premise fails here.

**Pairwise error correlation (phi):**

| pair | phi | both wrong | Jaccard |
|---|---|---|---|
| qwen vs llama | **+0.533** | 72 | 0.49 |
| qwen vs gemma | **+0.670** | 87 | 0.62 |
| llama vs gemma | **+0.683** | 88 | 0.63 |

**How many models are wrong per case — actual vs independence:**

| k wrong | actual | if independent |
|---|---|---|
| 0 | 245 (61.3%) | 148.7 (37.2%) |
| 1 | 38 (9.5%) | 174.4 (43.6%) |
| 2 | 52 (13.0%) | 68.0 (17.0%) |
| **3 (all wrong)** | **65 (16.2%)** | **8.8 (2.2%)** |

**All three models are wrong together 7.4x more often than independence
predicts.** And when they are wrong together they usually agree on the *same*
wrong value (typically `all`), so the majority confidently returns it.

## Why this matters for the paper

It completes a three-way argument, and all three legs point the same way:

| baseline | why it fails |
|---|---|
| **self-verification** (stage F) | depends on the very binding capability that failed |
| **majority voting** (stage H) | all models share the same binding defect, so errors correlate |
| **enumeration screener** | **depends on no model at all** — it enumerates the schema enum and recomputes |

The common structure: any detector that routes through model judgment inherits
the model's binding defect. Only an external, model-independent mechanism
escapes it. That is the paper's central practical claim, now supported from
two independent directions.

## Honest limitations

- Three models, one decision task, one parameter. The correlation magnitude is
  specific to this setup.
- All three are instruction-tuned models of similar scale (7B-12B) trained on
  overlapping public data — some error correlation is expected on those grounds
  alone. What the probe shows is that the correlation is large enough to defeat
  voting *in practice*, not that it is irreducible in principle.
- A vote over more diverse or stronger models might correlate less. Stage G
  (OpenRouter commercial models) tests exactly that.

## Files

- `probes/stageH_voting_baseline.py` — the analysis (reads stage-F outputs)
- this note
