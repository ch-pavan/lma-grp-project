#!/bin/bash
#SBATCH -J q9b-off
#SBATCH -A karthik.vaidhyanathan
#SBATCH -p u22
#SBATCH -w node01
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=32G
#SBATCH --time=02:00:00
#SBATCH -o /home/pavan.harshit/stay-on-task/logs/q9b-off-%j.out
# Offline 9B SLM judge on the 1,277 val calls, moved off job 49671's GPU so that one serves only the live runs.
# Same server settings as 49671; annotate.py resumes from the rows already in OUT. Usage: sbatch q9b_offline.sbatch OUT
set -u
H=/home/pavan.harshit/stay-on-task; S=/scratch/pavan.harshit; OUT=$1; R=$(dirname $OUT)
M=$S/models/Qwen3.5-9B-AWQ-4bit; NAME=cyankiwi/Qwen3.5-9B-AWQ-4bit; SIF=$S/vllm-openai-v0.27.1-cu129.sif
t0=$(date +%s); el() { echo "[$(( $(date +%s)-t0 ))s] $*"; }
PORT=$(python3 -c 'import socket; s=socket.socket(); s.bind(("127.0.0.1",0)); print(s.getsockname()[1])'); URL=http://127.0.0.1:$PORT/v1
module load u22/singularity-ce/4.2.2
singularity exec --nv --bind $S:$S --env HF_HUB_OFFLINE=1 --env VLLM_CACHE_ROOT=$S/tmp/vc-$SLURM_JOB_ID $SIF vllm serve $M \
  --served-model-name $NAME --host 127.0.0.1 --port $PORT --language-model-only --max-model-len 32768 \
  --gpu-memory-utilization 0.90 --enable-prefix-caching --enable-prompt-tokens-details --max-num-seqs 128 > $R/vllm_offline.log 2>&1 &
VP=$!; trap 'kill $VP 2>/dev/null; wait $VP 2>/dev/null' EXIT
until curl -sf $URL/models >/dev/null; do kill -0 $VP 2>/dev/null || { el SERVER_DIED; tail -30 $R/vllm_offline.log; exit 1; }; sleep 5; done
el "server up"
nvidia-smi --query-gpu=timestamp,utilization.gpu,memory.used,power.draw --format=csv,noheader -l 10 > $R/gpu_offline.csv &
SMI=$!
singularity exec --nv --bind $S:$S --env STAY_CODE=$H/code --env ANNOT_URL=$URL/chat/completions --env OPENCODE_KEY=local $SIF \
  python3 $H/analysis/annotate.py $H/runs/q9b_s1t_49146/val $NAME $OUT --what calls --conc 96 >> $R/offline_9b_steps.log 2>&1
kill $SMI
awk -F', ' '{gsub(/ %/,"",$2); u+=$2; n++} END {printf "mean GPU util %.0f%% over %d samples\n", u/n, n}' $R/gpu_offline.csv
el "DONE $(wc -l < $OUT) rows"
