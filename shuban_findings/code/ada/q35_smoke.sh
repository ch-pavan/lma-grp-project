# Qwen3.5 4B serve smoke on one 2080 Ti: fp16 official, then AWQ 4bit, then a co serve try with Qwen3 8B AWQ.
set -u
cd ~/agents/lma-project-initial
H=$PWD; S=/scratch/$USER/lma-$SLURM_JOB_ID; mkdir -p $S
trap 'kill $(jobs -p) 2>/dev/null; rm -rf $S' EXIT
export VLLM_ATTENTION_BACKEND=TRITON_ATTN VLLM_USE_FLASHINFER_SAMPLER=0 FLASHINFER_WORKSPACE_BASE=$S
export HF_HOME=/scratch/$USER/lma-hf VLLM_CACHE_ROOT=$S/vc XDG_CACHE_HOME=$S/cache PIP_NO_CACHE_DIR=1 HF_HUB_ENABLE_HF_TRANSFER=1 USE_TF=0
t0=$(date +%s); el() { echo "[$(( $(date +%s)-t0 ))s] $*"; }
python3.10 -m venv $S/venv && . $S/venv/bin/activate
pip install -q --no-index --find-links $H/wheels vllm hf_transfer "huggingface_hub[hf_transfer]" || { el PIP_FAIL; exit 1; }
nvidia-smi --query-gpu=name,memory.total,memory.used --format=csv
for m in Qwen/Qwen3.5-4B cyankiwi/Qwen3.5-4B-AWQ-4bit Qwen/Qwen3-8B-AWQ; do hf download $m >/dev/null 2>&1; el "downloaded $m rc $?"; done
serve() {  # port model util maxlen extra...
  local p=$1 m=$2 u=$3 ml=$4; shift 4
  CUDA_VISIBLE_DEVICES=0 vllm serve $m --dtype half --max-model-len $ml --gpu-memory-utilization $u --enable-prefix-caching \
    --enable-auto-tool-choice --port $p "$@" > $S/v_$p.log 2>&1 &
  SP=$!
  for i in $(seq 450); do curl -sf localhost:$p/v1/models >/dev/null && { el "UP $m port $p"; return 0; }; kill -0 $SP 2>/dev/null || break; sleep 2; done
  el "FAILED $m"; grep -iE "error|exception|not supported|capability" $S/v_$p.log | tail -12; kill $SP 2>/dev/null; wait $SP 2>/dev/null; return 1
}
stopall() { kill $(jobs -p) 2>/dev/null; wait 2>/dev/null; sleep 5; }
MM='--limit-mm-per-prompt {"image":0,"video":0}'
for m in Qwen/Qwen3.5-4B cyankiwi/Qwen3.5-4B-AWQ-4bit; do
  el "=== $m alone"
  if serve 8000 $m 0.88 20480 --tool-call-parser qwen3_coder $MM || serve 8000 $m 0.88 20480 --tool-call-parser qwen3_coder; then
    grep -iE "weights took|KV cache size|maximum concurrency|backend" $S/v_8000.log | tail -5
    python code/q35_smoke.py 8000 $m
    nvidia-smi --query-gpu=memory.used --format=csv
  fi
  cp $S/v_8000.log $H/logs/q35_$(basename $m)_$SLURM_JOB_ID.log; stopall
done
el "=== co serve Qwen3 8B AWQ + Qwen3.5 4B AWQ"
if serve 8000 Qwen/Qwen3-8B-AWQ 0.60 8192 --tool-call-parser hermes --enforce-eager --max-num-seqs 8; then
  grep -iE "KV cache size|maximum concurrency" $S/v_8000.log | tail -2
  serve 8001 cyankiwi/Qwen3.5-4B-AWQ-4bit 0.32 6144 --tool-call-parser qwen3_coder --enforce-eager --max-num-seqs 8 $MM && {
    grep -iE "KV cache size|maximum concurrency" $S/v_8001.log | tail -2; python code/q35_smoke.py 8001 cyankiwi/Qwen3.5-4B-AWQ-4bit; }
fi
nvidia-smi --query-gpu=memory.used --format=csv; stopall; el DONE
