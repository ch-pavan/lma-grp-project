#!/bin/bash
#SBATCH -J pg-done-cv
#SBATCH -A karthik.vaidhyanathan
#SBATCH -p u22
#SBATCH -w node01
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=12
#SBATCH --mem=64G
#SBATCH --time=01:30:00
#SBATCH -o /home/pavan.harshit/stay-on-task/logs/pg-done-cv-%j.out
# Plan item 3.4. Done head, full finetune with the job 49265 settings, on 5 scenario-grouped folds of TRAIN only.
# Each fold writes out-of-fold scores (val_scores.jsonl = the held-out fold). We pick the threshold from these on our
# side and apply it to the existing 49265 validation scores, so validation is never used to choose it.
# 2 epochs per fold (49265 was best after epoch 2), about 3 min per fold on one RTX 6000 Ada.
set -u
H=/home/pavan.harshit/stay-on-task; S=/scratch/pavan.harshit
O=$H/laya_runs/pg_done_cv_$SLURM_JOB_ID; mkdir -p $O
RES=$H/pavan_gpu/results/b_done_cv; mkdir -p $RES
module load u22/singularity-ce/4.2.2
nvidia-smi --query-gpu=name,memory.total --format=csv,noheader
py() { singularity exec --nv --bind $S:$S --env PYTHONPATH=$S/pylaya --env HF_HUB_OFFLINE=1 --env HF_HOME=$S/hf-cache \
  --env PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True $S/vllm-openai-v0.27.1-cu129.sif python3 "$@"; }
M=$S/models/laya-typed-decisions; F=$H/data/laya_done_folds
py $H/pavan_gpu/make_done_folds.py $H/data/laya_done $F --k 5 | tee $RES/folds.txt
for k in 0 1 2 3 4; do
  py $H/analysis/train_laya_done.py $F/fold$k $M $O/fold$k --mode full --epochs 2 --accum 4 --seed 0 > $O/fold$k.log 2>&1
  grep -q "^DONE" $O/fold$k.log || { echo "FOLD $k FAILED"; tail -n 30 $O/fold$k.log; exit 1; }
  tail -n 3 $O/fold$k.log
  mkdir -p $RES/fold$k && cp $O/fold$k/results.json $O/fold$k/val_scores.jsonl $O/fold$k.log $RES/fold$k/
done
echo ALL_DONE
