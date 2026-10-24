#!/bin/bash
#SBATCH -J q9b-laya
#SBATCH -A karthik.vaidhyanathan
#SBATCH -p u22
#SBATCH -w node01
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=16
#SBATCH --mem=64G
#SBATCH --time=01:30:00
#SBATCH -o /home/pavan.harshit/stay-on-task/logs/q9b-laya-%j.out
# Rerun of S_layastep@rbh2dc after the gate fix in laya_step_judge.py (closing messages pass the gate; the done head
# answers only the done check). Same server and thresholds as job 49671, its own GPU, all 120 val tasks at once.
# Usage: sbatch q9b_laya.sbatch RUN_DIR
set -u
H=/home/pavan.harshit/stay-on-task; S=/scratch/pavan.harshit; R=$1
M=$S/models/Qwen3.5-9B-AWQ-4bit; NAME=cyankiwi/Qwen3.5-9B-AWQ-4bit; SIF=$S/vllm-openai-v0.27.1-cu129.sif
t0=$(date +%s); el() { echo "[$(( $(date +%s)-t0 ))s] $*"; }
PORT=$(python3 -c 'import socket; s=socket.socket(); s.bind(("127.0.0.1",0)); print(s.getsockname()[1])'); URL=http://127.0.0.1:$PORT/v1
module load u22/singularity-ce/4.2.2
mkdir -p $S/laya_weights  # finetuned weights live on node scratch, not in home
[ -f $S/laya_weights/done_full_49265.pt ] || cp $H/laya_runs/49265/full/weights.pt $S/laya_weights/done_full_49265.pt 2>/dev/null
[ -f $S/laya_weights/step_full_49656.pt ] || mv $H/laya_runs/49656/seed0/weights.pt $S/laya_weights/step_full_49656.pt
ls -la $S/laya_weights
singularity exec --nv --bind $S:$S --env HF_HUB_OFFLINE=1 --env VLLM_CACHE_ROOT=$S/tmp/vc-$SLURM_JOB_ID $SIF vllm serve $M \
  --served-model-name $NAME --host 127.0.0.1 --port $PORT --language-model-only --max-model-len 32768 \
  --gpu-memory-utilization 0.85 --enable-prefix-caching --enable-prompt-tokens-details --enable-auto-tool-choice \
  --tool-call-parser qwen3_coder --max-num-seqs 160 > $R/vllm_laya.log 2>&1 &
VP=$!; trap 'kill $VP 2>/dev/null; wait $VP 2>/dev/null' EXIT
py() { singularity exec --nv --bind $S:$S --env BFCL_LB=$H/gorilla/berkeley-function-call-leaderboard --env PYTHONPATH=$S/pylaya \
  --env STAY_ANALYSIS=$H/analysis --env STAY_CODE=$H/code --env LAYA_DIR=$S/models/laya-typed-decisions \
  --env LAYA_DONE_WEIGHTS=$S/laya_weights/done_full_49265.pt --env LAYA_DONE_THR=0.5 \
  --env LAYA_STEP_WEIGHTS=$S/laya_weights/step_full_49656.pt --env LAYA_STEP_THR=0.204 --env HF_HUB_OFFLINE=1 \
  --env ANNOT_URL=$URL/chat/completions --env OPENCODE_KEY=local $SIF python3 "$@"; }
until curl -sf $URL/models >/dev/null; do kill -0 $VP 2>/dev/null || { el SERVER_DIED; tail -30 $R/vllm_laya.log; exit 1; }; sleep 5; done
el "server up"
cd $H/code
run() {  # system conc runs limit versions
  py actions.py --bench bfcl --system $1 --split val --runs $3 --limit $4 --versions $5 --concurrency $2 \
    --base-url $URL --model $NAME --out $R/$1_fix > $R/$1_fix.log 2>&1; el "$1 exit $?: $(tail -1 $R/$1_fix.log)"
}
run S_layastep@rbh2dc 3 1 3 base  # canary: done head answers done checks, the gate passes closing messages
n=$(cat $R/S_layastep@rbh2dc_fix/tasks_*.jsonl 2>/dev/null | wc -l)
[ "$n" -eq 3 ] && ! grep -q Traceback $R/S_layastep@rbh2dc_fix.log || { el "CANARY_FAIL ($n rows)"; tail -30 $R/S_layastep@rbh2dc_fix.log; exit 1; }
el "CANARY_OK: $(grep -o '"rolled_back": true' $R/S_layastep@rbh2dc_fix/steps_*.jsonl | wc -l) rollbacks, $(grep -o '"kind": "done_check"' $R/S_layastep@rbh2dc_fix/steps_*.jsonl | wc -l) done checks"
rm -rf $R/S_layastep@rbh2dc_fix $R/S_layastep@rbh2dc_fix.log
nvidia-smi --query-gpu=timestamp,utilization.gpu,memory.used,power.draw --format=csv,noheader -l 10 > $R/gpu_laya.csv &
SMI=$!
run S_layastep@rbh2dc 120 2 0 base,miss_param,miss_func,long_context
kill $SMI
awk -F', ' '{gsub(/ %/,"",$2); u+=$2; n++} END {printf "mean GPU util %.0f%% over %d samples\n", u/n, n}' $R/gpu_laya.csv
el DONE
