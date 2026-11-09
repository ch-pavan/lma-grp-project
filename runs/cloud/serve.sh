#!/bin/bash
# Runs ON the instance. Starts one vLLM server for both the 9B agent and the 9B judge, with the val runs' settings
# (vLLM 0.27.1, 32k context, prefix caching, qwen3_coder tool parser; the judge sends no tools, so the parser does not
# touch it). Only the batch size changes: an 80 GB card holds far more requests than Turing's 48 GB.
# GMU and MAXSEQ can be changed between restarts; results do not depend on them.
# usage: bash serve.sh     (returns once the server answers; log in $W/vllm.log)
set -uo pipefail
W=${W:-$HOME/sot}; . $W/venv/bin/activate
GMU=${GMU:-0.92}; MAXSEQ=${MAXSEQ:-256}
pkill -f "vllm serve" 2>/dev/null; sleep 3
nohup vllm serve $W/models/Qwen3.5-9B-AWQ-4bit --served-model-name cyankiwi/Qwen3.5-9B-AWQ-4bit --host 127.0.0.1 --port 8000 \
  --language-model-only --max-model-len 32768 --gpu-memory-utilization $GMU --enable-prefix-caching \
  --enable-prompt-tokens-details --enable-auto-tool-choice --tool-call-parser qwen3_coder --max-num-seqs $MAXSEQ \
  > $W/vllm.log 2>&1 &
for i in $(seq 1 120); do
  curl -sf http://127.0.0.1:8000/v1/models >/dev/null && { echo "server up (GMU $GMU, max-num-seqs $MAXSEQ)"; grep -iE "KV cache|maximum concurrency" $W/vllm.log | tail -2; exit 0; }
  pgrep -f "vllm serve" >/dev/null || { echo SERVER_DIED; tail -40 $W/vllm.log; exit 1; }
  sleep 5
done
echo "server not up after 10 min"; tail -20 $W/vllm.log; exit 1
