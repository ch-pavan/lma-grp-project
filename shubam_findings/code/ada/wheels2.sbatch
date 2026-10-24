#!/bin/bash
#SBATCH -A research
#SBATCH -p u22
#SBATCH -c 4
#SBATCH --mem=8G
#SBATCH -t 03:00:00
#SBATCH -o wheels2.log
# CUDA 12.9 stack (the 2080 Ti nodes run driver 575 = CUDA 12.9): vllm 0.31.0+cu129 and torch 2.13.0+cu129.
cd ~/agents/lma-project-initial
S=/scratch/$USER/lma-wheels2; rm -rf $S; mkdir -p $S; rm -rf wheels; mkdir -p wheels
export PIP_NO_CACHE_DIR=1
python3.10 -m venv $S/v && . $S/v/bin/activate && pip install -q -i https://pypi.tuna.tsinghua.edu.cn/simple --upgrade pip
t=$(date +%s)
V=vllm-0.31.0+cu129-cp38-abi3-manylinux_2_28_x86_64.whl
curl -s -S -L -o wheels/$V https://github.com/vllm-project/vllm/releases/download/v0.31.0/vllm-0.31.0%2Bcu129-cp38-abi3-manylinux_2_28_x86_64.whl
echo "vllm wheel $(du -h wheels/$V | cut -f1) in $(( $(date +%s)-t ))s"
pip install --dry-run --ignore-installed --quiet --report $S/report.json --extra-index-url https://download.pytorch.org/whl/cu129 \
  wheels/$V "torch==2.13.0+cu129" hf_transfer pandas matplotlib openai || { echo RESOLVE_FAIL; exit 1; }
python - <<'P' > $S/urls.txt
import json, os; r = json.load(open(f"/scratch/{os.environ['USER']}/lma-wheels2/report.json"))
for i in r["install"]:
    u = i["download_info"]["url"]
    if u.startswith("file:"): continue
    print(u.replace("https://files.pythonhosted.org/", "https://pypi.tuna.tsinghua.edu.cn/"))
P
echo "resolved $(wc -l < $S/urls.txt) wheels in $(( $(date +%s)-t ))s"; grep -o 'torch-[^/]*whl\|nvidia_cuda_runtime[^/]*whl' $S/urls.txt
cd wheels && xargs -P 16 -n 1 curl -s -S -L -O --retry 5 --retry-delay 3 < $S/urls.txt
for f in *%2B*; do [ -e "$f" ] && mv "$f" "${f//%2B/+}"; done
ls | wc -l; du -sh .
echo "fetched in $(( $(date +%s)-t ))s"
rm -rf $S
echo DONE
