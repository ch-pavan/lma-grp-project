#!/bin/bash
# Runs ON the instance. Plan item 4.1: the Qwen3.5 9B agent, no judge, every step's judge input recorded (S1_record),
# reasoning off, on the 100 TEST scenarios x 4 versions, PASSES passes (8: the stop rule in docs/phase_plan.md and the
# mid report). Same command as runs/turing/q9b_test_passes.sbatch except the concurrency. Safe to rerun after an
# interruption: clean_partial.py drops unfinished episodes and actions.py skips the finished ones.
# usage: bash passes.sh canary      (3 tasks, prints seconds per task)
#        nohup bash passes.sh run > ~/sot/passes.log 2>&1 &
set -uo pipefail
W=${W:-$HOME/sot}; . $W/venv/bin/activate
export BFCL_LB=$W/third_party/gorilla/berkeley-function-call-leaderboard AGENT_THINK=0
URL=http://127.0.0.1:8000/v1; NAME=cyankiwi/Qwen3.5-9B-AWQ-4bit
PASSES=${PASSES:-8}; CONC=${CONC:-128}
cd $W/shuban_findings/code
curl -sf $URL/models >/dev/null || { echo "vLLM is not up: bash $W/runs/cloud/serve.sh"; exit 1; }
if [ "${1:-}" = canary ]; then
  rm -rf $W/runs/canary
  python actions.py --bench bfcl --system S1_record --split test --runs 1 --limit 3 --versions base \
    --concurrency 3 --base-url $URL --model $NAME --out $W/runs/canary
  n=$(cat $W/runs/canary/tasks_*.jsonl 2>/dev/null | wc -l)
  [ "$n" -eq 3 ] && echo CANARY_OK || { echo "CANARY_FAIL ($n of 3)"; exit 1; }
  exit 0
fi
OUT=$W/runs/test; mkdir -p $OUT
[ -n "$(ls $OUT/tasks_*.jsonl 2>/dev/null)" ] && python $W/runs/cloud/clean_partial.py $OUT
python actions.py --bench bfcl --system S1_record --split test --runs $PASSES --limit 0 \
  --versions base,miss_param,miss_func,long_context --concurrency $CONC --base-url $URL --model $NAME --out $OUT
echo "PASSES_EXIT $?"
python analyze.py $OUT 2>&1 | tail -5
