#!/bin/bash
# Runs on the Mac. Chains plan item 4.4 (analysis/2026-11-09_typed_closing_head.md) after the 9B judge, on the same
# instance:
#   1. training labels: wait for both annotators, one resumable pass for the steps they could not label, build the rows
#   2. 9B judge: wait for the rejudge, copy its results to runs/raw/test9b_judge and check them
#   3. stop vLLM, upload the scripts and rows, run runs/cloud/typed_train.sh (check, 5 folds, 3 seeds)
#   4. copy the scores back (not the weights) and choose the run on validation (typed_select.py)
# The instance stays up afterwards, for the test scoring. Remote commands go through `bash -s` on stdin, so a process
# search on the instance never matches this script's own command line.
# usage: bash runs/cloud/typed_auto.sh USER@HOST
set -uo pipefail
cd "$(git -C "$(dirname "$0")" rev-parse --show-toplevel)"
H=$1; LAB=runs/raw/test9b_labels/train; R=runs/raw/typed_head; J=runs/raw/test9b_judge; PY=.venv/bin/python
log() { echo "$(date +%H:%M) $*"; }
rsh() { ssh -o ConnectTimeout=20 -o ServerAliveInterval=30 "$H" 'bash -s'; }

# 1. labels
until grep -q '^DONE' $LAB/annot_v3_deepseek_turns.log 2>/dev/null && grep -q '^DONE' $LAB/annot_v3_glm_turns.log 2>/dev/null; do sleep 60; done
log "labels: $(tail -1 $LAB/annot_v3_deepseek_turns.log) | $(tail -1 $LAB/annot_v3_glm_turns.log)"
export OPENCODE_KEY="$(cat ~/.config/stay-on-task/opencode_key)"
for m in deepseek glm; do
  f=$LAB/annot_v3_${m}_turns.jsonl
  python3 - "$f" <<'EOF'
import json, sys
p = sys.argv[1]; seen, keep, drop = set(), [], 0
for l in open(p):
    try: r = json.loads(l)
    except Exception: drop += 1; continue
    if r["uid"] in seen or r.get("answer") is None: drop += 1; continue
    seen.add(r["uid"]); keep.append(json.dumps(r) + "\n")
open(p, "w").writelines(keep); print(p, len(keep), "kept,", drop, "dropped to retry")
EOF
  model=$([ $m = deepseek ] && echo deepseek-v4.1-flash || echo glm-5.3-flash)
  python3 analysis/annotate.py runs/data/q9b_s1t_49146/train $model $f --what turns --guide v3 --conc 16 > $LAB/annot_v3_${m}_turns.retry.log 2>&1
  log "retry $m: $(tail -1 $LAB/annot_v3_${m}_turns.retry.log)"
done
unset OPENCODE_KEY
mkdir -p $R; git show origin/main:runs/data/laya_runs/ada_done_full/val_scores.jsonl > $R/frozen_done_val_scores.jsonl
$PY analysis/build_typed_data.py runs/data/laya_typed | tee $R/build.log

# 2. judge
until echo 'grep -q REJUDGE_EXIT ~/sot/judge.log' | rsh 2>/dev/null; do sleep 60; done
mkdir -p $J.part
echo 'cd ~/sot && tar -cz runs/judge9b judge.log rejudge_early.log' | rsh | tar -xz -C $J.part && rm -rf $J && mv $J.part $J
n1=$(wc -l < $J/runs/judge9b/full/predictions.jsonl); n2=$(wc -l < $J/runs/judge9b/pass2.jsonl)
log "judge copied: predictions $n1 (want 7214), rejudge rows $n2 (want 1412), $(grep REJUDGE_EXIT $J/judge.log)"
[ "$n1" -ge 7214 ] && [ "$n2" -ge 1412 ] || { log "JUDGE_COPY_INCOMPLETE, stopping before vLLM is shut down"; exit 1; }

# 3. train
rsh <<'EOF'
pkill -f "vllm serve"; sleep 10; nvidia-smi --query-gpu=memory.used --format=csv,noheader
EOF
tar -cz analysis/train_laya_done.py analysis/train_laya_typed.py runs/data/laya_done/dev.jsonl runs/data/laya_typed runs/cloud/typed_train.sh |
  ssh -o ConnectTimeout=20 "$H" 'cd ~/sot && tar -xz'
rsh <<'EOF'
cd ~/sot; setsid nohup bash runs/cloud/typed_train.sh > typed.log 2>&1 < /dev/null & sleep 2; echo started
EOF
log "training started"
until echo 'grep -qE "TYPED_ALL_DONE|CHECK_FAILED" ~/sot/typed.log' | rsh 2>/dev/null; do sleep 60; done
echo 'cat ~/sot/typed.log' | rsh

# 4. scores back, choice on validation
mkdir -p $R/out.part
echo 'cd ~/sot && tar -cz --exclude=weights.pt typed.log frozen.log runs/typed' | rsh | tar -xz -C $R/out.part && rm -rf $R/out && mv $R/out.part $R/out
grep -q CHECK_FAILED $R/out/typed.log && { log "environment check failed, no choice made"; exit 1; }
T=$R/out/runs/typed
$PY analysis/typed_select.py $R/select --oof $T/fold{0,1,2,3,4} --runs $T/seed{0,1,2} --done-scores $R/frozen_done_val_scores.jsonl | tee $R/select.log
log "TYPED_AUTO_DONE"
