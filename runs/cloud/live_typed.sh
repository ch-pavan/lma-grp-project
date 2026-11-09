#!/bin/bash
# Runs ON the instance, after setup.sh. Live run of the item 4.4 typed closing-message head (plan:
# analysis/2026-11-09_typed_closing_head.md, "Live run"): the 9B agent in rollback plus done check (S_layastep@rbh2dc)
# on the test split, 3 runs of the 400 tasks, as Swayam's frozen-Laya run on Ada (item 4.7), with the typed head in
# place of the done head and the frozen step head unchanged.
# usage: bash live_typed.sh prep          (Laya, base model, heads from the public releases; vLLM with room for Laya)
#        bash live_typed.sh smoke         (3 base tasks)
#        setsid nohup bash live_typed.sh run > ~/sot/live.log 2>&1 < /dev/null &
set -uo pipefail
W=${W:-$HOME/sot}; cd $W; . venv/bin/activate
URL=http://127.0.0.1:8000/v1; NAME=cyankiwi/Qwen3.5-9B-AWQ-4bit; SY=S_layastep@rbh2dc
REL=https://github.com/ch-pavan/lma-grp-project/releases/download
if [ "${1:-}" = prep ]; then
  UVB=$(deactivate; python3 -c 'import uv; print(uv.find_uv_bin())')   # uv lives in the base python (setup.sh), not the venv
  $UVB pip install -q --python venv/bin/python laya==0.3.27 2>&1 | tail -2
  python - <<'EOF'
import os
from huggingface_hub import snapshot_download
snapshot_download("convaiinnovations/laya-typed-decisions", revision="e929ae5cf69bc34259cd2f95c9e91145b818b1f0",
                  local_dir=os.path.expanduser("~/sot/models/laya-typed-decisions"))
EOF
  mkdir -p heads && cd heads
  for f in parts.sha256 step_head_49477_seed1.pt.part0{0..4}; do curl -sfLO $REL/laya-heads-frozen-2026-11-08/$f || echo "DOWNLOAD_FAILED $f"; done
  grep step_head parts.sha256 | sha256sum -c - && cat step_head_49477_seed1.pt.part0* > step_head_49477_seed1.pt && rm -f *.part0*
  curl -sfLO $REL/laya-typed-head-2026-11-09/typed_head_fp16.pt
  echo "b702252020a0af5bb8205baec35cbaa83f5c5d275f2d59a227d30e4e2881d26e  typed_head_fp16.pt" | sha256sum -c - && echo HEADS_OK
  cd $W; python -c "import torch, laya, vllm; print('torch', torch.__version__, 'laya', laya.__version__, 'vllm', vllm.__version__)"
  GMU=0.85 bash runs/cloud/serve.sh   # 0.85 leaves ~12 GB beside vLLM for the two Laya heads
  exit $?
fi
export BFCL_LB=$W/third_party/gorilla/berkeley-function-call-leaderboard AGENT_THINK=0 \
  LAYA_DIR=$W/models/laya-typed-decisions LAYA_DEVICE=cuda:0 LAYA_DTYPE=bf16 \
  LAYA_STEP_WEIGHTS=$W/heads/step_head_49477_seed1.pt LAYA_STEP_THR=0.1266 \
  LAYA_DONE_WEIGHTS=$W/heads/typed_head_fp16.pt LAYA_TYPED_WEIGHTS=$W/heads/typed_head_fp16.pt LAYA_TYPED_THR=0.2601,0.4173 \
  STAY_ANALYSIS=$W/analysis
curl -sf $URL/models >/dev/null || { echo "vLLM is not up: GMU=0.85 bash runs/cloud/serve.sh"; exit 1; }
cd $W/shuban_findings/code
if [ "${1:-}" = smoke ]; then
  rm -rf $W/runs/live_smoke; ts=$(date +%s)
  python actions.py --bench bfcl --system $SY --split test --runs 1 --limit 3 --versions base --concurrency 3 \
    --base-url $URL --model $NAME --out $W/runs/live_smoke > $W/live_smoke.log 2>&1
  echo "smoke: $(cat $W/runs/live_smoke/tasks_*.jsonl 2>/dev/null | wc -l) of 3 tasks in $(( $(date +%s)-ts ))s, $(grep -c Traceback $W/live_smoke.log) tracebacks"
  python - $W/runs/live_smoke <<'EOF'
import glob, json, sys
for f in glob.glob(sys.argv[1] + "/tasks_*.jsonl"):
    for l in open(f):
        r = json.loads(l); print(" ", r["id"], "pass", r["passed"], "steps", r["steps"], "int", r["interventions"], "err", r["harness_error"])
n = sum(1 for f in glob.glob(sys.argv[1] + "/steps_*.jsonl") for l in open(f) if '"p_typed"' in l)
print("  closing messages scored by the typed head:", n)
EOF
  exit 0
fi
OUT=$W/runs/live_typed; mkdir -p $OUT
[ -n "$(ls $OUT/tasks_*.jsonl 2>/dev/null)" ] && python $W/runs/cloud/clean_partial.py $OUT
python actions.py --bench bfcl --system $SY --split test --runs 3 --limit 0 --versions base,miss_param,miss_func,long_context \
  --concurrency ${CONC:-128} --base-url $URL --model $NAME --out $OUT
echo "LIVE_EXIT $?"
python analyze.py $OUT 2>&1 | tail -5
