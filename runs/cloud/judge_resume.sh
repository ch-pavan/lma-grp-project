#!/bin/bash
# Runs ON the instance. Resumes the 9B judge (same settings as judge.sh) from the predictions already in
# runs/judge9b/full/. The rejudge (8,192 tokens) of the steps already known to be unparsed starts at once, next to the
# main pass, so the GPU stays full at the end; a last rejudge with --resume covers the steps that become unparsed later.
# usage: setsid nohup bash runs/cloud/judge_resume.sh > judge.log 2>&1 < /dev/null &     (from ~/sot, vLLM up)
cd ${W:-$HOME/sot}; . venv/bin/activate
URL=http://127.0.0.1:8000/v1; NAME=cyankiwi/Qwen3.5-9B-AWQ-4bit; OUT=runs/judge9b; CONC=${CONC:-192}
for p in $OUT/full/predictions.jsonl $OUT/pass2.jsonl; do   # drop a line cut by an interruption
  [ -f $p ] && python - "$p" <<'EOF'
import json, sys
p = sys.argv[1]; L = open(p).readlines(); good = []
for l in L:
    try: json.loads(l); good.append(l if l.endswith("\n") else l + "\n")
    except Exception: pass
open(p, "w").writelines(good); print(p, len(good), "rows,", len(L) - len(good), "cut lines dropped")
EOF
done
cp $OUT/full/predictions.jsonl $OUT/preds_at_resume.jsonl
python analysis/rejudge_unparsed.py runs/test $OUT/preds_at_resume.jsonl $OUT/pass2.jsonl --resume \
  --base-url $URL --model $NAME --max-tokens 8192 --concurrency ${EARLY_CONC:-48} > rejudge_early.log 2>&1 &
EARLY=$!
python shuban_findings/code/offline_eval.py --steps runs/test --labels runs/test --keys sample_order.txt --resume \
  --judge llm --base-url $URL --model $NAME --reasoning on --concurrency $CONC --bootstrap 10 --out $OUT/full
echo "FIRST_PASS_EXIT $?: $(grep -c '"parsed": true' $OUT/full/predictions.jsonl) parsed of $(wc -l < $OUT/full/predictions.jsonl)"
wait $EARLY; echo "early rejudge done: $(tail -1 rejudge_early.log)"
python analysis/rejudge_unparsed.py runs/test $OUT/full/predictions.jsonl $OUT/pass2.jsonl --resume \
  --base-url $URL --model $NAME --max-tokens 8192 --concurrency $CONC
echo "REJUDGE_EXIT $?"
