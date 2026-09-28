#!/bin/bash
# S7 full run, API models, run locally. One pipeline per model, in parallel.
cd /d/luyao4/card3-discrete-tool-sensitivity/probes
export PYTHONUTF8=1
LOG=_s7_api.log
step() { echo "[$(date +%F_%T)] $*" >> $LOG; }
pipe() {  # tag model
  local t=$1 m=$2
  step "$t calls start"
  python S7_decision_screen.py calls --backend openrouter --model $m --concurrency 12 --out S7_calls_$t.jsonl > _s7_$t.calls.log 2>&1 || { step "$t calls FAILED"; return 1; }
  step "$t calls done ($(wc -l < S7_calls_$t.jsonl)); $(grep 'API:' _s7_$t.calls.log)"
  for mode in selfcons verify; do
    python S7_decision_screen.py baseline --mode $mode --backend openrouter --model $m --concurrency 12 --calls S7_calls_$t.jsonl --out S7_base_${mode}_$t.jsonl > _s7_$t.$mode.log 2>&1 || { step "$t $mode FAILED"; return 1; }
    step "$t $mode done"
  done
  python S7_decision_screen.py baseline --mode judge --backend openrouter --model anthropic/claude-sonnet-5 --concurrency 12 --calls S7_calls_$t.jsonl --out S7_base_judge_$t.jsonl > _s7_$t.judge.log 2>&1 || { step "$t judge FAILED"; return 1; }
  step "$t judge done"
}
pipe qwen38 qwen/qwen3.8-flash &
pipe dsv41 deepseek/deepseek-v4.1-flash &
pipe sonnet5 anthropic/claude-sonnet-5 &
wait
step "API ALL DONE"
touch _s7_api.done
