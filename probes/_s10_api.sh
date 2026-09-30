#!/bin/bash
# S10 API models, run locally; one pipeline per model in parallel. Judge runs afterwards.
cd /d/luyao4/card3-discrete-tool-sensitivity/probes
export PYTHONUTF8=1
LOG=_s10_api.log
step() { echo "[$(date +'%F %T')] $*" >> $LOG; }
pipe() {  # tag model
  python S10_adjustment.py calls --backend openrouter --model $2 --out S10_calls_$1.jsonl --resume --concurrency 8 > _s10_$1.calls.log 2>&1 || { step "$1 calls FAILED: $(tail -1 _s10_$1.calls.log)"; return 1; }
  step "$1 calls done ($(wc -l < S10_calls_$1.jsonl))"
  for m in selfcons verify; do
    python S10_adjustment.py baseline --mode $m --backend openrouter --model $2 --calls S10_calls_$1.jsonl --out S10_base_${m}_$1.jsonl --resume --concurrency 8 > _s10_$1.$m.log 2>&1 || { step "$1 $m FAILED: $(tail -1 _s10_$1.$m.log)"; return 1; }
    step "$1 $m done ($(wc -l < S10_base_${m}_$1.jsonl))"
  done
}
pipe luna openai/gpt-6-luna &
pipe dsv41 deepseek/deepseek-v4.1-flash &
pipe qwen38 qwen/qwen3.8-flash &
wait
step "API ALL DONE"
