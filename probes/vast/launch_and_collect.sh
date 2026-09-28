#!/bin/bash
# Rent -> watch -> collect -> destroy, for the S7 llama continuation.
# Run locally (Git Bash). Needs the vastai CLI and the local ed25519 key,
# which is registered on the vast account.
#
#   bash launch_and_collect.sh <offer_id> <commit>
#
# Destroys the instance ONLY after the results have been copied back and each
# expected file has been verified; on failure it leaves the instance up (so the
# log can be read) and says so.

set -u
OFFER=${1:?offer id}
COMMIT=${2:?pushed commit}
IMAGE=pytorch/pytorch:2.9.1-cuda12.8-cudnn9-runtime
HERE=$(cd "$(dirname "$0")" && pwd)
DEST=$HERE/..                                    # probes/
SSH="C:/Windows/System32/OpenSSH/ssh.exe"       # sees the Windows ssh-agent
SCP="C:/Windows/System32/OpenSSH/scp.exe"
export PYTHONUTF8=1
say() { echo "[$(date +%F_%T)] $*"; }

# A three-line onstart: set the commit explicitly (not relying on -e env vars
# reaching the onstart in ssh mode), fetch the pinned onstart.sh from GitHub
# (the exact file the luyao4 rehearsal ran), and start it in the background so
# the container's own startup is never blocked.
BOOT="export S7_COMMIT=$COMMIT
python -c \"import urllib.request; open('/root/s7_body.sh','wb').write(urllib.request.urlopen('https://raw.githubusercontent.com/ycsama0703/discrete-tool-sensitivity/$COMMIT/probes/vast/onstart.sh', timeout=60).read())\"
nohup bash /root/s7_body.sh > /root/s7_boot.out 2>&1 &"
ID=$(vastai create instance "$OFFER" --image "$IMAGE" --disk 60 --ssh --direct \
      --onstart-cmd "$BOOT" --raw \
      | python -c "import sys,json; print(json.load(sys.stdin)['new_contract'])") \
  || { say "create failed"; exit 1; }
say "instance $ID created"
echo "$ID" > "$HERE/.instance_id"

destroy() { echo y | vastai destroy instance "$ID" > /dev/null && say "instance $ID destroyed"; }

# wait for ssh details; a host whose docker daemon errors (seen: broken registry
# proxy), whose status stops changing for 20 min, or that takes >60 min is
# abandoned - nothing has run yet, so destroy it. (A flat 15-min cap killed a
# healthy host mid image-extract: the layer unpack alone can take >5 min.)
T0=$(date +%s); TCHG=$T0; LAST=
while :; do
  read -r HOST PORT STATUS BAD MSG < <(vastai show instance "$ID" --raw | python -c "
import sys,json,hashlib; d=json.load(sys.stdin); m=d.get('status_msg') or ''
print(d.get('ssh_host'), d.get('ssh_port'), d.get('actual_status'), int('Error response from daemon' in m), hashlib.md5(m.encode()).hexdigest())")
  [ "$STATUS" = "running" ] && [ "$HOST" != "None" ] && break
  NOW=$(date +%s); [ "$MSG" != "$LAST" ] && { LAST=$MSG; TCHG=$NOW; }
  if [ "$BAD" = "1" ] || [ $(( NOW - TCHG )) -gt 1800 ] || [ $(( NOW - T0 )) -gt 3600 ]; then
    say "host failed to start the image (daemon error / stalled 30 min / >60 min) - abandoning"
    vastai logs "$ID" --tail 40 > "$HERE/_boot_fail_$ID.log" 2>&1; say "boot log kept: _boot_fail_$ID.log"
    destroy; exit 5
  fi
  sleep 20
done
say "running: ssh -p $PORT root@$HOST"
R="-o StrictHostKeyChecking=accept-new -o ConnectTimeout=20 -p $PORT root@$HOST"

# watch
while :; do
  S=$("$SSH" $R 'if [ -f /root/S7_DONE ]; then echo DONE; elif [ -f /root/S7_FAILED ]; then echo FAILED; else echo RUN; fi; tail -1 /root/s7_llama.log' 2>/dev/null)
  case "$S" in
    DONE*)   say "done"; break ;;
    FAILED*) say "FAILED on the instance - left running for inspection:"; echo "$S"; exit 2 ;;
  esac
  sleep 120
done

# collect and verify
FILES="S7_calls_llama_FIN_HEALTH.jsonl S7_calls_llama_ENERGY_STAPLES.jsonl S7_calls_llama_CONSUMER.jsonl S7_calls_llama.jsonl S7_base_selfcons_llama.jsonl S7_base_verify_llama.jsonl"
for f in $FILES; do
  "$SCP" -o StrictHostKeyChecking=accept-new -P "$PORT" "root@$HOST:/root/repo/probes/$f" "$DEST/$f" || { say "copy failed: $f - instance left up"; exit 3; }
done
"$SCP" -P "$PORT" "root@$HOST:/root/s7_llama.log" "$DEST/_s7_vast_llama.log"
ok=1
for f in S7_calls_llama_FIN_HEALTH S7_calls_llama_ENERGY_STAPLES S7_calls_llama_CONSUMER; do
  n=$(wc -l < "$DEST/$f.jsonl"); [ "$n" -eq 960 ] || { say "$f has $n lines, expected 960"; ok=0; }
done
n=$(wc -l < "$DEST/S7_calls_llama.jsonl"); [ "$n" -eq 3840 ] || { say "combined has $n, expected 3840"; ok=0; }
for f in S7_base_selfcons_llama S7_base_verify_llama; do
  n=$(wc -l < "$DEST/$f.jsonl"); [ "$n" -eq 192 ] || { say "$f has $n lines, expected 192"; ok=0; }
done
[ $ok -eq 1 ] || { say "verification failed - instance $ID left up"; exit 4; }

destroy
