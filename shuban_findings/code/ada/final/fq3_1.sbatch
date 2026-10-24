#!/bin/bash
#SBATCH --dependency=afterok:37263
#SBATCH -A research
#SBATCH -p u22
#SBATCH --constraint=2080ti
#SBATCH --gres=gpu:1
#SBATCH -c 9
#SBATCH --mem=40G
#SBATCH -t 20:00:00
#SBATCH -o logs/fq3_1.log
# Qwen3 8B AWQ agent, shard 1 of 2: AgentDojo benign then BFCL test, 1 run per task
export MODEL=Qwen/Qwen3-8B-AWQ SUF="" MAXLEN=20480 SARGS="--tool-call-parser hermes --max-num-seqs 32"
export AD=S1_none,S3_llm_judge@dc BF=S1_none,S3_llm_judge@dc,S_oracle@rbh2dc CONC=10 RUNS=1 SHARD=1/2
source ~/agents/lma-project-initial/final_body.sh
