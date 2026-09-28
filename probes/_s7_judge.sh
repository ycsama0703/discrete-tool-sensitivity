#!/bin/bash
# S7 commercial-judge baseline with openai/gpt-6-luna (user, 2026-09-27: sonnet
# is too expensive for this role). Runs after the API resume has finished.
# Local models' calls (qwen/gemma/llama) get judged later, once pulled from luyao4.
cd /d/luyao4/card3-discrete-tool-sensitivity/probes
export PYTHONUTF8=1
LOG=_s7_judge.log
step() { echo "[$(date +%F_%T)] $*" >> $LOG; }
while [ ! -f _s7_api_resume.done ]; do sleep 60; done
for t in dsv41 qwen38; do
  python S7_decision_screen.py baseline --mode judge --backend openrouter --model openai/gpt-6-luna \
      --concurrency 12 --resume --calls S7_calls_$t.jsonl --out S7_base_judge_$t.jsonl > _s7_$t.judge.log 2>&1 \
      || { step "$t judge STOPPED: $(tail -1 _s7_$t.judge.log)"; exit 1; }
  step "$t judge done"
done
touch _s7_judge.done
step "JUDGE DONE"
