#!/bin/bash
# Runs on the Mac. Copies the instance's run outputs to the Mac every 10 minutes, so a spot interruption that loses the
# instance loses at most 10 minutes of work: a new instance gets these files back (jl upload) and resumes from them.
# Needs this Mac's SSH key on the cloud account (jl ssh-key add ~/.ssh/id_ed25519.pub --name pavan-mac).
# usage: bash runs/cloud/sync.sh MACHINE_ID [LOCAL_DIR]       (LOCAL_DIR defaults to runs/raw/test9b_sync)
set -uo pipefail
ID=$1; L=${2:-runs/raw/test9b_sync}; mkdir -p "$L"
JL=${JL:-jl}
while true; do
  CMD=$($JL ssh "$ID" --print-command 2>/dev/null | tail -1)   # e.g. ssh -p PORT root@HOST
  if [ -n "$CMD" ]; then
    # a tar stream over ssh (macOS openrsync does not talk to the instance): the run outputs, logs and the sample.
    # Written to a temp dir first and moved into place, so a cut connection never leaves a half copy.
    T="$L.part"; rm -rf "$T"; mkdir -p "$T"
    SSH_E=$(echo "$CMD" | sed -E 's/ [^ ]+@[^ ]+$//'); DEST=$(echo "$CMD" | awk '{print $NF}')   # options must come before the host
    if $SSH_E -o ConnectTimeout=20 "$DEST" \
         'cd ~/sot && tar -cz --ignore-failed-read runs/test runs/judge9b passes.log judge.log gpu.txt sample_order.txt sample_meta.json after_passes.log oracle_labels.log sample.log 2>/dev/null; true' \
         < /dev/null | tar -xz -C "$T" 2>/dev/null && [ -d "$T/runs/test" ]; then
      rm -rf "$L.old"; [ -d "$L" ] && mv "$L" "$L.old"; mv "$T" "$L"; rm -rf "$L.old"
    else
      echo "$(date +%H:%M) copy failed, keeping the previous copy"
    fi
    echo "$(date +%H:%M) synced: $(cat "$L"/runs/test/tasks_*.jsonl 2>/dev/null | wc -l | tr -d ' ') tasks, $(cat "$L"/runs/judge9b/full/predictions.jsonl 2>/dev/null | wc -l | tr -d ' ') judged"
  else
    echo "$(date +%H:%M) instance $ID not reachable (interrupted or paused?)"
  fi
  sleep 600
done
