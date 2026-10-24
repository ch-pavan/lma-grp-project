#!/bin/bash
#SBATCH -J q9b-s1t
#SBATCH -A karthik.vaidhyanathan
#SBATCH -p u22
#SBATCH -w node01
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=16
#SBATCH --mem=64G
#SBATCH --time=06:00:00
#SBATCH -o /home/pavan.harshit/stay-on-task/logs/q9b-s1t-%j.out
# Qwen3.5 9B AWQ as the agent, no judge (S1_record: every step's judge input is saved for oracle labelling).
# Shuban's harness (shuban_findings/code, actions.py), one RTX 6000 Ada 48 GB, high concurrency.
# Phases: serve + gold replay check in parallel, smoke, 3 task canaries (gate), then on one server at once:
# reasoning off val 2 runs + train 3 runs, reasoning on (AGENT_THINK=1, output uncapped) val 2 runs.
set -u
H=/home/pavan.harshit/stay-on-task; S=/scratch/pavan.harshit; R=$H/runs/q9b_s1t_$SLURM_JOB_ID; mkdir -p $R
M=$S/models/Qwen3.5-9B-AWQ-4bit; NAME=cyankiwi/Qwen3.5-9B-AWQ-4bit   # "Qwen3.5" in the name turns on actions.py's Qwen3.5 handling
t0=$(date +%s); el() { echo "[$(( $(date +%s)-t0 ))s] $*"; }
PORT=$(python3 -c 'import socket; s=socket.socket(); s.bind(("127.0.0.1",0)); print(s.getsockname()[1])')
URL=http://127.0.0.1:$PORT/v1
nvidia-smi --query-gpu=name,memory.total --format=csv,noheader
module load u22/singularity-ce/4.2.2 u22/python/3.12.4
singularity exec --nv --bind $S:$S --env HF_HUB_OFFLINE=1 --env VLLM_CACHE_ROOT=$S/tmp/vc-$SLURM_JOB_ID \
  $S/vllm-openai-v0.27.1-cu129.sif vllm serve $M --served-model-name $NAME --host 127.0.0.1 --port $PORT \
    --language-model-only --max-model-len ${MAXLEN:-32768} --gpu-memory-utilization 0.90 \
    --enable-prefix-caching --enable-prompt-tokens-details --enable-auto-tool-choice --tool-call-parser qwen3_coder \
    --max-num-seqs ${SEQS:-128} > $R/vllm.log 2>&1 &
VP=$!
trap 'kill $VP 2>/dev/null; wait $VP 2>/dev/null' EXIT
# the harness runs in the same container (python 3.12 with openai); bfcl_eval needs nothing beyond the stdlib
python() { singularity exec --bind $S:$S --env BFCL_LB=$H/gorilla/berkeley-function-call-leaderboard --env GOLD_LOG=$R/gold_steps.jsonl --env AGENT_THINK=${AGENT_THINK:-0} \
  $S/vllm-openai-v0.27.1-cu129.sif python3 "$@"; }
cd $H/code
python test_gold.py > $R/gold.log 2>&1; el "gold replay: $(tail -1 $R/gold.log)"
until curl -sf $URL/models >/dev/null; do kill -0 $VP 2>/dev/null || { el SERVER_DIED; tail -40 $R/vllm.log; exit 1; }; sleep 5; done
el "server up"; grep -iE "model weights took|KV cache|maximum concurrency" $R/vllm.log | tail -4
python q35_smoke.py $PORT $NAME 2>&1 | tail -4
run() {  # name split runs limit versions conc [think]
  AGENT_THINK=${7:-0} python actions.py --bench bfcl --system S1_record --split $2 --runs $3 --limit $4 --versions $5 \
    --concurrency $6 --base-url $URL --model $NAME --out $R/$1 > $R/$1.log 2>&1
  el "$1 exit $?: $(tail -1 $R/$1.log)"
}
gate() {
  n=$(cat $R/$1/tasks_*.jsonl 2>/dev/null | wc -l)
  if [ "$n" -ne 3 ] || grep -q Traceback $R/$1.log; then el "CANARY_FAIL $1 ($n of 3 rows)"; tail -30 $R/$1.log; exit 1; fi
  el "CANARY_OK $1 passed $(grep -o '"passed": true' $R/$1/tasks_*.jsonl | wc -l) of 3"
}
run canary val 1 3 base 3 0 & C1=$!
run canary_think val 1 3 base 3 1 & C2=$!
wait $C1 $C2; gate canary; gate canary_think
[ "${CANARY_ONLY:-0}" = 1 ] && exit 0
run val val 2 0 base,miss_param,miss_func,long_context ${CV:-24} 0 & P1=$!
run train train 3 0 base,miss_param,miss_func,long_context ${CT:-56} 0 & P2=$!
run val_think val 2 0 base,miss_param,miss_func,long_context ${CVT:-48} 1 & P3=$!
wait $P1 $P2 $P3
grep -iE "Traceback|error" $R/vllm.log | tail -3
for d in val val_think; do python analyze.py $R/$d > $R/${d}_summary.txt 2>&1; tail -5 $R/${d}_summary.txt; done
el DONE
