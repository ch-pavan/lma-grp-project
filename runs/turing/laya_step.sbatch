#!/bin/bash
#SBATCH -J laya-step
#SBATCH -A karthik.vaidhyanathan
#SBATCH -p u22
#SBATCH -w node01
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=12
#SBATCH --mem=64G
#SBATCH --time=01:30:00
#SBATCH -o /home/pavan.harshit/stay-on-task/logs/laya-step-%j.out
# Laya full finetune on the per call step check (build_step_data.py, pooled 9B and 8B steps), one RTX 6000 Ada.
# Canary first (200 rows, 1 epoch), then one seed; one run alone keeps the GPU at 97 to 100% (job 49646).
# GPU use is sampled every 10 s into gpu.csv.
set -u
H=/home/pavan.harshit/stay-on-task; S=/scratch/pavan.harshit; O=$H/laya_runs/$SLURM_JOB_ID; mkdir -p $O
module load u22/singularity-ce/4.2.2
nvidia-smi --query-gpu=name,memory.total --format=csv,noheader
nvidia-smi --query-gpu=timestamp,utilization.gpu,memory.used,power.draw --format=csv,noheader -l 10 > $O/gpu.csv &
SMI=$!
py() { singularity exec --nv --bind $S:$S --env PYTHONPATH=$S/pylaya --env HF_HUB_OFFLINE=1 --env HF_HOME=$S/hf-cache --env PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True \
  $S/vllm-openai-v0.27.1-cu129.sif python3 "$@"; }
M=$S/models/laya-typed-decisions; D=$H/data/laya_step
py $H/analysis/train_laya_done.py $D $M $O/canary --question step --mode full --epochs 1 --accum 4 --limit 200 > $O/canary.log 2>&1
grep -q DONE $O/canary.log || { echo CANARY_FAILED; tail -n 30 $O/canary.log; kill $SMI; exit 1; }
echo CANARY_OK
py $H/analysis/train_laya_done.py $D $M $O/seed0 --question step --mode full --epochs 4 --accum 4 --seed 0 > $O/seed0.log 2>&1
kill $SMI
tail -n 8 $O/seed0.log
awk -F', ' '{gsub(/ %/,"",$2); u+=$2; n++} END {printf "mean GPU util %.0f%% over %d samples\n", u/n, n}' $O/gpu.csv
echo ALL_DONE
