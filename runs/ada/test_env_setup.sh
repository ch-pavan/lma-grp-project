#!/bin/bash
# One-time setup for the Laya test run in Shuban's original BFCL test setup (laya_test.sbatch). Run it on the Ada login
# node, which has internet: BFCL at gorilla commit 6ea5797, a wheelhouse of Shuban's pins (vLLM 0.19.1, torch 2.10.0)
# plus laya 0.3.27. Compute nodes do not mount /share1, so the wheelhouse is then copied to ~/sot/wheels; the venv is
# built per job on the node's /scratch from it, and laya_test.sbatch downloads the agent model per node.
# usage: nohup bash ~/sot/testrun/runs/ada/test_env_setup.sh > ~/sot/logs/test_env_setup.log 2>&1 &
set -eu
SH=/share1/$USER/sot; H=$HOME/sot/testrun; UV=~/.local/bin/uv
T=https://pypi.tuna.tsinghua.edu.cn/simple
export UV_HTTP_TIMEOUT=300 UV_HTTP_RETRIES=10
mkdir -p $SH/wheels
t0=$(date +%s); el() { echo "[$(( $(date +%s)-t0 ))s] $*"; }

if [ ! -d $H/gorilla/.git ]; then
  git clone -q --filter=blob:none --no-checkout https://github.com/ShishirPatil/gorilla $H/gorilla
  git -C $H/gorilla sparse-checkout set berkeley-function-call-leaderboard
fi
git -C $H/gorilla checkout -q 6ea5797
el "gorilla $(git -C $H/gorilla rev-parse --short HEAD)"

$UV python install 3.10
D=/tmp/$USER-dl; rm -rf $D; $UV venv -q --seed --python 3.10 $D
$D/bin/python -m pip download -q --no-deps -d $SH/wheels -i $T -r $H/shuban_findings/code/ada/final/pins.txt laya==0.3.27
rm -rf $D
el "wheels $(ls $SH/wheels | wc -l), $(du -sh $SH/wheels | cut -f1)"
mkdir -p $HOME/sot/wheels && rsync -a $SH/wheels/ $HOME/sot/wheels/
el SETUP_DONE
