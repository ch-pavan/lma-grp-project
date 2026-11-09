#!/bin/bash
#SBATCH -J sot-done-full
#SBATCH -A research
#SBATCH -p u22
#SBATCH --constraint=2080ti
#SBATCH --exclude=gnode077,gnode066   # their GPUs fail CUDA init (31 Oct)
#SBATCH --gres=gpu:1
#SBATCH -c 8
#SBATCH --mem=32G
#SBATCH -t 01:00:00
#SBATCH -o /home2/swayam.goyal/sot/logs/done-full-%j.out
# Done head for the Laya test run: full finetune on the train split (dev picks the epoch, as in job 49265) with the
# recipe of the cross-validation folds (2 epochs, fp16, seed 0, jobs 49476 and 49598), so their out-of-fold threshold
# 0.561 applies.
set -u
H=$HOME/sot; M=$H/models/laya-typed-decisions
O=$H/runs/done_full_$SLURM_JOB_ID; mkdir -p $O
source $H/venv/bin/activate   # uv-made Python 3.12 venv in the shared home (setup: runs/ada/setup_env.sh)
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True HF_HUB_OFFLINE=1
nvidia-smi --query-gpu=name,memory.total --format=csv,noheader
python $H/analysis/train_laya_done.py $H/data/laya_done $M $O --mode full --epochs 2 --accum 8 \
  --dtype fp16 --seed 0 > $O/train.log 2>&1
tail -n 4 $O/train.log
grep -q "^DONE" $O/train.log && echo ALL_DONE || { echo RUN_FAILED; exit 1; }
