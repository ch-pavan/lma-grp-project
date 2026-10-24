#!/bin/bash
# pget.sh URL OUT [PARTS]: ranged parallel download, for hosts that throttle each connection (GitHub ~40 KB/s)
U=$1 O=$2 N=${3:-48}
L=$(curl -sIL "$U" | grep -i '^content-length' | tail -1 | tr -dc 0-9)
[ -z "$L" ] && { curl -s -L -o "$O" "$U"; exit; }
P=$(( (L + N - 1) / N )); T=$(mktemp -d)
for i in $(seq 0 $((N-1))); do a=$((i*P)); b=$((a+P-1)); [ $b -ge $L ] && b=$((L-1))
  echo "$i $a $b"; done | xargs -P $N -n 3 sh -c 'curl -s -L --retry 8 -r $1-$2 -o '$T'/$0 "'$U'"'
for i in $(seq 0 $((N-1))); do cat $T/$i; done > "$O"; rm -rf $T
[ "$(stat -c %s "$O")" = "$L" ] && echo "pget ok $L bytes" || echo "pget SIZE MISMATCH"
