#!/bin/bash
# Runs ON the instance. The 9B SLM judge on the test sample, exactly as on val (job 50247 + 50265): Shuban's offline_eval.py
# --judge llm --reasoning on (harness judge prompt, proposal state), 4,096 output tokens, then the steps with no verdict
# judged again with 8,192 (rejudge_unparsed.py). Only the steps listed in ORDER (analysis/sample_test.py, uploaded from
# the Mac) are judged, in that order. Resumable after an interruption.
# usage: nohup bash judge.sh ~/sot/sample_order.txt > ~/sot/judge.log 2>&1 &
set -uo pipefail
W=${W:-$HOME/sot}; . $W/venv/bin/activate
ORDER=$1; OUT=$W/runs/judge9b; mkdir -p $OUT
URL=http://127.0.0.1:8000/v1; NAME=cyankiwi/Qwen3.5-9B-AWQ-4bit; CONC=${CONC:-128}
export BFCL_LB=$W/third_party/gorilla/berkeley-function-call-leaderboard
curl -sf $URL/models >/dev/null || { echo "vLLM is not up: bash $W/runs/cloud/serve.sh"; exit 1; }
python $W/shuban_findings/code/offline_eval.py --steps $W/runs/test --labels $W/runs/test --keys $ORDER --resume \
  --judge llm --base-url $URL --model $NAME --reasoning on --concurrency $CONC --bootstrap 10 --out $OUT/full
echo "FIRST_PASS_EXIT $?: $(grep -c '"parsed": true' $OUT/full/predictions.jsonl) parsed of $(wc -l < $OUT/full/predictions.jsonl)"
python $W/analysis/rejudge_unparsed.py $W/runs/test $OUT/full/predictions.jsonl $OUT/pass2.jsonl --resume \
  --base-url $URL --model $NAME --max-tokens 8192 --concurrency $CONC
echo "REJUDGE_EXIT $?"
