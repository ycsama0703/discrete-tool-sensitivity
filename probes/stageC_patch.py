"""
Stage-C probe: activation intervention — does the binding signal control
parameter choice?

Tests the causal claim of docs/llm_semantic_binding_theory.md §5: is there a
layer whose activation carries the binding signal and controls parameter
choice by the relation uv?

Method: causal tracing via activation patching. For the 4 (u,v) inputs of a
task, record each layer's activation, then patch a source input's activation
into a target input at each layer and measure how the parameter log-odds ell
changes. The binding layer is where patching moves ell by the uv relation.

Usage (on luyao4, kolrl env):
    python stageC_patch.py --out stageC_patch.jsonl
    python stageC_patch.py --analyze stageC_patch.jsonl
"""

import argparse
import json
import sys

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

MODEL = "Qwen/Qwen2.5-7B-Instruct"
# GPU layers only (device_map="auto" puts 26,27,norm,lm_head on CPU)
GPU_LAYERS = list(range(26))

import stageA_binding as A  # reuse task/prompt construction


class PatchModel:
    def __init__(self, model=MODEL):
        self.tok = AutoTokenizer.from_pretrained(model)
        self.model = AutoModelForCausalLM.from_pretrained(
            model, torch_dtype=torch.bfloat16, device_map="auto")
        self.model.eval()

    def activations(self, prompt):
        """Return {layer: hidden_state} for all GPU layers at the final position."""
        ids = self.tok(prompt, return_tensors="pt")
        ids = {k: v.to(self.model.device) for k, v in ids.items()}
        acts = {}
        handles = []
        def make_hook(layer_idx):
            def hook(module, args, output):
                # output is a Tensor [batch, seq, hidden]
                acts[layer_idx] = output[0, -1, :].detach()  # final pos, [hidden]
            return hook
        for li in GPU_LAYERS:
            handles.append(self.model.model.layers[li].register_forward_hook(
                make_hook(li)))
        with torch.no_grad():
            self.model(**ids)
        for h in handles:
            h.remove()
        return acts

    def logprob_patched(self, prompt, token_str, patch_layer, patch_act):
        """log P(token_str | prompt) with layer patch_layer's activation
        replaced by patch_act (a [hidden] tensor). patch_layer=-1 -> no patch."""
        ids = self.tok(prompt, return_tensors="pt")
        ids = {k: v.to(self.model.device) for k, v in ids.items()}
        h = None
        if patch_layer >= 0:
            patch_act = patch_act.to(self.model.device)
            def make_hook(layer_idx):
                def hook(module, args, output):
                    hh = output.clone()
                    hh[0, -1, :] = patch_act
                    return hh
                return hook
            h = self.model.model.layers[patch_layer].register_forward_hook(
                make_hook(patch_layer))
        with torch.no_grad():
            out = self.model(**ids)
        if h is not None:
            h.remove()
        logits = out.logits[0, -1, :]
        logp = torch.log_softmax(logits, dim=-1)
        tids = self.tok(token_str, add_special_tokens=False)["input_ids"]
        return logp[tids[0]].item()


def run_task(pm, task, symbols):
    """Causal tracing for one task. Returns rows."""
    sym_q, sym_a = symbols
    # build the 4 (u,v) prompts and their activations
    cells = {}
    for u in (+1, -1):
        for v in (+1, -1):
            prompt, correct = A.build_prompt(task, u, v, symbols, native=False)
            acts = pm.activations(prompt)
            cells[(u, v)] = dict(prompt=prompt, correct=correct, acts=acts)
    # baseline ell for each cell (no patch)
    rows = []
    for (u, v), c in cells.items():
        ell = pm.logprob_patched(c["prompt"], sym_q, -1, None) - \
              pm.logprob_patched(c["prompt"], sym_a, -1, None)
        rows.append(dict(task=task[0], symbols="-".join(symbols), u=u, v=v,
                         correct=c["correct"], kind="baseline", ell=ell))
    # patching: for each target cell, patch each source cell's activation at
    # each layer, measure ell
    for (tu, tv), tc in cells.items():
        for (su, sv), sc in cells.items():
            if (su, sv) == (tu, tv):
                continue
            for li in GPU_LAYERS:
                ell = pm.logprob_patched(tc["prompt"], sym_q, li,
                                         sc["acts"][li]) - \
                      pm.logprob_patched(tc["prompt"], sym_a, li,
                                         sc["acts"][li])
                rows.append(dict(task=task[0], symbols="-".join(symbols),
                                 tu=tu, tv=tv, su=su, sv=sv, layer=li,
                                 kind="patch", ell=ell))
    return rows


def cmd_run(a):
    print(f"loading {a.model} ...", flush=True)
    pm = PatchModel(a.model)
    print("loaded\n", flush=True)
    rows = []
    # start with one financial task, one symbol pair
    for task in [A.FINANCIAL[0]]:
        rows += run_task(pm, task, ("A", "B"))
        print(f"  {task[0]} done ({len(rows)} rows)", flush=True)
    with open(a.out, "w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"\nwrote {a.out} ({len(rows)} rows)")


def cmd_analyze(a):
    rows = [json.loads(l) for l in open(a.out, encoding="utf-8")]
    base = {(r["u"], r["v"]): r["ell"] for r in rows if r["kind"] == "baseline"}
    print("baseline ell per (u,v):")
    for (u, v), e in sorted(base.items()):
        print(f"  u={u:+d} v={v:+d}: ell={e:.3f}")
    # for each patch, how much does ell move toward the source?
    print("\n=== patch effect by layer ===")
    # aggregate: for each layer, mean |delta ell| when patched
    from collections import defaultdict
    by_layer = defaultdict(list)
    for r in rows:
        if r["kind"] != "patch":
            continue
        t_ell = base[(r["tu"], r["tv"])]
        delta = r["ell"] - t_ell
        by_layer[r["layer"]].append(abs(delta))
    print(f"{'layer':>6} {'mean|delta|':>12} {'n':>4}")
    for li in sorted(by_layer):
        d = by_layer[li]
        print(f"{li:>6} {sum(d)/len(d):>12.3f} {len(d):>4}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="stageC_patch.jsonl")
    ap.add_argument("--analyze", metavar="JSONL")
    ap.add_argument("--model", default=MODEL,
                    help="HF model id (default Qwen/Qwen2.5-7B-Instruct)")
    a = ap.parse_args()
    if a.analyze:
        a.out = a.analyze
        cmd_analyze(a)
    else:
        cmd_run(a)


if __name__ == "__main__":
    main()
