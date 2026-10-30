#!/bin/bash
# One-time setup on Ada (shared home): uv-made Python 3.12 venv in ~/sot/venv, and Laya at the pinned commit.
set -e
export UV_HTTP_TIMEOUT=300 UV_HTTP_RETRIES=10
UV=~/.local/bin/uv
$UV venv --python 3.12 ~/sot/venv
$UV pip install --python ~/sot/venv/bin/python torch==2.7.1 --index-url https://download.pytorch.org/whl/cu126
$UV pip install --python ~/sot/venv/bin/python laya==0.3.27 huggingface_hub numpy
~/sot/venv/bin/python -c "import torch, laya; print(\"TORCH\", torch.__version__, \"LAYA\", laya.__version__)"
~/sot/venv/bin/python - <<"EOP"
from huggingface_hub import snapshot_download
import os
p = snapshot_download("convaiinnovations/laya-typed-decisions", revision="e929ae5cf69bc34259cd2f95c9e91145b818b1f0",
                      local_dir=os.path.expanduser("~/sot/models/laya-typed-decisions"))
print("LAYA_MODEL_OK", p)
EOP
du -sh ~/sot/venv ~/sot/models
echo SETUP_DONE
