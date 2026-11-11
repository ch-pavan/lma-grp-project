#!/bin/bash
# Runs on the Mac (the API key stays here). Waits for the 9B judge to finish on the instance, makes a final copy of the
# results, checks it, then stops the GPU billing:
#   copy complete  -> destroy the instance (everything is on the Mac)
#   no copy (SSH blocked or the instance unreachable) by the deadline -> pause it instead: GPU billing stops, the data
#   stays on its disk to be copied later (jl resume ID, then sync.sh).
# usage: bash runs/cloud/finish.sh MACHINE_ID DEADLINE_HHMM [EXPECTED_STEPS]     e.g. finish.sh 567406 1545 7214
set -uo pipefail
ID=$1; DEADLINE=$2; N=${3:-7214}; JL=${JL:-jl}
cd "$(git -C "$(dirname "$0")" rev-parse --show-toplevel)"
L=runs/raw/test9b_sync
log() { echo "$(date +%H:%M) $*"; }
copy_ok() {
  sed 's/sleep 600/break/' runs/cloud/sync.sh > /tmp/sync_once_$$.sh
  bash /tmp/sync_once_$$.sh "$ID" | tail -1
  local p=$L/runs/judge9b/full/predictions.jsonl
  [ -f "$p" ] && [ "$(wc -l < "$p")" -ge "$N" ] && [ -f "$L/runs/judge9b/pass2.jsonl" ] && grep -q REJUDGE_EXIT $L/judge.log
}
while true; do
  CMD=$($JL ssh "$ID" --print-command 2>/dev/null | tail -1)
  SSH_E=$(echo "$CMD" | sed -E 's/ [^ ]+@[^ ]+$//'); DEST=$(echo "$CMD" | awk '{print $NF}')
  st=$($SSH_E -o ConnectTimeout=20 "$DEST" 'grep -c REJUDGE_EXIT ~/sot/judge.log; wc -l < ~/sot/runs/judge9b/full/predictions.jsonl' < /dev/null 2>/dev/null | tr '\n' ' ')
  if [ -n "$st" ]; then
    log "judge status: finished=${st%% *} judged=${st#* }"
    if [ "${st%% *}" = "1" ]; then
      if copy_ok; then
        log "final copy complete and checked; destroying the instance"
        $JL destroy "$ID" --yes; $JL list | tail -3; exit 0
      fi
      log "final copy incomplete, retrying"
    fi
  else
    log "instance not reachable over SSH"
  fi
  if [ "$(date +%H%M)" -ge "$DEADLINE" ]; then
    log "deadline $DEADLINE reached without a complete copy; pausing (data stays on the instance)"
    $JL pause "$ID" --yes; $JL list | tail -3; exit 0
  fi
  sleep 120
done
