#!/bin/bash
#SBATCH -J q9b-s3
#SBATCH -A karthik.vaidhyanathan
#SBATCH -p u22
#SBATCH -w node01
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=32G
#SBATCH --time=03:00:00
#SBATCH -o /home/pavan.harshit/stay-on-task/logs/q9b-s3-%j.out
# One half of S3_llm_judge@rbh2dc on the 120 val tasks (shard i of 2), its own server, all 60 tasks at once.
# Split off job 49671 so the slow 9B judge runs on two GPUs; same server settings. Usage: sbatch q9b_s3.sbatch RUN_DIR SHARD
set -u
H=/home/pavan.harshit/stay-on-task; S=/scratch/pavan.harshit; R=$1; SH=$2
M=$S/models/Qwen3.5-9B-AWQ-4bit; NAME=cyankiwi/Qwen3.5-9B-AWQ-4bit; SIF=$S/vllm-openai-v0.27.1-cu129.sif
t0=$(date +%s); el() { echo "[$(( $(date +%s)-t0 ))s] $*"; }
PORT=$(python3 -c 'import socket; s=socket.socket(); s.bind(("127.0.0.1",0)); print(s.getsockname()[1])'); URL=http://127.0.0.1:$PORT/v1
module load u22/singularity-ce/4.2.2
TAG=${SH/\//of}
singularity exec --nv --bind $S:$S --env HF_HUB_OFFLINE=1 --env VLLM_CACHE_ROOT=$S/tmp/vc-$SLURM_JOB_ID $SIF vllm serve $M \
  --served-model-name $NAME --host 127.0.0.1 --port $PORT --language-model-only --max-model-len 32768 \
  --gpu-memory-utilization 0.90 --enable-prefix-caching --enable-prompt-tokens-details --enable-auto-tool-choice \
  --tool-call-parser qwen3_coder --max-num-seqs 160 > $R/vllm_s3_$TAG.log 2>&1 &
VP=$!; trap 'kill $VP 2>/dev/null; wait $VP 2>/dev/null' EXIT
until curl -sf $URL/models >/dev/null; do kill -0 $VP 2>/dev/null || { el SERVER_DIED; tail -30 $R/vllm_s3_$TAG.log; exit 1; }; sleep 5; done
el "server up"
nvidia-smi --query-gpu=timestamp,utilization.gpu,memory.used,power.draw --format=csv,noheader -l 10 > $R/gpu_s3_$TAG.csv &
SMI=$!
cd $H/code
singularity exec --nv --bind $S:$S --env BFCL_LB=$H/gorilla/berkeley-function-call-leaderboard --env STAY_CODE=$H/code --env HF_HUB_OFFLINE=1 $SIF \
  python3 actions.py --bench bfcl --system S3_llm_judge@rbh2dc --split val --runs 2 --versions base,miss_param,miss_func,long_context \
  --concurrency 60 --shard $SH --base-url $URL --model $NAME --out $R/S3_llm_judge@rbh2dc > $R/S3_llm_judge@rbh2dc_$TAG.log 2>&1
el "S3 shard $SH exit $?: $(tail -1 $R/S3_llm_judge@rbh2dc_$TAG.log)"
kill $SMI
awk -F', ' '{gsub(/ %/,"",$2); u+=$2; n++} END {printf "mean GPU util %.0f%% over %d samples\n", u/n, n}' $R/gpu_s3_$TAG.csv
