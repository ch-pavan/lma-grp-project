#!/bin/bash
#SBATCH -J q9b-slm
#SBATCH -A karthik.vaidhyanathan
#SBATCH -p u22
#SBATCH -w node01
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=32G
#SBATCH --time=01:30:00
#SBATCH -o /home/pavan.harshit/stay-on-task/logs/q9b-slm-%j.out
# The 9B SLM judge (reasoning on, the harness judge prompt and proposal state of Shuban's offline_eval.py) on all 1,772 val
# steps of the 9B no judge run, calls and closing messages, so both halves of the primary metric come from one run.
# Same server settings as job 49688. A canary of 8 steps first. Usage: sbatch q9b_slm.sbatch OUT_DIR
set -u
H=/home/pavan.harshit/stay-on-task; S=/scratch/pavan.harshit; OUT=$1; R=$OUT; mkdir -p $OUT; V=$H/runs/q9b_s1t_49146/val
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
ev() { singularity exec --nv --bind $S:$S $SIF python3 $H/shuban_findings/code/offline_eval.py --steps $V --labels $V \
  --judge llm --base-url $URL --model $NAME --reasoning on --concurrency 96 "$@"; }
ev --limit 8 --out $OUT/canary > $OUT/canary.log 2>&1
n=$(wc -l < $OUT/canary/predictions.jsonl 2>/dev/null || echo 0)
[ "$n" -eq 8 ] && ! grep -q Traceback $OUT/canary.log || { el "CANARY_FAIL ($n rows)"; tail -30 $OUT/canary.log; exit 1; }
el "CANARY_OK: $(grep -c '"parsed": true' $OUT/canary/predictions.jsonl) of 8 parsed"
ev --out $OUT/full > $OUT/full.log 2>&1
el "full exit $?: $(grep -c '"parsed": true' $OUT/full/predictions.jsonl) parsed of $(wc -l < $OUT/full/predictions.jsonl)"
kill $SMI
awk -F', ' '{gsub(/ %/,"",$2); u+=$2; n++} END {printf "mean GPU util %.0f%% over %d samples\n", u/n, n}' $R/gpu_offline.csv
el DONE
