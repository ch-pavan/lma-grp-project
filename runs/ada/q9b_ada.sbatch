#!/bin/bash
#SBATCH -J sot-q9b
#SBATCH -A research
#SBATCH -p u22
#SBATCH --constraint=2080ti
#SBATCH --exclude=gnode077,gnode066   # their GPUs fail CUDA init (31 Oct)
#SBATCH --gres=gpu:1
#SBATCH -c 9
#SBATCH --mem=40G
#SBATCH -t 24:00:00
#SBATCH -o /home2/swayam.goyal/sot/logs/q9b-%j.out
# Phase 4 on Ada (Turing is no longer available): the Qwen3.5 9B agent in actions.py, as runs/turing/q9b_test_passes.sbatch
# (item 4.1, S1_record) and runs/turing/q9b_rb.sbatch (live rollback plus done check, rbh2dc). Same server settings as
# Turing where the card allows: 32,768 token context, prefix caching, qwen3_coder tool parser, reasoning off for the
# agent, language model only. The 2080 Ti runs the vLLM 0.19.1 wheelhouse of test_env_setup.sh (Turing: 0.27.1).
# Systems in SYSTEMS run one after the other on the same server. With LAYA=1 (and --gres=gpu:2) the Laya heads sit on
# the second card in fp16; they are the heads frozen for the 8B test (runs/ada/test_freeze.md).
# usage: sbatch [--gres=gpu:2] --export=ALL,SYSTEMS=S1_record[+S_oracle@rbh2dc...][,LAYA=1][,TP=2][,SPLIT=test][,RUNS=3][,LIMIT=0][,SHARD=0/1][,OUT=dir] q9b_ada.sbatch
#   SMOKE=1: canary of 3 base tasks for each system in SYSTEMS, then stop.
#   The QOS allows up to 4 days (sbatch -t 4-00:00:00); a rerun with the same OUT and SHARD resumes the episodes left.
set -u
H=$HOME/sot/testrun; W=$HOME/sot/wheels; UV=~/.local/bin/uv
S=/scratch/$USER/sot-$SLURM_JOB_ID; mkdir -p $S
OUT=${OUT:-$HOME/sot/q9b_runs/q9b_$SLURM_JOB_ID}; mkdir -p $OUT
trap 'cp $S/vllm*.log $OUT/ 2>/dev/null; kill $(jobs -p) 2>/dev/null; rm -rf $S' EXIT
export VLLM_ATTENTION_BACKEND=TRITON_ATTN VLLM_USE_FLASHINFER_SAMPLER=0 FLASHINFER_WORKSPACE_BASE=$S
export HF_HOME=/scratch/$USER/sot-hf VLLM_CACHE_ROOT=$S/vc XDG_CACHE_HOME=$S/cache USE_TF=0 AGENT_THINK=0
export UV_CACHE_DIR=$S/uv UV_LINK_MODE=copy BFCL_LB=$H/gorilla/berkeley-function-call-leaderboard
t0=$(date +%s); el() { echo "[$(( $(date +%s)-t0 ))s] $*"; }
G0=${CUDA_VISIBLE_DEVICES%%,*}; G1=${CUDA_VISIBLE_DEVICES##*,}
nvidia-smi --query-gpu=index,name,memory.total --format=csv,noheader; el "agent GPU $G0, Laya GPU $G1"
$UV venv -q --python 3.10 $S/venv && . $S/venv/bin/activate
$UV pip install -q --no-index --find-links $W -r $H/shuban_findings/code/ada/final/pins.txt || { el PIP_FAIL; exit 1; }
$UV pip install -q --no-index --find-links $W --no-deps laya==0.3.27 || { el PIP_FAIL; exit 1; }
el "venv ready: vllm $(python -c 'import vllm; print(vllm.__version__)')"
NAME=cyankiwi/Qwen3.5-9B-AWQ-4bit
python -c "from huggingface_hub import snapshot_download as s; s('$NAME')" >/dev/null 2>&1 || { el MODEL_DOWNLOAD_FAIL; exit 1; }
export HF_HUB_OFFLINE=1; el "model ready: $(du -sh $HF_HOME | cut -f1)"
cd $H/shuban_findings/code
python -c "import actions" || { el IMPORT_FAIL; exit 1; }

ML=${MAXLEN:-32768}
# vLLM 0.19.1 ignores VLLM_ATTENTION_BACKEND and picks FlashInfer, whose workspace does not fit next to the 9B (job 64666)
HELP=$(vllm serve --help=all 2>/dev/null)
MM="--language-model-only"; grep -q -- "--language-model-only" <<< "$HELP" || MM="--limit-mm-per-prompt {\"image\":0,\"video\":0}"
AB=""; grep -q -- "--attention-backend" <<< "$HELP" && AB="--attention-backend TRITON_ATTN"
# TP=2: the 9B is split over both cards of the job (11 GB each); the Laya heads then share the second card
SG=$G0; TPA=""; [ "${TP:-1}" = 2 ] && { SG=$CUDA_VISIBLE_DEVICES; TPA="--tensor-parallel-size 2"; }
el "serve flags: $MM $AB $TPA ${EAGER:+--enforce-eager}"
for try in 1 2 3; do
  CUDA_VISIBLE_DEVICES=$SG vllm serve $NAME --dtype half --max-model-len $ML --gpu-memory-utilization ${UTIL:-0.90} $MM $AB $TPA \
    --enable-prefix-caching --enable-prompt-tokens-details --enable-auto-tool-choice --tool-call-parser qwen3_coder \
    --max-num-seqs ${SEQS:-16} ${EAGER:+--enforce-eager} --port 8000 > $S/vllm.log 2>&1 &
  QP=$!
  for i in $(seq 900); do curl -sf localhost:8000/v1/models >/dev/null && break; kill -0 $QP 2>/dev/null || break; sleep 2; done
  curl -sf localhost:8000/v1/models >/dev/null && break
  cp $S/vllm.log $S/vllm_try$try.log
  N=$(grep -o "estimated maximum model length is [0-9]*" $S/vllm.log | grep -o "[0-9]*$" | head -1)
  [ -z "$N" ] && { el SERVER_FAIL; grep -iE "error|memory|took" $S/vllm.log | tail -15; exit 1; }
  # first a retry at the same length (a start can see less KV room than the next one on the same card), then the fallback
  [ $try = 2 ] && ML=$(( N / 1024 * 1024 )); el "start $try: room for $N tokens, next try at $ML"; sleep 20
done
curl -sf localhost:8000/v1/models >/dev/null || { el SERVER_FAIL; exit 1; }
el "server up, max-model-len $ML"; grep -iE "KV cache size|maximum concurrency|weights took|model loading took" $S/vllm.log | tail -4

export LAYA_DIR=$HOME/sot/models/laya-typed-decisions LAYA_DEVICE=cuda:0 LAYA_DTYPE=fp16 \
  LAYA_STEP_WEIGHTS=${STEP_W:-$HOME/sot/runs/step_49477/orig_seed1/weights.pt} LAYA_STEP_THR=${STEP_THR:-0.1266} \
  LAYA_DONE_WEIGHTS=${DONE_W:-$HOME/sot/runs/done_full_64348/weights.pt} LAYA_DONE_THR=${DONE_THR:-0.561} STAY_ANALYSIS=$H/analysis
GL=$G0; [ "${LAYA:-0}" = 1 ] && GL=$G1
run() {  # system runs limit versions outdir
  mkdir -p $5; CUDA_VISIBLE_DEVICES=$GL python actions.py --bench bfcl --system $1 --split ${SPLIT:-test} --runs $2 --limit $3 --versions $4 \
    --concurrency ${CONC:-16} --base-url http://localhost:8000/v1 --model $NAME --out $5/$1 --shard ${SHARD:-0/1} > $5/$1.log 2>&1
  el "$1 exit $?: $(tail -1 $5/$1.log)"
}
for SY in ${SYSTEMS//+/ }; do  # SYSTEMS joined with + (sbatch --export splits on commas)
  if [ "${SMOKE:-0}" = 1 ]; then
    ts=$(date +%s); run $SY 1 3 base $OUT/smoke
    el "SMOKE $SY: $(cat $OUT/smoke/$SY/tasks_*.jsonl 2>/dev/null | wc -l) of 3 tasks in $(( $(date +%s)-ts ))s, $(grep -c Traceback $OUT/smoke/$SY.log) tracebacks"
    python -c "
import glob, json
for f in glob.glob('$OUT/smoke/$SY/tasks_*.jsonl'):
    for l in open(f): r = json.loads(l); print('  ', r['id'], 'pass', r['passed'], 'steps', r['steps'], 'int', r['interventions'], 'err', r['harness_error'], 'judge tok', r['judge_in'] + r['judge_out'])"
  else  # canary first: 3 base tasks must finish without a harness error (NOCANARY=1 skips it for a resumed run)
    if [ "${NOCANARY:-0}" != 1 ]; then
      CN=$OUT/canary_$SLURM_JOB_ID; SHARD=0/1 run $SY 1 3 base $CN
      bad=$(cat $CN/$SY/tasks_*.jsonl 2>/dev/null | python -c "import json,sys; r=[json.loads(l) for l in sys.stdin]; print(3-sum(not x['harness_error'] for x in r))")
      [ "$bad" = 0 ] || { el "CANARY_FAIL $SY ($bad of 3)"; grep -m3 -h harness_error $CN/$SY/tasks_*.jsonl | cut -c1-400; continue; }
    fi
    # a job killed at its time limit can leave a half-written last line; actions.py resumes from the task rows, so drop it
    # (only this shard's files: the other shard may be appending to its own at the same time)
    SH=${SHARD:-0/1}; for f in $OUT/$SY/tasks_${SY}_${SH/\//of}.jsonl $OUT/$SY/steps_${SY}_${SH/\//of}.jsonl; do [ -f "$f" ] && python -c "
import json, sys
ls = open(sys.argv[1]).readlines(); ok = []
for l in ls:
    try: json.loads(l); ok.append(l)
    except ValueError: pass
if len(ok) < len(ls): open(sys.argv[1], 'w').writelines(ok); print('dropped', len(ls) - len(ok), 'broken lines in', sys.argv[1])" "$f"; done
    run $SY ${RUNS:-3} ${LIMIT:-0} ${VERSIONS:-base,miss_param,miss_func,long_context} $OUT
  fi
done
grep -iE "Traceback|error" $S/vllm.log | grep -v "maximum context length" | tail -5
el ALL_DONE
