#!/bin/bash
#SBATCH -J laya-full
#SBATCH -A karthik.vaidhyanathan
#SBATCH -p u22
#SBATCH -w node01
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=48G
#SBATCH --time=01:30:00
#SBATCH -o /home/pavan.harshit/stay-on-task/logs/laya-full-%j.out
# Finetune Laya typed decisions on the turn end done check (oracle labels, 9B train run), one RTX 6000 Ada.
# Full finetune only (head only ran in job 49262): gradient checkpointing, micro batches of 8 (effective 32).
set -u
H=/home/pavan.harshit/stay-on-task; S=/scratch/pavan.harshit; O=$H/laya_runs/$SLURM_JOB_ID; mkdir -p $O
module load u22/singularity-ce/4.2.2
nvidia-smi --query-gpu=name,memory.total --format=csv,noheader
py() { singularity exec --nv --bind $S:$S --env PYTHONPATH=$S/pylaya --env HF_HUB_OFFLINE=1 --env HF_HOME=$S/hf-cache --env PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True \
  $S/vllm-openai-v0.27.1-cu129.sif python3 "$@"; }
M=$S/models/laya-typed-decisions
py $H/analysis/train_laya_done.py $H/data/laya_done $M $O/full --mode full --epochs 4 --accum 4 > $O/full.log 2>&1; tail -n 12 $O/full.log
echo ALL_DONE
