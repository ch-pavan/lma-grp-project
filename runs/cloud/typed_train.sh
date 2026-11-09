#!/bin/bash
# Runs ON the instance, after the 9B judge is done and vLLM is stopped. Plan item 4.4
# (analysis/2026-11-09_typed_closing_head.md): environment check, then the 5 out-of-fold runs and the 3 seeds, one at a
# time on one GPU; meanwhile the frozen heads are downloaded from the public release for the test scoring.
# usage: setsid nohup bash runs/cloud/typed_train.sh > typed.log 2>&1 < /dev/null &      (from ~/sot)
cd ${W:-$HOME/sot}; . venv/bin/activate
M=models/laya-typed-decisions; D=runs/data/laya_typed; O=runs/typed; mkdir -p $O frozen
out=$(python analysis/train_laya_typed.py $D $M $O/check --check 2>&1); echo "$out" | tail -3
a=$(echo "$out" | grep -oP 'AUROC \K[0-9.]+')
python -c "import sys; sys.exit(0 if abs(float('$a') - 0.7524) < 0.01 else 1)" || { echo "CHECK_FAILED (AUROC '$a', Ada 0.7524)"; exit 1; }
echo CHECK_OK
(cd frozen && R=https://github.com/ch-pavan/lma-grp-project/releases/download/laya-heads-frozen-2026-11-08 &&
 for f in parts.sha256 done_head_64348.pt.part0{0..4} step_head_49477_seed1.pt.part0{0..4}; do curl -sfLO $R/$f || echo "DOWNLOAD_FAILED $f"; done &&
 sha256sum -c parts.sha256 && cat done_head_64348.pt.part0* > done_head_64348.pt && cat step_head_49477_seed1.pt.part0* > step_head_49477_seed1.pt &&
 rm -f *.part0* && echo FROZEN_OK) > frozen.log 2>&1 &
job() {  # job NAME ARGS...
  n=$1; shift
  python analysis/train_laya_typed.py $D $M $O/$n "$@" > $O/$n.log 2>&1; echo "$(date +%H:%M) $n exit $? $(tail -1 $O/$n.log)"
}
export -f job; export D M O
printf '%s\n' "fold0 --fold 0" "fold1 --fold 1" "fold2 --fold 2" "fold3 --fold 3" "fold4 --fold 4" \
  "seed0 --seed 0" "seed1 --seed 1" "seed2 --seed 2" | xargs -P 1 -I{} bash -c 'job {}'
wait
echo TYPED_ALL_DONE
