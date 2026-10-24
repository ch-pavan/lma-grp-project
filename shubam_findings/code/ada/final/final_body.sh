# Final runs on one GPU for one agent model (actions.py, same harness as the val tuning).
# Env: MODEL, SUF (label suffix, "" or __q35), SARGS (extra vllm args), MAXLEN, VALSYS (val reruns, optional),
# BF (BFCL systems), AD (AgentDojo systems), PILOTX (extra systems to pilot), BESTFILE (file whose first line replaces BEST).
set -u
cd ~/agents/lma-project-initial
H=$PWD; S=/scratch/$USER/lma-$SLURM_JOB_ID; mkdir -p $S
trap 'cp $S/v_*.log $H/logs/ 2>/dev/null; kill $(jobs -p) 2>/dev/null; rm -rf $S' EXIT
export VLLM_ATTENTION_BACKEND=TRITON_ATTN VLLM_USE_FLASHINFER_SAMPLER=0 FLASHINFER_WORKSPACE_BASE=$S
export HF_HOME=/scratch/$USER/lma-hf VLLM_CACHE_ROOT=$S/vc XDG_CACHE_HOME=$S/cache PIP_NO_CACHE_DIR=1 USE_TF=0
T=https://pypi.tuna.tsinghua.edu.cn/simple
t0=$(date +%s); el() { echo "[$(( $(date +%s)-t0 ))s] $*"; }
python3.10 -m venv $S/venv && . $S/venv/bin/activate
pip install -q --no-index --find-links $H/wheels -r $H/pins.txt || { el PIP_FAIL; exit 1; }
pip install -q -i $T --no-deps laya python-dotenv tqdm >/dev/null 2>&1
pip freeze > $S/pins_now.txt; pip install -q -i $T -c $S/pins_now.txt agentdojo==0.1.35 > $S/ad_pip.log 2>&1 || { tail -5 $S/ad_pip.log; el AD_PIP_FAIL; }
python -c "import sys; sys.path.insert(0,'code'); import actions, agentdojo_run" || { el IMPORT_FAIL; exit 1; }
el "venv ok, vllm $(python -c 'import vllm; print(vllm.__version__)')"
QP=""
serve() {
  local m=$1; shift; local ml=${MAXLEN:-20480}
  for try in 1 2; do
    vllm serve $m --dtype half --max-model-len $ml --gpu-memory-utilization ${UTIL:-0.88} --enable-prefix-caching \
      --enable-auto-tool-choice --port 8000 "$@" > $S/v_$(basename $m).log 2>&1 &
    QP=$!
    for i in $(seq 900); do curl -sf localhost:8000/v1/models >/dev/null && { el "UP $m max-model-len $ml"; return 0; }; kill -0 $QP 2>/dev/null || break; sleep 2; done
    N=$(grep -o "estimated maximum model length is [0-9]*" $S/v_$(basename $m).log | grep -o "[0-9]*$" | head -1)
    [ -z "$N" ] || [ "${NORETRY:-0}" = 1 ] && break
    ml=$(( N / 1024 * 1024 )); el "retrying with max-model-len $ml"
  done
  el "SERVER_FAIL $m"; tail -30 $S/v_$(basename $m).log; return 1
}
run() {  # bench system outdir split runs limit
  python code/actions.py --bench $1 --system $2 --split $4 --runs $5 --limit $6 --concurrency ${CONC:-10} --model $MODEL --out $3/$2$SUF --shard ${7:-0/1}
  el "$1 $2$SUF exit $?"
}
best() { local b=$(head -1 $H/$BESTFILE 2>/dev/null | tr -d ' \r\n'); echo ${b:-S3_llm_judge@dc}; }
PD=$H/acts/pilot_final/${SLURM_JOB_ID}; mkdir -p $PD
pilot() {
  for SY in ${BF//,/ } ${PILOTX:-}; do [ $SY = BEST ] || run bfcl $SY $PD/bfcl test 1 1; done
  for SY in ${AD//,/ } ${PILOTX:-}; do [ $SY = BEST ] || run agentdojo $SY $PD/ad test 1 3; done
  python code/pilot_gate.py $PD "$SUF"
}
if [ -n "${TRYMODEL:-}" ]; then  # decider: try the bigger model at the full context, keep it only if it serves and passes the pilot
  hf download $TRYMODEL >/dev/null 2>&1
  M0=$MODEL S0=$SUF; MODEL=$TRYMODEL SUF=$TRYSUF
  if UTIL=0.92 NORETRY=1 serve $MODEL $SARGS && pilot; then el "CHOSE $MODEL"; else
    el "TRY_FAIL $TRYMODEL"; grep -iE "out of memory|KV cache|maximum model length|Error" $S/v_$(basename $TRYMODEL).log | tail -5
    kill $QP 2>/dev/null; wait $QP 2>/dev/null; QP=""; sleep 5; MODEL=$M0 SUF=$S0
  fi
  echo "$MODEL $SUF" > $H/$CHOICE
fi
if [ -n "${CHOICE:-}" ] && [ -z "${TRYMODEL:-}" ]; then  # follower: same model as the decider
  for i in $(seq 120); do [ -s $H/$CHOICE ] && break; sleep 30; done
  [ -s $H/$CHOICE ] || { el NO_CHOICE; exit 1; }
  read MODEL SUF < $H/$CHOICE; el "FOLLOW $MODEL"
fi
if [ -z "$QP" ]; then
  hf download $MODEL >/dev/null 2>&1
  serve $MODEL $SARGS || exit 1
  pilot || { el PILOT_FAIL; exit 1; }
fi
el PILOT_OK
if [ -n "${VALSYS:-}" ]; then  # val reruns (same 120 tasks as the tuning tables)
  for SY in ${VALSYS//,/ }; do run bfcl $SY $H/acts/tune4k 2,12,19,28,55,66,78,91,93,107,112,160,184,185,199 2 0; done
  el VAL_DONE
fi
for SY in ${AD//,/ }; do [ $SY = BEST ] && SY=$(best); run agentdojo $SY $H/acts/final_ad test ${RUNS:-1} 0 $SHARD; done
for SY in ${BF//,/ }; do [ $SY = BEST ] && SY=$(best); run bfcl $SY $H/acts/final_bfcl test ${RUNS:-1} 0 $SHARD; done
kill $QP 2>/dev/null; wait $QP 2>/dev/null
el DONE
