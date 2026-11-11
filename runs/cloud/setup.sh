#!/bin/bash
# Runs ON the rented GPU instance, once. Python env with vLLM 0.27.1 (the version of Turing's image, so serving matches
# the val runs), the same 4 bit Qwen3.5 9B checkpoint, and our code from bundle.tgz (made by make_bundle.sh on the Mac).
# usage: bash setup.sh            (bundle.tgz uploaded to $W first; W defaults to ~/sot)
set -euo pipefail
W=${W:-$HOME/sot}; mkdir -p $W/models $W/runs; cd $W
t0=$(date +%s); el() { echo "[$(( $(date +%s)-t0 ))s] $*"; }
nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader | tee $W/gpu.txt
df -h $W | tail -1
[ -f $W/bundle.tgz ] || { echo "upload bundle.tgz to $W first"; exit 1; }
tar --warning=no-unknown-keyword -xzf $W/bundle.tgz -C $W
el "code unpacked"
python3 -m pip install -q --root-user-action=ignore uv
UV=$(python3 -c 'import uv; print(uv.find_uv_bin())')   # the uv binary, usable from any env
rm -rf $W/venv
$UV venv -q --python 3.12 $W/venv
$UV pip install -q --python $W/venv/bin/python vllm==0.27.1 mpmath==1.3.0
. $W/venv/bin/activate
el "vllm $(python -c 'import vllm; print(vllm.__version__)'), torch $(python -c 'import torch; print(torch.__version__, torch.version.cuda)')"
python - <<EOF
from huggingface_hub import snapshot_download
m = "cyankiwi/Qwen3.5-9B-AWQ-4bit"
rev = "e4d2d39cede8c5d1716d824cd843e2889c648083"  # last change 19 Oct 2026, before the Turing val runs of 24 Oct
p = snapshot_download(m, revision=rev, local_dir="$W/models/Qwen3.5-9B-AWQ-4bit")
print("model at", p, "revision", rev)
EOF
du -sh $W/models/Qwen3.5-9B-AWQ-4bit
el "setup done"
