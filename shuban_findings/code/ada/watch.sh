#!/bin/bash
# watch.sh: one line per job of this chat that leaves the Ada queue (ledger jobs + chained_jobs.txt); exits when none remain
seen=""
while true; do
  out=$(ssh -o ConnectTimeout=20 ada 'cd ~/agents/lma-project-initial; ids=$(grep -o "[0-9]\+" chained_jobs.txt 2>/dev/null | tr "\n" ","); echo "CH $ids"; squeue -u $USER -h -o "%i %j %T"' 2>/dev/null) || { sleep 120; continue; }
  ch=$(echo "$out" | sed -n 's/^CH //p'); q=$(echo "$out" | grep -v '^CH')
  for id in $(echo "$ch" | tr ',' ' ') $(awk '{print $1}' /home/orbi8r/storage/.agentwork/ada/lma-project-initial.jobs 2>/dev/null); do
    echo "$q" | grep -q "^$id " && continue
    case " $seen " in *" $id "*) continue;; esac
    seen="$seen $id"; [ "$id" -ge 11402 ] && echo "LEFT QUEUE $id"
  done
  running=$(echo "$q" | grep -c "pilot\|bench2\|wheels3\|full_\|run_")
  [ "$running" = 0 ] && [ -n "$ch" ] && { echo "ALL DONE"; exit 0; }
  sleep 120
done
