#!/bin/bash
#SBATCH -J pg-test-passes
#SBATCH -A karthik.vaidhyanathan
#SBATCH -p u22
#SBATCH -w node01
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=16
#SBATCH --mem=64G
#SBATCH --time=06:00:00
#SBATCH -o /home/pavan.harshit/stay-on-task/logs/pg-test-passes-%j.out
# Plan item 4.1 (from 1 Nov, when the GPU budget resets). Qwen3.5 9B agent, no judge, S1_record on the 100 TEST
# scenarios x 4 versions, PASSES passes (default 4). Same server and sampling as job 49146 (vLLM 0.27.1, 32k context,
# reasoning off). Job 49146 ran 1,128 tasks in 67 min, so 4 passes (1,600 tasks) should take about 1.5 to 2 hours.
# Oracle labels and LLM annotation are done on our side after merging. These steps are also the S1 test baseline.
# usage: sbatch [--export=ALL,PASSES=4] runs/turing/q9b_test_passes.sbatch
# The gzipped outputs in $RES go into the repo as runs/raw/q9b_test_<job>/.
set -u
H=/home/pavan.harshit/stay-on-task; S=/scratch/pavan.harshit; R=$H/runs/pg_test_$SLURM_JOB_ID; mkdir -p $R
RES=$R/for_repo; mkdir -p $RES
M=$S/models/Qwen3.5-9B-AWQ-4bit; NAME=cyankiwi/Qwen3.5-9B-AWQ-4bit
t0=$(date +%s); el() { echo "[$(( $(date +%s)-t0 ))s] $*"; }
PORT=$(python3 -c 'import socket; s=socket.socket(); s.bind(("127.0.0.1",0)); print(s.getsockname()[1])')
URL=http://127.0.0.1:$PORT/v1
module load u22/singularity-ce/4.2.2 u22/python/3.12.4
singularity exec --nv --bind $S:$S --env HF_HUB_OFFLINE=1 --env VLLM_CACHE_ROOT=$S/tmp/vc-$SLURM_JOB_ID \
  $S/vllm-openai-v0.27.1-cu129.sif vllm serve $M --served-model-name $NAME --host 127.0.0.1 --port $PORT \
    --language-model-only --max-model-len 32768 --gpu-memory-utilization 0.90 \
    --enable-prefix-caching --enable-prompt-tokens-details --enable-auto-tool-choice --tool-call-parser qwen3_coder \
    --max-num-seqs 128 > $R/vllm.log 2>&1 &
VP=$!
trap 'kill $VP 2>/dev/null; wait $VP 2>/dev/null' EXIT
python() { singularity exec --bind $S:$S --env BFCL_LB=$H/gorilla/berkeley-function-call-leaderboard --env AGENT_THINK=0 \
  $S/vllm-openai-v0.27.1-cu129.sif python3 "$@"; }
cd $H/code
until curl -sf $URL/models >/dev/null; do kill -0 $VP 2>/dev/null || { el SERVER_DIED; tail -40 $R/vllm.log; exit 1; }; sleep 5; done
el "server up"
python actions.py --bench bfcl --system S1_record --split test --runs 1 --limit 3 --versions base \
  --concurrency 3 --base-url $URL --model $NAME --out $R/canary > $R/canary.log 2>&1
n=$(cat $R/canary/tasks_*.jsonl 2>/dev/null | wc -l)
[ "$n" -eq 3 ] || { el "CANARY_FAIL ($n of 3)"; tail -30 $R/canary.log; exit 1; }
el CANARY_OK
python actions.py --bench bfcl --system S1_record --split test --runs ${PASSES:-4} --limit 0 \
  --versions base,miss_param,miss_func,long_context --concurrency 56 --base-url $URL --model $NAME --out $R/test > $R/test.log 2>&1
el "test exit $?: $(tail -1 $R/test.log)"
python analyze.py $R/test > $R/test_summary.txt 2>&1; tail -5 $R/test_summary.txt
# results for the repo: everything gzipped except the small summaries
mkdir -p $RES/test
for f in $R/test/*.jsonl; do gzip -c "$f" > $RES/test/$(basename "$f").gz; done
cp $R/test_summary.txt $R/test.log $RES/
grep -iE "Traceback|error" $R/vllm.log | tail -3
el ALL_DONE
