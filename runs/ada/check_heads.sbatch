#!/bin/bash
#SBATCH -J sot-check-heads
#SBATCH -A research
#SBATCH -p u22
#SBATCH --constraint=2080ti
#SBATCH --exclude=gnode077,gnode066   # their GPUs fail CUDA init (31 Oct)
#SBATCH --gres=gpu:1
#SBATCH -c 8
#SBATCH --mem=32G
#SBATCH -t 01:00:00
#SBATCH -o /home2/swayam.goyal/sot/logs/check-heads-%j.out
# Runs check_heads.py in the test run's environment (same venv build as laya_test.sbatch).
# usage: sbatch --export=ALL,DONE_W=<done head weights.pt>[,STATES=<states jsonl>] check_heads.sbatch
set -u
H=$HOME/sot/testrun; W=$HOME/sot/wheels; UV=~/.local/bin/uv
S=/scratch/$USER/sot-$SLURM_JOB_ID; mkdir -p $S; trap 'rm -rf $S' EXIT
export BFCL_LB=$H/gorilla/berkeley-function-call-leaderboard UV_CACHE_DIR=$S/uv UV_LINK_MODE=copy HF_HUB_OFFLINE=1 STAY_ANALYSIS=$H/analysis LAYA_DIR=$HOME/sot/models/laya-typed-decisions
$UV venv -q --python 3.10 $S/venv && . $S/venv/bin/activate
$UV pip install -q --no-index --find-links $W -r $H/shuban_findings/code/ada/final/pins.txt && $UV pip install -q --no-index --find-links $W --no-deps laya==0.3.27 || exit 1
python -c "import torch, transformers, laya; print('torch', torch.__version__, 'transformers', transformers.__version__, 'laya', laya.__version__)"
python $H/runs/ada/check_heads.py ${STEP_W:-$HOME/sot/runs/step_49477/orig_seed1/weights.pt} $DONE_W $HOME/sot/data/laya_step/val.jsonl \
  $HOME/sot/data/laya_done/val.jsonl ${STATES:-}
echo CHECK_DONE
