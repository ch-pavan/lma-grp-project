# Correction modes (actions.py) on one GPU. Phase 1: Qwen3 8B server, systems in SYS8, then the offline S3 judge over
# recorded S1 states if OFF8=1. Phase 2: Q35MODEL server, systems in SYS35 (agent and judge both that model), offline judge if OFF35=1.
set -u
cd ~/agents/lma-project-initial
H=$PWD; S=/scratch/$USER/lma-$SLURM_JOB_ID; mkdir -p $S
trap 'cp $S/v_*.log $H/logs/ 2>/dev/null; kill $(jobs -p) 2>/dev/null; rm -rf $S' EXIT
export VLLM_ATTENTION_BACKEND=TRITON_ATTN VLLM_USE_FLASHINFER_SAMPLER=0 FLASHINFER_WORKSPACE_BASE=$S
export HF_HOME=/scratch/$USER/lma-hf VLLM_CACHE_ROOT=$S/vc XDG_CACHE_HOME=$S/cache PIP_NO_CACHE_DIR=1 USE_TF=0
T=https://pypi.tuna.tsinghua.edu.cn/simple
t0=$(date +%s); el() { echo "[$(( $(date +%s)-t0 ))s] $*"; }
python3.10 -m venv $S/venv && . $S/venv/bin/activate
pip install -q --no-index --find-links $H/wheels vllm hf_transfer "huggingface_hub[hf_transfer]" pandas matplotlib || { el PIP_FAIL; exit 1; }
pip install -q -i $T --no-deps laya python-dotenv tqdm >/dev/null 2>&1
[ "${BENCH:-bfcl}" = agentdojo ] && { pip freeze > $S/pins.txt; pip install -q -i $T -c $S/pins.txt agentdojo==0.1.35 > $S/ad_pip.log 2>&1 || tail -5 $S/ad_pip.log; }
python -c "import sys; sys.path.insert(0,'code'); import actions" || { el IMPORT_FAIL; exit 1; }
O=$H/${OUT:-acts/tune}; mkdir -p $O
QP=""
serve() {  # model, then extra vllm args
  local m=$1; shift; local ml=${MAXLEN:-20480}
  for try in 1 2; do
    CUDA_VISIBLE_DEVICES=${SGPU:-0} vllm serve $m --dtype half --max-model-len $ml --gpu-memory-utilization ${UTIL:-0.88} --enable-prefix-caching \
      --enable-auto-tool-choice --max-num-seqs 32 --port ${SPORT:-8000} "$@" > $S/v_$(basename $m).log 2>&1 &
    QP=$!
    for i in $(seq 900); do curl -sf localhost:${SPORT:-8000}/v1/models >/dev/null && { el "UP $m max-model-len $ml"; return 0; }; kill -0 $QP 2>/dev/null || break; sleep 2; done
    N=$(grep -o "estimated maximum model length is [0-9]*" $S/v_$(basename $m).log | grep -o "[0-9]*$" | head -1)
    [ -z "$N" ] && break
    ml=$(( N / 1024 * 1024 )); el "retrying with max-model-len $ml"
  done
  el "SERVER_FAIL $m"; tail -30 $S/v_$(basename $m).log; return 1
}
stop() { kill $QP 2>/dev/null; wait $QP 2>/dev/null; QP=""; sleep 5; }
runsys() {  # model, system, out label
  python code/actions.py --bench ${BENCH:-bfcl} --system $2 --split ${SPLIT:-test} --runs ${RUNS:-3} --limit ${LIMIT:-0} \
    --versions ${VERSIONS:-base,miss_param,miss_func,long_context} --concurrency ${CONC:-10} --model $1 --out $O/$3 ${JARGS:-}
  el "$3 exit $?"
}
if [ "${Q35SMOKE:-0}" = 1 ]; then  # which Qwen3.5 4B setup serves on this card; working ones go to q35_ok.txt
  for cfg in "cyankiwi/Qwen3.5-4B-AWQ-4bit|" "cyankiwi/Qwen3.5-4B-AWQ-4bit|--enforce-eager" "Qwen/Qwen3.5-4B|" "Qwen/Qwen3.5-4B|--enforce-eager"; do
    m=${cfg%%|*}; x=${cfg#*|}; hf download $m >/dev/null 2>&1
    if MAXLEN=16384 serve $m --tool-call-parser qwen3_coder --max-num-seqs 16 --limit-mm-per-prompt '{"image":0,"video":0}' $x; then
      grep -iE "weights took|KV cache size|maximum concurrency" $S/v_$(basename $m).log | tail -3
      python code/q35_smoke.py 8000 $m && echo "$m $x" >> $O/q35_ok.txt
    fi
    stop
  done
fi
if [ -n "${RANKERS:-}" ]; then  # offline ranker check: TRBench BFCL pairs and our oracle labelled steps
  for m in ${RANKERS//,/ }; do hf download $m --include "*.json" "*.safetensors" "*.txt" "*.jinja" >/dev/null 2>&1; el "got $m"; done
  timeout ${RANK_TIMEOUT:-80m} python code/rankers.py $O/rankers code/acts/trb500.jsonl code/acts/rec/states_S1_record.jsonl code/acts/rec/labels.jsonl ${RANKERS//,/ }
  el "rankers exit $?"
fi
if [ "${DROPCTX:-0}" = 1 ]; then  # episodes that died on the context limit rerun with old tool outputs trimmed (resume skips the rest)
  python - $O <<'PY'
import glob, json, sys
for f in glob.glob(sys.argv[1] + "/*/tasks_*.jsonl"):
    rows = [json.loads(l) for l in open(f) if l.strip()]
    keep = [r for r in rows if "maximum context length" not in str(r.get("harness_error"))]
    if len(keep) < len(rows):
        open(f, "w").write("".join(json.dumps(r) + "\n" for r in keep)); print("dropped", len(rows) - len(keep), f)
PY
fi
if [ -n "${SYS8:-}" ] || [ "${OFF8:-0}" = 1 ]; then
  hf download Qwen/Qwen3-8B-AWQ >/dev/null 2>&1
  serve Qwen/Qwen3-8B-AWQ --tool-call-parser hermes || exit 1
  for SY in ${SYS8//,/ }; do runsys Qwen/Qwen3-8B-AWQ $SY $SY; done
  [ "${OFF8:-0}" = 1 ] && python code/actions_offline.py $O/S1_record/states_S1_record.jsonl $O/offline_qwen3_8b.jsonl http://localhost:8000/v1 Qwen/Qwen3-8B-AWQ ${OFFN:-600} 12 && el "offline 8b done"
  stop
fi
if [ -n "${SYSJ:-}" ]; then  # two cards: Qwen3 8B agents on card 0, Qwen3.5 judge on card 1
  hf download Qwen/Qwen3-8B-AWQ >/dev/null 2>&1; hf download $Q35J >/dev/null 2>&1
  serve Qwen/Qwen3-8B-AWQ --tool-call-parser hermes || exit 1; P0=$QP
  SGPU=1 SPORT=8001 MAXLEN=16384 serve $Q35J --tool-call-parser qwen3_coder --max-num-seqs 16 --limit-mm-per-prompt '{"image":0,"video":0}' || exit 1; P1=$QP
  for SY in ${SYSJ//,/ }; do JARGS="--judge-url http://localhost:8001/v1 --judge-model $Q35J" runsys Qwen/Qwen3-8B-AWQ $SY ${SY}__j35; done
  kill $P0 $P1 2>/dev/null; wait $P0 $P1 2>/dev/null; QP=""; sleep 5
fi
if [ -n "${Q35MODEL:-}" ]; then
  hf download $Q35MODEL >/dev/null 2>&1
  MAXLEN=16384 serve $Q35MODEL --tool-call-parser qwen3_coder --max-num-seqs 16 --limit-mm-per-prompt '{"image":0,"video":0}' ${Q35ARGS:-} || exit 1
  for SY in ${SYS35//,/ }; do runsys $Q35MODEL $SY ${SY}__q35; done
  [ "${OFF35:-0}" = 1 ] && python code/actions_offline.py $O/S1_record/states_S1_record.jsonl $O/offline_qwen35.jsonl http://localhost:8000/v1 $Q35MODEL ${OFFN:-600} 12 && el "offline q35 done"
  stop
fi
el DONE
