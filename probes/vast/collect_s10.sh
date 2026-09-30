#!/bin/bash
# Collect -> verify -> destroy for an S10 vast instance whose launcher was stopped.
#   bash collect_s10.sh <instance_id> <ssh_host> <ssh_port>
# Destroys ONLY if every expected file is copied and has the expected line count.
set -u
ID=$1; HOST=$2; PORT=$3
HERE=$(cd "$(dirname "$0")" && pwd); DEST=$HERE/..
SSH="C:/Windows/System32/OpenSSH/ssh.exe"; SCP="C:/Windows/System32/OpenSSH/scp.exe"
export PYTHONUTF8=1
say() { echo "[$(date +%F_%T)] $*"; }
S=$("$SSH" -o ConnectTimeout=20 -p "$PORT" "root@$HOST" 'test -f /root/S10_DONE && echo DONE || (test -f /root/S10_FAILED && echo FAILED || echo RUN)' 2>/dev/null | grep -E "DONE|FAILED|RUN")
[ "$S" = "DONE" ] || { say "instance not done ($S) - nothing collected"; exit 2; }
for f in S10_calls_llama.jsonl S10_base_selfcons_llama.jsonl S10_base_verify_llama.jsonl; do
  "$SCP" -q -P "$PORT" "root@$HOST:/root/repo/probes/$f" "$DEST/$f" || { say "copy failed: $f - instance left up"; exit 3; }
done
"$SCP" -q -P "$PORT" "root@$HOST:/root/s10_llama.log" "$DEST/_s10_vast_llama.log"
ok=1
n=$(wc -l < "$DEST/S10_calls_llama.jsonl"); [ "$n" -eq 960 ] || { say "calls has $n lines, expected 960"; ok=0; }
for f in S10_base_selfcons_llama S10_base_verify_llama; do
  n=$(wc -l < "$DEST/$f.jsonl"); [ "$n" -eq 48 ] || { say "$f has $n lines, expected 48"; ok=0; }
done
[ $ok -eq 1 ] || { say "verification failed - instance $ID left up"; exit 4; }
echo y | vastai destroy instance "$ID" > /dev/null && say "collected and verified; instance $ID destroyed"
