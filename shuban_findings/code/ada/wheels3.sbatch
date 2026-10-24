#!/bin/bash
#SBATCH -A research
#SBATCH -p u22
#SBATCH -c 4
#SBATCH --mem=8G
#SBATCH -t 03:00:00
#SBATCH -o wheels3.log
# One wheelhouse in home so every GPU job installs from local disk instead of a 1 MB/s mirror.
# Resolve with pip (metadata only), then fetch all wheels with 12 parallel curls.
cd ~/agents/lma-project-initial
SPEC=${SPEC:-vllm}
S=/scratch/$USER/lma-wheels; rm -rf $S wheels; mkdir -p $S wheels
export PIP_NO_CACHE_DIR=1
# resolve against pypi.org (PEP 658 metadata files are tiny, so its slowness does not matter), download from the tuna mirror
python3.10 -m venv $S/v && . $S/v/bin/activate && pip install -q -i https://pypi.tuna.tsinghua.edu.cn/simple --upgrade pip
t=$(date +%s)
for TP in "torch==2.10.*" "torch==2.9.*"; do
  pip install --dry-run --ignore-installed --quiet --report $S/report.json vllm "$TP" hf_transfer pandas matplotlib openai && break
done
[ -s $S/report.json ] || { echo RESOLVE_FAIL; exit 1; }
grep -o '"name": "nvidia-cuda-runtime[^"]*", "version": "[^"]*"' $S/report.json
python - <<'P' > $S/urls.txt
import json; r = json.load(open("/scratch/" + __import__("os").environ["USER"] + "/lma-wheels/report.json"))
for i in r["install"]:
    print(i["download_info"]["url"].replace("https://files.pythonhosted.org/", "https://pypi.tuna.tsinghua.edu.cn/"))
P
echo "resolved $(wc -l < $S/urls.txt) wheels in $(( $(date +%s)-t ))s"; grep -o 'vllm-[^/]*whl\|torch-[^/]*whl' $S/urls.txt
cd wheels && xargs -P 16 -n 1 curl -s -S -L -O --retry 5 --retry-delay 3 < $S/urls.txt
ls | wc -l; du -sh .
echo "fetched in $(( $(date +%s)-t ))s"
rm -rf $S
cd ~/agents/lma-project-initial
for f in bench2 pilot_S1_none pilot_S2_rules pilot_S3_llm_judge pilot_S4a_laya pilot_S4b_granite; do sbatch $f.sbatch | tee -a chained_jobs.txt; done
echo DONE
