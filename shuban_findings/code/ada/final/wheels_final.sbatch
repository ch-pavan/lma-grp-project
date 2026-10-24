#!/bin/bash
#SBATCH -A research
#SBATCH -p u22
#SBATCH -c 4
#SBATCH --mem=8G
#SBATCH -t 04:00:00
#SBATCH -o logs/wheels_final.log
# Rebuild the wheelhouse with the exact versions every earlier run used (pins.txt, from wheels_list.txt), so results stay comparable.
# Resolve against pypi.org (metadata only), fetch from the tuna mirror with parallel curls.
cd ~/agents/lma-project-initial
S=/scratch/$USER/lma-wheels-$SLURM_JOB_ID; rm -rf $S wheels; mkdir -p $S wheels
export PIP_NO_CACHE_DIR=1
python3.10 -m venv $S/v && . $S/v/bin/activate && pip install -q -i https://pypi.tuna.tsinghua.edu.cn/simple --upgrade pip
t=$(date +%s)
pip install --dry-run --ignore-installed --no-deps --quiet --report $S/report.json -r pins.txt || { echo RESOLVE_FAIL; exit 1; }
python - $S/report.json > $S/urls.txt <<'P'
import json, sys
for i in json.load(open(sys.argv[1]))["install"]:
    print(i["download_info"]["url"].replace("https://files.pythonhosted.org/", "https://pypi.tuna.tsinghua.edu.cn/"))
P
echo "resolved $(wc -l < $S/urls.txt) wheels in $(( $(date +%s)-t ))s"
cd wheels && xargs -P 16 -n 1 curl -s -S -L -O --retry 5 --retry-delay 3 < $S/urls.txt
n=$(ls | wc -l); du -sh .
echo "fetched $n in $(( $(date +%s)-t ))s"
rm -rf $S
[ "$n" -eq "$(wc -l < ../pins.txt)" ] && echo WHEELS_DONE || { echo WHEELS_SHORT; exit 1; }
