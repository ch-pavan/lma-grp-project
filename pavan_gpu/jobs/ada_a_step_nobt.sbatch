#!/bin/bash
#SBATCH -J sot-step-nobt
#SBATCH -A research
#SBATCH -p u22
#SBATCH --constraint=2080ti
#SBATCH --exclude=gnode077,gnode066   # their GPUs fail CUDA init (31 Oct)
#SBATCH --gres=gpu:1
#SBATCH -c 8
#SBATCH --mem=32G
#SBATCH -t 06:00:00
#SBATCH --array=0-5
#SBATCH -o /home2/swayam.goyal/sot/logs/a-%A_%a.out
# Plan item 3.7 on Ada (Swayam's account), the Ada version of a_step_nobt.sbatch. RTX 2080 Ti has no fast bf16, so all
# six runs use fp16 with a GradScaler (train_laya_done.py --dtype fp16) and micro batches of 4 (--accum 8) to fit 11 GB.
# Both variants are trained in this same setup, so the comparison is like for like:
#   nobt_seed0..2  without the oracle breaks_task label (data/laya_step_nobt, from make_step_variant.py)
#   orig_seed0..2  the current label (data/laya_step)
# Run make_step_variant.py once before submitting (see pavan_gpu/README.md, "Running on Ada").
set -u
H=$HOME/sot; M=$H/models/laya-typed-decisions
NAMES=(nobt_seed0 nobt_seed1 nobt_seed2 orig_seed0 orig_seed1 orig_seed2)
DATA=($H/data/laya_step_nobt $H/data/laya_step_nobt $H/data/laya_step_nobt $H/data/laya_step $H/data/laya_step $H/data/laya_step)
SEEDS=(0 1 2 0 1 2)
i=$SLURM_ARRAY_TASK_ID; N=${NAMES[$i]}
O=$H/runs/step_$SLURM_ARRAY_JOB_ID/$N; RES=$H/pavan_gpu/results/a_step_nobt_ada/$N; mkdir -p $O $RES
source $H/venv/bin/activate   # uv-made Python 3.12 venv in the shared home (setup: ~/sot/setup_env.sh)
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True HF_HUB_OFFLINE=1
nvidia-smi --query-gpu=name,memory.total --format=csv,noheader
python $H/analysis/train_laya_done.py ${DATA[$i]} $M $O --question step --mode full --epochs 4 --accum 8 \
  --dtype fp16 --seed ${SEEDS[$i]} > $O/train.log 2>&1
tail -n 6 $O/train.log
cp $O/results.json $O/val_scores.jsonl $RES/ && cp $O/train.log $RES/$N.log
grep -q "^DONE" $O/train.log && echo ALL_DONE || { echo RUN_FAILED; exit 1; }
