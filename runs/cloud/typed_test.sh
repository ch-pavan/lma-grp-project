#!/bin/bash
# Runs on the Mac, after typed_auto.sh (TYPED_AUTO_DONE): the test scoring of the frozen Laya and the item 4.4 head chosen
# on validation, the final comparison against the 9B judge, a copy of the chosen head's weights (fp16), then the
# instance is destroyed. Stops before destroying if any copy or check fails.
# usage: JL_API_KEY=... JL=.../jl bash runs/cloud/typed_test.sh USER@HOST MACHINE_ID
set -uo pipefail
cd "$(git -C "$(dirname "$0")" rev-parse --show-toplevel)"
H=$1; ID=$2; R=runs/raw/typed_head; PY=.venv/bin/python; JL=${JL:-jl}
log() { echo "$(date +%H:%M) $*"; }
rsh() { ssh -o ConnectTimeout=20 -o ServerAliveInterval=30 "$H" 'bash -s'; }

until grep -q TYPED_AUTO_DONE runs/raw/typed_head/logs/auto.log 2>/dev/null; do
  grep -qE "JUDGE_COPY_INCOMPLETE|check failed" runs/raw/typed_head/logs/auto.log 2>/dev/null && { log "typed_auto stopped early"; exit 1; }
  sleep 60
done
SEED=$($PY -c "import json; print(json.load(open('$R/select/choice.json'))['choice'])")
log "chosen on validation: $SEED"
mkdir -p $R/stage/runs/data/laya_runs/ada_done_full $R/stage/runs/data/laya_runs/ada_step_nobt/orig_seed1 $R/stage/runs/data/laya_step $R/stage/runs/data/laya_done
cp $R/frozen_done_val_scores.jsonl $R/stage/runs/data/laya_runs/ada_done_full/val_scores.jsonl
cp runs/data/laya_runs/ada_step_nobt/orig_seed1/val_scores.jsonl.gz $R/stage/runs/data/laya_runs/ada_step_nobt/orig_seed1/
cp runs/data/laya_step/val.jsonl $R/stage/runs/data/laya_step/; cp runs/data/laya_done/val.jsonl $R/stage/runs/data/laya_done/
tar -cz analysis/score_test.py analysis/build_step_data.py analysis/build_done_data.py analysis/step_labels.py \
   analysis/train_laya_typed.py analysis/train_laya_done.py | ssh -o ConnectTimeout=20 "$H" 'cd ~/sot && tar -xz'
tar -cz -C $R/stage runs | ssh -o ConnectTimeout=20 "$H" 'cd ~/sot && tar -xz'   # one stream each: a second gzip member is ignored
echo 'cd ~/sot && ls runs/data/laya_step/val.jsonl runs/data/laya_done/val.jsonl runs/data/laya_runs/ada_done_full/val_scores.jsonl runs/data/laya_runs/ada_step_nobt/orig_seed1/val_scores.jsonl.gz' | rsh || { log "upload incomplete"; exit 1; }
rsh > $R/score_test.log 2>&1 <<EOF
cd ~/sot; . venv/bin/activate; grep FROZEN_OK frozen.log || { echo FROZEN_MISSING; exit 1; }
python analysis/score_test.py runs/test sample_order.txt models/laya-typed-decisions frozen/step_head_49477_seed1.pt \
  frozen/done_head_64348.pt runs/typed/$SEED/weights.pt laya_test_scores.jsonl --typed-val-scores runs/typed/$SEED/scores.jsonl
python -c "import torch; sd = torch.load('runs/typed/$SEED/weights.pt'); torch.save({k: v.half() if v.is_floating_point() else v for k, v in sd.items()}, 'typed_head_fp16.pt')"
sha256sum typed_head_fp16.pt laya_test_scores.jsonl
EOF
cat $R/score_test.log
grep -q "^SCORED" $R/score_test.log || { log "test scoring failed; instance left running"; exit 1; }
echo 'cd ~/sot && cat laya_test_scores.jsonl' | rsh > $R/laya_test_scores.jsonl
echo 'cat ~/sot/typed_head_fp16.pt' | rsh > $R/typed_head_fp16.pt   # ~ is /home there, while scp starts in /root
remote=$(grep typed_head_fp16.pt $R/score_test.log | awk '{print $1}'); local=$(shasum -a 256 $R/typed_head_fp16.pt | awk '{print $1}')
[ -n "$remote" ] && [ "$remote" = "$local" ] || { log "weights copy does not match ($remote vs $local); instance left running"; exit 1; }
[ "$(wc -l < $R/laya_test_scores.jsonl)" -ge 7000 ] || { log "test scores copy short; instance left running"; exit 1; }
$PY analysis/primary_test.py runs/raw/test9b/test runs/raw/test9b/sample_order.txt runs/raw/test9b_labels \
  runs/raw/test9b_judge/runs/judge9b $R/laya_test_scores.jsonl $R/select/thresholds.json | tee $R/primary_test.md
log "everything copied and checked; destroying the instance"
$JL destroy "$ID" --yes; $JL list | tail -3
log TYPED_TEST_DONE
