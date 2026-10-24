#!/bin/bash
#SBATCH -J q9b-dc
#SBATCH -A karthik.vaidhyanathan
#SBATCH -p u22
#SBATCH -w node01
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=16
#SBATCH --mem=64G
#SBATCH --time=03:00:00
#SBATCH -o /home/pavan.harshit/stay-on-task/logs/q9b-dc-%j.out
# Live done check on the 120 val tasks, Qwen3.5 9B agent (reasoning off), one RTX 6000 Ada shared by vLLM and Laya.
# Systems, all at once on one server: S1_none (rerun, noise check), S_layadone@dc (finetuned Laya, threshold 0.5 fixed
# before the run), S3_llm_judge@dc (the 9B as SLM judge, reasoning on), S_oracle@dc (ceiling).
# Also offline: the 9B as SLM judge on the 495 val turn ends with the annotators' typed prompt.
set -u
H=/home/pavan.harshit/stay-on-task; S=/scratch/pavan.harshit; R=$H/runs/q9b_dc_$SLURM_JOB_ID; mkdir -p $R
M=$S/models/Qwen3.5-9B-AWQ-4bit; NAME=cyankiwi/Qwen3.5-9B-AWQ-4bit; SIF=$S/vllm-openai-v0.27.1-cu129.sif
t0=$(date +%s); el() { echo "[$(( $(date +%s)-t0 ))s] $*"; }
PORT=$(python3 -c 'import socket; s=socket.socket(); s.bind(("127.0.0.1",0)); print(s.getsockname()[1])'); URL=http://127.0.0.1:$PORT/v1
module load u22/singularity-ce/4.2.2
mkdir -p $S/laya_weights  # finetuned weights live on node scratch, not in home
[ -f $S/laya_weights/done_full_49265.pt ] || mv $H/laya_runs/49265/full/weights.pt $S/laya_weights/done_full_49265.pt
singularity exec --nv --bind $S:$S --env HF_HUB_OFFLINE=1 --env VLLM_CACHE_ROOT=$S/tmp/vc-$SLURM_JOB_ID $SIF vllm serve $M \
  --served-model-name $NAME --host 127.0.0.1 --port $PORT --language-model-only --max-model-len 32768 \
  --gpu-memory-utilization 0.82 --enable-prefix-caching --enable-prompt-tokens-details --enable-auto-tool-choice \
  --tool-call-parser qwen3_coder --max-num-seqs 128 > $R/vllm.log 2>&1 &
VP=$!; trap 'kill $VP 2>/dev/null; wait $VP 2>/dev/null' EXIT
py() { singularity exec --nv --bind $S:$S --env BFCL_LB=$H/gorilla/berkeley-function-call-leaderboard --env PYTHONPATH=$S/pylaya \
  --env STAY_ANALYSIS=$H/analysis --env STAY_CODE=$H/code --env LAYA_DIR=$S/models/laya-typed-decisions \
  --env LAYA_DONE_WEIGHTS=$S/laya_weights/done_full_49265.pt --env LAYA_DONE_THR=0.5 --env HF_HUB_OFFLINE=1 \
  --env ANNOT_URL=$URL/chat/completions --env OPENCODE_KEY=local $SIF python3 "$@"; }
until curl -sf $URL/models >/dev/null; do kill -0 $VP 2>/dev/null || { el SERVER_DIED; tail -30 $R/vllm.log; exit 1; }; sleep 5; done
el "server up"
cd $H/code
run() {  # system conc runs limit versions
  py actions.py --bench bfcl --system $1 --split val --runs $3 --limit $4 --versions $5 --concurrency $2 \
    --base-url $URL --model $NAME --out $R/$1 > $R/$1.log 2>&1; el "$1 exit $?: $(tail -1 $R/$1.log)"
}
run S_layadone@dc 3 1 3 base  # canary: Laya loads next to vLLM and answers
n=$(cat $R/S_layadone@dc/tasks_*.jsonl 2>/dev/null | wc -l)
[ "$n" -eq 3 ] && ! grep -q Traceback $R/S_layadone@dc.log || { el "CANARY_FAIL ($n rows)"; tail -30 $R/S_layadone@dc.log; exit 1; }
el "CANARY_OK: $(grep -c p_not_done $R/S_layadone@dc/states_S_layadone.jsonl) Laya verdicts"; rm -rf $R/S_layadone@dc $R/S_layadone@dc.log
V=base,miss_param,miss_func,long_context
run S1_none 24 2 0 $V & run S_layadone@dc 24 2 0 $V & run S3_llm_judge@dc 24 2 0 $V & run S_oracle@dc 24 2 0 $V &
py $H/analysis/annotate.py $H/runs/q9b_s1t_49146/val $NAME $R/offline_9b_judge.jsonl --what turns --conc 24 > $R/offline_9b_judge.log 2>&1 &
wait $(jobs -p | grep -v "^$VP$")
el DONE
