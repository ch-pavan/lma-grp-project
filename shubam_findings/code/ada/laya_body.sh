# Laya tuning iteration on one GPU. PHASES picks the steps (default: pilot1 sweep an pilot2).
#   rec     S1 with saved judge inputs on train+val scenarios (labels for the offline sweep)
#   pilot1  systems that need no sweep (PILOT1) online on the val scenarios, RUNS_P runs
#   sweep   laya P(flag) per state format x question on the recorded live steps, resumable (vLLM stopped)
#   an      oracle label table + logistic head fit on train scenarios -> laya/an/{table.md,configs.json}
#   pilot2  laya configs (PILOT2) online on the same val tasks
#   jev     hosted Jev (classifier.dev, share_data false) on gold + live states in the background, scored in an
set -u
cd ~/agents/lma-project-initial
H=$PWD; S=/scratch/$USER/lma-$SLURM_JOB_ID; mkdir -p $S $H/laya
trap 'cp $S/vllm*.log $H/logs/ 2>/dev/null; kill $(jobs -p) 2>/dev/null; rm -rf $S' EXIT
export VLLM_ATTENTION_BACKEND=TRITON_ATTN VLLM_USE_FLASHINFER_SAMPLER=0 FLASHINFER_WORKSPACE_BASE=$S
export HF_HOME=/scratch/$USER/lma-hf VLLM_CACHE_ROOT=$S/vc XDG_CACHE_HOME=$S/cache PIP_NO_CACHE_DIR=1 HF_HUB_ENABLE_HF_TRANSFER=1 USE_TF=0
T=https://pypi.tuna.tsinghua.edu.cn/simple
t0=$(date +%s); el() { echo "[$(( $(date +%s)-t0 ))s] $*"; }
python3.10 -m venv $S/venv && . $S/venv/bin/activate
pip install -q --no-index --find-links $H/wheels vllm hf_transfer "huggingface_hub[hf_transfer]" pandas matplotlib || { el PIP_FAIL; exit 1; }
pip install -q -i $T --no-deps laya python-dotenv tqdm >/dev/null 2>&1
python -c "import sys; sys.path.insert(0,'code'); import run, laya, laya_variants" || { el IMPORT_FAIL; exit 1; }
hf download Qwen/Qwen3-8B-AWQ >/dev/null 2>&1
hf download convaiinnovations/laya-typed-decisions >/dev/null 2>&1
el "venv and models ready"
PH=" ${PHASES:-jev pilot1 sweep an pilot2} "
TRVAL=1,2,6,7,9,11,12,13,14,15,17,19,20,22,24,27,28,31,32,36,39,41,42,43,46,52,55,56,57,59,61,62,66,67,68,70,76,77,78,79,81,84,87,88,89,91,92,93,96,97,98,101,105,107,108,109,110,111,112,116,119,120,121,123,124,125,131,134,142,146,151,154,155,160,163,164,166,167,172,173,174,179,182,183,184,185,190,196,199
VAL=2,12,19,28,55,66,78,91,93,107,112,160,184,185,199
ALLV=base,miss_param,miss_func,long_context

QP=""
start_vllm() {
  ML=${MAXLEN:-20480}
  for try in 1 2; do
    CUDA_VISIBLE_DEVICES=0 vllm serve Qwen/Qwen3-8B-AWQ --dtype half --max-model-len $ML --gpu-memory-utilization ${UTIL:-0.78} \
      --enable-prefix-caching --enable-auto-tool-choice --tool-call-parser hermes --max-num-seqs 32 --port 8000 > $S/vllm0.log 2>&1 &
    QP=$!
    for i in $(seq 600); do curl -sf localhost:8000/v1/models >/dev/null && break; kill -0 $QP 2>/dev/null || break; sleep 2; done
    curl -sf localhost:8000/v1/models >/dev/null && [ $ML -lt ${MINLEN:-8192} ] && { el "max-model-len $ML is below ${MINLEN:-8192}, results would not compare"; exit 1; }
    curl -sf localhost:8000/v1/models >/dev/null && { el "qwen up, max-model-len $ML"; return 0; }
    N=$(grep -o "estimated maximum model length is [0-9]*" $S/vllm0.log | grep -o "[0-9]*$" | head -1)
    [ -z "$N" ] && break
    ML=$(( N / 1024 * 1024 )); el "retrying with max-model-len $ML"
  done
  el SERVER_FAIL; tail -30 $S/vllm0.log; exit 1
}
stop_vllm() { kill $QP 2>/dev/null; wait $QP 2>/dev/null; QP=""; sleep 5; el "qwen stopped"; }

