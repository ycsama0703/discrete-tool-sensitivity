#!/bin/bash
# S7 API models: resume after the 2026-09-27 credit exhaustion.
# Calls: --resume keeps every successful call and redoes only the 402s.
# Baselines: the previous baseline files were invalid (moved to _invalid_402/),
# so they are run fresh. Every step aborts immediately on a 402.
cd /d/luyao4/card3-discrete-tool-sensitivity/probes
export PYTHONUTF8=1
LOG=_s7_api_resume.log
step() { echo "[$(date +%F_%T)] $*" >> $LOG; }
pipe() {  # tag model
  local t=$1 m=$2
  python S7_decision_screen.py calls --backend openrouter --model $m --concurrency 12 \
      --resume --out S7_calls_$t.jsonl > _s7_$t.calls.log 2>&1 || { step "$t calls STOPPED: $(tail -1 _s7_$t.calls.log)"; return 1; }
  step "$t calls done"
  for mode in selfcons verify; do
    python S7_decision_screen.py baseline --mode $mode --backend openrouter --model $m --concurrency 12 \
        --resume --calls S7_calls_$t.jsonl --out S7_base_${mode}_$t.jsonl > _s7_$t.$mode.log 2>&1 || { step "$t $mode STOPPED"; return 1; }
    step "$t $mode done"
  done
  # strong-judge baseline uses claude-sonnet-5: deferred with sonnet (budget, 2026-09-27)
}
# sequential this time: a credit problem stops one model, not three at once.
# sonnet5 (as tested model AND as judge) deferred until budget allows.
pipe dsv41 deepseek/deepseek-v4.1-flash
pipe qwen38 qwen/qwen3.8-flash
step "API RESUME FINISHED"
touch _s7_api_resume.done
