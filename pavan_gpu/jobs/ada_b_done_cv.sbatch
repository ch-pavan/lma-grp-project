#!/bin/bash
#SBATCH -J sot-done-cv
#SBATCH -A research
#SBATCH -p u22
#SBATCH --constraint=2080ti
#SBATCH --exclude=gnode077,gnode066   # their GPUs fail CUDA init (31 Oct)
#SBATCH --gres=gpu:1
#SBATCH -c 8
#SBATCH --mem=32G
#SBATCH -t 03:00:00
#SBATCH --array=0-4
#SBATCH -o /home2/swayam.goyal/sot/logs/b-%A_%a.out
# Plan item 3.4 on Ada (Swayam's account), the Ada version of b_done_cv.sbatch: done head, full finetune, 2 epochs, on
# 5 scenario-grouped folds of TRAIN; each fold's val_scores.jsonl holds the out-of-fold scores. fp16 + GradScaler
# (no fast bf16 on the RTX 2080 Ti), micro batches of 4. Run make_done_folds.py once before submitting.
set -u
H=$HOME/sot; M=$H/models/laya-typed-decisions; k=$SLURM_ARRAY_TASK_ID
O=$H/runs/done_cv_$SLURM_ARRAY_JOB_ID/fold$k; RES=$H/pavan_gpu/results/b_done_cv_ada/fold$k; mkdir -p $O $RES
source $H/venv/bin/activate   # uv-made Python 3.12 venv in the shared home (setup: ~/sot/setup_env.sh)
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True HF_HUB_OFFLINE=1
nvidia-smi --query-gpu=name,memory.total --format=csv,noheader
python $H/analysis/train_laya_done.py $H/data/laya_done_folds/fold$k $M $O --mode full --epochs 2 --accum 8 \
  --dtype fp16 --seed 0 > $O/train.log 2>&1
tail -n 4 $O/train.log
cp $O/results.json $O/val_scores.jsonl $RES/ && cp $O/train.log $RES/fold$k.log
grep -q "^DONE" $O/train.log && echo ALL_DONE || { echo RUN_FAILED; exit 1; }
