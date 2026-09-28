#!/bin/bash
# S7 llama continuation on a rented vast.ai GPU. Passed to `vastai create
# instance --onstart`, so it runs by itself when the instance boots.
#
# Does, in order, and stops at the first failure (writes $ROOT/S7_FAILED):
#   1. download the repo at a pinned commit (python only: the image may lack git)
#   2. pip install the exact versions used on luyao4
#   3. download llama at the same revision as luyao4's cache
#   4. resume llama calls (FIN_HEALTH from its partial file, then the rest)
#   5. llama baselines: self-consistency (k=5) and self-verification
#   6. write $ROOT/S7_DONE
#
# Environment overrides (used for the rehearsal on luyao4):
#   ROOT      working root              default /root
#   PY        python interpreter        default python
#   SKIP_PIP  1 = do not pip install    default 0
#   MODEL     HF model id               default the llama below
#   LIMIT     cap new items per step    default empty (no cap; rehearsal only)

ROOT=${ROOT:-/root}
PY=${PY:-python}
MODEL=${MODEL:-NousResearch/Meta-Llama-3.1-8B-Instruct}
REV=${REV:-d10aef7999a2b5ba950ab3974312feeedbfe0b77}   # = luyao4 HF cache snapshot
COMMIT=${S7_COMMIT:?set S7_COMMIT to the pushed commit}
REPO_URL=https://github.com/ycsama0703/discrete-tool-sensitivity
LIM=${LIMIT:+--limit $LIMIT}

mkdir -p "$ROOT"
LOG=$ROOT/s7_llama.log
exec >> "$LOG" 2>&1
step() { echo "[$(date -u +%F_%T)] $*"; }
fail() { step "FAILED: $*"; touch "$ROOT/S7_FAILED"; exit 1; }
rm -f "$ROOT/S7_DONE" "$ROOT/S7_FAILED"

step "boot"
nvidia-smi --query-gpu=name,memory.total --format=csv,noheader || fail "no GPU visible"

# 1. code at a pinned commit
if [ ! -d "$ROOT/repo" ]; then
  $PY - "$REPO_URL/archive/$COMMIT.tar.gz" "$ROOT" <<'PYEOF' || fail "repo download"
import io, os, sys, tarfile, urllib.request
url, root = sys.argv[1], sys.argv[2]
data = urllib.request.urlopen(url, timeout=120).read()
with tarfile.open(fileobj=io.BytesIO(data)) as t:
    top = t.getnames()[0].split("/")[0]
    t.extractall(root)
os.rename(os.path.join(root, top), os.path.join(root, "repo"))
PYEOF
fi
step "repo ready at commit $COMMIT"

# 2. environment identical to luyao4 (torch 2.9.1+cu128 comes with the image)
if [ "${SKIP_PIP:-0}" != "1" ]; then
  $PY -m pip install -q transformers==5.3.0 accelerate==1.15.0 tokenizers==0.22.2 \
      safetensors==0.7.0 huggingface_hub hf_transfer || fail "pip install"
fi
$PY -c "import torch, transformers
assert torch.cuda.is_available(), 'no cuda'
assert torch.cuda.is_bf16_supported(), 'no bf16'
print('torch', torch.__version__, '| transformers', transformers.__version__, '|', torch.cuda.get_device_name(0))" \
  || fail "environment check"

# 3. model weights, same revision as luyao4
HF_HUB_ENABLE_HF_TRANSFER=1 $PY -c "
from huggingface_hub import snapshot_download
print(snapshot_download('$MODEL', revision='$REV', allow_patterns=['*.json', '*.safetensors']))" \
  || fail "model download"
step "model ready"

cd "$ROOT/repo/probes" || fail "no probes dir"

# 4. calls. FIN_HEALTH resumes from the 663-line partial file shipped in the repo.
for U in FIN_HEALTH ENERGY_STAPLES CONSUMER; do
  $PY S7_decision_screen.py calls --universe $U --backend transformers --model "$MODEL" \
      --resume $LIM --out S7_calls_llama_$U.jsonl || fail "calls $U"
  step "calls $U: $(wc -l < S7_calls_llama_$U.jsonl) lines"
done
cat S7_calls_llama_TECH.jsonl S7_calls_llama_FIN_HEALTH.jsonl \
    S7_calls_llama_ENERGY_STAPLES.jsonl S7_calls_llama_CONSUMER.jsonl > S7_calls_llama.jsonl
step "calls combined: $(wc -l < S7_calls_llama.jsonl) lines"

# 5. baselines
for mode in selfcons verify; do
  $PY S7_decision_screen.py baseline --mode $mode --backend transformers --model "$MODEL" \
      --resume $LIM --calls S7_calls_llama.jsonl --out S7_base_${mode}_llama.jsonl || fail "baseline $mode"
  step "baseline $mode: $(wc -l < S7_base_${mode}_llama.jsonl) lines"
done

touch "$ROOT/S7_DONE"
step "ALL DONE"
