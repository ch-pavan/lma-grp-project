#!/bin/bash
#SBATCH -J sot-laya-test
#SBATCH -A research
#SBATCH -p u22
#SBATCH --constraint=2080ti
#SBATCH --exclude=gnode077,gnode066   # their GPUs fail CUDA init (31 Oct)
#SBATCH --gres=gpu:2
#SBATCH -c 9
#SBATCH --mem=40G
#SBATCH -t 12:00:00
#SBATCH -o /home2/swayam.goyal/sot/logs/laya-test-%j.out
# Finetuned Laya (step head plus done head) as one more system in Shuban's original BFCL test baselines
# (shuban_findings/results/test_baselines.md): run.py plain block mode, Qwen3 8B AWQ agent on vLLM 0.19.1, 20,480 token
# context, concurrency 10, 100 test scenarios x 4 versions x 3 runs. The agent server is started exactly as in
# shuban_findings/code/ada/run_body.sh, on the first GPU; the two Laya heads sit on the second (they do not fit next to
# the server at the same context on one 11 GB card). Frozen choices: runs/ada/test_freeze.md. Setup: test_env_setup.sh.
# Compute nodes do not mount /share1: the wheelhouse is in ~/sot/wheels, and the agent model is downloaded once per node
# into /scratch/$USER/sot-hf (node local, kept between jobs, as Shuban's /scratch/$USER/lma-hf).
# usage: sbatch --export=ALL,DONE_W=<done head weights.pt>[,SHARD=0/3][,RUNS=3][,LIMIT=0][,OUT=dir] laya_test.sbatch
# SPLIT=val, DONE_MODE=once|off (closing messages, see analysis/laya_step_judge.py) and SYS=S1_none are for the validation
# comparison of closing message handling; the frozen test run uses the defaults. VERSIONS limits the versions run.
set -u
H=$HOME/sot/testrun; W=$HOME/sot/wheels; UV=~/.local/bin/uv
S=/scratch/$USER/sot-$SLURM_JOB_ID; mkdir -p $S
OUT=${OUT:-$HOME/sot/test_runs/laya_$SLURM_JOB_ID}; mkdir -p $OUT
trap 'cp $S/vllm0*.log $OUT/ 2>/dev/null; kill $(jobs -p) 2>/dev/null; rm -rf $S' EXIT
export VLLM_ATTENTION_BACKEND=TRITON_ATTN VLLM_USE_FLASHINFER_SAMPLER=0 FLASHINFER_WORKSPACE_BASE=$S  # as run_body.sh
export HF_HOME=/scratch/$USER/sot-hf VLLM_CACHE_ROOT=$S/vc XDG_CACHE_HOME=$S/cache USE_TF=0
export UV_CACHE_DIR=$S/uv UV_LINK_MODE=copy BFCL_LB=$H/gorilla/berkeley-function-call-leaderboard
t0=$(date +%s); el() { echo "[$(( $(date +%s)-t0 ))s] $*"; }
G0=${CUDA_VISIBLE_DEVICES%%,*}; G1=${CUDA_VISIBLE_DEVICES##*,}
nvidia-smi --query-gpu=index,name,memory.total --format=csv,noheader; el "agent GPU $G0, Laya GPU $G1"
$UV venv -q --python 3.10 $S/venv && . $S/venv/bin/activate
$UV pip install -q --no-index --find-links $W -r $H/shuban_findings/code/ada/final/pins.txt || { el PIP_FAIL; exit 1; }
$UV pip install -q --no-index --find-links $W --no-deps laya==0.3.27 || { el PIP_FAIL; exit 1; }
el "venv ready: vllm $(python -c 'import vllm; print(vllm.__version__)')"
python -c "from huggingface_hub import snapshot_download as s; s('Qwen/Qwen3-8B-AWQ')" >/dev/null 2>&1 || { el MODEL_DOWNLOAD_FAIL; exit 1; }
export HF_HUB_OFFLINE=1; el "model ready: $(du -sh $HF_HOME | cut -f1)"
cd $H/shuban_findings/code
python -c "import run, laya_run" || { el IMPORT_FAIL; exit 1; }
python test_gold.py base,miss_param,miss_func,long_context ${GOLD_N:-5} 2>&1 | tail -3; el "gold replay done"

ML=${MAXLEN:-20480}
# KEEPLEN=1: a failed start is retried at the same length instead of the fallback (job 64380's first start saw 1 GiB less
# KV room than its second on the same card, so the test ran at 16,384; the rerun at 20,480 showed this did not matter)
for try in 1 2 3; do
  [ $try = 3 ] && [ -z "${KEEPLEN:-}" ] && break
  CUDA_VISIBLE_DEVICES=$G0 vllm serve Qwen/Qwen3-8B-AWQ --dtype half --max-model-len $ML --gpu-memory-utilization ${UTIL:-0.88} \
    --enable-prefix-caching --enable-auto-tool-choice --tool-call-parser hermes --max-num-seqs ${SEQS:-32} --port 8000 > $S/vllm0.log 2>&1 &
  QP=$!
  for i in $(seq 600); do curl -sf localhost:8000/v1/models >/dev/null && break; kill -0 $QP 2>/dev/null || break; sleep 2; done
  curl -sf localhost:8000/v1/models >/dev/null && break
  N=$(grep -o "estimated maximum model length is [0-9]*" $S/vllm0.log | grep -o "[0-9]*$" | head -1)
  [ -z "$N" ] && { el SERVER_FAIL; tail -40 $S/vllm0.log; exit 1; }
  cp $S/vllm0.log $S/vllm0_try$try.log
  [ -n "${KEEPLEN:-}" ] && { el "context too long for this start's KV room ($N), retrying at $ML"; sleep 20; continue; }
  ML=$(( N / 1024 * 1024 )); el "context too long for this card's KV room, retrying with max-model-len $ML"
done
curl -sf localhost:8000/v1/models >/dev/null || { el SERVER_FAIL; tail -40 $S/vllm0.log; exit 1; }
el "server up, max-model-len $ML"; grep -i "KV cache\|maximum concurrency\|GPU blocks" $S/vllm0.log | tail -3

export LAYA_DIR=$HOME/sot/models/laya-typed-decisions LAYA_DEVICE=cuda:0 LAYA_GATE=0 LAYA_DTYPE=fp16 \
  LAYA_STEP_WEIGHTS=${STEP_W:-$HOME/sot/runs/step_49477/orig_seed1/weights.pt} LAYA_STEP_THR=${STEP_THR:-0.1266} \
  LAYA_DONE_WEIGHTS=$DONE_W LAYA_DONE_THR=${DONE_THR:-0.561} LAYA_DONE_MODE=${DONE_MODE:-block} STAY_ANALYSIS=$H/analysis
CUDA_VISIBLE_DEVICES=$G1 python laya_run.py --system ${SYS:-S_layastep} --split ${SPLIT:-test} --runs ${RUNS:-3} --limit ${LIMIT:-0} \
  --versions ${VERSIONS:-base,miss_param,miss_func,long_context} --concurrency ${CONC:-10} --out $OUT/${SYS:-S_layastep} --shard ${SHARD:-0/1}
el "run exit $?"
grep -iE "error|Traceback" $S/vllm0.log | tail -5
el ALL_DONE