if [[ $PH == *" rec "* ]]; then
  start_vllm
  python code/laya_run.py --system S1_record --split $TRVAL --runs 1 --versions $ALLV --concurrency ${CONC:-10} --out $H/laya/rec
  el "rec exit $?"
fi
pilot() {  # pilot SYSTEM...: each online on the val scenarios, RUNS_P runs, then a pass rate line per system
  [ -z "$QP" ] && start_vllm
  for sys in "$@"; do
    python code/laya_run.py --system $sys --split $VAL --runs ${RUNS_P:-2} --versions $ALLV --concurrency ${CONC:-10} --out $H/laya/${PILOT_OUT:-pilot}/$sys ${LAYA_DEVICE:+--laya-device $LAYA_DEVICE}
    el "pilot $sys exit $?"
  done
  python code/laya_pilot_summary.py $H/laya/${PILOT_OUT:-pilot}
}
if [[ $PH == *" jev "* ]]; then  # hosted Jev over the network, alongside the GPU phases
  (cd code && VAL=$VAL LIMIT_GOLD=600 python jev_client.py $H/laya/jev_feats.jsonl laya/gold_states.jsonl $H/laya/rec/states_S1_record.jsonl > $H/logs/jev_$SLURM_JOB_ID.log 2>&1) &
  JEVP=$!
fi
export LAYA_CFG=${LAYA_CFG:-$H/laya/an/configs.json} TREE_MODEL=$H/code/laya/tree_model.json
[[ $PH == *" pilot1 "* ]] && pilot ${PILOT1:-S1_record S_oracle S_tree S3_llm_judge}
if [[ $PH == *" sweep "* ]]; then
  [ -n "$QP" ] && stop_vllm
  PAIRS=${PAIRS:-cut} VRAM_FRAC=0.9 BS=${BS:-8} python code/laya_sweep.py $H/laya/feats_live.jsonl $H/laya/rec/states_S1_record.jsonl
  el "sweep exit $?"
fi
if [[ $PH == *" an "* ]]; then
  mkdir -p $H/laya/an; cp code/laya/tree_rows.json $H/laya/an/ 2>/dev/null
  if [ -n "${JEVP:-}" ]; then wait $JEVP; tail -2 $H/logs/jev_$SLURM_JOB_ID.log
    (cd code && python laya_table.py laya/oracle_labels.jsonl $H/laya/an_jev $H/laya/jev_feats.jsonl > $H/logs/jev_table_$SLURM_JOB_ID.log 2>&1) && cp $H/laya/an_jev/table.json $H/laya/an/jev_rows.json
    python -c "import json,statistics as s; r=[json.loads(l) for l in open('$H/laya/jev_feats.jsonl')]; m=[x['ms'] for x in r]; print('JEV latency ms median', s.median(m), 'p90', sorted(m)[int(.9*len(m))], 'n', len(m))"
  fi
  (cd code && python laya_table.py laya/oracle_labels.jsonl $H/laya/an $H/laya/feats_gold_iter1.jsonl $H/laya/feats_live.jsonl)
  el "table exit $?"
fi
[[ $PH == *" pilot2 "* ]] && pilot ${PILOT2:-S4v_single S4v_head}
el DONE
