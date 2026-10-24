#!/bin/bash
#SBATCH -J prep-laya
#SBATCH -A karthik.vaidhyanathan
#SBATCH -p u22
#SBATCH -w node01
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=01:00:00
#SBATCH -o /home/pavan.harshit/stay-on-task/logs/prep-laya-%j.out
# No GPU: download Laya typed decisions at a pinned commit and install the laya package (no deps; the vLLM image has them).
S=/scratch/pavan.harshit; SIF=$S/vllm-openai-v0.27.1-cu129.sif
module load u22/singularity-ce/4.2.2
singularity exec --bind $S:$S --env HF_HUB_DISABLE_XET=1 --env HF_HOME=$S/hf-cache $SIF python3 -c "
from huggingface_hub import snapshot_download
p = snapshot_download('convaiinnovations/laya-typed-decisions', revision='e929ae5cf69bc34259cd2f95c9e91145b818b1f0', local_dir='$S/models/laya-typed-decisions')
print('LAYA_OK', p)"
singularity exec --bind $S:$S $SIF python3 -m pip install -q --no-deps --target $S/pylaya laya==0.3.27 && echo PIP_OK
du -sh $S/models/laya-typed-decisions; ls $S/models/laya-typed-decisions $S/models/laya-typed-decisions/encoder
