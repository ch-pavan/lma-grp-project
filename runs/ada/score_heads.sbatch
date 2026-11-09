#!/bin/bash
#SBATCH -J sot-heads
#SBATCH -A research
#SBATCH -p u22
#SBATCH -c 12
#SBATCH --mem=24G
#SBATCH -t 2-00:00:00
#SBATCH -o /home2/swayam.goyal/sot/logs/heads-%j.out
# Item 4.5: the frozen Laya heads (runs/ada/test_freeze.md) on every recorded step of the 9B S1_record test passes
# (analysis/score_test_heads.py). CPU only: the four GPUs of the QOS run the live 9B systems, and 12 CPUs still fit
# under the 40 CPU cap next to two 2 GPU jobs. The heads run in fp32 on the CPU.
# usage: sbatch --export=ALL[,RUN=dir][,OUTF=file] score_heads.sbatch
set -u
H=$HOME/sot/testrun; W=$HOME/sot/wheels; UV=~/.local/bin/uv
S=/scratch/$USER/sot-$SLURM_JOB_ID; mkdir -p $S; trap 'rm -rf $S' EXIT
export HF_HOME=/scratch/$USER/sot-hf XDG_CACHE_HOME=$S/cache USE_TF=0 UV_CACHE_DIR=$S/uv UV_LINK_MODE=copy OMP_NUM_THREADS=12
export BFCL_LB=$H/gorilla/berkeley-function-call-leaderboard  # step_labels imports run.py, which needs bfcl_eval (job 65523)
t0=$(date +%s); el() { echo "[$(( $(date +%s)-t0 ))s] $*"; }
$UV venv -q --python 3.10 $S/venv && . $S/venv/bin/activate
$UV pip install -q --no-index --find-links $W -r $H/shuban_findings/code/ada/final/pins.txt || { el PIP_FAIL; exit 1; }
$UV pip install -q --no-index --find-links $W --no-deps laya==0.3.27 || { el PIP_FAIL; exit 1; }
el "venv ready"
RUN=${RUN:-$HOME/sot/q9b_runs/test/S1_record}; OUTF=${OUTF:-$HOME/sot/q9b_runs/test/heads_S1_record.jsonl}
export LAYA_DIR=$HOME/sot/models/laya-typed-decisions LAYA_DEVICE=cpu LAYA_DTYPE=fp32 \
  LAYA_STEP_WEIGHTS=$HOME/sot/runs/step_49477/orig_seed1/weights.pt LAYA_DONE_WEIGHTS=$HOME/sot/runs/done_full_64348/weights.pt
python $H/analysis/score_test_heads.py $RUN $OUTF || { el SCORE_FAIL; exit 1; }
el "DONE: $(wc -l < $OUTF) rows in $OUTF"
