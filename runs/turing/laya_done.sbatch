#!/bin/bash
#SBATCH -J laya-done
#SBATCH -A karthik.vaidhyanathan
#SBATCH -p u22
#SBATCH -w node01
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=48G
#SBATCH --time=01:30:00
#SBATCH -o /home/pavan.harshit/stay-on-task/logs/laya-done-%j.out
# Finetune Laya typed decisions on the turn end done check (oracle labels, 9B train run), one RTX 6000 Ada.
# Canary (32 rows, 1 epoch) gates the real runs: head only (encoder frozen), then full finetune.
set -u
H=/home/pavan.harshit/stay-on-task; S=/scratch/pavan.harshit; O=$H/laya_runs/$SLURM_JOB_ID; mkdir -p $O
module load u22/singularity-ce/4.2.2
nvidia-smi --query-gpu=name,memory.total --format=csv,noheader
py() { singularity exec --nv --bind $S:$S --env PYTHONPATH=$S/pylaya --env HF_HUB_OFFLINE=1 --env HF_HOME=$S/hf-cache \
  $S/vllm-openai-v0.27.1-cu129.sif python3 "$@"; }
M=$S/models/laya-typed-decisions
py $H/analysis/train_laya_done.py $H/data/laya_done $M $O/canary --mode head --epochs 1 --limit 32 > $O/canary.log 2>&1
grep -q "^DONE" $O/canary.log || { echo CANARY_FAIL; tail -30 $O/canary.log; exit 1; }
echo CANARY_OK; grep -E "AUROC|cut at" $O/canary.log
py $H/analysis/train_laya_done.py $H/data/laya_done $M $O/head --mode head --epochs 6 > $O/head.log 2>&1; tail -n 12 $O/head.log
py $H/analysis/train_laya_done.py $H/data/laya_done $M $O/full --mode full --epochs 4 > $O/full.log 2>&1; tail -n 12 $O/full.log
echo ALL_DONE
