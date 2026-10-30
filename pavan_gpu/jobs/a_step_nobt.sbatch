#!/bin/bash
#SBATCH -J pg-step-nobt
#SBATCH -A karthik.vaidhyanathan
#SBATCH -p u22
#SBATCH -w node01
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=12
#SBATCH --mem=64G
#SBATCH --time=03:00:00
#SBATCH -o /home/pavan.harshit/stay-on-task/logs/pg-step-nobt-%j.out
# Plan item 3.7. Step head WITHOUT the oracle "breaks_task" label (3 seeds), plus seeds 1 and 2 of the current setup
# (seed 0 is job 49656), all with the job 49656 settings. About 16 min per run on one RTX 6000 Ada, 5 runs.
set -u
H=/home/pavan.harshit/stay-on-task; S=/scratch/pavan.harshit
O=$H/laya_runs/pg_step_$SLURM_JOB_ID; mkdir -p $O
RES=$H/pavan_gpu/results/a_step_nobt; mkdir -p $RES
module load u22/singularity-ce/4.2.2
nvidia-smi --query-gpu=name,memory.total --format=csv,noheader
nvidia-smi --query-gpu=timestamp,utilization.gpu,memory.used,power.draw --format=csv,noheader -l 10 > $O/gpu.csv &
SMI=$!
py() { singularity exec --nv --bind $S:$S --env PYTHONPATH=$S/pylaya --env HF_HUB_OFFLINE=1 --env HF_HOME=$S/hf-cache \
  --env PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True --env STAY_CODE=$H/code \
  $S/vllm-openai-v0.27.1-cu129.sif python3 "$@"; }
M=$S/models/laya-typed-decisions; D=$H/data/laya_step; DN=$H/data/laya_step_nobt
py $H/pavan_gpu/make_step_variant.py $D $DN | tee $RES/variant.txt
py $H/analysis/train_laya_done.py $DN $M $O/canary --question step --mode full --epochs 1 --accum 4 --limit 200 > $O/canary.log 2>&1
grep -q DONE $O/canary.log || { echo CANARY_FAILED; tail -n 30 $O/canary.log; kill $SMI; exit 1; }
echo CANARY_OK
run() {  # name data_dir seed
  py $H/analysis/train_laya_done.py $2 $M $O/$1 --question step --mode full --epochs 4 --accum 4 --seed $3 > $O/$1.log 2>&1
  tail -n 4 $O/$1.log
  mkdir -p $RES/$1 && cp $O/$1/results.json $O/$1/val_scores.jsonl $O/$1.log $RES/$1/
}
run nobt_seed0 $DN 0
run nobt_seed1 $DN 1
run nobt_seed2 $DN 2
run orig_seed1 $D 1
run orig_seed2 $D 2
kill $SMI; cp $O/gpu.csv $RES/
echo ALL_DONE
