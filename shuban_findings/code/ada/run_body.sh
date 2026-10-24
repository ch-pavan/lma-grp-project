set -u
cd ~/agents/lma-project-initial
H=$PWD; S=/scratch/$USER/lma-$SLURM_JOB_ID; mkdir -p $S
trap 'cp $S/vllm*.log $H/logs/ 2>/dev/null; for f in $H/logs/vllm?.log; do [ -e "$f" ] && mv "$f" "${f%.log}_$SLURM_JOB_ID.log"; done; kill $(jobs -p) 2>/dev/null; rm -rf $S' EXIT
export VLLM_ATTENTION_BACKEND=TRITON_ATTN VLLM_USE_FLASHINFER_SAMPLER=0 FLASHINFER_WORKSPACE_BASE=$S  # Turing: FA2 needs sm80, FlashInfer JIT has no headers here
export HF_HOME=/scratch/$USER/lma-hf VLLM_CACHE_ROOT=$S/vc XDG_CACHE_HOME=$S/cache PIP_NO_CACHE_DIR=1 HF_HUB_ENABLE_HF_TRANSFER=1 USE_TF=0
T=https://pypi.tuna.tsinghua.edu.cn/simple
t0=$(date +%s); el() { echo "[$(( $(date +%s)-t0 ))s] $*"; }
python3.10 -m venv $S/venv && . $S/venv/bin/activate
pip install -q --no-index --find-links $H/wheels vllm hf_transfer "huggingface_hub[hf_transfer]" pandas matplotlib || { el PIP_FAIL; exit 1; }
pip install -q -i $T --no-deps laya python-dotenv tqdm >/dev/null 2>&1
el "venv ready: $(python -c 'import vllm; print(vllm.__version__)')"
python -c "import sys; sys.path.insert(0,'code'); import run" || { el IMPORT_FAIL; exit 1; }
hf download Qwen/Qwen3-8B-AWQ >/dev/null 2>&1 || huggingface-cli download Qwen/Qwen3-8B-AWQ >/dev/null
[ "$SYS" = S4a_laya ] && hf download convaiinnovations/laya-typed-decisions >/dev/null 2>&1
[ "$SYS" = S4b_granite ] && hf download ibm-granite/granite-guardian-3.2-3b-a800m >/dev/null 2>&1
el "models ready: $(du -sh $HF_HOME | cut -f1)"; PIDS=""
# KV room differs a little between nodes; if the context does not fit, restart at the length vLLM says fits
ML=${MAXLEN:-20480}
for try in 1 2; do
  CUDA_VISIBLE_DEVICES=0 vllm serve Qwen/Qwen3-8B-AWQ --dtype half --max-model-len $ML --gpu-memory-utilization ${UTIL:-0.88} \
    --enable-prefix-caching --enable-auto-tool-choice --tool-call-parser hermes --max-num-seqs ${SEQS:-32} --port 8000 > $S/vllm0.log 2>&1 &
  QP=$!
  for i in $(seq 600); do curl -sf localhost:8000/v1/models >/dev/null && break; kill -0 $QP 2>/dev/null || break; sleep 2; done
  curl -sf localhost:8000/v1/models >/dev/null && break
  N=$(grep -o "estimated maximum model length is [0-9]*" $S/vllm0.log | grep -o "[0-9]*$" | head -1)
  [ -z "$N" ] && break
  ML=$(( N / 1024 * 1024 )); el "context too long for this card's KV room, retrying with max-model-len $ML"; cp $S/vllm0.log $S/vllm0_try1.log
done
PIDS="$PIDS $QP"; el "qwen max-model-len $ML"
if [ "$SYS" = S4b_granite ] && [ -z "${GRANITE_URL:-}" ]; then
  CUDA_VISIBLE_DEVICES=1 vllm serve ibm-granite/granite-guardian-3.2-3b-a800m --dtype half --max-model-len 16384 \
    --gpu-memory-utilization 0.80 --max-num-seqs 16 --enable-prefix-caching --port 8001 > $S/vllm1.log 2>&1 & PIDS="$PIDS $!"
fi
for p in 8000 $([ "$SYS" = S4b_granite ] && [ -z "${GRANITE_URL:-}" ] && echo 8001); do
  for i in $(seq 600); do curl -sf localhost:$p/v1/models >/dev/null && break; for q in $PIDS; do kill -0 $q 2>/dev/null || { el "SERVER_DIED"; tail -30 $S/vllm*.log; exit 1; }; done; sleep 2; done
  curl -sf localhost:$p/v1/models >/dev/null || { el "SERVER_FAIL $p"; tail -40 $S/vllm*.log; exit 1; }
done
el "servers up"; grep -i "KV cache\|maximum concurrency\|GPU blocks" $S/vllm0.log | tail -3
# RUNPY=agentdojo_run.py runs AgentDojo; SYS may list several systems, run one after another on the same server
[ "${RUNPY:-run.py}" = agentdojo_run.py ] && { pip freeze > $S/pins.txt; pip install -q -i $T -c $S/pins.txt agentdojo==0.1.35 > $S/ad_pip.log 2>&1 || tail -5 $S/ad_pip.log; el "agentdojo $(pip show agentdojo 2>/dev/null | grep -i ^version)"; }
for SY in ${SYS//,/ }; do
python code/${RUNPY:-run.py} --system $SY --split ${SPLIT:-test} --runs ${RUNS:-3} --limit ${LIMIT:-0} \
  --versions ${VERSIONS:-base,miss_param,miss_func,long_context} --concurrency ${CONC:-8} --out $H/${OUT:-results}/$SY ${GRANITE_URL:+--granite-url $GRANITE_URL} --shard ${SHARD:-0/1}
el "run exit $?"
done
grep -iE "error|Traceback" $S/vllm0.log | tail -5
el DONE
