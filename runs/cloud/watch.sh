#!/bin/bash
# Runs ON the instance. One line a minute: GPU use and memory, vLLM running and waiting requests and KV cache use,
# finished episodes and judged steps. Used to size CONC: raise it while nothing waits and the KV cache is under ~80%,
# lower it if requests wait or get preempted.
# usage: bash watch.sh            (Ctrl-C to stop)
W=${W:-$HOME/sot}
while true; do
  g=$(nvidia-smi --query-gpu=utilization.gpu,memory.used --format=csv,noheader,nounits | tr -d ' ')
  m=$(curl -s http://127.0.0.1:8000/metrics | grep -E '^vllm:(num_requests_running|num_requests_waiting|kv_cache_usage_perc|gpu_cache_usage_perc|num_preemptions_total)' \
      | sed -E 's/^vllm:([a-z_]+)\{[^}]*\} /\1=/' | tr '\n' ' ')
  t=$(cat $W/runs/test/tasks_*.jsonl 2>/dev/null | wc -l)
  j=$(cat $W/runs/judge9b/full/predictions.jsonl 2>/dev/null | wc -l)
  echo "$(date +%H:%M) gpu%,MiB=$g tasks=$t judged=$j $m"
  sleep 60
done
